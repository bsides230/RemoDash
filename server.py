import os
import sys
try:
    import psutil
except ImportError:
    print("[System] Warning: psutil not found. Using mock implementation.")
    psutil = None

import asyncio
import json
import datetime
import shutil
import socket
import zipfile
import tempfile
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
import platform
import subprocess
import secrets
import time
import uuid
import shlex
from urllib.parse import quote_plus

from fastapi import FastAPI, Request, HTTPException, Header, Depends, Body, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import uvicorn

from settings_manager import SettingsManager

try:
    import pynvml
except ImportError:
    pynvml = None

try:
    import git
except ImportError:
    git = None

try:
    from crontab import CronTab
except ImportError:
    CronTab = None

# --- Psutil Mock for Android/No-Dep environments ---
if psutil is None:
    class MockPsutil:
        class VirtualMemory:
            percent = 0
            used = 0
            total = 0
        class DiskUsage:
            percent = 0
            used = 0
            total = 0
        class Battery:
            percent = 0
            power_plugged = False
            secsleft = 0
        class CpuFreq:
            current = 0
            max = 0
        class Process:
            def __init__(self, pid): pass
            def terminate(self): pass

        NoSuchProcess = Exception
        AccessDenied = Exception

        @staticmethod
        def cpu_percent(interval=None): return 0
        @staticmethod
        def virtual_memory(): return MockPsutil.VirtualMemory()
        @staticmethod
        def disk_usage(path): return MockPsutil.DiskUsage()
        @staticmethod
        def disk_partitions(): return []
        @staticmethod
        def cpu_count(logical=True): return 1
        @staticmethod
        def cpu_freq(): return MockPsutil.CpuFreq()
        @staticmethod
        def sensors_battery(): return None
        @staticmethod
        def net_io_counters():
            class NetIO:
                def _asdict(self): return {}
            return NetIO()
        @staticmethod
        def process_iter(attrs=None): return []
        @staticmethod
        def Process(pid): return MockPsutil.Process(pid)

    psutil = MockPsutil()

# Platform-specific imports for Terminal
if platform.system() != "Windows":
    import pty
    import termios
    import struct
    import fcntl

# Global reference to the main event loop
main_loop: Optional[asyncio.AbstractEventLoop] = None
REMODASH_TOKEN: Optional[str] = None

# Short-lived session keys: {key: expiry_timestamp}
SESSION_KEYS: Dict[str, float] = {}

