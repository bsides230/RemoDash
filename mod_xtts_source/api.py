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
import platform
import sys
import importlib.util
import re
from pathlib import Path
from datetime import datetime
import traceback
import gc

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
    "model_name": "xtts_v2",
    "dependency_missing": False,
    "missing_deps": []  # List of missing requirements for UI
}

tts_instance = None

# --- Constants ---
XTTS_FILES = {
    "model.pth": "https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth",
    "config.json": "https://huggingface.co/coqui/XTTS-v2/resolve/main/config.json",
    "vocab.json": "https://huggingface.co/coqui/XTTS-v2/resolve/main/vocab.json",
    "speakers_xtts.pth": "https://huggingface.co/coqui/XTTS-v2/resolve/main/speakers_xtts.pth",
    "dvae.pth": "https://huggingface.co/coqui/XTTS-v2/resolve/main/dvae.pth",
    "mel_stats.pth": "https://huggingface.co/coqui/XTTS-v2/resolve/main/mel_stats.pth"
}

# --- Helper Functions ---

def check_dependencies():
    """Checks if critical python dependencies are importable."""
    missing = []

    # Check for requests
    if importlib.util.find_spec("requests") is None:
        missing.append("requests")

    # Check for TTS (coqui-tts)
    if importlib.util.find_spec("TTS") is None:
        missing.append("coqui-tts")

    # Check for torch
    if importlib.util.find_spec("torch") is None:
        missing.append("torch")

    # Check for torchaudio
    if importlib.util.find_spec("torchaudio") is None:
        missing.append("torchaudio")

    return missing

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                s = json.load(f)
                if "max_chunk_chars" not in s:
                    s["max_chunk_chars"] = 220
                return s
        except:
            pass
    return {"device": "cpu", "agreed_to_terms": False, "max_chunk_chars": 220}

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

    # We need torch to check for cuda, so we do a lazy import here if needed
    if device_pref == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

    if device_pref == "vulkan":
        try:
            import torch
            if hasattr(torch, 'is_vulkan_available') and torch.is_vulkan_available():
                 return "vulkan"
            logger.warning("Vulkan requested but torch.is_vulkan_available() is False or missing. Falling back to CPU.")
        except ImportError:
            pass
        return "cpu"

    return "cpu"

def check_files_exist():
    target_dir = MODELS_DIR / "xtts_v2"
    if not target_dir.exists(): return False
    for filename in XTTS_FILES.keys():
        if not (target_dir / filename).exists():
            return False
    return True

def download_file(url, dest_path):
    import requests
    logger.info(f"Downloading {url} to {dest_path}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Download complete: {dest_path}")
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        # Clean up partial file
        if dest_path.exists():
            dest_path.unlink()
        raise e

def ensure_model_files():
    """Checks for XTTS v2 files and downloads them if missing."""
    target_dir = MODELS_DIR / "xtts_v2"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in XTTS_FILES.items():
        file_path = target_dir / filename
        if not file_path.exists():
            logger.info(f"Model file {filename} missing. Downloading...")
            download_file(url, file_path)

    return target_dir

