"""Exact-ratio size presets on a multiple-of-16 grid, and the size-step choices."""
from __future__ import annotations

from math import gcd

ASPECTS = ("16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16")
STEPS = (16, 32, 64, 128, 256, 512, 1024, 2048)
DEFAULT_STEP = 128
MIN_MP, MAX_MP = 0.065, 4.2       # 256 × 256 to about 2048 × 2048
GRIDS = (16, 32, 64, 128)
MAX_PRESETS = 16


def ratio(aspect):
    a, b = map(int, aspect.split(":"))
    return a, b


def _exact(a, b, grid):
    """All (w, h) = (a·m, b·m) with both sides multiples of `grid` and area in [MIN_MP, MAX_MP] megapixels."""
    unit_w, unit_h = grid // gcd(a, grid), grid // gcd(b, grid)
    unit = unit_w * unit_h // gcd(unit_w, unit_h)
    out, m = [], unit
    while a * m * b * m <= MAX_MP * 1e6:
        if a * m * b * m >= MIN_MP * 1e6:
            out.append((a * m, b * m))
        m += unit
    return out


def presets(aspect):
    """Sizes on the finest grid that keeps the menu to MAX_PRESETS entries."""
    a, b = ratio(aspect)
    for grid in GRIDS:
        sizes = _exact(a, b, grid)
        if len(sizes) <= MAX_PRESETS:
            return sizes
    return sizes[:MAX_PRESETS]


def aspect_of(width, height):
    """The listed aspect ratio that (width, height) matches exactly, else None."""
    g = gcd(width, height)
    reduced = f"{width // g}:{height // g}"
    return reduced if reduced in ASPECTS else None


def label(width, height):
    mp = width * height / 1e6
    return f"{mp:.2f} MP" if mp < 1 else f"{mp:.1f} MP"


def ratio_label(width, height):
    """The listed aspect if (width, height) matches one exactly, else the ratio rounded to two places, e.g. 1.37:1."""
    return aspect_of(width, height) or f"{width / height:.2f}:1"


SCALES = (1, 1.5, 2, 2.5, 3, 4)


def scaled(width, height, max_mp=MAX_MP):
    """Upscaling choices for a size that matches no preset: (factor, w, h) for each factor in SCALES whose
    area stays within max_mp, each side rounded to the nearest multiple of 16."""
    out = []
    for k in SCALES:
        w, h = (max(16, round(side * k / 16) * 16) for side in (width, height))
        if w * h <= max_mp * 1e6:
            out.append((k, w, h))
    return out


def scale_label(k, width, height):
    return f"{label(width, height)} (×{k:g})" if k != 1 else label(width, height)
