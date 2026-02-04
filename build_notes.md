# Build Notes

## Update: Single-Instance Refactor & Enhanced File Management

**Date:** (Current Date)

### Summary
This update refactors the window management system to strictly enforce single instances for main applications while allowing "Child Windows" (pop-outs). It significantly upgrades the File Explorer and Terminal, and introduces a dedicated File Editor and Image Viewer.

### Logging
*   **System**: Logging remains handled by `DiskJournalLogger` in `server.py`.
*   **Debug**: `OPEN_CHILD_WINDOW` and `OPEN_FILE` events are logged to the console in `dashboard.html` for debugging window lifecycle.

### Changes

#### Core System (`server.py`)
-   **API**: Updated `get_sysinfo` to include partition mount options (e.g., `ro` status).
-   **API**: Added `/api/files/view` endpoint to serve binary files (images) with correct MIME types.

#### Dashboard (`web/dashboard.html`)
-   **Window Management**:
    -   Removed Multi-Instance Picker. Main apps (Terminal, Explorer, Editor) are now singletons.
    -   Implemented **Child Window** logic: Tabs can be "popped out" into independent windows.
    -   Implemented **Snap-Back** logic: Minimizing a Child Window returns it to its parent module as a tab.
    -   Updated Message Bus to handle `OPEN_CHILD_WINDOW` and `OPEN_FILE`.

#### Modules
-   **File Explorer (`web/modules/FileExplorer.html`)**:
    -   **Layout**: New Sidebar + Main Content layout.
    -   **Sidebar**: Displays Favorites and Connected Drives (Partitions).
    -   **Tabs**: Internal tab system for browsing multiple paths.
    -   **Selection**: Checkbox-based multi-selection.
    -   **Clipboard**: Added Copy/Cut/Paste functionality (Cut moves files).
    -   **Integration**: Double-clicking opens files in Editor (Code/Text) or Image Viewer (Images).
    -   **Pop-Out**: Tabs can be popped out into new windows.

-   **Terminal (`web/modules/Terminal.html`)**:
    -   **Pop-Out**: Added button to pop current terminal tabs out into new windows.
    -   **Snap-Back**: Listening for `CHILD_RETURNING` to restore minimized pop-outs as tabs.

-   **File Editor (`web/modules/FileEditor.html`)**:
    -   **New Module**: Integrated `CodeMirror 5` for syntax highlighting.
    -   **Features**: Tabbed editing, Save functionality, Dark/Light theme support.

-   **Image Viewer (`web/modules/ImageViewer.html`)**:
    -   **New Module**: Lightweight popup widget for viewing images.

#### Documentation
-   Added `suggested_modules.md`.

## Update: Multi-Instance Modules and System Tools

**Date:** (Previous Update)

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
