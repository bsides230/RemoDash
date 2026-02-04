import os
import sys
import psutil
import asyncio
import json
import datetime
import shutil
import socket
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
import platform
import subprocess

from fastapi import FastAPI, Request, HTTPException, Header, Depends, Body, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from settings_manager import SettingsManager

try:
    import pynvml
except ImportError:
    pynvml = None

# Platform-specific imports for Terminal
if platform.system() != "Windows":
    import pty
    import termios
    import struct
    import fcntl

# Global reference to the main event loop
main_loop: Optional[asyncio.AbstractEventLoop] = None
REMODASH_TOKEN: Optional[str] = None

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
            yield f"data: {json.dumps({'level':'Success', 'msg': 'Connected to Log Stream', 'ts': datetime.datetime.now().isoformat(), 'source': 'System'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
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

# Global Logger
logger = DiskJournalLogger()
settings_manager = SettingsManager()

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

async def verify_token(x_token: Optional[str] = Header(None, alias="X-Token"), token: Optional[str] = None):
    # Check for No Auth Flag
    if Path("global_flags/no_auth").exists():
        return "NO_AUTH"

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

@app.get("/health")
async def health_check():
    cpu_percent = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('.')

    # Extended System Info

    # CPU Info
    cpu_info = {
        "percent": cpu_percent,
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
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
            "total_gb": disk.total / (1024**3)
        },
        "gpu": gpu_stats,
        "battery": battery_info,
        "os": os_info
    }

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

    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "os": f"{platform.system()} {platform.release()}",
        "cpu_model": cpu_model,
        "partitions": partitions
    }

# --- Terminal Logic ---

class TerminalSession:
    def __init__(self):
        self.process = None
        self.master_fd = None
        self.os_type = platform.system()
        self.loop = asyncio.get_running_loop()

    def start(self, cols=80, rows=24):
        if self.os_type == "Windows":
            self.process = subprocess.Popen(
                ["cmd.exe"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                shell=False
            )
        else:
            # Linux PTY
            self.master_fd, slave_fd = pty.openpty()
            shell = os.environ.get("SHELL", "/bin/bash")

            # Set initial size
            self.resize(cols, rows)

            self.process = subprocess.Popen(
                [shell],
                preexec_fn=os.setsid,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                universal_newlines=False
            )
            os.close(slave_fd)

    def resize(self, cols, rows):
        if self.os_type != "Windows" and self.master_fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except: pass

    async def read_output(self):
        """Reads from the process and returns bytes."""
        if self.os_type == "Windows":
            return await self.loop.run_in_executor(None, self._read_windows)
        else:
            return await self.loop.run_in_executor(None, self._read_linux)

    def _read_windows(self):
        # Read from stdout (blocking)
        # Note: This simple implementation merges stdout and stderr roughly
        # For a better Windows shell, pywinpty is recommended but we are using stdlib
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
        if self.os_type == "Windows":
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(data.encode())
                    self.process.stdin.flush()
                except: pass
        else:
            if self.master_fd:
                os.write(self.master_fd, data.encode())

    def close(self):
        if self.process:
            self.process.terminate()
        if self.os_type != "Windows" and self.master_fd:
            os.close(self.master_fd)


@app.websocket("/api/terminal")
async def terminal_websocket(websocket: WebSocket, token: Optional[str] = None):
    # Verify Auth manually
    if Path("global_flags/no_auth").exists():
        pass # No Auth required
    elif not REMODASH_TOKEN or not token or token != REMODASH_TOKEN:
        await websocket.close(code=4003)
        return

    await websocket.accept()

    session = TerminalSession()
    try:
        session.start()

        # Reader Task
        async def sender():
            while True:
                data = await session.read_output()
                if not data:
                    break
                try:
                    # Send as text (decode with replacement)
                    text = data.decode(errors="replace")
                    await websocket.send_text(json.dumps({"type": "output", "data": text}))
                except:
                    break

        sender_task = asyncio.create_task(sender())

        # Receiver Loop
        while True:
            try:
                msg_text = await websocket.receive_text()
                msg = json.loads(msg_text)

                if msg["type"] == "input":
                    session.write_input(msg["data"])
                elif msg["type"] == "resize":
                    session.resize(msg.get("cols", 80), msg.get("rows", 24))
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Terminal error: {e}")
                break

        sender_task.cancel()

    finally:
        session.close()

# --- File System Endpoints ---

@app.get("/api/files/list", dependencies=[Depends(verify_token)])
async def list_files(path: str, sort_by: str = "name", order: str = "asc"):
    """Lists files in the given directory with sorting."""
    # Ensure path exists
    target_path = Path(path)
    if not target_path.exists():
         raise HTTPException(status_code=404, detail="Path not found")

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

    # Sorting
    reverse = (order == "desc")
    if sort_by == "name":
        items.sort(key=lambda x: x["name"].lower(), reverse=reverse)
    elif sort_by == "size":
        items.sort(key=lambda x: x["size"], reverse=reverse)
    elif sort_by == "date":
        items.sort(key=lambda x: x["mtime"], reverse=reverse)
    elif sort_by == "type":
        items.sort(key=lambda x: (x["type"], x["name"].lower()), reverse=reverse)

    # Always put directories first if sorting by name or type
    if sort_by == "name":
         items.sort(key=lambda x: 0 if x["type"] == "dir" else 1)

    return {"path": str(target_path), "items": items}

@app.get("/api/files/content", dependencies=[Depends(verify_token)])
async def get_file_content(path: str):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        # Read as text, binary handling might be needed later for other types
        # For now assuming text editing as per requirement
        async with asyncio.Lock(): # Simple lock not strictly needed for read but good practice
             with open(p, "r", encoding="utf-8", errors="ignore") as f:
                 content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/view", dependencies=[Depends(verify_token)])
async def view_file(path: str):
    """Serves a file for viewing (e.g. images)."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Security check: Prevent traversing above root if necessary?
    # For this dashboard, we assume full access if authenticated.

    return FileResponse(path)

@app.post("/api/files/save", dependencies=[Depends(verify_token)])
async def save_file_content(data: FileOpRequest):
    p = Path(data.path)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(data.content if data.content else "")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/create_folder", dependencies=[Depends(verify_token)])
async def create_folder(data: FileOpRequest):
    p = Path(data.path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/delete", dependencies=[Depends(verify_token)])
async def delete_item(data: FileOpRequest):
    p = Path(data.path)
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
    src = Path(data.path)
    dst = Path(data.new_path)
    try:
        src.rename(dst)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Logging Endpoints
@app.get("/api/logs", dependencies=[Depends(verify_token)])
async def stream_logs(request: Request):
    return StreamingResponse(logger.subscribe(request), media_type="text/event-stream")

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
    return {
        "settings": settings_manager.settings,
        "ui_settings": settings_manager.ui_settings
    }

@app.post("/api/config", dependencies=[Depends(verify_token)])
async def save_config(data: Dict[str, Any]):
    """Saves the full system configuration."""
    if "settings" in data:
        settings_manager.settings = data["settings"]
    if "ui_settings" in data:
        settings_manager.ui_settings = data["ui_settings"]

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
