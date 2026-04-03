# RemoDash

A visual control plane for headless machines (servers, SBCs, home labs). Turns a headless machine into a server that serves a browser-based GUI, exposing system capabilities such as file management, terminal access, and system monitoring.

## Tech Stack

- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Frontend**: HTML5, CSS3, vanilla JavaScript
- **Key Libraries**: psutil, xterm.js, GitPython, websockets, sse-starlette

## Project Structure

- `server.py` — Main FastAPI application (all routes and business logic)
- `settings_manager.py` — Settings persistence
- `module_manager.py` — Plugin/module system
- `remo_media_player.py` — Media player functionality
- `hardware_manager.py` — Hardware detection and monitoring
- `web/` — Frontend assets (HTML, CSS, JS)
  - `dashboard.html` — Main dashboard UI
  - `viewer.html` — Viewer UI
  - `modules/` — Dashboard widgets (Terminal, FileExplorer, etc.)
- `modules/` — Backend-integrated modules
- `data/` — Persistent configuration (shortcuts.json, etc.)
- `port.txt` — Server port configuration (set to 5000)

## Configuration

- Port: 5000 (set in `port.txt`)
- Host: `0.0.0.0` (all interfaces)
- Auth: Optional admin token authentication via `admin_token.txt`

## Running

```bash
python server.py
```

The workflow "Start application" runs `python server.py` and serves on port 5000.

## Deployment

Configured for autoscale deployment with `python server.py`.
