import os
import subprocess

def launch_viewer(url: str):
    """
    Launches a local fullscreen viewer window.
    Windows preferred: Edge or Chrome in app/fullscreen mode.
    """
    browsers = [
        ["msedge.exe", "--kiosk", url, "--edge-kiosk-type=fullscreen"],
        ["chrome.exe", "--kiosk", "--app=" + url],
        ["firefox.exe", "-kiosk", url]
    ]

    for cmd in browsers:
        try:
            # We use CREATE_NO_WINDOW to hide the console if launched from pythonw
            flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

            process = subprocess.Popen(
                cmd,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except FileNotFoundError:
            continue

    # Try generic shell execution if path isn't mapped
    try:
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "msedge", "--kiosk", url, "--edge-kiosk-type=fullscreen"],
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except:
        pass

    print("[Viewer] Error: No suitable browser found for kiosk mode on Windows.")
    return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        launch_viewer(sys.argv[1])
    else:
        print("Usage: python viewer_windows.py <url>")
