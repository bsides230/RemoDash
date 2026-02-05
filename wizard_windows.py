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

def install_dependencies():
    print("--- Dependencies ---")

    # Check if we are already in a venv
    in_venv = (sys.prefix != sys.base_prefix)

    use_venv = False

    if not in_venv:
        print("You are not running in a virtual environment.")
        v_choice = input("Would you like to create/use a local virtual environment (venv)? (Y/n): ").strip().lower()
        if v_choice in ['y', 'yes', '']:
            use_venv = True

    choice = input("Install/Update Dependencies now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nInstalling dependencies...")

        # Check for offline packages
        offline_dir = Path("offline_packages")
        use_offline = False
        if offline_dir.exists() and offline_dir.is_dir():
            print(f"\n[!] Offline packages detected in '{offline_dir}'.")
            off_choice = input("Install from local offline packages? (Y/n): ").strip().lower()
            if off_choice in ['y', 'yes', '']:
                use_offline = True

        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]

        if use_venv:
            # Create venv if not exists
            venv_path = Path("venv")
            if not venv_path.exists():
                print("Creating virtual environment...")
                try:
                    subprocess.check_call([sys.executable, "-m", "venv", "venv"])
                except subprocess.CalledProcessError:
                    print("Failed to create venv.")
                    return False

            # Adjust pip command to use venv
            pip_exe = venv_path / "Scripts" / "pip.exe"
            python_exe = venv_path / "Scripts" / "python.exe"

            if pip_exe.exists():
                pip_cmd = [str(pip_exe), "install", "-r", "requirements.txt"]
                # Update sys.executable for the rest of the script/launch
                global venv_python
                venv_python = str(python_exe)
            else:
                print("Error: venv created but pip not found.")
                return False

        if use_offline:
            pip_cmd.extend(["--no-index", f"--find-links={offline_dir}"])

        try:
            subprocess.check_call(pip_cmd)
            print("Dependencies installed successfully.")
        except subprocess.CalledProcessError:
            print("Error installing dependencies.")
            return False
    else:
        print("Skipping dependencies.")
    return True

venv_python = sys.executable

def configure_filesystem_mode():
    print("\n--- Filesystem Access Mode ---")
    print("[1] FULL SYSTEM ACCESS (DEFAULT)")
    print("    RemoDash can read, write, delete, and execute files")
    print("    anywhere on this machine.")
    print("\n[2] JAILED FILESYSTEM (RESTRICTIVE MODE)")
    print("    RemoDash is locked to one directory and cannot")
    print("    access anything outside it.")
    print("    This may break some modules and workflows.")

    choice = input("\nChoose [1/2]: ").strip()

    mode = "open"
    root = ""
    extra_roots = []

    if choice == "2":
        mode = "jailed"
        while True:
            r = input("\nEnter Jail Root Directory: ").strip()
            if not r:
                print("Root directory is required for Jailed mode.")
                continue

            p = Path(r)
            try:
                if not p.exists():
                    create = input(f"Directory '{r}' does not exist. Create it? (Y/n): ").strip().lower()
                    if create in ['y', 'yes', '']:
                        p.mkdir(parents=True, exist_ok=True)
                    else:
                        print("Please enter a valid directory.")
                        continue
                if not p.is_dir():
                    print("Path exists but is not a directory.")
                    continue
                root = str(p.resolve())
                break
            except Exception as e:
                print(f"Error validating path: {e}")

        # Extra Roots
        print("\n--- Extra Allowed Roots (Optional) ---")
        print("You can allow access to additional paths (e.g., external drives).")
        print("Examples: D:\\, E:\\")

        while True:
            extra = input("Add an extra root path (leave empty to finish): ").strip()
            if not extra:
                break

            p_extra = Path(extra)
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

def configure_service():
    print("\n--- Service Installer ---")
    choice = input("Install RemoDash as a startup task? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("Skipping service installation.")
        return

    # Windows: Startup Folder Shortcut via VBS
    try:
        startup_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
        if not os.path.exists(startup_folder):
            print(f"Error: Startup folder not found at {startup_folder}")
            return

        # Ensure we have a .bat file to launch
        bat_path = Path("start_remodash.bat").resolve()
        with open(bat_path, "w") as f:
            f.write(f'@echo off\ncd /d "{os.getcwd()}"\n"{venv_python}" server.py\n')

        # Create VBS script in startup to launch invisible
        vbs_path = os.path.join(startup_folder, "RemoDash.vbs")
        with open(vbs_path, "w") as f:
            f.write('Set WshShell = CreateObject("WScript.Shell")\n')
            f.write(f'WshShell.Run chr(34) & "{bat_path}" & chr(34), 0\n')
            f.write('Set WshShell = Nothing\n')

        print(f"Created startup entry: {vbs_path}")
        print("RemoDash will start automatically on login.")

    except Exception as e:
        print(f"Error installing service: {e}")

def configure_port():
    print("\n--- Server Port ---")
    current_port = "8240"
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
        choice = input("Generate Admin Token? (Y/n): ").strip().lower()
        if choice in ['y', 'yes', '']:
            run_token_gen()
        else:
            print("WARNING: No admin token generated. You may not be able to log in unless No-Auth mode is enabled.")

def run_token_gen():
    try:
        subprocess.check_call([venv_python, "token_generator.py"])
    except Exception as e:
        print(f"Error generating token: {e}")

def start_server():
    print("\n--- Launch ---")
    choice = input("Start RemoDash Server now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nStarting Server...")
        try:
            # Use the python executable determined during dependency install (venv or system)
            subprocess.run([venv_python, "server.py"])
        except KeyboardInterrupt:
            print("\nServer stopped.")
        except Exception as e:
            print(f"Error starting server: {e}")

def main():
    print_header("REMODASH WINDOWS WIZARD")

    if platform.system() != "Windows":
        print("Warning: This wizard is designed for Windows.")

    if not install_dependencies():
        print("Dependency installation failed. Aborting.")
        input("Press Enter to exit...")
        return

    configure_port()
    configure_auth()
    configure_filesystem_mode()
    # Tailscale skipped for Windows
    configure_service()

    print("\nSetup Complete!")
    start_server()

if __name__ == "__main__":
    main()
