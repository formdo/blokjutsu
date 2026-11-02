"""Settings as one JSON file in the app's home folder; no OS preference store."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


SUPPORT = Path.home() / "Library" / "Application Support"
HOME_NAME = "Blokjutsu.noindex"              # Spotlight skips folders named *.noindex
BACKUP_MARKER = ".excluded-from-backups"     # kept outside settings.json, which users may reset


def app_home():
    """$BLOKJUTSU_HOME, else ~/Library/Application Support/Blokjutsu.noindex (macOS) or ~/.config/blokjutsu."""
    if env := os.environ.get("BLOKJUTSU_HOME"):
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return SUPPORT / HOME_NAME
    return Path.home() / ".config" / "blokjutsu"


def default_output():
    return app_home() / "images"


def models_dir():
    """Blokjutsu's own Hugging Face cache, inside its home rather than the shared ~/.cache/huggingface."""
    return app_home() / "models"


def use_own_model_folder():
    """Call before huggingface_hub is imported."""
    os.environ["HF_HUB_CACHE"] = str(models_dir())


def tilde(path):
    """A path as shown to the user: the home folder written as ~."""
    path, home = Path(path), Path.home()
    return "~/" + str(path.relative_to(home)) if path.is_relative_to(home) and path != home else str(path)


def keep_out_of_backups(path):
    """Set the flag Time Machine skips (as `tmutil addexclusion` does); False where unavailable."""
    try:
        from Foundation import NSURL, NSURLIsExcludedFromBackupKey
    except ImportError:
        return False
    ok, _ = NSURL.fileURLWithPath_(str(path)).setResourceValue_forKey_error_(True, NSURLIsExcludedFromBackupKey, None)
    return bool(ok)


def prepare_home():
    """Create the home folder and keep it out of backups, once: a later `tmutil removeexclusion` is respected."""
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    marker = home / BACKUP_MARKER
    if not marker.exists() and keep_out_of_backups(home):
        marker.touch()


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else app_home() / "settings.json"
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)


def physical_memory():
    """Installed memory in bytes, or None if unknown."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass
    try:
        import subprocess
        return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
    except (OSError, ValueError):
        return None
