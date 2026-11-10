"""Layouts: a readable draft (pixel boxes from the top-left) and the compact prompt MOSS-Image reads.

The draft is MOSS-Image's "Pixel Layout draft" (skills/moss-image-prompt-enhancer/references/layout.md):

    {"width": W, "height": H, "bbox_coord_space": "abs", "bbox_format": "xyxy",
     "summary": {"caption": ..., "meta": [...], "canvas": "single"},
     "items": [{"label": "object" | "character" | "text", "caption": ..., "text": ..., "bbox": [x1, y1, x2, y2]}]}

compile_prompt follows MOSS-Image's scripts/compile_prompt.py (Apache License 2.0, the OpenMOSS Team / MOSI.AI):
the same checks and the same model-facing form (one line of JSON, boxes [y1, x1, y2, x2] about the canvas centre).
Changes: the draft's boxes are scaled to the picture's size when the two differ, and it reads drafts from text.
"""
from __future__ import annotations

import json
import math

LABELS = ("object", "character", "text")
CANVASES = ("single", "multi_panel", "collage")
ROOT_FIELDS = {"width", "height", "bbox_coord_space", "bbox_format", "summary", "items"}
SUMMARY_FIELDS = {"caption", "meta", "canvas", "palette"}
ITEM_FIELDS = {"label", "caption", "bbox", "text", "tags", "palette"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def new(width, height):
    return {"width": width, "height": height, "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": {"caption": ""}, "items": []}


def loads(text):
    """Draft from its JSON text ('' → None)."""
    return json.loads(text) if text.strip() else None


def dumps(draft):
    return json.dumps(draft, ensure_ascii=False, separators=(",", ":")) if draft else ""


def _nonempty(value, where):
    require(isinstance(value, str) and value.strip(), f"{where} is empty.")


def _strings(value, where):
    require(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
            f"{where} must be a list of words.")


def _name(index, item):
    words = str(item.get("text") or "").strip()
    return f"Box {index + 1}" + (f" (“{words.splitlines()[0]}”)" if words else "")


def check(draft):
    """Raise ValueError, in words for the person using the editor, if the draft can't be compiled."""
    require(isinstance(draft, dict), "A layout must be a JSON object.")
    require(set(draft) == ROOT_FIELDS, f"A layout has exactly the fields {sorted(ROOT_FIELDS)}.")
    for key in ("width", "height"):
        require(type(draft[key]) is int and draft[key] > 0 and draft[key] % 16 == 0,
                f"The layout's {key} must be a positive multiple of 16.")
    require(draft["bbox_coord_space"] == "abs" and draft["bbox_format"] == "xyxy",
            "A layout draft uses bbox_coord_space \"abs\" and bbox_format \"xyxy\".")
    summary = draft["summary"]
    require(isinstance(summary, dict) and not set(summary) - SUMMARY_FIELDS,
            f"The summary may hold only {sorted(SUMMARY_FIELDS)}.")
    _nonempty(summary.get("caption"), "The description of the whole picture")
    require(summary.get("canvas", "single") in CANVASES, f"canvas must be one of {', '.join(CANVASES)}.")
    for key in ("meta", "palette"):
        if key in summary:
            _strings(summary[key], f"summary.{key}")
    items = draft["items"]
    require(isinstance(items, list) and items, "A layout needs at least one box.")
    w, h = draft["width"], draft["height"]
    for i, item in enumerate(items):
        name = _name(i, item) if isinstance(item, dict) else f"Box {i + 1}"
        require(isinstance(item, dict) and not set(item) - ITEM_FIELDS, f"{name} has fields a layout can't hold.")
        require(item.get("label") in LABELS, f"{name}: the kind must be object, character or text.")
        _nonempty(item.get("caption"), f"{name}: the description")
        if item["label"] == "text":
            _nonempty(item.get("text"), f"{name}: the words")
        elif "text" in item:
            _nonempty(item["text"], f"{name}: the words")
        for key in ("tags", "palette"):
            if key in item:
                _strings(item[key], f"{name}: {key}")
        box = item.get("bbox")
        require(isinstance(box, list) and len(box) == 4
                and all(type(v) in (int, float) and math.isfinite(v) for v in box), f"{name}: bad box.")
        x1, y1, x2, y2 = box
        require(x1 < x2 and y1 < y2, f"{name} has no area.")
        require(0 <= x1 and 0 <= y1 and x2 <= w and y2 <= h, f"{name} goes past the edge of the picture.")


def _centered(box, width, height):
    """[x1, y1, x2, y2] from the top-left → [y1, x1, y2, x2] about the centre, enclosing whole pixels."""
    x1, y1, x2, y2 = box
    return [math.floor(round(y1, 9)) - height // 2, math.floor(round(x1, 9)) - width // 2,
            math.ceil(round(y2, 9)) - height // 2, math.ceil(round(x2, 9)) - width // 2]


def _scale_box(box, sx, sy, width, height):
    """A box stretched by sx, sy, in whole pixels (as the model was trained), kept on the canvas and at least
    one pixel wide and high."""
    x1, y1 = (min(max(round(v * s), 0), lim - 1) for v, s, lim in ((box[0], sx, width), (box[1], sy, height)))
    x2, y2 = (min(max(round(v * s), lo + 1), lim) for v, s, lo, lim in ((box[2], sx, x1, width), (box[3], sy, y1, height)))
    return [x1, y1, x2, y2]


def scaled(draft, width, height):
    """The draft with its boxes stretched to a width × height picture (unchanged if that's its own size)."""
    sx, sy = width / draft["width"], height / draft["height"]
    if (sx, sy) == (1, 1):
        return draft
    items = [{**it, "bbox": _scale_box(it["bbox"], sx, sy, width, height)} for it in draft["items"]]
    return {**draft, "width": width, "height": height, "items": items}


def compile_prompt(draft, width=None, height=None):
    """The one-line prompt MOSS-Image reads, for a width × height picture (default: the draft's own size)."""
    check(draft)
    draft = scaled(draft, width or draft["width"], height or draft["height"])
    w, h = draft["width"], draft["height"]
    items = [{k: (_centered(v, w, h) if k == "bbox" else v) for k, v in it.items()} for it in draft["items"]]
    result = {"summary": draft["summary"], "items": items,
              "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def from_prompt(text, width, height):
    """A draft from a layout prompt (a draft, or MOSS-Image's centred form), or None if it isn't one."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("summary"), dict) or not isinstance(data.get("items"), list):
        return None
    space, form = data.get("bbox_coord_space"), data.get("bbox_format")
    w, h = data.get("width", width), data.get("height", height)
    items = []
    for item in data["items"]:
        if not isinstance(item, dict) or not (isinstance(item.get("bbox"), list) and len(item["bbox"]) == 4):
            return None
        b = item["bbox"]
        if (space, form) == ("abs_centralized", "yxyx"):
            box = [b[1] + w // 2, b[0] + h // 2, b[3] + w // 2, b[2] + h // 2]
        elif (space, form) == ("abs", "xyxy"):
            box = list(b)
        else:
            return None
        items.append({**{k: v for k, v in item.items() if k in ITEM_FIELDS}, "bbox": box})
    summary = {k: v for k, v in data["summary"].items() if k in SUMMARY_FIELDS}
    return {"width": w, "height": h, "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": summary, "items": items}


def signature(draft):
    """What makes two drafts the same layout: the summary, and each item with its box in whole pixels."""
    return json.dumps([draft.get("summary"), [{**it, "bbox": [round(x) for x in it["bbox"]]}
                                             for it in draft.get("items", [])]], sort_keys=True)


def describe(draft):
    """One line for the controls and the history: the picture's description and how many boxes."""
    n = len(draft["items"])
    caption = draft["summary"].get("caption", "").strip() or "No description yet"
    return f"{caption} ({n} box{'es' if n != 1 else ''})"
