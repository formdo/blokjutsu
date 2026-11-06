"""Build a thin Blokjutsu.app that runs `python -m blokjutsu` with a given interpreter.

    python -m blokjutsu.macapp [--dest ~/Applications] [--python PATH]

The bundle holds only Info.plist, the icon and a launcher script; the code stays in the Python environment, so
reinstalling the package updates the app. Output goes to <app data>/logs/console.log. scripts/make_dmg.sh uses
skeleton() for the self-contained app in the .dmg.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__

NAME = "Blokjutsu"
BUNDLE_ID = "io.github.formdo.blokjutsu"
ICON = Path(__file__).with_name("resources") / "icon.png"

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{name}</string>
  <key>CFBundleDisplayName</key><string>{name}</string>
  <key>CFBundleIdentifier</key><string>{bundle_id}</string>
  <key>CFBundleExecutable</key><string>blokjutsu</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>LSMinimumSystemVersion</key><string>12.3</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.graphics-design</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

LAUNCHER = """#!/bin/bash
LOG_DIR="${{BLOKJUTSU_HOME:-$HOME/Library/Application Support/Blokjutsu.noindex}}/logs"
mkdir -p "$LOG_DIR"
export PYTORCH_ENABLE_MPS_FALLBACK=1
exec "{python}" -m blokjutsu "$@" >>"$LOG_DIR/console.log" 2>&1
"""


def icns(png, out):
    """macOS .icns from a 1024² PNG, with the system's sips and iconutil."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                px = size * scale
                subprocess.run(["sips", "-z", str(px), str(px), str(png), "--out",
                                str(iconset / f"icon_{size}x{size}{suffix}.png")], check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)


def skeleton(app):
    """Contents/{Info.plist, MacOS/, Resources/AppIcon.icns}; the executable Contents/MacOS/blokjutsu is the
    caller's to add."""
    contents = Path(app) / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(exist_ok=True)
    (contents / "Info.plist").write_text(PLIST.format(name=NAME, bundle_id=BUNDLE_ID, version=__version__))
    if sys.platform == "darwin":
        icns(ICON, contents / "Resources" / "AppIcon.icns")
    return contents


def build(dest, python):
    app = Path(dest).expanduser() / f"{NAME}.app"
    if app.exists():
        shutil.rmtree(app)
    launcher = skeleton(app) / "MacOS" / "blokjutsu"
    launcher.write_text(LAUNCHER.format(python=Path(python).absolute()))
    launcher.chmod(0o755)
    app.touch()                      # so Finder and the Dock pick up the icon
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m blokjutsu.macapp")
    parser.add_argument("--dest", default="~/Applications")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    print("Built", build(args.dest, args.python))


if __name__ == "__main__":
    main()
