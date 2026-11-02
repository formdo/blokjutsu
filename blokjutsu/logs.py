"""The app's log files: <app data>/logs/blokjutsu.log (Help → Show Log) and console.log (the .app's raw output)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import app_home

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def log_folder():
    return app_home() / "logs"


def log_file():
    return log_folder() / "blokjutsu.log"


def log_to_file():
    """Everything logged also goes to blokjutsu.log, 2 × 5 MB."""
    path = log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5 << 20, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMAT))
    logging.getLogger().addHandler(handler)


def clear_logs(folder=None):
    """Empty every log in the folder. Files still open for writing (this process's log, the launcher's
    console.log) are truncated in place so writing continues; rotated copies are deleted."""
    folder = Path(folder or log_folder())
    open_paths = set()
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).parent == folder:
            open_paths.add(Path(handler.baseFilename))
            handler.acquire()
            try:
                if handler.stream is not None:
                    handler.stream.seek(0)
                    handler.stream.truncate()
            finally:
                handler.release()
    for path in folder.glob("*") if folder.is_dir() else ():
        try:
            if not path.is_file() or path in open_paths:
                continue
            if path.suffix == ".log":
                os.truncate(path, 0)
            else:
                path.unlink()
        except OSError:
            logging.getLogger(__name__).warning("Could not clear %s", path)
