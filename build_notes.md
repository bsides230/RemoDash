# Build Notes

## Update: Multi-Instance Modules and System Tools

**Date:** (Current Date)

### Summary
This update introduces a full multi-instance windowing system, a robust File Explorer, and a Terminal with WebSocket support.

### Changes

#### Core System
- **API**: Added `/api/sysinfo` for detailed system information.
- **File System**: Added full CRUD endpoints (`/api/files/*`) for filesystem management.
- **Terminal**: Added `/api/terminal` WebSocket endpoint supporting `pty` (Linux) and `subprocess` (Windows).
- **Dependencies**: Added `websockets` to `requirements.txt`.

#### Frontend
- **Dashboard (`web/dashboard.html`)**:
    -   Implemented multi-instance support (multiple windows per app).
    -   Added "Instance Picker" UI for managing multiple open windows.
    -   Updated module registry (System Status, File Explorer, Terminal, Settings).
- **File Explorer (`web/modules/FileExplorer.html`)**:
    -   New module for browsing, editing, renaming, and deleting files.
- **Terminal (`web/modules/Terminal.html`)**:
    -   New module using `xterm.js`.
    -   Supports internal tabs and resizing.
- **System Status (`web/modules/ServerStatus.html`)**:
    -   Added "Info" tab displaying Hostname, IP, OS, CPU Model, and Drive partitions.

#### Deleted Files
- `web/modules/LogViewer.html` (Replaced by Terminal)

## Update: Cleanup and Tailscale Integration

**Date:** (Previous Update)

### Summary
This update transitions the repository from a generic system dashboard.

### Changes
(Legacy notes preserved)
