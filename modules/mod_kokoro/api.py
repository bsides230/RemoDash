from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import torch
import numpy as np
import soundfile as sf
import io
import os
import logging
from pathlib import Path
import threading
import time
import importlib.util

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mod_kokoro")

# Config
MODULE_DIR = Path(__file__).parent
MODELS_DIR = MODULE_DIR / "models"
os.environ["HF_HOME"] = str(MODELS_DIR) # Cache models here

router = APIRouter()

# Global State
pipeline = None
pipeline_lock = threading.Lock()
shutdown_event = threading.Event()
model_status = {
    "loaded": False,
    "loading": False,
    "error": None,
    "dependency_missing": False,
    "missing_deps": []
}

# Voices (Hardcoded common ones for Kokoro v0.19)
VOICES = [
    {"id": "af_heart", "name": "Heart (Default)", "gender": "Female"},
    {"id": "af_bella", "name": "Bella", "gender": "Female"},
    {"id": "af_nicole", "name": "Nicole", "gender": "Female"},
    {"id": "af_sarah", "name": "Sarah", "gender": "Female"},
    {"id": "af_sky", "name": "Sky", "gender": "Female"},
    {"id": "am_adam", "name": "Adam", "gender": "Male"},
    {"id": "am_michael", "name": "Michael", "gender": "Male"},
    {"id": "bf_emma", "name": "Emma (British)", "gender": "Female"},
    {"id": "bf_isabella", "name": "Isabella (British)", "gender": "Female"},
    {"id": "bm_george", "name": "George (British)", "gender": "Male"},
    {"id": "bm_lewis", "name": "Lewis (British)", "gender": "Male"}
]

class GenerateRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0

def check_dependencies():
    missing = []
    if not importlib.util.find_spec("kokoro"): missing.append("kokoro")
    if not importlib.util.find_spec("soundfile"): missing.append("soundfile")
    if not importlib.util.find_spec("torch"): missing.append("torch")
    # misaki might be optional but good to check if we rely on it
    return missing

def load_model():
    global pipeline, model_status
    if model_status["loaded"] or model_status["loading"]: return

    if shutdown_event.is_set():
        return

    missing = check_dependencies()
    if missing:
        model_status["dependency_missing"] = True
        model_status["missing_deps"] = missing
        model_status["error"] = "Missing dependencies"
        return

    try:
        model_status["loading"] = True
        logger.info("Loading Kokoro Pipeline...")

        # Import inside function to avoid startup errors if dependencies missing
        from kokoro import KPipeline

        # Determine device
        device = 'cpu'
        if torch.cuda.is_available():
            device = 'cuda'
            logger.info("CUDA detected, using GPU.")
        elif torch.backends.mps.is_available():
            device = 'mps'
            logger.info("MPS detected, using Apple Silicon GPU.")

        with pipeline_lock:
            if shutdown_event.is_set():
                 model_status["loading"] = False
                 return

            # Initialize pipeline (downloads model if needed)
            # lang_code='a' for American English (en-us)
            # KPipeline handles device placement usually, or we might need to move it?
            # KPipeline source suggests it uses 'cuda' if available or we can pass device?
            # Actually KPipeline usually puts on CPU by default unless specified or detected.
            # We'll just init and see.
            pipeline = KPipeline(lang_code='a')

        model_status["loaded"] = True
        model_status["error"] = None
        model_status["dependency_missing"] = False
        logger.info(f"Kokoro loaded successfully.")

    except Exception as e:
        logger.error(f"Failed to load Kokoro: {e}")
        model_status["error"] = str(e)
        model_status["loaded"] = False
    finally:
        model_status["loading"] = False

@router.on_event("shutdown")
def shutdown_handler():
    logger.info("Shutdown event received in mod_kokoro.")
    shutdown_event.set()

@router.get("/status")
def get_status():
    # Perform a quick check if not loaded
    if not model_status["loaded"] and not model_status["loading"]:
        missing = check_dependencies()
        if missing:
            model_status["dependency_missing"] = True
            model_status["missing_deps"] = missing
        else:
            model_status["dependency_missing"] = False
    return model_status

@router.get("/voices")
def get_voices():
    return VOICES

@router.post("/start")
def start_engine():
    if not model_status["loaded"]:
        threading.Thread(target=load_model).start()
        return {"status": "loading"}
    return {"status": "ready"}

@router.post("/generate")
def generate_stream(req: GenerateRequest):
    if not model_status["loaded"]:
        # Try auto-load if not running?
        if not model_status["loading"]:
             threading.Thread(target=load_model).start()
             raise HTTPException(status_code=503, detail="Model is loading, please wait.")
        else:
             raise HTTPException(status_code=503, detail="Model is still loading.")

    if not pipeline:
         raise HTTPException(status_code=500, detail="Pipeline is None despite loaded status.")

    def audio_generator():
        # Lock to ensure single-threaded access to model
        with pipeline_lock:
            try:
                # Generate returns generator of (graphemes, phonemes, audio)
                # audio is 24khz float32 numpy
                stream = pipeline(
                    req.text,
                    voice=req.voice,
                    speed=req.speed,
                    split_pattern=r'\n+'
                )

                for i, (gs, ps, audio) in enumerate(stream):
                    if shutdown_event.is_set():
                        break
                    if audio is None: continue
                    # audio is numpy array float32
                    # Yield raw float32 bytes
                    yield audio.tobytes()

            except Exception as e:
                logger.error(f"Generation error: {e}")
                # We can't easily return JSON error in stream.
                pass

    # Return raw PCM stream. Client must know it's 24kHz Mono Float32.
    return StreamingResponse(
        audio_generator(),
        media_type="application/octet-stream"
    )
