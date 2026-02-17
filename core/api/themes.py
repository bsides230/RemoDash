from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import os
from core.api.auth import verify_token

router = APIRouter()

@router.get("/list", dependencies=[Depends(verify_token)])
async def list_themes(request: Request):
    """List all installed themes."""
    return request.app.state.theme_manager.get_installed_themes()

@router.post("/install", dependencies=[Depends(verify_token)])
async def install_theme(request: Request, file: UploadFile = File(...)):
    """Install a theme from a .tmpk file."""
    if not file.filename.endswith(".tmpk"):
        raise HTTPException(status_code=400, detail="Invalid file format. Must be .tmpk")

    # Save uploaded file temporarily
    temp_path = Path("temp_theme_upload.tmpk")
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Install via manager
        metadata = request.app.state.theme_manager.register_theme(temp_path)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@router.post("/uninstall", dependencies=[Depends(verify_token)])
async def uninstall_theme(request: Request, payload: dict):
    """Uninstall a theme by ID."""
    theme_id = payload.get("id")
    if not theme_id:
        raise HTTPException(status_code=400, detail="Theme ID required")

    try:
        result = request.app.state.theme_manager.unregister_theme(theme_id)
        if result:
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Theme not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{theme_id}/theme.css")
async def get_theme_css(request: Request, theme_id: str):
    """Serve the theme.css file for a specific theme."""
    # Note: No auth dependency here as per instructions (hot-loading in frontend)
    # But usually static assets are public or require token. Dashboard.html has logic to fetch it via link tag.
    # Link tags usually send cookies, but here we use token header in fetch/xhr, but <link> tags?
    # <link> tags do NOT send custom headers.
    # The user instruction said: "This is mounted at /api/themes/{id}/theme.css. The dashboard <link id="theme-css"> href points here."
    # So it must be accessible without token or via cookie?
    # The user said: "No StaticFiles mount needed for themes" and "Serving theme CSS: route handler".
    # And "Do NOT use app.mount("/themes/", StaticFiles(...))".

    # Check if we should verify token?
    # If the user accesses dashboard, they have the token in localStorage.
    # But <link href="..."> makes a GET request. It does not attach the X-Token header.
    # So this endpoint likely needs to be public or use a query param token if strictly secured.
    # Given dashboard.html logic, it just sets href.
    # So we should probably make it public or at least not fail on missing header.
    # The prompt doesn't strictly specify auth for this specific endpoint, but lists it under `core/api/themes.py`.
    # I will leave it public for now to ensure <link> works.

    theme_path = request.app.state.theme_manager.themes_dir / theme_id / "theme.css"

    if not theme_path.exists():
        raise HTTPException(status_code=404, detail="Theme CSS not found")

    return FileResponse(str(theme_path), media_type="text/css")
