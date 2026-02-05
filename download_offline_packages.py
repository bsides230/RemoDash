import os
import sys
import subprocess
from pathlib import Path

def print_header(title):
    print("\n" + "=" * 40)
    print(f"       {title}")
    print("=" * 40 + "\n")

def main():
    print_header("OFFLINE PACKAGE DOWNLOADER")

    print("This script will download all Python dependencies to a local folder.")
    print("You can then copy this entire folder to a machine with slow/no internet")
    print("and run the wizard there.")

    # Use script directory as base
    script_dir = Path(__file__).parent.resolve()
    req_file = script_dir / "requirements.txt"
    dest_dir = script_dir / "offline_packages"

    # Platform warning
    print("\n[!] WARNING: Packages are downloaded for the CURRENT platform and Python version.")
    print(f"    Platform: {sys.platform}")
    print(f"    Python: {sys.version.split()[0]}")
    print("    If you intend to install on a different OS or Python version, these packages may not work.")
    print("    For cross-platform downloading, use 'pip download --platform ... --python-version ...' manually.\n")

    if not req_file.exists():
        print(f"Error: requirements.txt not found at {req_file}")
        return

    print(f"Destination: {dest_dir}")
    if not dest_dir.exists():
        print("Creating destination directory...")
        dest_dir.mkdir(parents=True, exist_ok=True)

    confirm = input("Start download? (Y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '']:
        print("Aborted.")
        return

    print("\nDownloading packages... This may take a while.")

    # 1. Download requirements
    cmd = [
        sys.executable, "-m", "pip", "download",
        "-r", str(req_file),
        "-d", str(dest_dir)
    ]

    try:
        subprocess.check_call(cmd)
        print("Successfully downloaded requirements.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading requirements: {e}")
        return

    # 2. Download basic build tools (pip, setuptools, wheel) to be safe
    print("\nDownloading build tools (pip, setuptools, wheel)...")
    cmd_tools = [
        sys.executable, "-m", "pip", "download",
        "pip", "setuptools", "wheel",
        "-d", str(dest_dir)
    ]

    try:
        subprocess.check_call(cmd_tools)
        print("Successfully downloaded build tools.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to download build tools: {e}")
        # Not fatal

    print("\n" + "=" * 40)
    print("DOWNLOAD COMPLETE")
    print("=" * 40)
    print(f"All packages are in: {dest_dir}")
    print("To install offline on another machine, run wizard_linux.py or wizard_windows.py")
    print("and it will automatically detect this folder.")

if __name__ == "__main__":
    main()
