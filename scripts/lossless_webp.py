"""Convert PNGs to lossless WebP for the User's Guide, keeping a file only if it decodes to identical pixels.

Usage: python scripts/lossless_webp.py SOURCE_FOLDER DEST_FOLDER
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def pixels(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"))


def convert(source, dest):
    with Image.open(source) as image:
        image.save(dest, "WEBP", lossless=True, quality=100, method=6, exact=True)
    if not np.array_equal(pixels(source), pixels(dest)):
        dest.unlink()
        raise ValueError(f"{source.name}: lossless WebP is not pixel-identical")
    return source.stat().st_size, dest.stat().st_size


def main():
    source, dest = map(Path, sys.argv[1:3])
    dest.mkdir(parents=True, exist_ok=True)
    before = after = 0
    for png in sorted(source.glob("*.png")):
        a, b = convert(png, dest / (png.stem + ".webp"))
        before, after = before + a, after + b
        print(f"{png.name}: {a / 1e3:.0f} KB → {b / 1e3:.0f} KB")
    print(f"total: {before / 1e6:.1f} MB → {after / 1e6:.1f} MB, all pixel-identical")


if __name__ == "__main__":
    main()
