#!/usr/bin/env python3

import argparse
import getpass
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, check=True):
    return subprocess.run(cmd, check=check, text=True)


def install_service(service_name, service_text):
    service_path = f"/etc/systemd/system/{service_name}.service"

    subprocess.run(
        ["sudo", "tee", service_path],
        input=service_text,
        text=True,
        check=True
    )


def main():
    parser = argparse.ArgumentParser(description="Install RemoDash as a systemd service.")
    parser.add_argument("--service-name", default="remodash")
    parser.add_argument("--app-dir", default=str(Path.home() / "RemoDash"))
    parser.add_argument("--user", default=getpass.getuser())
    parser.add_argument("--entry-file", default="server.py")

    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser().resolve()
    entry_file = (app_dir / args.entry_file).resolve()
    python_bin = shutil.which("python3")

    if not python_bin:
        print("Error: python3 not found")
        sys.exit(1)

    if not app_dir.exists():
        print(f"Error: app dir not found: {app_dir}")
        sys.exit(1)

    if not entry_file.exists():
        print(f"Error: entry file not found: {entry_file}")
        sys.exit(1)

    print("Installing RemoDash service...")

    service_text = f"""[Unit]
Description=RemoDash Server
After=network.target

[Service]
User={args.user}
WorkingDirectory={app_dir}
ExecStart={python_bin} {entry_file}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

    install_service(args.service_name, service_text)

    run(["sudo", "systemctl", "daemon-reload"])
    run(["sudo", "systemctl", "enable", args.service_name])
    run(["sudo", "systemctl", "restart", args.service_name])

    print("\nService installed and running:\n")
    subprocess.run(["sudo", "systemctl", "status", args.service_name, "--no-pager"])


if __name__ == "__main__":
    main()
