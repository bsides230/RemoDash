# Build Notes

## Updates - [Date]

### Documentation
- **README:** Rewrote `README.md` to adopt a professional, concise tone.
  - Added "Quick Start" section with OS-specific wizard commands.
  - Explicitly documented Windows UAC limitations regarding admin access.
  - Condensed Admin Token and Configuration sections.
- **License:** Added MIT `LICENSE` file to the repository.

## Updates - [Date]

### Installation
- **Split Wizard:** Refactored `wizard.py` into `wizard_linux.py` and `wizard_windows.py` to provide cleaner, OS-specific installation flows.
  - Windows wizard removes Linux-specific checks (Tailscale, systemd, break-system-packages).
  - Linux wizard retains full server-grade configuration.
  - Updated `wizard.bat` to launch the Windows wizard.

### Documentation & Templates
- **Module Guide:** Created `templates and guides/Module_Dev_Guide.md` and `template_module.html` to assist developers in extending RemoDash.
- **README:** Completely rewrote `README.md` with a visual tour and clear value propositions, replacing the legacy text file.
- **Screenshots:** Added automated screenshots to `assets/` for the documentation.

### User Experience
- **Welcome Tour:** Replaced the simple welcome popup with a multi-step interactive tour explaining the Dock, Modules, and basic usage.

## Updates - [Date]

### New Modules
- **Shortcuts:** Added a user-defined launcher module (`web/modules/Shortcuts.html`) to execute scripts and commands. Backend endpoints at `/api/shortcuts`.
  - Supports `output` mode (capturing stdout/stderr) and `terminal` mode (running in a new Terminal tab).
  - Configurable execution arguments and working directory.

### UI Improvements
- **File Explorer:** Added "Create Shortcut" context action.
  - Selecting a runnable file (`.py`, `.sh`, `.bat`, etc.) shows a "Create Shortcut" button in the toolbar.
  - Automatically prefills shortcut details from the selected file.
- **Terminal:**
  - Added support for opening new tabs with a specific working directory and initial command via `ADD_TAB` message.
  - Fixed UX issue where popped-out tabs were not correctly re-integrated into the main window upon return.
- **Dashboard:**
  - Implemented inter-module communication to allow Shortcuts to trigger Terminal tabs.
  - Fixed `returnChildToParent` logic to handle window ID prefixes correctly.

### Backend
- **Server:**
  - Added `ShortcutsManager` for persisting shortcuts to `data/shortcuts.json`.
  - Updated `TerminalSession` to accept `cwd` and initial `command` injection.
  - Improved argument parsing for shortcuts using `shlex`.
  - Enforced `filesystem_mode` restrictions on shortcut paths.

## Updates - [Date]

### New Modules
- **Git Manager:** Added a GUI for managing local Git repositories (`web/modules/GitManager.html`). backend endpoints at `/api/git/*`.
- **Task Manager:** Added a process viewer and killer (`web/modules/TaskManager.html`). Backend endpoints at `/api/tasks`.
- **Network Monitor:** Added a real-time network traffic graph (`web/modules/NetworkMonitor.html`). Backend endpoints at `/api/network`.
- **Log Viewer:** Added a server log viewer using SSE (`web/modules/LogViewer.html`).
- **Cron Manager:** Added a crontab editor (`web/modules/CronManager.html`). Backend endpoints at `/api/cron`.

### Refactoring & UI Improvements
- **Settings:** Merged the Settings module into the main dashboard UI.
  - Global settings are now accessible via the "Config" icon in the top-right popup.
  - "Server Configuration" (editing `settings.json`) is now a modal window.
  - Removed `web/modules/Settings.html`.
- **Server Status:**
  - Moved detailed drive information to the "System" tab.
  - Removed the legacy disk usage slider.
- **Wizard:** Updated `wizard.py` to handle PEP 668 by prompting for venv creation or allowing `--break-system-packages`.
- **Theming:** Improved theme consistency (Light/Dark mode) across modules, specifically fixing `Terminal.html` dynamic theming.

### Backend
- Updated `requirements.txt` to include `GitPython` and `python-crontab`.
- Expanded `/health` endpoint to include partition information.

## Updates - [Date]

### File Explorer Enhancements
- **Mobile Optimization:**
  - Implemented a responsive layout for mobile devices.
  - Added a collapsible sidebar (drawer) for Favorites/Drives on mobile.
  - Reorganized the toolbar for better reachability on small screens.
  - Improved row selection: Tapping anywhere on a file row now toggles selection.
- **File Transfer:**
  - **Upload:** Added multi-file upload support with a real-time progress bar. (Securely sanitized filenames).
  - **Download:** Added a "Download" button. Single files download directly; multiple files or folders are automatically zipped server-side before download.

### Backend
- **Server:**
  - Added `VLCManager` class to handle VLC process management and communication.
  - Implemented interaction with VLC's Remote Control (RC) interface via TCP socket (port 4212).
  - Added endpoints: `/api/vlc/launch`, `/api/vlc/command`, `/api/vlc/status`, `/api/vlc/kill`.
  - Added automatic `.m3u` playlist generation from folder contents.

