"""Output folder layout: <root>/<NNNNN>/{image.png, parameters.json}; also reads the repo/Gradio layouts."""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, replace
from pathlib import Path

from . import params as P

RECORD = "parameters.json"


@dataclass(frozen=True)
class Entry:
    folder: Path
    image: Path
    params: P.Params
    created: float
    elapsed: float | None = None


def _images(folder, record):
    names = record.get("images") or [record.get("image", "image.png")]
    return [folder / n for n in names if (folder / n).is_file()]


def load(folder):
    """Entries in one folder (several if a Gradio run saved a batch); [] if unreadable."""
    try:
        record = json.loads((folder / RECORD).read_text(encoding="utf-8"))
        params = P.from_record(record)
    except (OSError, ValueError, TypeError, KeyError):
        return []
    extra = record.get("blokjutsu", {})
    params = resolve_files(params, folder)
    return [Entry(folder, image, params, extra.get("created") or image.stat().st_mtime,
                  extra.get("elapsed_seconds") or record.get("elapsed_seconds"))
            for image in _images(folder, record)]


def resolve_files(params, folder):
    """Input image and mask paths relative to a record's folder made absolute; missing files dropped."""
    for name in ("init_image", "mask_image"):
        value = getattr(params, name)
        if value and not Path(value).is_absolute():
            value = str(Path(folder) / value)
            params = replace(params, **{name: value if Path(value).is_file() else ""})
    if not params.init_image:
        params = replace(params, mask_image="")
    return params


def scan(root):
    """All entries under root, newest first."""
    root = Path(root)
    if not root.is_dir():
        return []
    entries = [e for d in root.iterdir() if (d / RECORD).is_file() for e in load(d)]
    return sorted(entries, key=lambda e: (e.created, e.folder.name, e.image.name), reverse=True)


def delete(folder):
    """Permanently delete one image folder; refuses anything that isn't an image folder. Returns success."""
    folder = Path(folder)
    if not (folder / RECORD).is_file():
        return False
    try:
        shutil.rmtree(folder)
    except OSError:
        return False
    return True


def _new_folder(root):
    numbers = [int(d.name) for d in root.iterdir() if d.is_dir() and d.name.isdigit()]
    n = max(numbers, default=0) + 1
    while True:
        folder = root / f"{n:05d}"
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            n += 1


def save(root, params, image, embed=False, **extra):
    """Save one picture and its parameters.json in a new folder. With embed, the PNG also carries the
    parameters; without, it carries no metadata at all (no text, no time, no color profile)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    folder = _new_folder(root)
    path = folder / "image.png"
    copied = {}
    for name, stem in (("init_image", "input"), ("mask_image", "mask")):
        source = getattr(params, name)
        if source and Path(source).is_file():
            copied[name] = stem + Path(source).suffix.lower()
            shutil.copy2(source, folder / copied[name])
            params = replace(params, **{name: str(folder / copied[name])})
    created = time.time()
    record = P.to_record(params, path.name, created=created, **extra)
    record["blokjutsu"].update(copied)
    text = json.dumps(record, indent=2, ensure_ascii=False)
    write_png(image, path, text if embed else None)
    (folder / RECORD).write_text(text + "\n", encoding="utf-8")
    return Entry(folder, path, params, created, extra.get("elapsed_seconds"))


def write_png(image, path, record_json=None):
    """PNG with only the chunks the format needs, plus the parameters if `record_json` is given."""
    clean = image.copy()
    clean.info = {}                       # PIL would otherwise copy an ICC profile or text from the source
    if record_json is None:
        clean.save(path, format="PNG")
    else:
        clean.save(path, format="PNG", pnginfo=png_text(record_json))


def png_text(record_json):
    """The full parameters.json as a PNG text chunk, so a copied image still carries its settings."""
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_itxt("parameters", record_json)
    info.add_text("Software", "Blokjutsu")
    return info


def png_parameters(path):
    """The parameters.json text embedded in a Blokjutsu PNG; ValueError if there is none."""
    from PIL import Image
    with Image.open(path) as image:
        text = image.info.get("parameters")
    if not text:
        raise ValueError("This PNG has no Blokjutsu parameters.")
    return text
