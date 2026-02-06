import os
import sys
import subprocess
import platform
import json
from pathlib import Path

def print_header(title):
    print("\n" + "=" * 40)
    print(f"       {title}")
    print("=" * 40 + "\n")

def install_system_dependencies():
    print("--- Termux System Dependencies ---")
    print("Checking for required system packages...")
    packages = ["build-essential", "clang", "python", "libffi", "openssl", "git", "binutils", "rust"]

    cmd = ["pkg", "install", "-y"] + packages

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("System dependencies installed.")
    except subprocess.CalledProcessError:
        print("Error installing system dependencies.")
        print("Suggestions:")
        print("1. Ensure you have internet access.")
        print("2. Run 'pkg update' to refresh package lists.")
        print("3. If you see mirror errors, run 'termux-change-repo' to select a working mirror.")
        return False
    except FileNotFoundError:
        print("Error: 'pkg' command not found. Are you running this in Termux?")
        return False
    return True

def install_python_dependencies():
    print("\n--- Python Dependencies ---")

    # Check for offline packages
    offline_dir = Path("offline_packages")
    use_offline = False
    if offline_dir.exists() and offline_dir.is_dir():
        print(f"\n[!] Offline packages detected in '{offline_dir}'.")
        off_choice = input("Install from local offline packages? (Y/n): ").strip().lower()
        if off_choice in ['y', 'yes', '']:
            use_offline = True

    # 1. Install Cython (Build dependency)
    print("Installing Cython...")
    cython_cmd = [sys.executable, "-m", "pip", "install", "cython"]
    if use_offline:
         cython_cmd.extend(["--no-index", f"--find-links={offline_dir}"])

    try:
        subprocess.check_call(cython_cmd)
    except subprocess.CalledProcessError:
        print("Failed to install Cython. Installation may fail.")

    # 2. Install requirements_android.txt
    print("Installing dependencies from requirements_android.txt...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements_android.txt"]

    if use_offline:
        pip_cmd.extend(["--no-index", f"--find-links={offline_dir}"])

    try:
        subprocess.check_call(pip_cmd)
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print("Error installing dependencies.")
        return False

    return True

