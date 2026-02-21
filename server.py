import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

from settings_manager import SettingsManager
from module_manager import ModuleManager
from theme_manager import ThemeManager
from core.api import auth, system, themes, modules
from core.api.auth import verify_token, init_auth

settings_manager = SettingsManager()
module_manager = ModuleManager()
theme_manager = ThemeManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Auth (load token)
    init_auth()
    print("[System] RemoDash Server started.")
    yield

app = FastAPI(title="RemoDash Server", lifespan=lifespan)

# Load Modules
module_manager.load_modules(app)
app.state.theme_manager = theme_manager

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

# --- Mount Core APIs ---
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(system.router, prefix="/api", tags=["System"]) # /api/sysinfo, /api/health (via system)
app.include_router(themes.router, prefix="/api/themes", tags=["Themes"])
app.include_router(modules.router, prefix="/api/modules", tags=["Modules"])

# --- Legacy / Root Endpoints ---

@app.get("/health")
async def health_check_root():
    """Redirects or proxies to /api/health logic."""
    return await system.health_check()

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

@app.get("/api/modules", dependencies=[Depends(verify_token)])
async def list_modules():
    return module_manager.get_installed_modules()

@app.get("/api/fonts", dependencies=[Depends(verify_token)])
async def list_fonts():
    fonts_dir = Path("web/assets/fonts")
    if not fonts_dir.exists():
        return []

    fonts = []
    # extensions: .ttf, .otf, .woff, .woff2
    for ext in ["*.ttf", "*.otf", "*.woff", "*.woff2"]:
        for f in fonts_dir.glob(ext):
            fonts.append(f.name)
    return sorted(fonts)

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
