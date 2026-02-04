import os
import sys
import subprocess
from pathlib import Path

def print_header(title):
    print("\n" + "=" * 40)
    print(f"       {title}")
    print("=" * 40 + "\n")

def install_dependencies():
    print("--- Dependencies ---")
    choice = input("Install/Update Dependencies? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nInstalling dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("Dependencies installed successfully.")
        except subprocess.CalledProcessError:
            print("Error installing dependencies.")
            return False
    else:
        print("Skipping dependencies.")
    return True

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
        subprocess.check_call([sys.executable, "token_generator.py"])
    except Exception as e:
        print(f"Error generating token: {e}")

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
    print_header("REMODASH SETUP WIZARD")

    if not install_dependencies():
        print("Dependency installation failed. Aborting.")
        input("Press Enter to exit...")
        return

    configure_port()
    configure_auth()

    print("\nSetup Complete!")
    start_server()

if __name__ == "__main__":
    main()
