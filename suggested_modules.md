# Suggested Modules for RemoDash

Based on the current architecture (FastAPI + HTML/JS Frontend), here are several module suggestions that would fit the "Lite/Robust" philosophy:

### 1. **System Monitor (Task Manager)**
*   **Purpose**: View running processes, detailed memory/CPU usage history.
*   **Features**: Kill process, filter by name, resource graphs (Chart.js).
*   **Why**: The current top bar is minimal; a dedicated module allows deep diving into system performance.

### 2. **Network Activity Monitor**
*   **Purpose**: Monitor incoming/outgoing network connections.
*   **Features**: Speed test, active connections list (netstat), bandwidth usage history.

### 3. **Log Viewer (Advanced)**
*   **Purpose**: Specialized viewer for system logs (`/var/log`) or app logs.
*   **Features**: Live tailing (WebSocket), grep/regex search, syntax highlighting for logs.

### 4. **Cron Job Manager**
*   **Purpose**: Schedule tasks.
*   **Features**: UI for editing `crontab`, viewing next run times.

### 5. **Docker / Container Manager**
*   **Purpose**: Manage local Docker containers.
*   **Features**: Start/Stop/Restart containers, view container logs, basic stats.
*   **Why**: Fits well with the "Dashboard" theme for power users.
