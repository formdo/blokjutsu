"""Network policy: the app never contacts the internet on its own.

Hugging Face libraries are put in offline mode before any of them is imported, so every attempt to reach
huggingface.co fails locally instead of being sent. The only network access is an explicit, user-confirmed
model download/update, which runs in a separate process with offline mode lifted for that process alone.
"""
from __future__ import annotations

import os
import sys

OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",            # huggingface_hub, diffusers, transformers: no requests at all
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",   # never attach a saved login token implicitly
    "DO_NOT_TRACK": "1",
}

WHAT_IS_SENT = (
    "The names of the files requested, your IP address (as with any web request) and a User-Agent string "
    "with library and Python versions. You are not logged in. No prompts, images, settings or files of yours "
    "are sent."
)


def go_offline():
    """Call before importing torch/diffusers/transformers/huggingface_hub."""
    os.environ.update(OFFLINE_ENV)


def download_command(*args):
    """argv for the child process that performs one confirmed download (see fetch.py)."""
    return [sys.executable, "-m", "blokjutsu.fetch", *args]


def download_environment():
    """The current environment with offline mode lifted (only for the download process)."""
    env = {k: v for k, v in os.environ.items() if k not in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
                                                           "HF_DATASETS_OFFLINE")}
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return env
