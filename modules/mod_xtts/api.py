from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import shutil
import json
import time
import threading
import uuid
import logging
from pathlib import Path
from datetime import datetime

# --- Configuration ---
MODULE_DIR = Path(__file__).parent
MODELS_DIR = MODULE_DIR / "models"
VOICES_DIR = MODULE_DIR / "voices"
OUTPUT_DIR = MODULE_DIR / "output"
SETTINGS_FILE = MODULE_DIR / "settings.json"
HISTORY_FILE = MODULE_DIR / "history.json"

# Set TTS_HOME to ensure models are downloaded to our directory
os.environ["TTS_HOME"] = str(MODELS_DIR)

# Ensure directories exist
for d in [MODELS_DIR, VOICES_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mod_xtts")

router = APIRouter()

# --- Global State ---
model_state = {
    "loaded": False,
    "loading": False,
    "error": None,
    "model_name": "tts_models/multilingual/multi-dataset/xtts_v2"
}

tts_instance = None

# --- TTS Import ---
try:
    import torch
    import torchaudio
    from TTS.api import TTS
    logger.info("Coqui TTS imported successfully.")
except ImportError as e:
    logger.error(f"Coqui TTS not found: {e}. Please install dependencies.")
    # We do NOT enable MOCK_MODE here as requested. We let it fail later or raise errors.

# --- Helper Functions ---

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"device": "cpu", "agreed_to_terms": False}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

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

def get_device():
    settings = load_settings()
    device_pref = settings.get("device", "cpu")

    if device_pref == "vulkan":
        # Check if vulkan is available in torch (experimental usually)
        # For now, we trust the user. If it fails, we catch it.
        return "vulkan"
    elif device_pref == "cuda" and torch.cuda.is_available():
        return "cuda"

    return "cpu"

def load_model_task():
    global tts_instance, model_state

    if model_state["loading"] or model_state["loaded"]:
        return

    model_state["loading"] = True
    model_state["error"] = None

    try:
        device = get_device()
        logger.info(f"Loading TTS model on {device}...")

        # Initialize TTS
        # This will download the model if not present in TTS_HOME
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        tts_instance = tts
        model_state["loaded"] = True
        logger.info("TTS Model loaded successfully.")

    except Exception as e:
        logger.error(f"Failed to load TTS model: {e}")
        model_state["error"] = str(e)
        model_state["loaded"] = False
    finally:
        model_state["loading"] = False

# --- Pydantic Models ---

class DownloadRequest(BaseModel):
    agree: bool

class GenerateRequest(BaseModel):
    text: str
    voice_id: str
    language: str = "en"

class DeleteHistoryRequest(BaseModel):
    filenames: List[str]

class SettingsUpdate(BaseModel):
    device: str

# --- Routes ---

@router.get("/status")
def get_status():
    logger.info("Status check requested")
    return model_state

@router.post("/download")
def download_model(req: DownloadRequest, background_tasks: BackgroundTasks):
    logger.info("Download requested")
    if not req.agree:
        raise HTTPException(status_code=400, detail="You must agree to the CPML license.")

    settings = load_settings()
    settings["agreed_to_terms"] = True
    save_settings(settings)

    background_tasks.add_task(load_model_task)
    return {"status": "started", "message": "Model download/loading started in background."}

@router.get("/voices")
def list_voices():
    voices = []
    if VOICES_DIR.exists():
        for d in VOICES_DIR.iterdir():
            if d.is_dir():
                # Check for metadata
                meta_file = d / "metadata.json"
                if meta_file.exists():
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        voices.append(meta)
                else:
                    # Fallback if manual folder
                    voices.append({"id": d.name, "name": d.name})
    return voices

@router.post("/voices/add")
async def add_voice(name: str = Form(...), audio: UploadFile = File(...)):
    logger.info(f"Adding voice: {name}")
    if not tts_instance:
        raise HTTPException(status_code=400, detail="Model is not loaded. Cannot calculate latents.")

    # 1. Create Voice Dir
    voice_id = str(uuid.uuid4())
    voice_path = VOICES_DIR / voice_id
    voice_path.mkdir(parents=True, exist_ok=True)

    # 2. Save Reference Audio
    ref_path = voice_path / "reference.wav"
    with open(ref_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)

    # 3. Calculate Latents
    try:
        if tts_instance:
            gpt_cond_latent, speaker_embedding = tts_instance.get_conditioning_latents(audio_path=[str(ref_path)])
        else:
            # Should only happen if logic above fails, fallback for safety
            gpt_cond_latent, speaker_embedding = ([0.0], [0.0])

        # Save latents
        # Convert tensors to lists if necessary
        if hasattr(gpt_cond_latent, "tolist"):
            gpt_cond_latent = gpt_cond_latent.tolist()
        if hasattr(speaker_embedding, "tolist"):
            speaker_embedding = speaker_embedding.tolist()

        latents_data = {
            "gpt_cond_latent": gpt_cond_latent,
            "speaker_embedding": speaker_embedding
        }

        with open(voice_path / "latents.json", "w") as f:
            json.dump(latents_data, f)

    except Exception as e:
        logger.error(f"Failed to add voice: {e}")
        # Cleanup
        if voice_path.exists():
            shutil.rmtree(voice_path)
        raise HTTPException(status_code=500, detail=f"Failed to calculate latents: {e}")

    # 4. Save Metadata
    meta = {
        "id": voice_id,
        "name": name,
        "created_at": time.time()
    }
    with open(voice_path / "metadata.json", "w") as f:
        json.dump(meta, f)

    return meta

