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

    print("\nSetup Complete!")
    start_server()

if __name__ == "__main__":
    main()
