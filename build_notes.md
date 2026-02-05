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
  - Added `/api/files/upload` endpoint (POST) supporting `multipart/form-data`.
  - Added `/api/files/zip` endpoint (POST) for creating temporary zip archives of selected files/folders.
  - Added `python-multipart` dependency.
  - Implemented filename sanitization to prevent path traversal attacks during upload.

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
