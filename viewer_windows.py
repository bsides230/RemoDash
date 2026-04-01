import os
import subprocess

def launch_viewer(url: str):
    """
    Launches a local fullscreen viewer window.
    Windows preferred: Edge or Chrome in app/fullscreen mode.
    """
    # Add common installation paths to increase the chance of finding the browser
    # even if it's not in the system PATH.
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData", "C:\\Users\\Default\\AppData\\Local")

    chrome_paths = [
        "chrome.exe",
        os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe")
    ]

    edge_paths = [
        "msedge.exe",
        os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe")
    ]

    firefox_paths = [
        "firefox.exe",
        os.path.join(program_files, "Mozilla Firefox\\firefox.exe"),
        os.path.join(program_files_x86, "Mozilla Firefox\\firefox.exe")
    ]

    browsers = []

    # Prioritize Chrome
    for path in chrome_paths:
        browsers.append([path, "--kiosk", "--app=" + url])

    # Fallback to Edge
    for path in edge_paths:
        browsers.append([path, "--kiosk", url, "--edge-kiosk-type=fullscreen"])

    # Fallback to Firefox
    for path in firefox_paths:
        browsers.append([path, "-kiosk", url])

    for cmd in browsers:
        try:
            # We use CREATE_NO_WINDOW to hide the console if launched from pythonw
            flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

            # For absolute paths, check if the file exists before trying to run it
            if os.path.isabs(cmd[0]) and not os.path.exists(cmd[0]):
                continue

            process = subprocess.Popen(
                cmd,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[Viewer] Warning: Failed to launch {cmd[0]}: {e}")
            continue

    # Try generic shell execution if path isn't mapped
    try:
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        # Try chrome first via start
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "chrome", "--kiosk", "--app=" + url],
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except:
            # Fallback to edge via start
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
