import os
import sys
import subprocess
import platform
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
    break_system = False

    if not in_venv:
        print("You are not running in a virtual environment.")
        v_choice = input("Would you like to create/use a local virtual environment (venv)? (Y/n): ").strip().lower()
        if v_choice in ['y', 'yes', '']:
            use_venv = True
        else:
            # If they decline venv, ask about break-system-packages (mostly for Linux/PEP 668)
            bs_choice = input("Install globally? This may require '--break-system-packages' on some systems. Proceed? (Y/n): ").strip().lower()
            if bs_choice in ['y', 'yes', '']:
                break_system = True
            else:
                print("Aborting dependency installation.")
                return False

    choice = input("Install/Update Dependencies now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nInstalling dependencies...")

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
            if platform.system() == "Windows":
                pip_exe = venv_path / "Scripts" / "pip.exe"
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                pip_exe = venv_path / "bin" / "pip"
                python_exe = venv_path / "bin" / "python"

            if pip_exe.exists():
                pip_cmd = [str(pip_exe), "install", "-r", "requirements.txt"]
                # Update sys.executable for the rest of the script/launch
                global venv_python
                venv_python = str(python_exe)
            else:
                print("Error: venv created but pip not found.")
                return False

        elif break_system:
            pip_cmd.append("--break-system-packages")

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

def configure_tailscale():
    print("\n--- Tailscale (Remote Access) ---")
    if platform.system() != "Linux":
        print("Note: Automated Tailscale installation is only supported on Linux.")
        return

    choice = input("Install Tailscale? (y/N): ").strip().lower()
    if choice in ['y', 'yes']:
        print("Installing Tailscale...")
        try:
            # Using the official install script for better compatibility
            subprocess.check_call("curl -fsSL https://tailscale.com/install.sh | sh", shell=True)
            print("Tailscale installed. You may need to run 'sudo tailscale up' to connect.")
        except subprocess.CalledProcessError:
             print("Tailscale installation failed. Please install manually.")
    else:
        print("Skipping Tailscale.")

def configure_service():
    print("\n--- Service Installer ---")
    choice = input("Install RemoDash as a system service/startup task? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("Skipping service installation.")
        return

    if platform.system() == "Windows":
        # Windows: Startup Folder Shortcut via VBS
        try:
            startup_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
            if not os.path.exists(startup_folder):
                print(f"Error: Startup folder not found at {startup_folder}")
                return

            # Ensure we have a .bat file to launch
            bat_path = Path("start_remodash.bat").resolve()
            with open(bat_path, "w") as f:
                f.write(f'@echo off\ncd /d "{os.getcwd()}"\n"{venv_python}" server.py\npause')

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

    elif platform.system() == "Linux":
        # Linux: systemd service
        if os.geteuid() != 0:
            print("Error: You must run this script with sudo to install a systemd service.")
            return

        try:
            # Determine user
            user = os.environ.get('SUDO_USER') or os.environ.get('USER')
            if not user or user == 'root':
                user = input("Enter username to run service as: ").strip()

            cwd = str(Path.cwd().resolve())
            python_path = str(Path(venv_python).resolve())
            server_script = str(Path("server.py").resolve())

            service_content = f"""[Unit]
Description=RemoDash Server
After=network.target

[Service]
User={user}
WorkingDirectory={cwd}
ExecStart={python_path} {server_script}
Restart=always

[Install]
WantedBy=multi-user.target
"""
            service_path = "/etc/systemd/system/remodash.service"
            with open(service_path, "w") as f:
                f.write(service_content)

            print(f"Created {service_path}")

            print("Reloading systemd...")
            subprocess.check_call(["systemctl", "daemon-reload"])

            print("Enabling service...")
            subprocess.check_call(["systemctl", "enable", "remodash"])

            choice = input("Start service now? (Y/n): ").strip().lower()
            if choice in ['y', 'yes', '']:
                subprocess.check_call(["systemctl", "start", "remodash"])
                print("Service started.")

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
    print_header("REMODASH SETUP WIZARD")

    if not install_dependencies():
        print("Dependency installation failed. Aborting.")
        input("Press Enter to exit...")
        return

    configure_port()
    configure_auth()
    configure_tailscale()
    configure_service()

    print("\nSetup Complete!")
    start_server()

if __name__ == "__main__":
    main()
