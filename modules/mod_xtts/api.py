from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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
    "missing_deps": []
}

tts_instance = None

# Generation State
gen_state = {
    "job_id": None,
    "is_generating": False,
    "progress": 0,
    "stage": "idle",  # idle, generating, merging, done, error
    "chunk_current": 0,
    "chunk_total": 0,
    "logs": [],
    "metrics": {},
    "output_filename": None,
    "output_path": None,
    "error": None
}
gen_lock = threading.Lock()

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
    if importlib.util.find_spec("requests") is None: missing.append("requests")
    if importlib.util.find_spec("TTS") is None: missing.append("coqui-tts")
    if importlib.util.find_spec("torch") is None: missing.append("torch")
    if importlib.util.find_spec("torchaudio") is None: missing.append("torchaudio")
    return missing

def load_settings():
    defaults = {
        "device": "cpu",
        "agreed_to_terms": False,
        "max_chunk_chars": 220,
        "temperature": 0.75,
        "length_penalty": 1.0,
        "repetition_penalty": 2.0,
        "top_k": 50,
        "top_p": 0.8,
        "speed": 1.0
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                s = json.load(f)
                defaults.update(s)
                return defaults
        except:
            pass
    return defaults

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
            # Check for Vulkan availability if the installed torch supports it
            if hasattr(torch, 'is_vulkan_available') and torch.is_vulkan_available():
                 return "vulkan"
            # Some older or specific torch builds might support it but not have the function?
            # Unlikely. If not available, fallback.
            logger.warning("Vulkan requested but torch.is_vulkan_available() is False or missing.")
        except ImportError:
            pass
        # Fallback to CPU if Vulkan fails
        return "cpu"

    return "cpu"

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
        if dest_path.exists():
            dest_path.unlink()
        raise e

def ensure_model_files():
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
    if model_state["loading"] or model_state["loaded"]: return

    model_state["loading"] = True
    model_state["error"] = None

    try:
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
            if not model_state["missing_deps"]:
                 model_state["missing_deps"] = [f"Import Error: {str(e)}"]
            model_state["loaded"] = False
            model_state["loading"] = False
            return
        except Exception as e:
            logger.error(f"Critical error during import: {e}")
            model_state["error"] = f"Critical import error: {e}"
            model_state["dependency_missing"] = True
            model_state["missing_deps"] = ["Check Console for Detail"]
            model_state["loaded"] = False
            model_state["loading"] = False
            return

        try:
            import soundfile as _sf
            _orig_torchaudio_load = torchaudio.load
            def _sf_audio_load(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, **kwargs):
                try:
                    data, sr = _sf.read(str(uri), dtype='float32', always_2d=True)
                    tensor = torch.from_numpy(data.T if channels_first else data)
                    return tensor, sr
                except Exception:
                    return _orig_torchaudio_load(uri, frame_offset=frame_offset, num_frames=num_frames, normalize=normalize, channels_first=channels_first, **kwargs)
            torchaudio.load = _sf_audio_load
            logger.info("torchaudio.load patched to use soundfile backend.")
        except ImportError:
            logger.warning("soundfile not installed; torchaudio will use its default backend.")

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
    # New settings override
    temperature: Optional[float] = None
    length_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    speed: Optional[float] = None

class DeleteHistoryRequest(BaseModel):
    filenames: List[str]

class SettingsUpdate(BaseModel):
    device: str
    max_chunk_chars: int = 220
    temperature: float = 0.75
    length_penalty: float = 1.0
    repetition_penalty: float = 2.0
    top_k: int = 50
    top_p: float = 0.8
    speed: float = 1.0

# --- Routes ---

@router.get("/status")
def get_status():
    if not model_state["loaded"] and not model_state["loading"]:
        missing = check_dependencies()
        if missing:
            model_state["dependency_missing"] = True
            model_state["missing_deps"] = missing
        else:
            if not model_state["error"]:
                model_state["dependency_missing"] = False
                model_state["missing_deps"] = []
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
                meta_file = d / "metadata.json"
                if meta_file.exists():
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        voices.append(meta)
                else:
                    voices.append({"id": d.name, "name": d.name})
    return voices

@router.post("/voices/add")
async def add_voice(name: str = Form(...), audio: UploadFile = File(...)):
    logger.info(f"Adding voice: {name}")
    if not tts_instance:
        raise HTTPException(status_code=400, detail="Model is not loaded.")

    voice_id = str(uuid.uuid4())
    voice_path = VOICES_DIR / voice_id
    voice_path.mkdir(parents=True, exist_ok=True)
    ref_path = voice_path / "reference.wav"
    with open(ref_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)

    try:
        import soundfile as sf
        _audio_data, _sr = sf.read(str(ref_path))
        if _audio_data.ndim > 1:
            _audio_data = _audio_data.mean(axis=1)
        sf.write(str(ref_path), _audio_data, _sr, subtype='PCM_16')
    except Exception as _prep_err:
        logger.warning(f"Audio pre-processing skipped: {_prep_err}")

    try:
        gpt_cond_latent, speaker_embedding = tts_instance.synthesizer.tts_model.get_conditioning_latents(audio_path=[str(ref_path)])
        if hasattr(gpt_cond_latent, "tolist"): gpt_cond_latent = gpt_cond_latent.tolist()
        if hasattr(speaker_embedding, "tolist"): speaker_embedding = speaker_embedding.tolist()
        latents_data = {"gpt_cond_latent": gpt_cond_latent, "speaker_embedding": speaker_embedding}
        with open(voice_path / "latents.json", "w") as f:
            json.dump(latents_data, f)
    except Exception as e:
        if voice_path.exists(): shutil.rmtree(voice_path)
        raise HTTPException(status_code=500, detail=f"Failed to calculate latents: {e}")

    meta = {"id": voice_id, "name": name, "created_at": time.time()}
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
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            sub_parts = re.split(r'(?<=,)\s+', sentence)
            for part in sub_parts:
                if len(part) > max_chars:
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

# --- Generation Logic ---

def log_gen(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    logger.info(entry)
    with gen_lock:
        gen_state["logs"].append(entry)

def _run_generation_task(req: GenerateRequest):
    global gen_state

    with gen_lock:
        gen_state["is_generating"] = True
        gen_state["progress"] = 0
        gen_state["stage"] = "initializing"
        gen_state["logs"] = []
        gen_state["metrics"] = {"start_time": time.time(), "chunk_times": []}
        gen_state["error"] = None
        gen_state["chunk_current"] = 0
        gen_state["chunk_total"] = 0

    log_gen(f"Starting generation task for voice {req.voice_id}")
    log_gen(f"Text length: {len(req.text)} chars")

    try:
        if not tts_instance:
            raise Exception("Model not loaded")

        voice_path = VOICES_DIR / req.voice_id
        if not voice_path.exists():
            raise Exception("Voice not found")

        # Load settings (merge defaults with request overrides)
        saved_settings = load_settings()

        # Helper to get setting from req or saved
        def get_set(key, default):
            val = getattr(req, key, None)
            if val is not None: return val
            return saved_settings.get(key, default)

        params = {
            "temperature": get_set("temperature", 0.75),
            "length_penalty": get_set("length_penalty", 1.0),
            "repetition_penalty": get_set("repetition_penalty", 2.0),
            "top_k": get_set("top_k", 50),
            "top_p": get_set("top_p", 0.8),
            "speed": get_set("speed", 1.0),
            "enable_text_splitting": True
        }

        log_gen(f"Inference Params: {params}")

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
                    log_gen("Loaded cached latents.")
            except Exception as e:
                log_gen(f"Error loading latents: {e}")

        # Prepare Tensors
        import torch
        if gpt_cond_latent and isinstance(gpt_cond_latent, list):
            gpt_cond_latent = torch.tensor(gpt_cond_latent)
        if speaker_embedding and isinstance(speaker_embedding, list):
            speaker_embedding = torch.tensor(speaker_embedding)

        device = get_device()
        log_gen(f"Using device: {device}")

        if device == "cuda" or device == "vulkan":
            # Note: For Vulkan, we need to be careful.
            # If tts_instance is already on device, latents might need move.
            if gpt_cond_latent is not None: gpt_cond_latent = gpt_cond_latent.to(device)
            if speaker_embedding is not None: speaker_embedding = speaker_embedding.to(device)

        # Chunking
        max_chunk_chars = saved_settings.get("max_chunk_chars", 220)
        chunks = split_text_into_chunks(req.text, max_chunk_chars)

        with gen_lock:
            gen_state["chunk_total"] = len(chunks)
            gen_state["stage"] = "generating"

        log_gen(f"Split text into {len(chunks)} chunks.")

        import numpy as np
        wav_segments = []

        for i, chunk in enumerate(chunks):
            start_chunk = time.time()
            current_chunk_idx = i + 1

            with gen_lock:
                gen_state["chunk_current"] = current_chunk_idx

            log_gen(f"Generating chunk {current_chunk_idx}/{len(chunks)} ({len(chunk)} chars)...")

            # Generate
            if gpt_cond_latent is not None and speaker_embedding is not None:
                out = tts_instance.synthesizer.tts_model.inference(
                    text=chunk,
                    language=req.language,
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding,
                    **params
                )
                seg = out["wav"]
            else:
                log_gen("Latents missing, using reference wav (slower).")
                wav_out = tts_instance.tts(
                    text=chunk,
                    speaker_wav=str(voice_path / "reference.wav"),
                    language=req.language,
                    **params
                )
                seg = wav_out

            # Normalize
            if isinstance(seg, list):
                seg = np.array(seg, dtype=np.float32)
            elif hasattr(seg, 'cpu'):
                seg = seg.cpu().numpy()
            if seg.ndim > 1:
                seg = seg.squeeze()

            wav_segments.append(seg)

            end_chunk = time.time()
            duration = end_chunk - start_chunk
            log_gen(f"Chunk {current_chunk_idx} done in {duration:.2f}s")

            with gen_lock:
                gen_state["metrics"]["chunk_times"].append(duration)
                # Update progress roughly based on chunks
                gen_state["progress"] = int((current_chunk_idx / len(chunks)) * 90)

        # Merging
        with gen_lock:
            gen_state["stage"] = "merging"
            gen_state["progress"] = 95

        log_gen("Merging audio segments...")
        if wav_segments:
            wav = np.concatenate(wav_segments)
        else:
            wav = np.array([], dtype=np.float32)

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_text = "".join([c for c in req.text if c.isalnum() or c in (' ', '_')]).strip()[:25]
        filename = f"{timestamp}_{safe_text}.wav"
        output_path = OUTPUT_DIR / filename

        import soundfile as sf
        sf.write(str(output_path), wav, 24000, subtype='PCM_16')

        log_gen(f"Saved to {filename}")

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

        with gen_lock:
            gen_state["stage"] = "done"
            gen_state["progress"] = 100
            gen_state["output_filename"] = filename
            gen_state["output_path"] = f"/api/modules/mod_xtts/output/{filename}"
            gen_state["metrics"]["end_time"] = time.time()
            total_time = gen_state["metrics"]["end_time"] - gen_state["metrics"]["start_time"]
            log_gen(f"Task Complete. Total time: {total_time:.2f}s")

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        traceback.print_exc()
        log_gen(f"Error: {str(e)}")
        with gen_lock:
            gen_state["stage"] = "error"
            gen_state["error"] = str(e)
    finally:
        with gen_lock:
            gen_state["is_generating"] = False


@router.post("/generate")
def start_generation(req: GenerateRequest, background_tasks: BackgroundTasks):
    global gen_state

    # Simple check if busy
    if gen_state["is_generating"]:
        # Optional: allow queueing? For now, reject or just restart.
        # User asked for a "Reset" button, implying single user usage.
        # We will restart.
        pass

    # Start in background
    job_id = str(uuid.uuid4())
    # We assign job_id here but it's also set in task? No, task uses global state.
    with gen_lock:
        gen_state["job_id"] = job_id

    background_tasks.add_task(_run_generation_task, req)

    return {"job_id": job_id, "status": "started"}

@router.get("/generation_status")
def get_generation_status():
    return gen_state

@router.post("/generation/stop")
def stop_generation():
    # Not easily cancellable with threads without flags, but we can reset state
    # Ideally checking a flag in the loop.
    # For now, just reset the UI state on next poll?
    # We won't implement hard kill yet, just API for it.
    return {"status": "ignored"} # TODO: Implement cancellation flag

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
            if p.exists(): p.unlink()
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
    settings.update(s.dict())
    save_settings(settings)
    return settings
