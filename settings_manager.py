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

        if self.first_boot:
            # Create and save a default settings file
            self.settings = self.create_empty_settings_structure()
            self.save_settings()

    def create_empty_settings_structure(self) -> dict:
        """Create empty settings structure for first boot"""
        return {
            "allowed_origins": []
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
