import os
import json
import shutil
from pathlib import Path

# Script directory and settings path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, "settings.json")

class SettingsManager:
    """Enhanced settings manager with UI preferences for RemoDash"""

    def __init__(self):
        self.settings = None
        self.first_boot = False
        self.ui_settings = {
            "font_size": 12,
            "window_size": "1400x900",
            "confirmation_preferences": {}
        }
        self.load_or_detect_first_boot()

    def get_setting(self, key: str, default: any = None) -> any:
        """Gets a setting from the UI settings."""
        return self.ui_settings.get(key, default)

    def set_setting(self, key: str, value: any):
        """Sets a setting in the UI settings and saves it."""
        self.ui_settings[key] = value
        self.save_settings()

    def load_or_detect_first_boot(self):
        """Load settings or create a default one on first boot."""
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.settings = data.get('settings', {})
                    self.ui_settings.update(data.get('ui_settings', {}))

                print("Settings loaded successfully")
            except Exception as e:
                print(f"Error loading settings: {e}. Assuming first boot.")
                self.first_boot = True
        else:
            print("No settings.json found - First boot detected. Creating default settings.")
            self.first_boot = True

        if self.settings is not None:
            # Inject defaults if missing
            if "git_root_mode" not in self.settings:
                self.settings["git_root_mode"] = "manual"
            if "git_root_path" not in self.settings:
                try:
                    self.settings["git_root_path"] = str(Path.home() / "documents" / "github" / "repos")
                except Exception as e:
                    print(f"Error resolving default git root path: {e}")
                    self.settings["git_root_path"] = ""

            self.detect_shell()

        if self.first_boot:
            # Create and save a default settings file
            self.settings = self.create_empty_settings_structure()
            self.save_settings()

    def detect_shell(self):
        """Detects a valid shell executable and updates settings."""
        # Check if existing setting is valid
        current = self.settings.get("terminal_shell")
        if current:
            # Check if it exists (using shutil.which to verify executable status effectively or os.access)
            # If it's just a command name like "bash", shutil.which handles it.
            # If it's a path, shutil.which checks it too.
            if shutil.which(current) or (os.path.exists(current) and os.access(current, os.X_OK)):
                return

        # Search for a valid shell
        candidates = []

        # 1. Environment Variable
        env_shell = os.environ.get("SHELL")
        if env_shell: candidates.append(env_shell)

        # 2. Common Termux Paths
        candidates.extend([
            "/data/data/com.termux/files/usr/bin/bash",
            "/data/data/com.termux/files/usr/bin/zsh",
            "/data/data/com.termux/files/usr/bin/sh"
        ])

        # 3. Standard Linux Paths
        candidates.extend([
            "/bin/bash",
            "/usr/bin/bash",
            "/bin/sh",
            "/usr/bin/sh",
            "/system/bin/sh" # Android system shell
        ])

        found_shell = None
        for path in candidates:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                found_shell = path
                break

        # 4. Fallback to shutil.which
        if not found_shell:
            for name in ["bash", "zsh", "sh"]:
                path = shutil.which(name)
                if path:
                    found_shell = path
                    break

        if found_shell:
            print(f"[System] Auto-detected terminal shell: {found_shell}")
            self.settings["terminal_shell"] = found_shell
            self.save_settings()

    def create_empty_settings_structure(self) -> dict:
        """Create empty settings structure for first boot"""
        default_git = ""
        try:
            default_git = str(Path.home() / "documents" / "github" / "repos")
        except Exception as e:
            print(f"Error resolving default git root path: {e}")

        return {
            "allowed_origins": [],
            "git_repos": [],
            "git_root_mode": "manual",
            "git_root_path": default_git
        }

    def save_settings(self, settings: dict = None):
        """Save settings and UI preferences to JSON file"""
        try:
            if os.path.exists(SETTINGS_PATH):
                backup_path = SETTINGS_PATH + '.bk'
                shutil.copy2(SETTINGS_PATH, backup_path)

            data = {
                "settings": settings or self.settings,
                "ui_settings": self.ui_settings
            }

            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if settings:
                self.settings = settings
            self.first_boot = False
            print("Settings saved successfully")

        except Exception as e:
            print(f"Error saving settings: {e}")
