import json
import os
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel

# Try to import from RemoDash server context
try:
    from server import verify_token
except ImportError:
    # Dummy for standalone tests
    def verify_token():
        return True

router = APIRouter()

SERVICES_FILE = Path("data/services.json")

class ServiceItem(BaseModel):
    name: str

class ServiceAction(BaseModel):
    name: str
    action: str

def load_services() -> List[str]:
    if not SERVICES_FILE.exists():
        # Default services
        default_services = ["remodash.service"]
        save_services(default_services)
        return default_services
    try:
        with open(SERVICES_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_services(services: List[str]):
    SERVICES_FILE.parent.mkdir(exist_ok=True)
    with open(SERVICES_FILE, "w") as f:
        json.dump(services, f, indent=4)

@router.get("/api/services/list", dependencies=[Depends(verify_token)])
async def list_services():
    services = load_services()
    results = []
    for s in services:
        status = "unknown"
        if os.name == "posix":
            # Check systemd status
            try:
                res = subprocess.run(["systemctl", "is-active", s], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                status = res.stdout.strip()
            except:
                pass
        results.append({"name": s, "status": status})
    return results

@router.post("/api/services/add", dependencies=[Depends(verify_token)])
async def add_service(item: ServiceItem):
    services = load_services()
    if item.name not in services:
        services.append(item.name)
        save_services(services)
    return {"success": True}

@router.post("/api/services/remove", dependencies=[Depends(verify_token)])
async def remove_service(item: ServiceItem):
    services = load_services()
    if item.name in services:
        services.remove(item.name)
        save_services(services)
    return {"success": True}

@router.post("/api/services/action", dependencies=[Depends(verify_token)])
async def perform_action(req: ServiceAction):
    allowed_actions = ["start", "stop", "restart", "reload"]
    if req.action not in allowed_actions:
        raise HTTPException(status_code=400, detail="Invalid action")

    if os.name != "posix":
        raise HTTPException(status_code=501, detail="Only supported on Linux")

    try:
        # e.g., sudo systemctl restart remodash.service
        res = subprocess.run(["sudo", "systemctl", req.action, req.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise Exception(res.stderr.strip() or "Failed to perform action")
        return {"success": True, "message": f"Successfully {req.action}ed {req.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