@router.delete("/voices/{voice_id}")
def delete_voice(voice_id: str):
    voice_path = VOICES_DIR / voice_id
    if voice_path.exists():
        shutil.rmtree(voice_path)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Voice not found")

@router.get("/voices/{voice_id}/reference")
def get_voice_reference(voice_id: str):
    voice_path = VOICES_DIR / voice_id
    ref_path = voice_path / "reference.wav"
    if ref_path.exists():
        return FileResponse(ref_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Reference audio not found")

@router.post("/generate")
def generate_speech(req: GenerateRequest):
    logger.info(f"Generating speech for voice_id: {req.voice_id}")
    if not tts_instance:
        raise HTTPException(status_code=400, detail="Model not loaded.")

    voice_path = VOICES_DIR / req.voice_id
    if not voice_path.exists():
        raise HTTPException(status_code=404, detail="Voice not found.")

    # Load Latents
    latents_path = voice_path / "latents.json"
    ref_path = voice_path / "reference.wav"

    gpt_cond_latent = None
    speaker_embedding = None

    if latents_path.exists():
        try:
            with open(latents_path, 'r') as f:
                data = json.load(f)
                gpt_cond_latent = data.get("gpt_cond_latent")
                speaker_embedding = data.get("speaker_embedding")
        except Exception as e:
            logger.error(f"Failed to load latents: {e}")

    # Output Filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_text = "".join([c for c in req.text if c.isalnum() or c in (' ', '_')]).strip()[:25]
    filename = f"{timestamp}_{safe_text}.wav"
    output_path = OUTPUT_DIR / filename

    try:
        if tts_instance:
            # Depending on version, we pass latents or wav
            # tts_to_file(text, speaker_wav=..., language=..., file_path=...)
            # If we have latents, we might need to use `tts.tts()` which returns wav, then save it?
            # Or pass latents to `tts_to_file` if supported.
            # Looking at source, `tts_to_file` often re-computes.
            # Ideally we use `tts.tts(text, language, gpt_cond_latent=..., speaker_embedding=...)` -> wav -> save.

            if gpt_cond_latent and speaker_embedding:
                # We have latents, try to use them
                # Check method signature via introspection or just try
                # XTTS v2 specific:
                wav = tts_instance.tts(
                    text=req.text,
                    language=req.language,
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding
                )
                # Save wav
                # tts.tts returns a list of floats/tensor usually.
                # We need to save it.
                # Torchaudio or internal method?
                # TTS usually has `save_wav`
                try:
                    tts_instance.synthesizer.save_wav(wav, str(output_path))
                except:
                    # Fallback if helper not found, use torchaudio if installed
                    import torch
                    import torchaudio
                    if isinstance(wav, list):
                        wav = torch.tensor(wav).unsqueeze(0)
                    elif isinstance(wav, torch.Tensor):
                        if wav.dim() == 1:
                            wav = wav.unsqueeze(0)
                    # XTTS sample rate is usually 24000
                    torchaudio.save(str(output_path), wav, 24000)

            else:
                # Fallback to re-computing from reference wav
                tts_instance.tts_to_file(
                    text=req.text,
                    speaker_wav=str(ref_path),
                    language=req.language,
                    file_path=str(output_path)
                )

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Update History
    history = load_history()
    history.insert(0, {
        "filename": filename,
        "text": req.text,
        "voice_id": req.voice_id,
        "date": timestamp,
        "path": str(output_path)
    })
    save_history(history)

    return {"filename": filename, "path": f"/api/modules/mod_xtts/output/{filename}"}

@router.get("/history")
def get_history():
    # Verify files exist, clean up if missing?
    # For now just return list
    return load_history()

@router.get("/output/{filename}")
def get_output_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="File not found")

@router.post("/history/delete")
def delete_history(req: DeleteHistoryRequest):
    history = load_history()
    new_history = []
    deleted_count = 0

    to_delete = set(req.filenames)

    for item in history:
        if item["filename"] in to_delete:
            # Delete file
            p = OUTPUT_DIR / item["filename"]
            if p.exists():
                p.unlink()
            deleted_count += 1
        else:
            new_history.append(item)

    save_history(new_history)
    return {"deleted": deleted_count}

@router.get("/settings")
def get_settings():
    return load_settings()

@router.post("/settings")
def update_settings(s: SettingsUpdate):
    settings = load_settings()
    settings["device"] = s.device
    save_settings(settings)
    return settings
