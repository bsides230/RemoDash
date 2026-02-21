import os
import json
import shutil
import zipfile
import importlib.util
import importlib.metadata
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

# --- Constants ---
MODULES_DIR = Path("modules")
DATA_DIR = Path("data")
REGISTRY_FILE = DATA_DIR / "module_registry.json"
MANIFEST_FILE = DATA_DIR / "module_manifest.json"

class ModuleManager:
    def __init__(self):
        self.modules: Dict[str, Any] = {}
        self.registry: List[Dict[str, Any]] = []
        self.manifest: Dict[str, List[str]] = {}

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MODULES_DIR.mkdir(parents=True, exist_ok=True)

        self.load_registry()
        self.load_manifest()

    def load_registry(self):
        """Loads the module registry from JSON."""
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.registry = data.get("modules", [])
            except Exception as e:
                print(f"[ModuleManager] Failed to load registry: {e}")
                self.registry = []
        else:
            self.registry = []

    def save_registry(self):
        """Saves the module registry to JSON."""
        try:
            data = {"modules": self.registry}
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ModuleManager] Failed to save registry: {e}")

    def load_manifest(self):
        """Loads the module manifest (pip packages) from JSON."""
        if MANIFEST_FILE.exists():
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                    self.manifest = json.load(f)
            except Exception as e:
                print(f"[ModuleManager] Failed to load manifest: {e}")
                self.manifest = {}
        else:
            self.manifest = {}

    def save_manifest(self):
        """Saves the module manifest to JSON."""
        try:
            with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            print(f"[ModuleManager] Failed to save manifest: {e}")

    def load_modules(self, app: FastAPI):
        """
        Discovers and loads enabled modules.
        - Mounts static files at /modules/{module_id}
        - Imports api.py and includes router
        """
        print("[ModuleManager] Loading modules...")

        # Auto-discover new modules
        self.discover_modules()

        # Reload registry to be fresh
        self.load_registry()

        for mod_entry in self.registry:
            mod_id = mod_entry.get("id")
            enabled = mod_entry.get("enabled", True)

            if not mod_id or not enabled:
                continue

            self.load_single_module(app, mod_entry)

    def load_single_module(self, app: FastAPI, mod_entry: Dict[str, Any]):
        """Loads a single module given its registry entry."""
        mod_id = mod_entry.get("id")
        if not mod_id:
            return

        mod_path = MODULES_DIR / mod_id
        if not mod_path.exists():
            print(f"[ModuleManager] Module {mod_id} not found at {mod_path}")
            return

        print(f"[ModuleManager] Loading {mod_id}...")

        # 1. Mount Static Files (web/)
        web_path = mod_path / "web"
        if web_path.exists() and web_path.is_dir():
            # Check if already mounted to avoid errors on reload
            mounted = False
            for route in app.router.routes:
                 if hasattr(route, "path") and route.path == f"/modules/{mod_id}":
                     mounted = True
                     break

            if not mounted:
                # Manually create and insert the Mount to ensure it precedes the root catch-all
                module_mount = Mount(
                    path=f"/modules/{mod_id}",
                    app=StaticFiles(directory=str(web_path), html=True),
                    name=f"module_{mod_id}"
                )

                # Find index of catch-all route "/" if it exists
                insert_idx = len(app.router.routes)
                for idx, route in enumerate(app.router.routes):
                    # Check for root path (can be "/" or "") or name="static"
                    if hasattr(route, "path") and (route.path == "/" or route.path == ""):
                        insert_idx = idx
                        break
                    if hasattr(route, "name") and route.name == "static":
                        insert_idx = idx
                        break

                app.router.routes.insert(insert_idx, module_mount)
                print(f"  - Mounted static files at /modules/{mod_id}")

        # 2. Load API (api.py)
        api_path = mod_path / "api.py"
        if api_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(f"modules.{mod_id}.api", api_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"modules.{mod_id}.api"] = module
                    spec.loader.exec_module(module)

                    # Look for 'router' attribute
                    if hasattr(module, "router") and isinstance(module.router, APIRouter):
                        # Note: app.include_router doesn't easily support un-mounting or checking for duplicates by prefix.
                        # It simply appends routes. Ideally we would check if these routes exist, but for now we append.
                        app.include_router(module.router, prefix=f"/api/modules/{mod_id}", tags=[f"Module: {mod_id}"])
                        print(f"  - Registered API router at /api/modules/{mod_id}")
                    else:
                        print(f"  - No 'router' (APIRouter) found in api.py for {mod_id}")
            except Exception as e:
                print(f"  - Failed to load API for {mod_id}: {e}")

        self.modules[mod_id] = mod_entry

    def get_installed_modules(self) -> List[Dict[str, Any]]:
        self.load_registry()
        return self.registry

    def register_module(self, mod_id: str, name: str, icon: str, version: str = "1.0"):
        """Adds or updates a module in the registry."""
        # Check if exists
        existing = next((m for m in self.registry if m["id"] == mod_id), None)
        if existing:
            existing.update({
                "name": name,
                "icon": icon,
                "version": version,
                "enabled": True
            })
        else:
            self.registry.append({
                "id": mod_id,
                "name": name,
                "icon": icon,
                "version": version,
                "enabled": True,
                "path": str(MODULES_DIR / mod_id)
            })
        self.save_registry()

    def unregister_module(self, mod_id: str):
        """Removes a module from the registry."""
        self.registry = [m for m in self.registry if m["id"] != mod_id]
        self.save_registry()

    def update_manifest(self, mod_id: str, packages: List[str]):
        """Updates the pip package manifest for a module."""
        self.manifest[mod_id] = packages
        self.save_manifest()

    def remove_from_manifest(self, mod_id: str):
        """Removes a module from the manifest."""
        if mod_id in self.manifest:
            del self.manifest[mod_id]
            self.save_manifest()

    def discover_modules(self):
        """Scans the modules directory for unregistered modules and adds them."""
        if not MODULES_DIR.exists():
            return

        changed = False
        for item in MODULES_DIR.iterdir():
            if item.is_dir():
                mod_id = item.name
                # Check if already in registry
                if any(m["id"] == mod_id for m in self.registry):
                    continue

                # Check for module.json
                json_path = item / "module.json"
                if json_path.exists():
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            # Register it
                            self.registry.append({
                                "id": mod_id,
                                "name": meta.get("name", mod_id),
                                "icon": meta.get("icon", "extension"),
                                "version": meta.get("version", "1.0"),
                                "enabled": True,
                                "path": str(item)
                            })
                            changed = True
                            print(f"[ModuleManager] Discovered new module: {mod_id}")
                    except Exception as e:
                        print(f"[ModuleManager] Failed to load metadata for {mod_id}: {e}")

        if changed:
            self.save_registry()

    def check_requirements(self, mod_id: str) -> List[str]:
        """Checks for missing requirements for a module."""
        req_path = MODULES_DIR / mod_id / "requirements.txt"
        if not req_path.exists():
            return []

        missing = []
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                pkg = line.strip()
                if not pkg or pkg.startswith("#"): continue

                try:
                    # Strip version specifiers for check (e.g. numpy>=1.2 -> numpy)
                    pkg_name = pkg.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                    # Strip extras (e.g. misaki[en] -> misaki)
                    if "[" in pkg_name:
                        pkg_name = pkg_name.split("[")[0].strip()

                    # Mapping for common mismatched package names (basic list)
                    # We might need a better solution later, but this covers basic cases
                    if pkg_name == "Pillow": pkg_name = "PIL"

                    importlib.metadata.distribution(pkg_name)
                except importlib.metadata.PackageNotFoundError:
                    # Try original name just in case (e.g. some pkgs match exact name)
                    try:
                         importlib.metadata.distribution(pkg)
                    except:
                        missing.append(pkg)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error checking requirements for {mod_id}: {e}")

        return missing
