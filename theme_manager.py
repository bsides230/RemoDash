import os
import json
import shutil
import zipfile
from pathlib import Path

class ThemeManager:
    def __init__(self, data_dir="data", themes_dir="themes"):
        self.data_dir = Path(data_dir)
        self.themes_dir = Path(themes_dir)
        self.registry_file = self.data_dir / "theme_registry.json"
        self.registry = []

        # Ensure directories exist
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.themes_dir.exists():
            self.themes_dir.mkdir(parents=True)

        self.scan_themes()

    def load_registry(self):
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    self.registry = json.load(f)
            except Exception as e:
                print(f"Error loading theme registry: {e}")
                self.registry = []
        else:
            self.registry = []

    def save_registry(self):
        try:
            with open(self.registry_file, 'w') as f:
                json.dump(self.registry, f, indent=4)
        except Exception as e:
            print(f"Error saving theme registry: {e}")

    def scan_themes(self):
        """Scans the themes directory and registers any valid themes found."""
        self.registry = []
        if not self.themes_dir.exists():
            return

        for item in self.themes_dir.iterdir():
            if item.is_dir():
                theme_json_path = item / "theme.json"
                if theme_json_path.exists():
                    try:
                        with open(theme_json_path, 'r') as f:
                            metadata = json.load(f)
                            # Ensure ID matches directory name
                            if metadata.get('id') != item.name:
                                metadata['id'] = item.name
                            self.registry.append(metadata)
                    except Exception as e:
                        print(f"Error reading theme metadata for {item.name}: {e}")

        self.save_registry()

    def get_installed_themes(self):
        return self.registry

    def register_theme(self, theme_path):
        """Installs a .tmpk file."""
        try:
            with zipfile.ZipFile(theme_path, 'r') as zip_ref:
                # Extract to temp first to check metadata
                temp_extract_path = self.themes_dir / "temp_extract"
                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)
                temp_extract_path.mkdir()

                zip_ref.extractall(temp_extract_path)

                theme_json_path = temp_extract_path / "theme.json"
                if not theme_json_path.exists():
                    raise Exception("Invalid theme package: theme.json missing")

                with open(theme_json_path, 'r') as f:
                    metadata = json.load(f)

                theme_id = metadata.get('id')
                if not theme_id:
                    raise Exception("Invalid theme package: id missing in theme.json")

                # Move to final destination
                final_path = self.themes_dir / theme_id
                if final_path.exists():
                    shutil.rmtree(final_path)

                shutil.move(str(temp_extract_path), str(final_path))

                # Update registry
                # Remove existing entry if any
                self.registry = [t for t in self.registry if t['id'] != theme_id]
                self.registry.append(metadata)
                self.save_registry()

                return metadata
        except Exception as e:
            print(f"Error installing theme: {e}")
            raise e

    def unregister_theme(self, theme_id):
        """Removes a theme."""
        theme_path = self.themes_dir / theme_id
        if theme_path.exists():
            shutil.rmtree(theme_path)

        self.registry = [t for t in self.registry if t['id'] != theme_id]
        self.save_registry()
        return True
