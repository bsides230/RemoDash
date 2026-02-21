import os
import sys
import json
import uuid
import shlex
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from settings_manager import SettingsManager

router = APIRouter()
settings_manager = SettingsManager()

# --- Pydantic Models ---
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

# --- Helper: Check Path Access ---
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
            raise HTTPException(status_code=500, detail="Filesystem is jailed but no roots are configured.")

        # Check if target is inside any allowed root
        is_allowed = False
        for root in allowed_roots:
            try:
                if os.path.commonpath([root, target]) == str(root):
                    is_allowed = True
                    break
            except ValueError:
                continue

        if not is_allowed:
            raise HTTPException(status_code=403, detail="Access denied: Path is outside filesystem jail")

        return target

    return target

# --- Shortcuts Manager ---
class ShortcutsManager:
    def __init__(self, data_file="data/shortcuts.json"):
        self.data_file = Path(data_file)
        self.shortcuts = []
        self._load()

    def _load(self):
        if not self.data_file.exists():
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

shortcuts_manager = ShortcutsManager()

# --- Helper Functions ---
def build_command(s: Shortcut) -> str:
    # Construct a shell string command for Terminal injection
    base = s.path
    if " " in base: base = f'"{base}"'

    args = s.args

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

# --- Endpoints ---

@router.get("/")
async def list_shortcuts():
    return shortcuts_manager.list()

@router.post("/")
async def add_shortcut(s: Shortcut):
    try:
        check_path_access(s.path)
        if s.cwd:
            check_path_access(s.cwd)
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {str(e)}")

    return shortcuts_manager.add(s)

@router.put("/{sid}")
async def update_shortcut(sid: str, s: Shortcut):
    try:
        check_path_access(s.path)
        if s.cwd:
            check_path_access(s.cwd)
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {str(e)}")

    data = s.dict()
    data['id'] = sid
    updated = shortcuts_manager.update(sid, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    return updated

@router.delete("/{sid}")
async def delete_shortcut(sid: str):
    shortcuts_manager.delete(sid)
    return {"success": True}

@router.post("/{sid}/run")
async def run_shortcut_endpoint(sid: str, req: ShortcutRunRequest):
    s = shortcuts_manager.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    check_path_access(s.path)
    if s.cwd:
        check_path_access(s.cwd)

    run_mode = req.run_mode or s.run_mode

    if run_mode == "terminal":
        return {"action": "terminal", "cwd": s.cwd, "command": build_command(s)}

    # Output Mode
    cmd_list = build_command_list(s)
    cwd = s.cwd if s.cwd else os.path.dirname(s.path)
    if not cwd: cwd = None

    try:
        proc = subprocess.run(
            cmd_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )

        stdout = proc.stdout[:200000]
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