# --- DiskJournalLogger ---
class DiskJournalLogger:
    def __init__(self, log_dir="logs", lines_per_chunk=1000):
        self.log_dir = Path(log_dir)
        self.lines_per_chunk = lines_per_chunk
        self.current_session_dir = None
        self.current_chunk_index = 0
        self.current_chunk_lines = 0
        self.current_chunk_path = None

        # In-memory buffer for live streaming (tail)
        self.subscribers = set()
        self._lock = None

        # Initialize session
        self._start_session()

    @property
    def lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _start_session(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session_dir = self.log_dir / f"session_{timestamp}"
        self.current_session_dir.mkdir(parents=True, exist_ok=True)
        self._start_new_chunk()
        print(f"[System] Logging to session: {self.current_session_dir}")

    def _start_new_chunk(self):
        self.current_chunk_index += 1
        filename = f"chunk_{self.current_chunk_index:03d}.log"
        self.current_chunk_path = self.current_session_dir / filename
        self.current_chunk_lines = 0
        # Create empty file
        with open(self.current_chunk_path, "w", encoding="utf-8") as f:
            pass

    async def emit(self, level: str, msg: str, source: str = "System"):
        event = {
            "ts": datetime.datetime.now().isoformat(),
            "level": level,
            "msg": msg,
            "source": source
        }

        # 1. Write to Disk
        try:
            line = json.dumps(event) + "\n"
            with open(self.current_chunk_path, "a", encoding="utf-8") as f:
                f.write(line)

            self.current_chunk_lines += 1
            if self.current_chunk_lines >= self.lines_per_chunk:
                self._start_new_chunk()

        except Exception as e:
            print(f"Logging Failed: {e}")

        # 2. Log to console
        print(f"[{level}] {source}: {msg}")

        # 3. Notify subscribers (Live Stream)
        async with self.lock:
            for q in self.subscribers:
                await q.put(event)

    async def subscribe(self, request: Request):
        q = asyncio.Queue()
        async with self.lock:
            self.subscribers.add(q)

        try:
            # Yield initial connection message
            yield {
                "data": json.dumps({'level':'Success', 'msg': 'Connected to Log Stream', 'ts': datetime.datetime.now().isoformat(), 'source': 'System'})
            }

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {"data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"comment": "heartbeat"}
        finally:
            async with self.lock:
                if q in self.subscribers:
                    self.subscribers.remove(q)

    # --- Historical Access Methods ---
    def list_sessions(self):
        if not self.log_dir.exists():
            return []
        sessions = []
        for d in self.log_dir.iterdir():
            if d.is_dir() and d.name.startswith("session_"):
                # timestamp from name
                ts_str = d.name.replace("session_", "")
                sessions.append({"id": d.name, "timestamp": ts_str})
        return sorted(sessions, key=lambda x: x["timestamp"], reverse=True)

    def list_chunks(self, session_id):
        session_path = self.log_dir / session_id
        if not session_path.exists():
            return []
        chunks = []
        for f in session_path.glob("chunk_*.log"):
            # Parse index
            try:
                idx = int(f.stem.split("_")[1])
                chunks.append({"id": f.name, "index": idx, "size": f.stat().st_size})
            except: pass
        return sorted(chunks, key=lambda x: x["index"])

    def get_chunk_content(self, session_id, chunk_id):
        path = self.log_dir / session_id / chunk_id
        if not path.exists():
            return []

        lines = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            lines.append(json.loads(line))
                        except: pass
        except Exception:
            return []
        return lines

# --- Pydantic Models (Forward) ---
class Shortcut(BaseModel):
    id: Optional[str] = None
    name: str
    path: str
    type: str = "auto"
    args: Optional[str] = ""
    cwd: Optional[str] = ""
    confirm: bool = False
    capture_output: bool = True
    run_mode: str = "output"

class ShortcutRunRequest(BaseModel):
    run_mode: Optional[str] = None # Allow override

# --- VLC Manager ---
class VLCManager:
    def __init__(self, host="127.0.0.1", port=4212):
        self.host = host
        self.port = port
        self.process = None

    def _send_command(self, cmd: str) -> str:
        """Connects to VLC RC, sends command, returns response."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((self.host, self.port))

                # Receive initial welcome banner/prompt if any
                try:
                    s.recv(1024)
                except: pass

                # Send command
                s.sendall(f"{cmd}\n".encode())

                # Read response
                # RC interface is tricky, it doesn't always signal end of message well.
                # We read a bit.
                data = b""
                try:
                    while True:
                        chunk = s.recv(4096)
                        if not chunk: break
                        data += chunk
                        if len(chunk) < 4096: break
                except socket.timeout:
                    pass

                return data.decode(errors="ignore").strip()
        except ConnectionRefusedError:
            return "Error: VLC not running or RC interface not active."
        except Exception as e:
            return f"Error: {str(e)}"

    def launch(self, path: str):
        """Launches VLC with the specified playlist/folder."""
        # 1. Kill existing if running (simple single-instance management)
        self.kill()

        # 2. Build Playlist
        playlist_path = self._create_playlist(path)
        if not playlist_path:
            raise Exception("Could not create playlist from path")

        # 3. Launch
        # Check settings for vlc_path override
        custom_vlc = settings_manager.settings.get("vlc_path")
        vlc_bin = custom_vlc if custom_vlc and custom_vlc.strip() else "vlc"

        cmd = [
            vlc_bin,
            "--extraintf", "rc",
            "--rc-host", f"{self.host}:{self.port}",
            "--fullscreen",
            "--loop",   # Repeat All
            "--random", # Shuffle
            playlist_path
        ]

        # Windows specific: vlc might not be in PATH.
        # Try common paths if simple 'vlc' fails?
        # For now assume 'vlc' is in PATH as per typical user setup or allow config.
        # We will try strict 'vlc' first.

        try:
            if platform.system() == "Windows":
                 # Detach process
                 self.process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                 # Linux: set DISPLAY if needed, though usually inherited
                 env = os.environ.copy()
                 if "DISPLAY" not in env: env["DISPLAY"] = ":0"
                 self.process = subprocess.Popen(cmd, env=env, preexec_fn=os.setsid)
        except FileNotFoundError:
             # Fallback logic could go here
             custom_vlc = settings_manager.settings.get("vlc_path")
             if custom_vlc:
                 raise Exception(f"VLC executable not found at configured path: {custom_vlc}")
             raise Exception("VLC executable not found. Please ensure VLC is installed and in your PATH, or configure the path in settings.")

    def kill(self):
        # Kill python-tracked process
        if self.process:
            try:
                self.process.terminate()
                self.process = None
            except: pass

        # Force kill by port/name to be sure (in case launched externally or lost track)
        # This is aggressive but requested: "start the vlc app... make new playlist" implies fresh start.
        # We can use psutil to find process listening on port 4212?
        # Or just pkill vlc.
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info and proc.info['name'] and "vlc" in proc.info['name'].lower():
                        proc.terminate()
                except: pass
        except Exception:
            pass

    def _create_playlist(self, folder_path: str) -> Optional[str]:
        p = Path(folder_path)
        if not p.exists(): return None

        media_exts = {'.mp4', '.mkv', '.avi', '.mov', '.mp3', '.flac', '.wav', '.webm', '.m4v'}
        files = []

        if p.is_file():
            files.append(p)
        else:
            for entry in p.iterdir():
                if entry.is_file() and entry.suffix.lower() in media_exts:
                    files.append(entry)

        if not files: return None

        # Create temp m3u
        fd, temp_path = tempfile.mkstemp(suffix=".m3u", prefix="remodash_vlc_")
        os.close(fd)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in files:
                f.write(f"{str(item)}\n")

        return temp_path

    def command(self, action: str):
        # Map simple actions to RC commands
        valid = {
            "play": "play",
            "pause": "pause",
            "stop": "stop",
            "next": "next",
            "prev": "prev",
            "vol_up": "volup 2",
            "vol_down": "voldown 2",
            "fullscreen": "f"
        }
        if action in valid:
            return self._send_command(valid[action])
        return "Invalid command"

    def get_status(self):
        # 'status' returns state (playing/stopped)
        # 'get_title' returns title
        state = self._send_command("status")
        title = self._send_command("get_title")

        # Clean up output
        # VLC RC often echoes prompt "> "
        state = state.replace(">", "").strip()
        title = title.replace(">", "").strip()

        return {"state": state, "title": title}

# --- Shortcuts Manager ---
class ShortcutsManager:
    def __init__(self, data_file="data/shortcuts.json"):
        self.data_file = Path(data_file)
        self.shortcuts = []
        self._load()

    def _load(self):
        if not self.data_file.exists():
            # Create parent dir if needed
            try:
                self.data_file.parent.mkdir(parents=True, exist_ok=True)
            except: pass
            self.shortcuts = []
            self._save()
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.shortcuts = [Shortcut(**s) for s in data.get("shortcuts", [])]
        except Exception as e:
            print(f"Failed to load shortcuts: {e}")
            self.shortcuts = []

    def _save(self):
        try:
            data = {"shortcuts": [s.dict() for s in self.shortcuts]}
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save shortcuts: {e}")

    def list(self):
        return self.shortcuts

    def get(self, sid):
        for s in self.shortcuts:
            if s.id == sid:
                return s
        return None

    def add(self, s: Shortcut):
        # Generate ID if missing
        if not s.id:
            s.id = str(uuid.uuid4())
        self.shortcuts.append(s)
        self._save()
        return s

    def update(self, sid, updates: Dict[str, Any]):
        for i, s in enumerate(self.shortcuts):
            if s.id == sid:
                updated = s.copy(update=updates)
                self.shortcuts[i] = updated
                self._save()
                return updated
        return None

    def delete(self, sid):
        self.shortcuts = [s for s in self.shortcuts if s.id != sid]
        self._save()

# Global Logger
logger = DiskJournalLogger()
settings_manager = SettingsManager()
shortcuts_manager = ShortcutsManager()
vlc_manager = VLCManager()

# --- Pydantic Models ---
class PresetModel(BaseModel):
    preset_id: str
    config: Dict[str, Any]

class ActiveConfigModel(BaseModel):
    config: Dict[str, Any]

class FileOpRequest(BaseModel):
    path: str
    content: Optional[str] = None
    new_path: Optional[str] = None

class FilesListRequest(BaseModel):
    paths: List[str]

class GitRepoRequest(BaseModel):
    path: str
    message: Optional[str] = None
    branch: Optional[str] = None
    files: Optional[List[str]] = None
    delete_files: Optional[bool] = False

class GitCloneRequest(BaseModel):
    url: str
    path: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    token: Optional[str] = None

class TaskKillRequest(BaseModel):
    pid: int

class CronRequest(BaseModel):
    lines: str

class VLCLaunchRequest(BaseModel):
    path: str

class VLCCommandRequest(BaseModel):
    command: str

# --- App Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop, REMODASH_TOKEN
    main_loop = asyncio.get_running_loop()

    # Load Admin Token
    token_file = Path("admin_token.txt")
    if token_file.exists():
        try:
            REMODASH_TOKEN = token_file.read_text(encoding="utf-8").strip()
            print("[System] Loaded admin token from admin_token.txt")
        except Exception as e:
            print(f"[System] Failed to read admin_token.txt: {e}")

    # --- Git Configuration Fix ---
    # Fix "detected dubious ownership" by trusting all directories
    if git:
        try:
            subprocess.run(["git", "config", "--global", "--replace-all", "safe.directory", "*"], check=False)
            print("[System] Git safe.directory set to '*'")
        except Exception as e:
            print(f"[System] Failed to set git safe.directory: {e}")

    await logger.emit("Info", "RemoDash Server started.", "System")

    yield

app = FastAPI(title="RemoDash Server", lifespan=lifespan)

# Determine allowed origins
allowed_origins = settings_manager.settings.get("allowed_origins", [])
current_port = 8000
try:
    if os.path.exists("port.txt"):
        with open("port.txt", "r") as f:
            val = f.read().strip()
            if val.isdigit():
                current_port = int(val)
except: pass

defaults = [
    f"http://localhost:{current_port}",
    f"http://127.0.0.1:{current_port}"
]
# Ensure defaults are present
for d in defaults:
    if d not in allowed_origins:
        allowed_origins.append(d)

print(f"[System] Allowed Origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["X-Token", "Content-Type", "Authorization"],
)

# --- Routes ---

async def verify_token(x_token: Optional[str] = Header(None, alias="X-Token"), token: Optional[str] = None, key: Optional[str] = None):
    # Check for No Auth Flag
    if Path("global_flags/no_auth").exists():
        return "NO_AUTH"

    # 1. Check Session Key (Preferred for WS/SSE)
    if key:
        expiry = SESSION_KEYS.get(key)
        if expiry and time.time() < expiry:
            return "SESSION_KEY_VALID"
        # If invalid/expired, fall through to token check

    # 2. Check Standard Token
    # Support both Header (preferred) and Query Param (SSE/EventSource)
    auth_token = x_token or token
    if not REMODASH_TOKEN or not auth_token or auth_token != REMODASH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return auth_token

@app.get("/api/auth/status")
async def get_auth_status():
    if Path("global_flags/no_auth").exists():
        return {"required": False}
    return {"required": True}

@app.post("/api/verify_token", dependencies=[Depends(verify_token)])
async def verify_token_endpoint():
    return {"status": "valid"}

@app.post("/api/session/terminal", dependencies=[Depends(verify_token)])
async def create_session_token():
    """Generates a short-lived session token."""
    key = secrets.token_urlsafe(32)
    # Valid for 60 seconds
    SESSION_KEYS[key] = time.time() + 60

    # Lazy cleanup of expired keys
    expired = [k for k, exp in SESSION_KEYS.items() if time.time() > exp]
    for k in expired:
        del SESSION_KEYS[k]

    return {"key": key}

@app.get("/health")
async def health_check():
    # Wrap psutil calls for Android/PermissionError compatibility
    try:
        cpu_percent = psutil.cpu_percent()
    except (PermissionError, Exception):
        cpu_percent = 0

    try:
        ram = psutil.virtual_memory()
    except (PermissionError, Exception):
        # Mock object if access denied
        class MockRAM:
            percent = 0
            used = 0
            total = 0
        ram = MockRAM()

    # Disk Usage (Root)
    try:
        disk = psutil.disk_usage('.')
    except (PermissionError, Exception):
        class MockDisk:
            percent = 0
            used = 0
            total = 0
        disk = MockDisk()

    # Detailed Partitions (New)
    partitions_info = []
    try:
        for part in psutil.disk_partitions():
            try:
                # Skip inaccessible partitions
                if "cdrom" in part.opts or part.fstype == "":
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                partitions_info.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "percent": usage.percent
                })
            except (OSError, PermissionError):
                continue
    except Exception:
        pass

    # Extended System Info

    # CPU Info
    cpu_info = {
        "percent": cpu_percent,
        "count_logical": psutil.cpu_count(logical=True) or 1,
        "count_physical": psutil.cpu_count(logical=False) or 1,
        "freq_current": 0,
        "freq_max": 0
    }
    try:
        freq = psutil.cpu_freq()
        if freq:
            cpu_info["freq_current"] = freq.current
            cpu_info["freq_max"] = freq.max
    except: pass

    # GPU Info
    gpu_stats = {}
    if pynvml:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_stats[f"gpu_{i}"] = {
                    "name": name,
                    "vram_used_gb": mem_info.used / (1024**3),
                    "vram_total_gb": mem_info.total / (1024**3),
                    "vram_percent": (mem_info.used / mem_info.total) * 100,
                    "gpu_util_percent": util.gpu
                }
        except Exception as e:
            gpu_stats["error"] = str(e)

    # Battery
    battery_info = {}
    try:
        sb = psutil.sensors_battery()
        if sb:
            battery_info = {
                "percent": sb.percent,
                "power_plugged": sb.power_plugged,
                "secsleft": sb.secsleft
            }
    except: pass

    # OS Info
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "node": platform.node()
    }

    # Net IO
    net_io = {}
    try:
        if psutil:
            # Check if implemented
            try:
                net_io = psutil.net_io_counters()._asdict()
            except AttributeError: pass
    except (PermissionError, Exception):
        pass

    return {
        "status": "ok",
        "cpu": cpu_info,
        "ram": {
            "percent": ram.percent,
            "used_gb": ram.used / (1024**3),
            "total_gb": ram.total / (1024**3)
        },
        "disk": {
            "percent": disk.percent,
            "used_gb": disk.used / (1024**3),
            "total_gb": disk.total / (1024**3),
            "partitions": partitions_info
        },
        "gpu": gpu_stats,
        "battery": battery_info,
        "os": os_info,
        "net": net_io
    }

# --- Power Endpoints ---
@app.post("/api/power/restart", dependencies=[Depends(verify_token)])
async def restart_server():
    """Restarts the RemoDash server process."""
    try:
        # We use sys.executable to restart the current script
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/power/reboot", dependencies=[Depends(verify_token)])
async def reboot_system():
    """Reboots the host machine."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "0"])
        else:
            subprocess.run(["sudo", "reboot"])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/git/stash", dependencies=[Depends(verify_token)])
async def git_stash(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)
        try: _ = r.head.commit
        except ValueError: raise Exception("Cannot stash: No commits yet")

        r.git.stash('save', req.message or f"Stash from RemoDash {datetime.datetime.now()}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/git/stash/pop", dependencies=[Depends(verify_token)])
async def git_stash_pop(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)
        r.git.stash('pop')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/git/discard", dependencies=[Depends(verify_token)])
async def git_discard(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)

        has_commits = True
        try: _ = r.head.commit
        except ValueError: has_commits = False

        if req.files and len(req.files) > 0:
            # Discard specific files
            untracked = set(r.untracked_files)

            for f in req.files:
                fp = os.path.join(req.path, f)
                if f in untracked:
                     if os.path.exists(fp):
                         try:
                            if os.path.isdir(fp): shutil.rmtree(fp)
                            else: os.remove(fp)
                         except: pass
                else:
                    if has_commits:
                        r.git.checkout('HEAD', '--', f)
                    else:
                        # No commits: unstage and delete
                        try:
                            r.git.rm('--cached', f)
                            if os.path.exists(fp): os.remove(fp)
                        except: pass
        else:
            # Discard all
            if has_commits:
                r.git.reset('--hard', 'HEAD')
            else:
                # No commits: Unstage all
                try: r.git.rm('-r', '--cached', '.', ignore_unmatch=True)
                except: pass

            r.git.clean('-fd') # Clean untracked

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/power/shutdown", dependencies=[Depends(verify_token)])
async def shutdown_system():
    """Shuts down the host machine."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["sudo", "shutdown", "now"])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Task Manager Endpoints ---
@app.get("/api/tasks", dependencies=[Depends(verify_token)])
async def get_tasks():
    processes = []
    try:
        # 'username' often causes PermissionError on Android
        attrs = ['pid', 'name', 'cpu_percent', 'memory_percent', 'status']
        if not ("ANDROID_ROOT" in os.environ or "com.termux" in os.environ.get("PREFIX", "")):
             attrs.append('username')

        for proc in psutil.process_iter(attrs):
            try:
                p_info = proc.info
                # Polyfill username if missing
                if 'username' not in p_info: p_info['username'] = "?"
                processes.append(p_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception: pass
    return processes

@app.post("/api/tasks/kill", dependencies=[Depends(verify_token)])
async def kill_task(req: TaskKillRequest):
    try:
        p = psutil.Process(req.pid)
        p.terminate()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Network Monitor Endpoints ---
@app.get("/api/network", dependencies=[Depends(verify_token)])
async def get_network_stats():
    try:
        return psutil.net_io_counters()._asdict()
    except (PermissionError, Exception, AttributeError):
        return {}

# --- Cron Manager Endpoints ---
@app.get("/api/cron", dependencies=[Depends(verify_token)])
async def get_cron():
    if not CronTab:
        raise HTTPException(status_code=501, detail="python-crontab not installed")
    try:
        cron = CronTab(user=True)
        return {"lines": cron.render()}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cron", dependencies=[Depends(verify_token)])
async def save_cron(req: CronRequest):
    try:
        proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(input=req.lines.encode('utf-8'))

        if proc.returncode != 0:
             raise Exception(stderr.decode())

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- VLC Endpoints ---

@app.post("/api/vlc/launch", dependencies=[Depends(verify_token)])
async def vlc_launch(req: VLCLaunchRequest):
    try:
        # Validate path access using existing check
        check_path_access(req.path)
        vlc_manager.launch(req.path)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vlc/command", dependencies=[Depends(verify_token)])
async def vlc_command(req: VLCCommandRequest):
    try:
        res = vlc_manager.command(req.command)
        return {"result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vlc/status", dependencies=[Depends(verify_token)])
async def vlc_status():
    try:
        return vlc_manager.get_status()
    except Exception as e:
        return {"state": "error", "title": str(e)}

@app.post("/api/vlc/kill", dependencies=[Depends(verify_token)])
async def vlc_kill():
    vlc_manager.kill()
    return {"success": True}

# --- Shortcuts Endpoints ---

def build_command(s: Shortcut) -> str:
    # Construct a shell string command for Terminal injection
    # Simple join for now, might need quoting
    base = s.path
    if " " in base: base = f'"{base}"'

    args = s.args

    # Determine prefix based on type/ext
    ext = os.path.splitext(s.path)[1].lower()
    prefix = ""

    if s.type == "auto":
        if ext == ".py": prefix = "python "
        elif ext == ".js": prefix = "node "
        elif ext == ".sh": prefix = "bash "
        elif ext == ".ps1": prefix = "powershell -ExecutionPolicy Bypass -File "
        elif ext == ".bat": prefix = "" # cmd handles it
    elif s.type == "python": prefix = "python "
    elif s.type == "node": prefix = "node "
    elif s.type == "bash": prefix = "bash "

    # For Terminal, we just type it in
    return f"{prefix}{base} {args}".strip()

def build_command_list(s: Shortcut) -> List[str]:
    # Construct list for subprocess
    path = s.path
    try:
        args = shlex.split(s.args) if s.args else []
    except:
        args = s.args.split(" ") if s.args else []

    ext = os.path.splitext(path)[1].lower()

    # Defaults
    cmd = [path] + args

    if s.type == "auto":
        if ext == ".py": cmd = [sys.executable, path] + args
        elif ext == ".js": cmd = ["node", path] + args
        elif ext == ".sh": cmd = ["bash", path] + args
        elif ext == ".ps1": cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", path] + args
        elif ext == ".bat": cmd = ["cmd.exe", "/c", path] + args
    elif s.type == "python":
        cmd = [sys.executable, path] + args
    elif s.type == "node":
        cmd = ["node", path] + args
    elif s.type == "bash":
        cmd = ["bash", path] + args

    return cmd

@app.get("/api/shortcuts", dependencies=[Depends(verify_token)])
async def list_shortcuts():
    return shortcuts_manager.list()

@app.post("/api/shortcuts", dependencies=[Depends(verify_token)])
async def add_shortcut(s: Shortcut):
    # Validate Access
    try:
        check_path_access(s.path)
        if s.cwd:
            check_path_access(s.cwd)
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {str(e)}")

    return shortcuts_manager.add(s)

@app.put("/api/shortcuts/{sid}", dependencies=[Depends(verify_token)])
async def update_shortcut(sid: str, s: Shortcut):
    # Validate Access
    try:
        check_path_access(s.path)
        if s.cwd:
            check_path_access(s.cwd)
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {str(e)}")

    data = s.dict()
    data['id'] = sid # Enforce ID persistence
    updated = shortcuts_manager.update(sid, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    return updated

@app.delete("/api/shortcuts/{sid}", dependencies=[Depends(verify_token)])
async def delete_shortcut(sid: str):
    shortcuts_manager.delete(sid)
    return {"success": True}

@app.post("/api/shortcuts/{sid}/run", dependencies=[Depends(verify_token)])
async def run_shortcut_endpoint(sid: str, req: ShortcutRunRequest):
    s = shortcuts_manager.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    # Validate Access (Double check at runtime)
    check_path_access(s.path)
    if s.cwd:
        check_path_access(s.cwd)

    run_mode = req.run_mode or s.run_mode

    if run_mode == "terminal":
        # Client should handle terminal opening via websocket, using data from the shortcut.
        return {"action": "terminal", "cwd": s.cwd, "command": build_command(s)}

    # Output Mode (Server Execution)
    cmd_list = build_command_list(s)
    cwd = s.cwd if s.cwd else os.path.dirname(s.path)
    if not cwd: cwd = None

    try:
        # Bounded execution
        proc = subprocess.run(
            cmd_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30 # 30s timeout
        )

        stdout = proc.stdout[:200000] # Cap at ~200KB
        stderr = proc.stderr[:200000]

        return {
            "action": "output",
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr
        }

    except subprocess.TimeoutExpired:
        return {"action": "output", "exit_code": -1, "stdout": "", "stderr": "Execution Timeout (30s)"}
    except Exception as e:
        return {"action": "output", "exit_code": -1, "stdout": "", "stderr": f"Error: {str(e)}"}

# --- Git Manager Endpoints ---

def check_path_access(path: str) -> Path:
    """
    Validates if the requested path is allowed under the current filesystem mode.
    Returns the resolved Path object or raises HTTPException.
    """
    try:
        target = Path(path).expanduser().resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")

    mode = settings_manager.settings.get("filesystem_mode", "open")

    if mode == "open":
        return target

    # Jailed Mode
    if mode == "jailed":
        root_str = settings_manager.settings.get("filesystem_root")
        extra_roots = settings_manager.settings.get("filesystem_extra_roots", [])

        allowed_roots = []
        if root_str:
            try:
                allowed_roots.append(Path(root_str).expanduser().resolve())
            except: pass

        for er in extra_roots:
            try:
                allowed_roots.append(Path(er).expanduser().resolve())
            except: pass

        if not allowed_roots:
            # If jailed but no roots configured, block everything
            raise HTTPException(status_code=500, detail="Filesystem is jailed but no roots are configured.")

        # Check if target is inside any allowed root
        is_allowed = False
        for root in allowed_roots:
            # Check if target starts with root path
            try:
                # Use commonpath to verify containment
                if os.path.commonpath([root, target]) == str(root):
                    is_allowed = True
                    break
            except ValueError:
                # Paths on different drives
                continue

        if not is_allowed:
            raise HTTPException(status_code=403, detail="Access denied: Path is outside filesystem jail")

        return target

    # Fallback (should not happen)
    return target

@app.get("/api/git/repos", dependencies=[Depends(verify_token)])
async def list_git_repos():
    repos = settings_manager.settings.get("git_repos", [])
    result = []

    # Get current mode and roots for filtering
    mode = settings_manager.settings.get("filesystem_mode", "open")
    allowed_roots = []
    if mode == "jailed":
        root_str = settings_manager.settings.get("filesystem_root")
        if root_str: allowed_roots.append(Path(root_str).expanduser().resolve())
        for er in settings_manager.settings.get("filesystem_extra_roots", []):
             allowed_roots.append(Path(er).expanduser().resolve())

    for path in repos:
        # Check access (Filter out repos outside jail in JAILED mode)
        if mode == "jailed":
            try:
                p_obj = Path(path).expanduser().resolve()
                is_allowed = False
                for ar in allowed_roots:
                    try:
                        if os.path.commonpath([ar, p_obj]) == str(ar):
                            is_allowed = True
                            break
                    except: continue
                if not is_allowed:
                    continue
            except:
                continue

        status = "Unknown"
        branch = "Unknown"
        changed = False
        try:
            if git:
                r = git.Repo(path)
                try:
                    branch = r.active_branch.name
                except:
                    branch = "Detached"
                changed = r.is_dirty() or (len(r.untracked_files) > 0)
                status = "Dirty" if changed else "Clean"
        except Exception as e:
            status = f"Error: {str(e)}"

        result.append({
            "path": path,
            "name": os.path.basename(path),
            "status": status,
            "branch": branch,
            "changed": changed
        })
    return result

@app.post("/api/git/repos", dependencies=[Depends(verify_token)])
async def add_git_repo(req: GitRepoRequest):
    # Validate path access
    p_obj = check_path_access(req.path)
    p = str(p_obj)

    if not p_obj.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")

    current = settings_manager.settings.get("git_repos", [])
    if p not in current:
        current.append(p)
        settings_manager.settings["git_repos"] = current
        settings_manager.save_settings()
    return {"success": True}

@app.post("/api/git/repos/remove", dependencies=[Depends(verify_token)])
async def remove_git_repo(req: GitRepoRequest):
    p = req.path
    current = settings_manager.settings.get("git_repos", [])
    if p in current:
        current.remove(p)
        settings_manager.settings["git_repos"] = current
        settings_manager.save_settings()

    if req.delete_files:
        try:
            # Validate safety
            p_obj = check_path_access(p)
            if p_obj.exists() and p_obj.is_dir():
                shutil.rmtree(p_obj)
        except Exception as e:
            # If removing from settings succeeded but file delete failed, we still return success
            # but maybe log it?
            print(f"Failed to delete repo files: {e}")
            pass

    return {"success": True}

@app.post("/api/git/clone", dependencies=[Depends(verify_token)])
async def git_clone(req: GitCloneRequest):
    if not git: raise HTTPException(status_code=501, detail="GitPython not installed")

    # Determine Destination
    mode = settings_manager.settings.get("git_root_mode", "manual")
    root_path = settings_manager.settings.get("git_root_path", "")

    target_path_str = ""

    if mode == "auto":
        if not root_path:
             raise HTTPException(status_code=400, detail="Git Root Path not configured in settings")

        # Determine name
        name = req.name
        if not name:
             # Try to parse from URL
             try:
                 name = req.url.split("/")[-1]
                 if name.endswith(".git"): name = name[:-4]
             except: pass

        if not name:
             raise HTTPException(status_code=400, detail="Could not determine repository name")

        target_path_str = str(Path(root_path).expanduser() / name)
    else:
        if not req.path:
             raise HTTPException(status_code=400, detail="Path is required in Manual mode")
        target_path_str = req.path

    # Validate destination
    p_obj = check_path_access(target_path_str)

    if p_obj.exists() and any(p_obj.iterdir()):
         raise HTTPException(status_code=400, detail="Destination path exists and is not empty")

    try:
        # Prepare Environment for SSH (Skip Host Key Checking)
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no"

        # Prepare URL for HTTPS Auth (if provided)
        clone_url = req.url
        if req.username and req.token:
            # Inject credentials: https://user:token@host/repo.git
            safe_user = quote_plus(req.username)
            safe_token = quote_plus(req.token)
            if clone_url.startswith("https://"):
                clone_url = clone_url.replace("https://", f"https://{safe_user}:{safe_token}@", 1)
            elif clone_url.startswith("http://"):
                clone_url = clone_url.replace("http://", f"http://{safe_user}:{safe_token}@", 1)

        git.Repo.clone_from(clone_url, str(p_obj), env=env)

        # Auto-add to known repos
        current = settings_manager.settings.get("git_repos", [])
        if str(p_obj) not in current:
            current.append(str(p_obj))
            settings_manager.settings["git_repos"] = current
            settings_manager.save_settings()

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/git/status", dependencies=[Depends(verify_token)])
async def get_git_status(path: str):
    check_path_access(path) # Validate Access
    if not git:
         raise HTTPException(status_code=501, detail="GitPython not installed")
    try:
        try:
            r = git.Repo(path)
        except git.exc.InvalidGitRepositoryError:
            return {"error": "Invalid Git Repository", "branch": "Invalid", "files": [], "history": []}
        except git.exc.NoSuchPathError:
            return {"error": "Path not found", "branch": "Missing", "files": [], "history": []}

        diffs = []
        # Staged
        try:
            for item in r.index.diff(None):
                diffs.append({"file": item.a_path, "type": "modified", "staged": False})
        except: pass

        # Diff against HEAD (only if HEAD exists)
        try:
            # Check if HEAD is valid
            _ = r.head.commit
            for item in r.index.diff("HEAD"):
                diffs.append({"file": item.a_path, "type": "modified", "staged": True})
        except ValueError:
            # Empty repo (no commits)
            pass
        except: pass

        # Untracked
        try:
            for f in r.untracked_files:
                diffs.append({"file": f, "type": "untracked", "staged": False})
        except: pass

        history = []
        try:
            for c in list(r.iter_commits(max_count=10)):
                history.append({
                    "hexsha": c.hexsha[:7],
                    "message": c.message.strip(),
                    "author": str(c.author),
                    "time": c.committed_datetime.isoformat()
                })
        except: pass

        branch_name = "Unknown"
        try:
            if r.head.is_detached:
                branch_name = "Detached"
            else:
                branch_name = r.active_branch.name
        except:
            # Likely empty repo without branch yet
            try: branch_name = r.git.branch(show_current=True) or "No Branch"
            except: branch_name = "No Branch"

        return {
            "branch": branch_name,
            "files": diffs,
            "history": history
        }
    except Exception as e:
        # Return structured error instead of 500
        return {"error": str(e), "branch": "Error", "files": [], "history": []}

@app.post("/api/git/commit", dependencies=[Depends(verify_token)])
async def git_commit(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)
        if req.files and len(req.files) > 0:
            r.git.reset()
            for f in req.files:
                r.git.add(f)
        else:
            r.git.add(A=True)
        r.index.commit(req.message or "Update from RemoDash")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/git/diff", dependencies=[Depends(verify_token)])
async def get_git_diff(path: str, file: str):
    check_path_access(path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(path)
        try:
            diff = r.git.diff('HEAD', file)
        except:
            try:
                diff = r.git.diff(file)
                if not diff and (file in r.untracked_files):
                    with open(os.path.join(path, file), 'r', encoding='utf-8', errors='replace') as f:
                        diff = f.read()
            except:
                diff = ""
        return {"diff": diff}
    except Exception as e:
        return {"diff": f"Error: {str(e)}"}

@app.post("/api/git/push", dependencies=[Depends(verify_token)])
async def git_push(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)
        origin = r.remote(name='origin')
        with r.git.custom_environment(GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no'):
            origin.push()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/git/pull", dependencies=[Depends(verify_token)])
async def git_pull(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    if not git: raise HTTPException(status_code=501)
    try:
        r = git.Repo(req.path)
        origin = r.remote(name='origin')
        with r.git.custom_environment(GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no'):
            origin.pull()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SSH Key Management ---

@app.get("/api/git/ssh_key", dependencies=[Depends(verify_token)])
async def get_ssh_key():
    """Checks for SSH key and returns public key + fingerprint."""
    ssh_dir = Path.home() / ".ssh"
    # Prefer Ed25519, fall back to RSA
    key_types = ["id_ed25519", "id_rsa"]
    found_key = None

    for k in key_types:
        if (ssh_dir / k).exists() and (ssh_dir / f"{k}.pub").exists():
            found_key = ssh_dir / k
            break

    if not found_key:
        return {"exists": False}

    try:
        pub_path = found_key.with_suffix(".pub")
        pub_content = pub_path.read_text(encoding="utf-8").strip()

        # Get Fingerprint (Randomart)
        # ssh-keygen -lv -f /path/to/key
        proc = subprocess.run(
            ["ssh-keygen", "-lv", "-f", str(found_key)],
            capture_output=True, text=True
        )
        fingerprint = proc.stdout

        return {
            "exists": True,
            "type": found_key.name,
            "public_key": pub_content,
            "fingerprint": fingerprint
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read key: {str(e)}")

@app.post("/api/git/ssh_key/generate", dependencies=[Depends(verify_token)])
async def generate_ssh_key():
    """Generates a new Ed25519 SSH key pair."""
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    key_path = ssh_dir / "id_ed25519"

    if key_path.exists():
        raise HTTPException(status_code=400, detail="SSH Key already exists")

    try:
        # Generate Ed25519 key, no passphrase (-N ""), comment "remodash@local"
        cmd = [
            "ssh-keygen", "-t", "ed25519",
            "-C", "remodash@local",
            "-f", str(key_path),
            "-N", ""
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            raise Exception(proc.stderr)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/api/sysinfo", dependencies=[Depends(verify_token)])
async def get_sysinfo():
    """Returns static system information."""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "Unknown"

    # CPU Model
    cpu_model = "Unknown"
    if platform.system() == "Windows":
        try:
            cpu_model = subprocess.check_output(["wmic", "cpu", "get", "name"]).decode().split("\n")[1].strip()
        except: pass
    elif platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
        except: pass

    if cpu_model == "Unknown":
        cpu_model = platform.processor()

    # Partitions
    partitions = []
    try:
        for part in psutil.disk_partitions():
            try:
                # Skip inaccessible/dummy partitions
                if "cdrom" in part.opts or part.fstype == "":
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "percent": usage.percent
                })
            except OSError:
                continue
    except: pass

    # Android Detection & Paths
    is_android = "ANDROID_ROOT" in os.environ or "com.termux" in os.environ.get("PREFIX", "")
    standard_paths = []

    # Always include Home
    home_dir = str(Path.home().resolve())

    if is_android:
        standard_paths.append({"name": "Home", "path": home_dir})
        if os.path.exists("/sdcard"):
            standard_paths.append({"name": "Internal Storage", "path": "/sdcard"})

        # Check for Termux storage links
        storage_shared = Path.home() / "storage" / "shared"
        if storage_shared.exists():
             standard_paths.append({"name": "Shared Storage", "path": str(storage_shared.resolve())})

    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "os": f"{platform.system()} {platform.release()}",
        "cpu_model": cpu_model,
        "partitions": partitions,
        "home_dir": home_dir,
        "standard_paths": standard_paths
    }

# --- Terminal Logic ---

class TerminalSession:
    def __init__(self, session_id: str, cwd: Optional[str] = None):
        self.id = session_id
        self.created_at = time.time()
        self.cwd = cwd
        self.cols = 80
        self.rows = 24

        self.process = None
        self.master_fd = None
        self.os_type = platform.system()
        self.loop = asyncio.get_running_loop()

        self.history = [] # List of strings
        self.subscribers: set[WebSocket] = set()
        self.reader_task = None
        self.closed = False

        self._start()

    def _start(self):
        # Validate CWD if provided
        if self.cwd:
            try:
                check_path_access(self.cwd)
            except:
                self.cwd = None # Fallback

        if self.os_type == "Windows":
            self.process = subprocess.Popen(
                ["cmd.exe"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                shell=False,
                cwd=self.cwd
            )
        else:
            # Linux PTY
            self.master_fd, slave_fd = pty.openpty()

            # Use configured shell from settings, or fallback to env/default
            shell = settings_manager.settings.get("terminal_shell")
            if not shell:
                shell = os.environ.get("SHELL", "/bin/bash")

            print(f"[Terminal] Spawning shell: {shell}")

            try:
                self.process = subprocess.Popen(
                    [shell],
                    preexec_fn=os.setsid,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    universal_newlines=False,
                    cwd=self.cwd
                )
            except FileNotFoundError:
                print(f"[Terminal] Error: Shell '{shell}' not found.")
                # Fallback attempts
                fallback = "/bin/sh"
                # Android/Termux fallback
                if os.path.exists("/system/bin/sh"):
                    fallback = "/system/bin/sh"
                elif os.path.exists("/data/data/com.termux/files/usr/bin/sh"):
                    fallback = "/data/data/com.termux/files/usr/bin/sh"

                if shell != fallback and os.path.exists(fallback):
                     print(f"[Terminal] Fallback to {fallback}")
                     try:
                        self.process = subprocess.Popen(
                            [fallback],
                            preexec_fn=os.setsid,
                            stdin=slave_fd,
                            stdout=slave_fd,
                            stderr=slave_fd,
                            universal_newlines=False,
                            cwd=self.cwd
                        )
                     except: pass

            os.close(slave_fd)

        # Start Reader Task
        self.reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        while not self.closed:
            data = await self._read_output()
            if not data:
                # Process likely died
                break

            try:
                text = data.decode(errors="replace")
                self.history.append(text)
                # Optional: Cap history size?
                if len(self.history) > 1000:
                     self.history = self.history[-1000:]

                await self._broadcast(text)
            except Exception as e:
                print(f"Terminal Read Error: {e}")
                break

        self.close()

    async def _broadcast(self, text: str):
        msg = json.dumps({"type": "output", "data": text})
        to_remove = []
        for ws in self.subscribers:
            try:
                await ws.send_text(msg)
            except:
                to_remove.append(ws)
        for ws in to_remove:
            self.subscribers.discard(ws)

    async def _read_output(self):
        if self.os_type == "Windows":
            return await self.loop.run_in_executor(None, self._read_windows)
        else:
            return await self.loop.run_in_executor(None, self._read_linux)

    def _read_windows(self):
        if self.process and self.process.stdout:
            return self.process.stdout.read(1024)
        return b""

    def _read_linux(self):
        if self.master_fd:
            try:
                return os.read(self.master_fd, 1024)
            except OSError:
                return b""
        return b""

    def write_input(self, data: str):
        if self.closed: return
        if self.os_type == "Windows":
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(data.encode())
                    self.process.stdin.flush()
                except: pass
        else:
            if self.master_fd:
                try:
                    os.write(self.master_fd, data.encode())
                except: pass

    def resize(self, cols, rows):
        self.cols = cols
        self.rows = rows
        if self.os_type != "Windows" and self.master_fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except: pass

    def close(self):
        self.closed = True
        if self.process:
            self.process.terminate()
        if self.os_type != "Windows" and self.master_fd:
            try: os.close(self.master_fd)
            except: pass
        # Cancel reader?
        # if self.reader_task: self.reader_task.cancel()

class TerminalManager:
    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}
        self.event_subscribers: set[WebSocket] = set()

    def create_session(self, cwd=None) -> str:
        sid = str(uuid.uuid4())
        session = TerminalSession(sid, cwd)
        self.sessions[sid] = session
        asyncio.create_task(self.broadcast_event("create", {"id": sid, "cwd": cwd}))
        return sid

    def get_session(self, sid: str) -> Optional[TerminalSession]:
        return self.sessions.get(sid)

    def kill_session(self, sid: str):
        if sid in self.sessions:
            s = self.sessions.pop(sid)
            s.close()
            asyncio.create_task(self.broadcast_event("kill", {"id": sid}))

    def list_sessions(self):
        return [{"id": k, "created": v.created_at} for k, v in self.sessions.items()]

    async def broadcast_event(self, event_type: str, data: Any):
        msg = json.dumps({"type": event_type, "data": data})
        to_remove = []
        for ws in self.event_subscribers:
            try:
                await ws.send_text(msg)
            except:
                to_remove.append(ws)
        for ws in to_remove:
            self.event_subscribers.discard(ws)

    async def subscribe_events(self, websocket: WebSocket):
        await websocket.accept()
        self.event_subscribers.add(websocket)
        try:
            # Send initial list
            current = self.list_sessions()
            await websocket.send_text(json.dumps({"type": "init", "data": current}))
            while True:
                await websocket.receive_text() # Keep alive / wait for close
        except:
            pass
        finally:
            self.event_subscribers.discard(websocket)

terminal_manager = TerminalManager()

class CreateTerminalRequest(BaseModel):
    cwd: Optional[str] = None
    command: Optional[str] = None # Ignored for now, or could implement "run and hold"

@app.get("/api/terminals", dependencies=[Depends(verify_token)])
async def list_terminals():
    return terminal_manager.list_sessions()

@app.post("/api/terminals", dependencies=[Depends(verify_token)])
async def create_terminal(req: CreateTerminalRequest):
    sid = terminal_manager.create_session(req.cwd)
    # If command provided, maybe inject it?
    if req.command:
        s = terminal_manager.get_session(sid)
        if s:
             await asyncio.sleep(0.1)
             s.write_input(req.command + "\r\n")
    return {"id": sid}

@app.delete("/api/terminals/{sid}", dependencies=[Depends(verify_token)])
async def kill_terminal(sid: str):
    terminal_manager.kill_session(sid)
    return {"success": True}

@app.websocket("/api/terminal/events")
async def terminal_events_ws(websocket: WebSocket, token: Optional[str] = None, key: Optional[str] = None):
    # Verify Auth (Copy-paste verify logic or factor out)
    if not Path("global_flags/no_auth").exists():
        if key:
            expiry = SESSION_KEYS.get(key)
            if not expiry or time.time() > expiry:
                 await websocket.close(code=4003)
                 return
        else:
            if not REMODASH_TOKEN or not token or token != REMODASH_TOKEN:
                await websocket.close(code=4003)
                return

    await terminal_manager.subscribe_events(websocket)

@app.websocket("/api/terminal/{sid}")
async def terminal_stream_ws(sid: str, websocket: WebSocket, token: Optional[str] = None, key: Optional[str] = None):
    # Verify Auth
    if not Path("global_flags/no_auth").exists():
        if key:
            expiry = SESSION_KEYS.get(key)
            if not expiry or time.time() > expiry:
                 await websocket.close(code=4003)
                 return
        else:
            if not REMODASH_TOKEN or not token or token != REMODASH_TOKEN:
                await websocket.close(code=4003)
                return

    session = terminal_manager.get_session(sid)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.subscribers.add(websocket)

    try:
        # Send history
        for chunk in session.history:
             await websocket.send_text(json.dumps({"type": "output", "data": chunk}))

        # Loop for input
        while True:
            msg_text = await websocket.receive_text()
            msg = json.loads(msg_text)

            if msg["type"] == "input":
                session.write_input(msg["data"])
            elif msg["type"] == "resize":
                session.resize(msg.get("cols", 80), msg.get("rows", 24))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass
    finally:
        session.subscribers.discard(websocket)


# --- File System Endpoints ---

@app.get("/api/files/list", dependencies=[Depends(verify_token)])
async def list_files(path: str, sort_by: str = "name", order: str = "asc"):
    """Lists files in the given directory with sorting."""
    # Ensure path exists and is allowed
    target_path = check_path_access(path)

    if not target_path.is_dir():
         raise HTTPException(status_code=400, detail="Path is not a directory")

    items = []
    try:
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    stat = entry.stat()
                    item_type = "dir" if entry.is_dir() else "file"
                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "type": item_type,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
                except OSError:
                    continue # Skip permission denied etc
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission Denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Correct Single-Pass Sorting
    reverse = (order == "desc")

    # Python sort is stable. We want directories first always.
    # We construct a tuple for key: (is_not_directory, sort_field)
    # is_not_directory: 0 for dir, 1 for file. So dirs come first.

    def sort_key(x):
        is_file = 1 if x["type"] == "file" else 0
        val = x["name"].lower()

        if sort_by == "size":
            val = x["size"]
        elif sort_by == "date":
            val = x["mtime"]
        elif sort_by == "type":
            val = (x["type"], x["name"].lower())

        return (is_file, val)

    items.sort(key=sort_key, reverse=reverse)

    # However, 'reverse' applies to the whole tuple.
    # Usually users want "Dirs First" regardless of sort order.
    # So if we reverse, files might come first.
    # Let's fix that.

    if reverse:
        # If reverse=True, we want Z-A but still Dirs First.
        # So we can't just use one key with reverse=True if we want Dirs First fixed.
        # Strategy: Sort by main criteria, then stable sort by Type.

        # 1. Sort by content (reversed)
        if sort_by == "name":
            items.sort(key=lambda x: x["name"].lower(), reverse=True)
        elif sort_by == "size":
            items.sort(key=lambda x: x["size"], reverse=True)
        elif sort_by == "date":
            items.sort(key=lambda x: x["mtime"], reverse=True)
        elif sort_by == "type":
             items.sort(key=lambda x: (x["type"], x["name"].lower()), reverse=True)

        # 2. Stable sort by Type (Dirs first = 0, Files = 1)
        items.sort(key=lambda x: 0 if x["type"] == "dir" else 1)

    else:
        # Ascending
        if sort_by == "name":
            items.sort(key=lambda x: x["name"].lower())
        elif sort_by == "size":
            items.sort(key=lambda x: x["size"])
        elif sort_by == "date":
            items.sort(key=lambda x: x["mtime"])
        elif sort_by == "type":
             items.sort(key=lambda x: (x["type"], x["name"].lower()))

        # Stable sort by Type
        items.sort(key=lambda x: 0 if x["type"] == "dir" else 1)

    return {"path": str(target_path), "items": items}

@app.get("/api/files/content", dependencies=[Depends(verify_token)])
async def get_file_content(path: str):
    p = check_path_access(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        # Read as text, binary handling might be needed later for other types
        # For now assuming text editing as per requirement
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
             content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/view", dependencies=[Depends(verify_token)])
async def view_file(path: str):
    """Serves a file for viewing (e.g. images)."""
    p = check_path_access(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(p)

@app.post("/api/files/save", dependencies=[Depends(verify_token)])
async def save_file_content(data: FileOpRequest):
    p = check_path_access(data.path)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(data.content if data.content else "")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/create_folder", dependencies=[Depends(verify_token)])
async def create_folder(data: FileOpRequest):
    p = check_path_access(data.path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/delete", dependencies=[Depends(verify_token)])
async def delete_item(data: FileOpRequest):
    p = check_path_access(data.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/rename", dependencies=[Depends(verify_token)])
async def rename_item(data: FileOpRequest):
    if not data.new_path:
        raise HTTPException(status_code=400, detail="new_path required")
    src = check_path_access(data.path)
    dst_input = data.new_path

    try:
        dst = Path(dst_input)
        if not dst.is_absolute() and len(dst.parts) == 1:
             dst = src.parent / dst_input

        # Validate Access for Destination
        check_path_access(str(dst))

        src.rename(dst)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/upload", dependencies=[Depends(verify_token)])
async def upload_files(path: str = Form(...), files: List[UploadFile] = File(...)):
    """Uploads multiple files to the specified path."""
    target_dir = check_path_access(path)
    if not target_dir.is_dir():
         raise HTTPException(status_code=400, detail="Target path is not a directory")

    results = []
    try:
        for file in files:
            # Sanitize filename (prevent path traversal)
            safe_name = os.path.basename(file.filename)
            file_path = target_dir / safe_name

            # Security check: ensure final path is still within jail if applicable
            # (Already covered by check_path_access(path) + normal path join, but good to be safe)

            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            results.append(file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "uploaded": results}

@app.post("/api/files/zip", dependencies=[Depends(verify_token)])
async def download_zip(req: FilesListRequest, background_tasks: BackgroundTasks):
    """Creates a temporary zip of requested files/folders and serves it."""
    if not req.paths:
        raise HTTPException(status_code=400, detail="No paths provided")

    # Validate all paths first
    valid_paths = []
    for p in req.paths:
        try:
            valid_paths.append(check_path_access(p))
        except HTTPException:
            continue # Skip invalid/denied paths

    if not valid_paths:
        raise HTTPException(status_code=400, detail="No valid paths found")

    try:
        # Create temp file
        # We use delete=False so we can serve it, then cleanup in background task
        fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in valid_paths:
                if p.is_file():
                    zf.write(p, arcname=p.name)
                elif p.is_dir():
                    # Recursive add
                    parent_len = len(str(p.parent))
                    for root, dirs, files in os.walk(p):
                        for file in files:
                            abs_path = Path(root) / file
                            # Relative path inside zip
                            rel_path = str(abs_path)[parent_len:].strip(os.sep)
                            zf.write(abs_path, arcname=rel_path)

        background_tasks.add_task(os.unlink, temp_path)
        return FileResponse(temp_path, filename="archive.zip", media_type="application/zip")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Logging Endpoints
@app.get("/api/logs", dependencies=[Depends(verify_token)])
async def stream_logs(request: Request):
    return EventSourceResponse(logger.subscribe(request))

@app.get("/api/logs/sessions", dependencies=[Depends(verify_token)])
async def list_log_sessions():
    return logger.list_sessions()

@app.get("/api/logs/sessions/{session_id}/chunks", dependencies=[Depends(verify_token)])
async def list_log_chunks(session_id: str):
    return logger.list_chunks(session_id)

@app.get("/api/logs/sessions/{session_id}/chunks/{chunk_id}", dependencies=[Depends(verify_token)])
async def get_log_chunk(session_id: str, chunk_id: str):
    return logger.get_chunk_content(session_id, chunk_id)

@app.get("/api/config", dependencies=[Depends(verify_token)])
async def get_config():
    """Gets the full system configuration."""
    if not settings_manager.settings:
        settings_manager.load_or_detect_first_boot()

    # Read Port
    port = 8000
    if os.path.exists("port.txt"):
        try:
            with open("port.txt", "r") as f:
                val = f.read().strip()
                if val.isdigit(): port = int(val)
        except: pass

    return {
        "settings": settings_manager.settings,
        "ui_settings": settings_manager.ui_settings,
        "port": port
    }

@app.post("/api/config", dependencies=[Depends(verify_token)])
async def save_config(data: Dict[str, Any]):
    """Saves the full system configuration."""
    if "settings" in data:
        settings_manager.settings = data["settings"]
    if "ui_settings" in data:
        settings_manager.ui_settings = data["ui_settings"]

    if "port" in data:
        try:
            with open("port.txt", "w") as f:
                f.write(str(data["port"]))
        except Exception as e:
            print(f"Failed to save port: {e}")

    settings_manager.save_settings()
    return {"success": True, "message": "Settings saved."}

# Serve dashboard at root
@app.get("/")
async def read_root():
    return FileResponse('web/dashboard.html')

# Serve Static Files
app.mount("/", StaticFiles(directory="web", html=True), name="static")

if __name__ == "__main__":
    port = 8000
    try:
        if os.path.exists("port.txt"):
            with open("port.txt", "r") as f:
                val = f.read().strip()
                if val.isdigit():
                    port = int(val)
    except Exception as e:
        print(f"Failed to load port.txt: {e}")

    print(f"Starting RemoDash server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
