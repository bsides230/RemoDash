#!/usr/bin/env python3
import os
import sys
import json
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from module_manager import ModuleManager

# Initialize Module Manager
manager = ModuleManager()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 60)
    print("      RemoDash Module Manager      ")
    print("=" * 60)
    print()

def list_modules():
    clear_screen()
    print_header()
    modules = manager.get_installed_modules()

    if not modules:
        print("No modules installed.")
    else:
        print(f"{'ID':<20} {'Name':<20} {'Version':<10} {'Status'}")
        print("-" * 60)
        for m in modules:
            status = "Enabled" if m.get("enabled", True) else "Disabled"
            print(f"{m['id']:<20} {m['name']:<20} {m.get('version', '1.0'):<10} {status}")

    input("\nPress Enter to return to menu...")

def install_module():
    clear_screen()
    print_header()
    print("Install Module from .mdpk (Zip file)\n")

    path_str = input("Enter path to .mdpk file: ").strip()
    if not path_str:
        return

    # Handle quotes
    if path_str.startswith('"') and path_str.endswith('"'):
        path_str = path_str[1:-1]

    mdpk_path = Path(path_str)

    if not mdpk_path.exists() or not mdpk_path.is_file():
        print("Error: File not found.")
        input("Press Enter to continue...")
        return

    if not zipfile.is_zipfile(mdpk_path):
        print("Error: Invalid zip file.")
        input("Press Enter to continue...")
        return

    try:
        with zipfile.ZipFile(mdpk_path, 'r') as z:
            # Check for module.json
            if "module.json" not in z.namelist():
                print("Error: Invalid module package (missing module.json).")
                input("Press Enter to continue...")
                return

            # Read metadata
            with z.open("module.json") as f:
                meta = json.load(f)

            mod_id = meta.get("id")
            if not mod_id:
                print("Error: Module ID missing in module.json.")
                input("Press Enter to continue...")
                return

            print(f"Installing {meta.get('name', mod_id)} ({mod_id})...")

            # Extract to modules/
            target_dir = Path("modules") / mod_id
            if target_dir.exists():
                print(f"Warning: Module {mod_id} already exists. Overwriting...")
                shutil.rmtree(target_dir)

            target_dir.mkdir(parents=True, exist_ok=True)
            z.extractall(target_dir)

            # Check for requirements.txt
            req_file = target_dir / "requirements.txt"
            if req_file.exists():
                print("\n" + "="*40)
                print("MODULE DEPENDENCIES REQUIRED")
                print("="*40)
                print("This module requires the following packages:")
                print("-" * 40)
                try:
                    with open(req_file, "r") as rf:
                        print(rf.read().strip())
                except Exception:
                    print("(Error reading requirements.txt)")
                print("-" * 40)
                print("Please install them manually using:")
                print(f"pip install -r modules/{mod_id}/requirements.txt")
                print("="*40 + "\n")
                input("Press Enter to acknowledge...")

            # Register Module
            manager.register_module(
                mod_id=mod_id,
                name=meta.get("name", mod_id),
                icon=meta.get("icon", "extension"),
                version=meta.get("version", "1.0")
            )

            print(f"\nSuccess! Module {mod_id} installed.")
            print("Please restart the server to load the new module.")

    except Exception as e:
        print(f"Installation Failed: {e}")

    input("\nPress Enter to return to menu...")

def uninstall_module():
    clear_screen()
    print_header()
    modules = manager.get_installed_modules()

    if not modules:
        print("No modules installed.")
        input("\nPress Enter to return to menu...")
        return

    print("Select module to uninstall:")
    for i, m in enumerate(modules):
        print(f"{i+1}. {m['name']} ({m['id']})")
    print("0. Cancel")

    choice = input("\nEnter number: ").strip()
    if not choice.isdigit():
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(modules):
        return

    mod = modules[idx]
    mod_id = mod["id"]

    confirm = input(f"Are you sure you want to uninstall {mod['name']}? (y/N): ").lower()
    if confirm != 'y':
        return

    try:
        # 1. Remove files
        mod_dir = Path("modules") / mod_id
        if mod_dir.exists():
            shutil.rmtree(mod_dir)

        # 2. Unregister
        manager.unregister_module(mod_id)

        # 3. Clean dependencies? (Hard to track per module safely without venv, skipping for now)

        print(f"Module {mod_id} uninstalled.")
        print("Restart server to apply changes.")

    except Exception as e:
        print(f"Uninstall Failed: {e}")

    input("\nPress Enter to return to menu...")

def create_module_wizard():
    clear_screen()
    print_header()
    print("Create New Module Template\n")

    mod_id = input("Module ID (e.g., my_plugin): ").strip()
    if not mod_id: return

    mod_name = input("Module Name (e.g., My Plugin): ").strip() or mod_id
    mod_desc = input("Description: ").strip()
    mod_icon = input("Icon (Material Symbol name, default 'extension'): ").strip() or "extension"

    target_dir = Path("modules") / mod_id
    if target_dir.exists():
        print("Error: Module directory already exists.")
        input("Press Enter to continue...")
        return

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        web_dir = target_dir / "web"
        web_dir.mkdir()

        # 1. module.json
        meta = {
            "id": mod_id,
            "name": mod_name,
            "description": mod_desc,
            "icon": mod_icon,
            "version": "0.1.0",
            "author": "You"
        }
        with open(target_dir / "module.json", "w") as f:
            json.dump(meta, f, indent=2)

        # 2. api.py
        api_content = f'''from fastapi import APIRouter

router = APIRouter()

@router.get("/hello")
async def hello():
    return {{"message": "Hello from {mod_name}!"}}
'''
        with open(target_dir / "api.py", "w") as f:
            f.write(api_content)

        # 3. web/index.html (Fragment)
        html_content = f'''<div class="p-4">
    <h2 class="text-2xl font-bold mb-4">{mod_name}</h2>
    <p>{mod_desc}</p>
    <button class="btn btn-primary mt-4" onclick="callApi()">Call API</button>
    <div id="{mod_id}-result" class="mt-4 p-2 bg-base-200 rounded"></div>
</div>

<script>
async function callApi() {{
    const res = await fetch('/api/modules/{mod_id}/hello');
    const data = await res.json();
    document.getElementById('{mod_id}-result').innerText = JSON.stringify(data, null, 2);
}}
</script>
'''
        with open(web_dir / "index.html", "w") as f:
            f.write(html_content)

        # Register it so it shows up
        manager.register_module(mod_id, mod_name, mod_icon, "0.1.0")

        print(f"\nModule {mod_id} created successfully!")
        print(f"Location: {target_dir}")
        print("Restart the server to see it in action.")

    except Exception as e:
        print(f"Creation Failed: {e}")

    input("\nPress Enter to return to menu...")

def main_menu():
    while True:
        clear_screen()
        print_header()
        print("1. List Installed Modules")
        print("2. Install Module (.mdpk)")
        print("3. Uninstall Module")
        print("4. Create New Module (Interactive)")
        print("5. Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == '1':
            list_modules()
        elif choice == '2':
            install_module()
        elif choice == '3':
            uninstall_module()
        elif choice == '4':
            create_module_wizard()
        elif choice == '5':
            sys.exit(0)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
