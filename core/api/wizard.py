import os
import shutil
import json
import zipfile
import tempfile
import sys
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from pydantic import BaseModel

from module_manager import ModuleManager
from core.api.auth import verify_token

router = APIRouter()
module_manager = ModuleManager()

class WizardUninstallRequest(BaseModel):
    module_id: str

@router.post("/install", dependencies=[Depends(verify_token)])
async def wizard_install(request: Request, file: UploadFile = File(...)):
    try:
        # Save temp file
        fd, temp_path = tempfile.mkstemp(suffix=".mdpk")
        os.close(fd)

        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        if not zipfile.is_zipfile(temp_path):
            os.unlink(temp_path)
            raise HTTPException(status_code=400, detail="Invalid zip file")

        with zipfile.ZipFile(temp_path, 'r') as z:
            if "module.json" not in z.namelist():
                os.unlink(temp_path)
                raise HTTPException(status_code=400, detail="Missing module.json")

            with z.open("module.json") as f:
                meta = json.load(f)

            mod_id = meta.get("id")
            if not mod_id:
                os.unlink(temp_path)
                raise HTTPException(status_code=400, detail="Module ID missing")

            target_dir = Path("modules") / mod_id
            if target_dir.exists():
                shutil.rmtree(target_dir)

            target_dir.mkdir(parents=True, exist_ok=True)
            z.extractall(target_dir)

            # Check requirements
            req_file = target_dir / "requirements.txt"
            if req_file.exists():
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])

            # Register
            module_manager.register_module(
                mod_id=mod_id,
                name=meta.get("name", mod_id),
                icon=meta.get("icon", "extension"),
                version=meta.get("version", "1.0")
            )

            # Load dynamically
            mod_entry = {
                "id": mod_id,
                "name": meta.get("name", mod_id),
                "icon": meta.get("icon", "extension"),
                "version": meta.get("version", "1.0"),
                "enabled": True,
                "path": str(target_dir)
            }
            module_manager.load_single_module(request.app, mod_entry)

        os.unlink(temp_path)
        return {"success": True, "module_id": mod_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/uninstall", dependencies=[Depends(verify_token)])
async def wizard_uninstall(req: WizardUninstallRequest):
    try:
        mod_id = req.module_id

        # 1. Remove files
        mod_dir = Path("modules") / mod_id
        if mod_dir.exists():
            shutil.rmtree(mod_dir)

        # 2. Unregister
        module_manager.unregister_module(mod_id)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