### Logging
- **VLC Manager:** Logs VLC launch events and errors to the main system log. Connection errors to the RC interface are handled gracefully and reported to the frontend.

## Updates - Today

### Offline Support
- **Package Downloader:** Created `download_offline_packages.py` to facilitate offline installations.
  - Downloads all dependencies from `requirements.txt` into a local `offline_packages/` directory.
  - Also fetches essential build tools (`pip`, `setuptools`, `wheel`).
- **Wizards:** Updated `wizard_linux.py` and `wizard_windows.py` to auto-detect the `offline_packages` folder.
  - If detected, users are prompted to install dependencies from the local cache instead of PyPI.

## Updates - Today

### New Modules
- **VLC Control:** Added a remote control interface for VLC Media Player (`web/modules/VLCControl.html`).
  - Allows launching VLC on the host machine with a specific folder as a playlist.
  - Automatically configures VLC for Fullscreen, Random, and Loop playback.
  - Provides playback controls (Play, Pause, Stop, Next, Prev) and volume control via the web interface.
  - Displays real-time "Now Playing" status and playback state.

### Backend
- **Server:**
  - Added `VLCManager` class to handle VLC process management and communication.
  - Implemented interaction with VLC's Remote Control (RC) interface via TCP socket (port 4212).
  - Added endpoints: `/api/vlc/launch`, `/api/vlc/command`, `/api/vlc/status`, `/api/vlc/kill`.
  - Added automatic `.m3u` playlist generation from folder contents.

### Logging
- **VLC Manager:** Logs VLC launch events and errors to the main system log. Connection errors to the RC interface are handled gracefully and reported to the frontend.

## Updates - Today

### Persistent Terminal
- **Global Sync:** Terminal sessions are now persistent and synchronized across all connected devices.
  - Opening a terminal tab on one device automatically opens it on all other connected devices via WebSocket events.
  - Output is broadcast to all clients in real-time.
  - History buffer allows new clients to see previous session output upon connection.
- **Backend:**
  - Implemented `GlobalTerminalManager` in `server.py` to manage persistent sessions.
  - Added `WS /api/terminal/events` for real-time session list updates.
  - Added `GET /api/terminals` and `POST /api/terminals` for session management.
- **Frontend:**
  - Updated `Terminal.html` to sync with the server's session list and handle "pop-out" windows correctly without killing the session.

### Utilities
- **Port Killer:** Added `kill_port.py`, a standalone interactive script to list active ports and terminate processes.

## Updates - Today

### Git Manager Improvements
- **Robust Error Handling:** Fixed "500 Internal Server Error" when clicking on empty, broken, or missing repositories. The UI now gracefully handles these states.
- **Delete Files:** Added option to delete repository files from disk when removing a repository.
  - Added "Also delete files from disk" checkbox to the removal confirmation modal in `GitManager.html`.
  - Updated backend to support file deletion via `shutil.rmtree`.

## Updates - 2026-03-24

### Git Manager Deep-Dive + Branch Control Expansion
- Expanded the Git Manager UI (`web/modules/GitManager.html`) with full branch controls in the main toolbar and a dedicated Branch Manager modal.
  - Added local branch selector for quick checkout.
  - Added a Fetch button to update remote refs.
  - Added branch creation workflow (`branch name` + optional `start point`).
  - Added local branch switch/delete actions.
  - Added remote branch checkout flow (track remote branch locally).
- Extended runtime state wiring so branch metadata is loaded with repository status and rendered in both toolbar controls and modal views.

### New Git API Controls (Backend)
- Added branch and remote sync API endpoints in `server.py`:
  - `GET /api/git/branches`
  - `POST /api/git/fetch`
  - `POST /api/git/branches/checkout`
  - `POST /api/git/branches/create`
  - `POST /api/git/branches/delete`
- Added server-side branch state collector and included branch metadata in `/api/git/status` responses so frontend updates are simple and lightweight.
- Added request models for the new branch operations and validation checks for missing branch names / active branch deletion safety.

### Runtime & Button Coverage Testing
- Added `tests/test_git_manager_runtime.py` with end-to-end runtime tests that exercise the backend actions behind Git Manager controls:
  - repo add/list/remove
  - status/diff/commit
  - stash/stash-pop/discard
  - fetch/push/pull
  - branch list/create/checkout/delete
  - remote branch checkout/tracking
  - clone endpoint flow
  - credentials save/load masking
  - SSH key status endpoint
- Added `pytest` to `requirements.txt` to keep testing dependency explicit and reproducible.

### Logging
- Verified that this update preserves existing lightweight logging approach in server runtime (no heavy logging framework added).
- Kept branch/fetch features consistent with current simple-action pattern so existing console and server event logging behavior remains stable.
- Test coverage now provides repeatable runtime verification for Git operations that previously depended on manual button checks.

## Updates - 2026-03-25

