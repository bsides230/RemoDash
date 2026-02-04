# Build Notes

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
