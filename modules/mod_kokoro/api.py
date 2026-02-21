from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import io
import os
import logging
from pathlib import Path
import threading
import time
import importlib.util
import json
import uuid
from datetime import datetime

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mod_kokoro")

# Config
MODULE_DIR = Path(__file__).parent
MODELS_DIR = MODULE_DIR / "models"
OUTPUT_DIR = MODULE_DIR / "output"
HISTORY_FILE = MODULE_DIR / "history.json"

os.environ["HF_HOME"] = str(MODELS_DIR) # Cache models here

# Ensure directories exist
for d in [MODELS_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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

class DeleteHistoryRequest(BaseModel):
    filenames: List[str]

def check_dependencies():
    missing = []
    if not importlib.util.find_spec("kokoro"): missing.append("kokoro")
    if not importlib.util.find_spec("soundfile"): missing.append("soundfile")
    if not importlib.util.find_spec("torch"): missing.append("torch")
    if not importlib.util.find_spec("numpy"): missing.append("numpy")
    return missing

def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

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

        # Local Imports
        import torch
        from kokoro import KPipeline

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

            pipeline = KPipeline(lang_code='a') # 'a' for American English

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

@router.post("/generate/stream")
def generate_stream(req: GenerateRequest):
    if not model_status["loaded"]:
        if not model_status["loading"]:
             threading.Thread(target=load_model).start()
             raise HTTPException(status_code=503, detail="Model is loading, please wait.")
        else:
             raise HTTPException(status_code=503, detail="Model is still loading.")

    if not pipeline:
         raise HTTPException(status_code=500, detail="Pipeline is None despite loaded status.")

    def audio_generator():
        with pipeline_lock:
            try:
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

                    # Convert Tensor to Numpy if needed
                    if hasattr(audio, 'cpu'):
                        audio = audio.cpu().numpy()

                    yield audio.tobytes()

            except Exception as e:
                logger.error(f"Generation error: {e}")
                pass

    return StreamingResponse(
        audio_generator(),
        media_type="application/octet-stream"
    )

def _generate_and_save_task(req: GenerateRequest, job_id: str):
    logger.info(f"Starting generation task {job_id}")
    try:
        # Local Imports
        import numpy as np
        import soundfile as sf

        # Wait for model if needed (simple check)
        if not pipeline:
            logger.error("Pipeline not ready")
            return

        all_audio = []

        with pipeline_lock:
            stream = pipeline(
                req.text,
                voice=req.voice,
                speed=req.speed,
                split_pattern=r'\n+'
            )

            for i, (gs, ps, audio) in enumerate(stream):
                if shutdown_event.is_set(): break
                if audio is None: continue

                if hasattr(audio, 'cpu'):
                    audio = audio.cpu().numpy()

                all_audio.append(audio)

        if not all_audio:
            logger.warning("No audio generated")
            return

        final_wav = np.concatenate(all_audio)

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_text = "".join([c for c in req.text if c.isalnum() or c in (' ', '_')]).strip()[:25]
        filename = f"{timestamp}_{safe_text}.wav"
        output_path = OUTPUT_DIR / filename

        sf.write(str(output_path), final_wav, 24000)
        logger.info(f"Saved to {filename}")

        # Update History
        history = load_history()
        history.insert(0, {
            "filename": filename,
            "text": req.text,
            "voice": req.voice,
            "date": timestamp,
            "path": str(output_path),
            "job_id": job_id
        })
        save_history(history)

    except Exception as e:
        logger.error(f"Task failed: {e}")

@router.post("/generate")
def generate_file(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not model_status["loaded"]:
         if not model_status["loading"]:
             threading.Thread(target=load_model).start()
             return JSONResponse(status_code=503, content={"detail": "Model is loading, please wait."})
         else:
             return JSONResponse(status_code=503, content={"detail": "Model is still loading."})

    job_id = str(uuid.uuid4())
    background_tasks.add_task(_generate_and_save_task, req, job_id)
    return {"job_id": job_id, "status": "started"}

@router.get("/history")
def get_history():
    return load_history()

@router.get("/output/{filename}")
def get_output_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="File not found")

@router.post("/history/delete")
def delete_history_items(req: DeleteHistoryRequest):
    history = load_history()
    new_history = []
    deleted_count = 0
    to_delete = set(req.filenames)

    for item in history:
        if item["filename"] in to_delete:
            p = OUTPUT_DIR / item["filename"]
            if p.exists():
                try:
                    p.unlink()
                except:
                    pass
            deleted_count += 1
        else:
            new_history.append(item)

    save_history(new_history)
    return {"deleted": deleted_count}
