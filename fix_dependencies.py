import sys
import subprocess
import os

def run_pip(args, allow_break=False):
    """
    Runs a pip command.
    If the command fails and allow_break is True, it retries with --break-system-packages.
    """
    cmd = [sys.executable, '-m', 'pip'] + args

    # Base command string for logging
    cmd_str = ' '.join(cmd)
    print(f"Running: {cmd_str}")

    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        if allow_break:
            print(f"Command failed. Retrying with --break-system-packages...")
            cmd.append("--break-system-packages")
            try:
                subprocess.check_call(cmd)
                return True
            except subprocess.CalledProcessError:
                return False
        return False

def main():
    print("=======================================")
    print("   RemoDash Dependency Fixer Script    ")
    print("=======================================")
    print(f"Python Interpreter: {sys.executable}")

    # Step 1: Uninstall pynvml
    print("\n[Step 1] Uninstalling deprecated 'pynvml'...")
    # We attempt to uninstall. If it fails, it might be because it's not installed,
    # or because of permission/environment issues.
    # We allow break-system-packages just in case it's a managed environment.
    if run_pip(['uninstall', '-y', 'pynvml'], allow_break=True):
        print(">> Successfully uninstalled pynvml (or handled cleanup).")
    else:
        print(">> Warning: pynvml uninstall failed. It might not be installed. Proceeding...")

    # Step 2: Force Reinstall nvidia-ml-py
    print("\n[Step 2] Installing/Verifying 'nvidia-ml-py'...")
    # We use --force-reinstall to ensure that if pynvml (old) removed the files,
    # nvidia-ml-py puts them back correctly.
    if run_pip(['install', '--force-reinstall', 'nvidia-ml-py'], allow_break=True):
        print(">> Successfully installed nvidia-ml-py.")
    else:
        print(">> Error: Failed to install nvidia-ml-py.")
        print(">> Please check your internet connection or permissions.")
        print(">> You may need to run this script with 'sudo' on Linux.")

    print("\n=======================================")
    print("Fix complete. You can now start the server.")
    print("=======================================")

if __name__ == "__main__":
    main()
