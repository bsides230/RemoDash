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
