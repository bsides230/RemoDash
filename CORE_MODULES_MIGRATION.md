# Core Modules Migration List

This file tracks the migration of "core" modules (HTML files in `web/modules`) into standalone `.mdpk` packages.

## Migration Process

1.  Identify the module from the list below.
2.  Create a new folder structure for the module:
    -   `module.json`: Define ID, name, icon, and version.
    -   `api.py`: Extract backend logic (if any) from `server.py` and create an `APIRouter`.
    -   `web/index.html`: Move the HTML file from `web/modules/` to this location.
3.  Update the `web/index.html` to point to the new API endpoints (`/api/modules/{module_id}/...`).
4.  Zip the folder contents into a `.mdpk` file.
5.  Install the `.mdpk` file using the module wizard or manager.

## Core Modules List

-   [ ] **CronManager** (`CronManager.html`)
-   [ ] **FileEditor** (`FileEditor.html`)
-   [ ] **FileExplorer** (`FileExplorer.html`)
-   [ ] **GitManager** (`GitManager.html`)
-   [ ] **HardwareReport** (`HardwareReport.html`)
-   [ ] **ImageViewer** (`ImageViewer.html`)
-   [ ] **LogViewer** (`LogViewer.html`)
-   [ ] **MediaViewer** (`MediaViewer.html`)
-   [ ] **NetworkMonitor** (`NetworkMonitor.html`)
-   [ ] **ServerStatus** (`ServerStatus.html`)
-   [x] **Shortcuts** (`Shortcuts.html`) -> `mod_shortcuts.mdpk` (Created)
-   [ ] **TaskManager** (`TaskManager.html`)
-   [ ] **Terminal** (`Terminal.html`)
-   [x] **VLCControl** (`VLCControl.html`) -> `mod_vlc.mdpk` (Created)

## Notes

-   The goal is to decouple these modules from `server.py` to make the core server lighter and more maintainable.
-   Once migrated, the original HTML files and backend logic in `server.py` can be removed.
