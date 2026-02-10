import os
import shutil
import zipfile
import tempfile
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from settings_manager import SettingsManager
from core.api.auth import verify_token

router = APIRouter()
settings_manager = SettingsManager()

# --- Pydantic Models ---
class FileOpRequest(BaseModel):
    path: str
    content: Optional[str] = None
    new_path: Optional[str] = None

class FilesListRequest(BaseModel):
    paths: List[str]

# --- Helper ---
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

# --- Endpoints ---

@router.get("/list", dependencies=[Depends(verify_token)])
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

@router.get("/content", dependencies=[Depends(verify_token)])
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

@router.get("/view", dependencies=[Depends(verify_token)])
async def view_file(path: str):
    """Serves a file for viewing (e.g. images)."""
    p = check_path_access(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(p)

@router.post("/save", dependencies=[Depends(verify_token)])
async def save_file_content(data: FileOpRequest):
    p = check_path_access(data.path)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(data.content if data.content else "")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_folder", dependencies=[Depends(verify_token)])
async def create_folder(data: FileOpRequest):
    p = check_path_access(data.path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete", dependencies=[Depends(verify_token)])
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

@router.post("/rename", dependencies=[Depends(verify_token)])
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

@router.post("/upload", dependencies=[Depends(verify_token)])
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

@router.post("/zip", dependencies=[Depends(verify_token)])
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
