from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from module_manager import ModuleManager
from core.api.auth import verify_token

router = APIRouter()
module_manager = ModuleManager()

@router.post("/{module_id}/check_requirements", dependencies=[Depends(verify_token)])
async def check_requirements(module_id: str):
    """Checks if the module's requirements are installed."""
    missing = module_manager.check_requirements(module_id)
    return {"missing": missing}