def load_model_task():
    global tts_instance, model_state

    if model_state["loading"] or model_state["loaded"]:
        return

    model_state["loading"] = True
    model_state["error"] = None

    try:
        # 1. Check Python Deps (Lazy Import)
        logger.info("Attempting to import Coqui TTS...")
        try:
            import torch
            import torchaudio
            from TTS.api import TTS
        except ImportError as e:
            logger.error(f"Import failed: {e}")
            model_state["error"] = f"Failed to import dependencies: {e}"
            model_state["dependency_missing"] = True
            model_state["missing_deps"] = check_dependencies()
            # If check_dependencies didn't find anything (meaning packages exist but import failed)
            # we manually add the specific import error
            if not model_state["missing_deps"]:
                 model_state["missing_deps"] = [f"Import Error: {str(e)}"]

            model_state["loaded"] = False
            model_state["loading"] = False
            return
        except Exception as e:
            # Catch other startup crashes like the transformers error
            logger.error(f"Critical error during import: {e}")
            model_state["error"] = f"Critical import error: {e}"
            model_state["dependency_missing"] = True
            model_state["missing_deps"] = ["Check Console for Detail"]
            model_state["loaded"] = False
            model_state["loading"] = False
            return

        # Patch torchaudio.load to use soundfile backend.
        # Newer torchaudio (paired with PyTorch 2.x) defaults to torchcodec which
        # requires FFmpeg DLLs. soundfile handles WAV/FLAC/OGG without FFmpeg.
        try:
            import soundfile as _sf
            _orig_torchaudio_load = torchaudio.load

            def _sf_audio_load(uri, frame_offset=0, num_frames=-1,
                               normalize=True, channels_first=True, **kwargs):
                try:
                    data, sr = _sf.read(str(uri), dtype='float32', always_2d=True)
                    tensor = torch.from_numpy(data.T if channels_first else data)
                    return tensor, sr
                except Exception:
                    return _orig_torchaudio_load(uri, frame_offset=frame_offset,
                                                 num_frames=num_frames,
                                                 normalize=normalize,
                                                 channels_first=channels_first,
                                                 **kwargs)

            torchaudio.load = _sf_audio_load
            logger.info("torchaudio.load patched to use soundfile backend.")
        except ImportError:
            logger.warning("soundfile not installed; torchaudio will use its default backend.")

        # 2. Check/Download Model Files
        model_dir = ensure_model_files()

        device = get_device()
        logger.info(f"Loading TTS model from {model_dir} on {device}...")

        config_path = model_dir / "config.json"
        model_path = model_dir / "model.pth"

        tts = TTS(
            model_path=str(model_dir),
            config_path=str(config_path),
            progress_bar=False,
            gpu=(device == "cuda")
        )

        # Force device move just in case
        tts.to(device)

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
    max_chunk_chars: int = 220

# --- Routes ---

@router.get("/status")
def get_status():
    # Perform a lightweight check if not loaded
    if not model_state["loaded"] and not model_state["loading"]:
        missing = check_dependencies()
        if missing:
            model_state["dependency_missing"] = True
            model_state["missing_deps"] = missing
        else:
            # If imports are present, we don't set dependency_missing=True yet
            # It will be set if load_model_task fails.
            # But we can try to reset it if it was previously set
            if not model_state["error"]:
                model_state["dependency_missing"] = False
                model_state["missing_deps"] = []

    model_state["files_exist"] = check_files_exist()
    return model_state

@router.post("/start")
def start_model(background_tasks: BackgroundTasks):
    if model_state["loaded"] or model_state["loading"]:
        return {"status": "already_running", "message": "Model is already loaded or loading."}

    if not check_files_exist():
        raise HTTPException(status_code=400, detail="Model files missing. Please download first.")

    background_tasks.add_task(load_model_task)
    return {"status": "started", "message": "Model loading started."}

@router.post("/stop")
def stop_model():
    global tts_instance, model_state
    if not model_state["loaded"] and not model_state["loading"]:
        return {"status": "stopped", "message": "Model is not running."}

    logger.info("Stopping TTS Model...")
    tts_instance = None
    model_state["loaded"] = False
    model_state["loading"] = False

    # Cleanup
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except:
        pass
    gc.collect()

    logger.info("TTS Model stopped and memory cleared.")
    return {"status": "stopped", "message": "Model stopped."}

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
        raise HTTPException(status_code=400, detail="Model is not loaded.")

    # 1. Create Voice Dir
    voice_id = str(uuid.uuid4())
    voice_path = VOICES_DIR / voice_id
    voice_path.mkdir(parents=True, exist_ok=True)

    # 2. Save Reference Audio
    ref_path = voice_path / "reference.wav"
    with open(ref_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)

    # Normalise uploaded audio to a clean PCM WAV using soundfile.
    # Converts stereo to mono and re-encodes so torchaudio can load it reliably.
    try:
        import soundfile as sf
        _audio_data, _sr = sf.read(str(ref_path))
        if _audio_data.ndim > 1:  # stereo → mono
            _audio_data = _audio_data.mean(axis=1)
        sf.write(str(ref_path), _audio_data, _sr, subtype='PCM_16')
    except Exception as _prep_err:
        logger.warning(f"Audio pre-processing skipped: {_prep_err}")

    # 3. Calculate Latents
    try:
        # Access get_conditioning_latents via synthesizer.tts_model
        gpt_cond_latent, speaker_embedding = tts_instance.synthesizer.tts_model.get_conditioning_latents(audio_path=[str(ref_path)])

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