### Remo Media Player (VLC Replacement) Foundation
- Added a new server-side `RemoMediaPlayerManager` in `server.py` with a playlist-authoritative state model stored in `data/remo_media_player.json`.
- Implemented mixed-media playlist operations (audio/video/image): create playlist, set active playlist, add item, remove item, and reorder item.
- Added playback control state machine APIs under `/api/remo-player/*` for play/pause/next/prev/repeat/shuffle.
- Added shuffle preparation flow that precomputes playback order and prebuilds the next repeat loop order near the last 20% boundary.
- Added cross-loop boundary guard (by `media_key`) to prevent overlap between previous-loop tail 20% and next-loop head 20% when possible.

### RemoDash Module UI
- Added `web/modules/RemoMediaPlayer.html` as an initial module UI focused on:
  - playlist creation and selection
  - mixed media item insertion
  - mobile-friendly pointer-based drag-and-drop reordering
  - item removal
  - playback transport/repeat/shuffle controls
  - now-playing status display from API state

### Architecture Documentation
- Added `docs/remo_media_player_design.md` to define:
  - layered architecture (data/API/viewer)
  - API contract
  - playlist schema
  - playback state model
  - Linux/Windows viewer strategy
  - phased implementation plan

### Logging
- Kept logging consistent with existing lightweight approach (no heavy framework changes).
- New Remo Player endpoints and state transitions rely on existing server logging surface and error propagation patterns.
- Design notes include explicit follow-up for viewer heartbeat/state telemetry integration so runtime events can be tracked cleanly without architecture bloat.

## Updates - 2026-03-25 (Refactor + Session Prompts)

### Remo Player Refactor (Reduce `server.py` Bloat)
- Moved core Remo media player state machine logic from `server.py` into a dedicated module: `remo_media_player.py`.
- Kept `server.py` focused on API routing/request models and manager wiring, while business logic now lives in the separate script.
- Preserved existing `/api/remo-player/*` endpoint contract to avoid breaking module integration.

### Multi-Phase Prompt Pack
- Added dedicated phase prompt files under `docs/prompts/` so future sessions can execute scoped work by phase:
  - Phase 01 (foundation/contract/data)
  - Phase 02 (fullscreen viewer)
  - Phase 03 (mixed media playback)
  - Phase 04 (shuffle/repeat boundary logic)
  - Phase 05 (hardening/tests/UX)
- Added `docs/prompts/README.md` as an index for the phase prompt set.

### Logging
- Refactor intentionally preserved the existing lightweight logging approach.
- No new heavyweight logging dependencies were introduced.
- Phase prompt files explicitly require logging updates in each phase to keep observability consistent as viewer/playback features expand.

## Updates - 2026-03-26 (Remo Player Phase 01)

### Remo Media Player Endpoint Logging
- Implemented `await logger.emit(...)` for all `RemoPlayer` actions in `server.py` to preserve the lightweight observability standard.
- Actions logged include:
  - Playlist creation and setting active playlists.
  - Adding, deleting, and reordering items within playlists.
  - Core control actions (play, pause, next, prev, toggle repeat, toggle shuffle).
  - Explicit warning logs for invalid control actions and error logs for uncaught exceptions in endpoint execution.

## Updates - 2026-03-27 (Remo Player Phase 02)

### Fullscreen Local Viewer Integration
- Implemented a host-local fullscreen media viewer (`web/viewer.html`) with a minimalist interface containing an invisible close hotspot and an auto-hiding control bar.
- The viewer polls `/api/remo-player/state` every second for synchronization with the server-side playback engine.
- Implemented `viewer_linux.py` and `viewer_windows.py` as abstraction layers to handle launching OS-specific browser instances in kiosk or fullscreen app modes.
- Added a new API endpoint `/api/remo-player/viewer/launch` to dynamically determine the host OS and trigger the local viewer launch securely.
- Preserved existing event-driven architecture, avoiding bloat while keeping the presentation and state decoupled.

### Logging
- Extended the lightweight `DiskJournalLogger` to capture events related to the local viewer launch.
- `RemoPlayer` actions successfully launching the local viewer via `/api/remo-player/viewer/launch` are logged via `await logger.emit(...)`.
- The logging standard continues to be strictly upheld, ensuring full traceability without heavy dependency introduction.

## Updates - Today (Remo Player Phase 03)

### Mixed-Media Playback Engine
- Enhanced `web/viewer.html` to fully support playing mixed media (video, audio, and images) sequentially within the same playlist.
- The viewer now dynamically switches between `<video>`, `<audio>`, and `<img>` elements based on the currently active item's type, pausing and hiding unused elements.
- Image items are now displayed for a configurable duration. The viewer checks `duration_sec` on the item, falling back to `image_default_duration_sec` in the playback state, and automatically advances to the next item when the time expires.
- Added `ended` event listeners to video and audio elements to seamlessly trigger the next media item.
- Play and pause actions are correctly synchronized with the `state.playback.is_playing` flag for video and audio elements.
- Added a floating "Now Playing" UI overlay to reliably update and display metadata (title or source) for the current active item.

### Logging
- Maintained the existing lightweight logging strategy. All state transitions (play, pause, next, prev) triggered by the viewer automatically advancing media are processed by the existing endpoints (`/api/remo-player/control`) and logged using `await logger.emit(...)`.
- Ensured no new heavyweight logging dependencies were introduced during the client-side playback implementation.
