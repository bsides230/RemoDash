# Suggested Modules for RemoDash

Based on the current architecture (FastAPI + HTML/JS Frontend), here are several module suggestions that would fit the "Lite/Robust" philosophy:

### 1. **System Monitor (Task Manager)**
*   **Purpose**: View running processes, detailed memory/CPU usage history.
*   **Features**: Kill process, filter by name, resource graphs (Chart.js).
*   **Why**: The current top bar is minimal; a dedicated module allows deep diving into system performance.

### 2. **Docker / Container Manager**
*   **Purpose**: Manage local Docker containers.
*   **Features**: Start/Stop/Restart containers, view container logs, basic stats.
*   **Why**: Fits well with the "Dashboard" theme for power users.

### 3. **AI Chat / Local LLM Interface**
*   **Purpose**: Chat with a local LLM (Ollama/Llama.cpp).
*   **Features**: Chat history, model selection, system prompt configuration.
*   **Why**: Leverage the "Cognition" aspect of the LYRN philosophy.

### 4. **Network Activity Monitor**
*   **Purpose**: Monitor incoming/outgoing network connections.
*   **Features**: Speed test, active connections list (netstat), bandwidth usage history.

### 5. **Markdown Notes / Wiki**
*   **Purpose**: Personal knowledge base.
*   **Features**: Folder-based markdown file management (extending the File Editor), rendered view, simple search.
*   **Why**: Useful for keeping "Build Notes" or project documentation directly in the dashboard.

### 6. **Log Viewer (Advanced)**
*   **Purpose**: Specialized viewer for system logs (`/var/log`) or app logs.
*   **Features**: Live tailing (WebSocket), grep/regex search, syntax highlighting for logs.

### 7. **Cron Job Manager**
*   **Purpose**: Schedule tasks.
*   **Features**: UI for editing `crontab`, viewing next run times.

### 8. **Media Player**
*   **Purpose**: Play music/videos from the server.
*   **Features**: Playlist support, background audio (if iframe allows), basic video controls.
