import secrets
import time
from typing import Optional, Dict
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Depends

router = APIRouter()

# Global Auth State
REMODASH_TOKEN: Optional[str] = None
SESSION_KEYS: Dict[str, float] = {}

def load_admin_token():
    global REMODASH_TOKEN
    token_file = Path("admin_token.txt")
    if token_file.exists():
        try:
            REMODASH_TOKEN = token_file.read_text(encoding="utf-8").strip()
            print("[Auth] Loaded admin token from admin_token.txt")
        except Exception as e:
            print(f"[Auth] Failed to read admin_token.txt: {e}")

# Alias for external use
init_auth = load_admin_token

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

@router.get("/status")
async def get_auth_status():
    if Path("global_flags/no_auth").exists():
        return {"required": False}
    return {"required": True}

@router.post("/verify_token")
async def verify_token_endpoint(auth: str = Depends(verify_token)):
    return {"status": "valid"}

@router.post("/session/terminal")
async def create_session_token(auth: str = Depends(verify_token)):
    """Generates a short-lived session token."""
    key = secrets.token_urlsafe(32)
    # Valid for 60 seconds
    SESSION_KEYS[key] = time.time() + 60

    # Lazy cleanup of expired keys
    expired = [k for k, exp in SESSION_KEYS.items() if time.time() > exp]
    for k in expired:
        del SESSION_KEYS[k]

    return {"key": key}