def configure_general():
    print("\n--- General Settings ---")

    # Device Name
    settings_path = Path("settings.json")
    data = {"settings": {}, "ui_settings": {}}

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except: pass

    if "settings" not in data: data["settings"] = {}

    current_name = data["settings"].get("device_name", "")
    print(f"Current Device Name: {current_name if current_name else '(Not Set)'}")

    new_name = input("Enter Device Name (leave empty to keep/skip): ").strip()
    if new_name:
        data["settings"]["device_name"] = new_name
        print(f"Device Name set to: {new_name}")

    # Set default VLC path to empty (Termux usually doesn't have CLI VLC)
    if "vlc_path" not in data["settings"]:
        data["settings"]["vlc_path"] = ""

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def configure_filesystem_mode():
    print("\n--- Filesystem Access Mode ---")
    print("For Termux, 'Jailed Mode' is recommended to restrict access to the internal storage or specific folders.")
    print("\n[1] FULL SYSTEM ACCESS")
    print("    Access everything Termux can access (Internal Storage requires 'termux-setup-storage')")
    print("\n[2] JAILED FILESYSTEM (RECOMMENDED)")
    print("    Restrict RemoDash to a specific directory.")

    choice = input("\nChoose [1/2] (Default: 2): ").strip()
    if choice == "": choice = "2"

    mode = "open"
    root = ""
    extra_roots = []

    if choice == "2":
        mode = "jailed"

        # Default to current directory if not specified
        default_root = str(Path.cwd().resolve())
        print(f"\nDefault Root: {default_root}")

        r = input("Enter Jail Root Directory (Leave empty for default): ").strip()
        if not r:
            root = default_root
        else:
            p = Path(r)
            try:
                if not p.exists():
                    create = input(f"Directory '{r}' does not exist. Create it? (Y/n): ").strip().lower()
                    if create in ['y', 'yes', '']:
                        p.mkdir(parents=True, exist_ok=True)
                    else:
                        print("Using default root.")
                        root = default_root
                if not root: # if not set above
                    if p.is_dir():
                        root = str(p.resolve())
                    else:
                        print("Path is not a directory. Using default.")
                        root = default_root
            except Exception as e:
                print(f"Error validating path: {e}. Using default.")
                root = default_root

        # Extra Roots
        print("\n--- Extra Allowed Roots (Optional) ---")
        print("If you ran 'termux-setup-storage', your internal storage is at '~/storage'.")
        print("You can add that here.")

        while True:
            extra = input("Add an extra root path (e.g. ~/storage/shared) (leave empty to finish): ").strip()
            if not extra:
                break

            p_extra = Path(extra).expanduser()
            try:
                if p_extra.exists() and p_extra.is_dir():
                    extra_roots.append(str(p_extra.resolve()))
                    print(f"Added: {p_extra.resolve()}")
                else:
                    print("Path does not exist or is not a directory. Skipping.")
            except Exception as e:
                print(f"Error: {e}")

    # Save to settings.json
    settings_path = Path("settings.json")
    data = {"settings": {}, "ui_settings": {}}

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except: pass

    if "settings" not in data:
        data["settings"] = {}

    data["settings"]["filesystem_mode"] = mode
    if mode == "jailed":
        data["settings"]["filesystem_root"] = root
        data["settings"]["filesystem_extra_roots"] = extra_roots
        print(f"\nMode set to JAILED. Root: {root}")
        if extra_roots:
            print(f"Extra Roots: {extra_roots}")
    else:
        print("\nMode set to OPEN (Full Access).")

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def configure_auth():
    print("\n--- Authentication ---")
    token_file = Path("admin_token.txt")

    if token_file.exists():
        print("Admin Token: Found.")
        choice = input("Regenerate Admin Token? (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
             run_token_gen()
    else:
        print("Admin Token: Not Found.")
        print("Generating new token...")
        run_token_gen()

def run_token_gen():
    try:
        subprocess.check_call([sys.executable, "token_generator.py"])
    except Exception as e:
        print(f"Error generating token: {e}")

def configure_port():
    print("\n--- Server Port ---")
    current_port = "8050"
    port_file = Path("port.txt")
    if port_file.exists():
        try:
            current_port = port_file.read_text().strip()
        except:
            pass

    print(f"Current Port: {current_port}")
    choice = input(f"Change Port? (current: {current_port}) (y/N): ").strip().lower()
    if choice in ['y', 'yes']:
        new_port = input("Enter new port number: ").strip()
        if new_port.isdigit():
            try:
                port_file.write_text(new_port)
                print(f"Port updated to {new_port}.")
            except Exception as e:
                print(f"Error saving port: {e}")
        else:
            print("Invalid port number. Keeping current port.")
    else:
        print("Keeping current port.")

def start_server():
    print("\n--- Launch ---")
    choice = input("Start RemoDash Server now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nStarting Server...")
        try:
            subprocess.run([sys.executable, "server.py"])
        except KeyboardInterrupt:
            print("\nServer stopped.")
        except Exception as e:
            print(f"Error starting server: {e}")

def main():
    print_header("REMODASH ANDROID (TERMUX) WIZARD")

    if not install_system_dependencies():
        print("System dependency installation failed. Some python packages may fail to build.")
        # Continue anyway? No, probably should stop or ask.
        cont = input("Continue anyway? (y/N): ").strip().lower()
        if cont not in ['y', 'yes']:
            return

    if not install_python_dependencies():
        print("Python dependency installation failed. Aborting.")
        return

    configure_port()
    configure_auth()
    configure_general()
    configure_filesystem_mode()

    print("\nSetup Complete!")
    print("Tip: Run 'termux-wake-lock' to keep the server running in the background.")
    start_server()

if __name__ == "__main__":
    main()
