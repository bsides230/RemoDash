import os
import subprocess
import platform

def launch_viewer(url: str):
    """
    Launches a local fullscreen viewer window.
    Linux preferred: Chromium/Chrome in kiosk mode.
    Fallback: Firefox.
    """
    browsers = [
        ["chromium", "--kiosk", "--app=" + url],
        ["chromium-browser", "--kiosk", "--app=" + url],
        ["google-chrome", "--kiosk", "--app=" + url],
        ["firefox", "--kiosk", url]
    ]

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    for cmd in browsers:
        try:
            # Try to run the command in the background
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            return True
        except FileNotFoundError:
            continue

    print("[Viewer] Error: No suitable browser found for kiosk mode on Linux.")
    return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        launch_viewer(sys.argv[1])
    else:
        print("Usage: python viewer_linux.py <url>")
