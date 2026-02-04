# Build Notes

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
