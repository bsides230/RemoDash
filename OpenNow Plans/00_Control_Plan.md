# OpenNOW RemoDash Conversion: Overall Control Plan

## Objective
Convert the OpenNOW Electron/React desktop client into a native RemoDash module (`mod_opennow`). This migration replaces the Node.js Main process with a Python/FastAPI backend and replaces the React UI with pure HTML/CSS/JS, removing Electron entirely.

## Migration Phases Checklist

- [ ] **Phase 1: Foundation & Authentication (`01_Phase_1_Auth.md`)**
  - Initialize the `mod_opennow` structure.
  - Implement the NVIDIA OAuth flow in Python.
- [ ] **Phase 2: Data Fetching & Caching (`02_Phase_2_Data.md`)**
  - Port GFN GraphQL queries (Library, Public games) to Python.
  - Implement data caching.
- [ ] **Phase 3: Session Orchestration & Signaling (`03_Phase_3_Session.md`)**
  - Translate CloudMatch logic to Python.
  - Port WebRTC signaling protocol.
- [ ] **Phase 4: Frontend UI & WebRTC Player (`04_Phase_4_Frontend.md`)**
  - Build pure HTML/CSS/JS UI matching RemoDash styling.
  - Implement the in-browser WebRTC player and controls.

## General Instructions
- **Backend:** Code should be written in Python 3 using FastAPI for endpoints. Use `aiohttp` for async HTTP requests instead of `requests` where applicable to avoid blocking the event loop.
- **Frontend:** Code must reside in `modules/mod_opennow/web`. Use vanilla JavaScript (no build steps, no React/Webpack) and standard RemoDash CSS variables for styling.
- **State:** Avoid storing state in global variables. Use appropriate JSON data files or in-memory caches configured at the module level.
- **Module Structure:**
  - `module.json` defining the RemoDash module.
  - `api.py` serving as the backend entrypoint.
  - `web/index.html` as the main UI interface.

---

## Build Notes

### Phase 1 Notes
*To be filled during Phase 1 implementation.*

### Phase 2 Notes
*To be filled during Phase 2 implementation.*

### Phase 3 Notes
*To be filled during Phase 3 implementation.*

### Phase 4 Notes
*To be filled during Phase 4 implementation.*
