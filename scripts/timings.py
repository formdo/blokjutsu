"""Table of the newest pictures' sizes, steps and times, for the Speed and memory page.

Usage: python scripts/timings.py [N] [OUTPUT_FOLDER]     (default: 20 newest, in the app's own folder)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blokjutsu.settings import default_output  # noqa: E402


def records(root):
    for path in Path(root).glob("*/parameters.json"):
        record = json.loads(path.read_text())
        yield path.stat().st_mtime, record


def row(record):
    p, extra = record["parameters"], record.get("blokjutsu", {})
    change = extra.get("init_strength") if extra.get("init_image") else None
    return (f"{p['width']}×{p['height']}", f"{p['width'] * p['height'] / 1e6:.2f}", p["steps"],
            "" if change is None else f"{change:g}", extra.get("elapsed_seconds"))


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    root = sys.argv[2] if len(sys.argv) > 2 else default_output()
    newest = sorted(records(root), key=lambda r: r[0])[-count:]
    print("| size | MP | steps | change | seconds |\n|---|---|---|---|---|")
    for _, record in newest:
        print("| " + " | ".join("" if v is None else str(v) for v in row(record)) + " |")


if __name__ == "__main__":
    main()