def split_text_into_chunks(text: str, max_chars: int = 220) -> List[str]:
    """Split text at sentence boundaries to stay within XTTS character limit."""
    # Split on sentence-ending punctuation, keeping the delimiter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        # If a single sentence is too long, break at commas then spaces
        if len(sentence) > max_chars:
            sub_parts = re.split(r'(?<=,)\s+', sentence)
            for part in sub_parts:
                if len(part) > max_chars:
                    # Last resort: hard word-boundary split
                    words = part.split()
                    for word in words:
                        if len(current) + len(word) + 1 > max_chars and current:
                            chunks.append(current.strip())
                            current = word + " "
                        else:
                            current += word + " "
                else:
                    if len(current) + len(part) + 1 > max_chars and current:
                        chunks.append(current.strip())
                        current = part + " "
                    else:
                        current += part + " "
        else:
            if len(current) + len(sentence) + 1 > max_chars and current:
                chunks.append(current.strip())
                current = sentence + " "
            else:
                current += sentence + " "
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]

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

    # Chunking
    settings = load_settings()
    max_chunk_chars = settings.get("max_chunk_chars", 220)
    chunks = split_text_into_chunks(req.text, max_chunk_chars)
    logger.info(f"Text split into {len(chunks)} chunk(s) for voice {req.voice_id}")

    try:
        # We need to handle tensor conversion if data was loaded from JSON
        import torch
        if gpt_cond_latent and isinstance(gpt_cond_latent, list):
            gpt_cond_latent = torch.tensor(gpt_cond_latent)
        if speaker_embedding and isinstance(speaker_embedding, list):
            speaker_embedding = torch.tensor(speaker_embedding)

        # Depending on device, we might need to move tensors
        device = get_device()
        if device == "cuda":
            if gpt_cond_latent is not None: gpt_cond_latent = gpt_cond_latent.to(device)
            if speaker_embedding is not None: speaker_embedding = speaker_embedding.to(device)

        import numpy as np
        wav_segments = []

        for chunk in chunks:
            # Generate
            if gpt_cond_latent is not None and speaker_embedding is not None:
                # Use the lower-level inference() API to pass pre-computed conditioning
                # latents directly.
                out = tts_instance.synthesizer.tts_model.inference(
                    text=chunk,
                    language=req.language,
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding,
                )
                seg = out["wav"]
            else:
                # Fallback: using tts() directly to get wav in memory
                # If latents are missing, tts() recomputes them from reference audio
                wav_out = tts_instance.tts(
                    text=chunk,
                    speaker_wav=str(voice_path / "reference.wav"),
                    language=req.language
                )
                seg = wav_out

            # Normalize segment
            if isinstance(seg, list):
                seg = np.array(seg, dtype=np.float32)
            elif hasattr(seg, 'cpu'):
                seg = seg.cpu().numpy()
            if seg.ndim > 1:
                seg = seg.squeeze()

            wav_segments.append(seg)

        if wav_segments:
            wav = np.concatenate(wav_segments)
        else:
             wav = np.array([], dtype=np.float32)

        # Save wav using soundfile
        import soundfile as sf
        # XTTS outputs at 24000 Hz sample rate
        sf.write(str(output_path), wav, 24000, subtype='PCM_16')

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
    settings["max_chunk_chars"] = s.max_chunk_chars
    save_settings(settings)
    return settings
