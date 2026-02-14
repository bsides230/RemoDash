import os
import sys
import time
import json
import asyncio
import struct
import platform
import subprocess
from typing import Optional, Set
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

try:
    if platform.system() != "Windows":
        import pty
        import termios
        import fcntl
except ImportError:
    pass

from settings_manager import SettingsManager
from core.api.auth import SESSION_KEYS, REMODASH_TOKEN
from core.api.filesystem import check_path_access

router = APIRouter()
settings_manager = SettingsManager()

class TerminalSession:
    def __init__(self, session_id: str, cwd: Optional[str] = None):
        self.id = session_id
        self.created_at = time.time()
        self.cwd = cwd
        self.cols = 80
        self.rows = 24

        self.process = None
        self.master_fd = None
        self.os_type = platform.system()
        self.loop = asyncio.get_running_loop()

        self.history = [] # List of strings
        self.subscribers: Set[WebSocket] = set()
        self.reader_task = None
        self.closed = False

        self._start()

    def _start(self):
        # Validate CWD if provided
        if self.cwd:
            try:
                check_path_access(self.cwd)
            except Exception as e:
                print(f"Terminal CWD access denied, using fallback: {e}")
                self.cwd = None # Fallback

        if self.os_type == "Windows":
            self.process = subprocess.Popen(
                ["cmd.exe"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                shell=False,
                cwd=self.cwd
            )
        else:
            # Linux PTY
            self.master_fd, slave_fd = pty.openpty()

            # Use configured shell from settings, or fallback to env/default
            shell = settings_manager.settings.get("terminal_shell")
            if not shell:
                shell = os.environ.get("SHELL", "/bin/bash")

            # Prepare Environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            print(f"[Terminal] Spawning shell: {shell}")

            # Helper to try spawn
            def try_spawn(cmd_list):
                try:
                    return subprocess.Popen(
                        cmd_list,
                        preexec_fn=os.setsid,
                        stdin=slave_fd,
                        stdout=slave_fd,
                        stderr=slave_fd,
                        universal_newlines=False,
                        cwd=self.cwd,
                        env=env
                    )
                except Exception as e:
                    print(f"[Terminal] Spawn failed for {cmd_list}: {e}")
                    return None

            self.process = try_spawn([shell])

            if not self.process:
                # Fallback attempts
                fallbacks = ["/bin/sh", "/system/bin/sh", "/data/data/com.termux/files/usr/bin/sh"]

                for fb in fallbacks:
                     if fb != shell and os.path.exists(fb):
                          print(f"[Terminal] Fallback to {fb}")
                          self.process = try_spawn([fb])
                          if self.process: break

            os.close(slave_fd)

            if not self.process:
                print("[Terminal] Critical: Failed to start any shell.")
                self.history.append("Error: Failed to start shell process. Please check settings.\r\n")
                self.close()
                return

        # Start Reader Task
        self.reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        while not self.closed:
            data = await self._read_output()
            if not data:
                # Process likely died
                break

            try:
                text = data.decode(errors="replace")
                self.history.append(text)
                # Optional: Cap history size?
                if len(self.history) > 1000:
                     self.history = self.history[-1000:]

                await self._broadcast(text)
            except Exception as e:
                print(f"Terminal Read Error: {e}")
                break

        # Append exit message
        if not self.closed:
             msg = "\r\n\x1b[1;31m[Process terminated]\x1b[0m\r\n"
             self.history.append(msg)
             await self._broadcast(msg)

        self.close()

    async def _broadcast(self, text: str):
        msg = json.dumps({"type": "output", "data": text})
        to_remove = []
        for ws in self.subscribers:
            try:
                await ws.send_text(msg)
            except Exception as e:
                print(f"Error sending to WebSocket subscriber: {e}")
                to_remove.append(ws)
        for ws in to_remove:
            self.subscribers.discard(ws)

    async def _read_output(self):
        if self.os_type == "Windows":
            return await self.loop.run_in_executor(None, self._read_windows)
        else:
            return await self.loop.run_in_executor(None, self._read_linux)

    def _read_windows(self):
        if self.process and self.process.stdout:
            return self.process.stdout.read(1024)
        return b""

    def _read_linux(self):
        if self.master_fd:
            try:
                return os.read(self.master_fd, 1024)
            except OSError:
                return b""
        return b""

    def write_input(self, data: str):
        if self.closed: return
        if self.os_type == "Windows":
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(data.encode())
                    self.process.stdin.flush()
                except Exception as e:
                    print(f"Error writing to terminal stdin: {e}")
        else:
            if self.master_fd:
                try:
                    os.write(self.master_fd, data.encode())
                except Exception as e:
                    print(f"Error writing to terminal fd: {e}")

    def resize(self, cols, rows):
        self.cols = cols
        self.rows = rows
        if self.os_type != "Windows" and self.master_fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                print(f"Error resizing terminal: {e}")

    def close(self):
        self.closed = True
        if self.process:
            self.process.terminate()
        if self.os_type != "Windows" and self.master_fd:
            try: os.close(self.master_fd)
            except Exception as e:
                print(f"Error closing terminal fd: {e}")
        # Cancel reader?
        # if self.reader_task: self.reader_task.cancel()

@router.websocket("/{sid}")
async def terminal_stream_ws(sid: str, websocket: WebSocket, token: Optional[str] = None, key: Optional[str] = None, cwd: Optional[str] = None, command: Optional[str] = None):
    # Verify Auth
    if not Path("global_flags/no_auth").exists():
        if key:
            expiry = SESSION_KEYS.get(key)
            if not expiry or time.time() > expiry:
                 await websocket.close(code=4003)
                 return
        else:
            if not REMODASH_TOKEN or not token or token != REMODASH_TOKEN:
                await websocket.close(code=4003)
                return

    await websocket.accept()

    # Create Local Session
    session = TerminalSession(sid, cwd=cwd)
    session.subscribers.add(websocket)

    # Optional Command Injection
    if command:
        # We append newline to execute
        session.write_input(command + "\r\n")

    try:
        # Send history (captures startup messages/errors)
        for chunk in session.history:
             await websocket.send_text(json.dumps({"type": "output", "data": chunk}))

        # Loop for input
        while True:
            msg_text = await websocket.receive_text()
            msg = json.loads(msg_text)

            if msg["type"] == "input":
                session.write_input(msg["data"])
            elif msg["type"] == "resize":
                session.resize(msg.get("cols", 80), msg.get("rows", 24))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Terminal WS Error: {e}")
    finally:
        session.close()
