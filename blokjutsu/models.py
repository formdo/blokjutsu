"""Your own models: fine-tuned MOSS-Image image models, kept in a library beside the two original models.

A library model is a folder under the app's home holding at least the image model (the transformer), as a
Diffusers `transformer/` folder or one `transformer.safetensors` file; it may also hold its own text encoder,
image decoder, scheduler or tokenizer. Any part it lacks comes from an original model on this Mac, so a fine-tune
of the image model alone is about 10 GB, not 30. A picture made with one records `library:<id>` as its model.

Weights are checked against MOSS-Image's structure from the file headers alone, before anything big is
downloaded; Blokjutsu's own pipeline code is always used, never code from a model's repository.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from .lora import DEFAULT_CONFIG, _slug, read_header, sha256
from .settings import app_home

PREFIX = "library:"
INFO = "info.json"
SINGLE = "transformer.safetensors"
PARTS = ("transformer", "text_encoder", "vae", "scheduler", "tokenizer")
STRIP = ("model.diffusion_model.", "diffusion_model.", "transformer.")


def library_dir():
    return app_home() / "model-library"


def is_library(model):
    return isinstance(model, str) and model.startswith(PREFIX)


def library_id(model):
    return model[len(PREFIX):] if is_library(model) else None


# the image model's structure

def expected_shapes(config=None):
    """{parameter name: shape} of the MOSS-Image transformer (rope.bands, a derived constant, may be absent)."""
    c = {**DEFAULT_CONFIG, **(config or {})}
    d, f, t, h = c["dim"], c["ffn_dim"], c["text_dim"], c["dim"] // c["num_heads"]
    s = {"video_embedder.weight": (d, c["latent_channels"]), "video_embedder.bias": (d,),
         "text_embedder.proj.weight": (d, t), "text_embedder.proj.bias": (d,),
         "time_embedding.0.weight": (d, c["freq_dim"]), "time_embedding.0.bias": (d,),
         "time_embedding.2.weight": (d, d), "time_embedding.2.bias": (d,),
         "shared_block_modulation.weight": (6 * d, d), "shared_block_modulation.bias": (6 * d,),
         "final_norm_video.weight": (d,), "final_linear_video.weight": (c["latent_channels"], d),
         "video_head_modulation.weight": (2 * d, d), "video_head_modulation.bias": (2 * d,)}
    for b in range(2):
        p = f"text_embedder.blocks.{b}."
        s |= {p + "norm1.weight": (d,), p + "norm2.weight": (d,), p + "q_norm.weight": (h,), p + "k_norm.weight": (h,),
              p + "qkv.weight": (3 * d, d), p + "qkv.bias": (3 * d,), p + "proj.weight": (d, d), p + "proj.bias": (d,),
              p + "ffn_gate.weight": (f, d), p + "ffn_gate.bias": (f,), p + "ffn_up.weight": (f, d),
              p + "ffn_up.bias": (f,), p + "ffn_down.weight": (d, f), p + "ffn_down.bias": (d,)}
    for i in range(c["num_layers"]):
        p = f"layers.{i}."
        s |= {p + "norm1.weight": (d,), p + "norm2.weight": (d,), p + "q_norm.weight": (h,), p + "k_norm.weight": (h,)}
        s |= {p + f"proj.{n}.weight": (d, d) for n in "qkvo"}
        s |= {p + "proj.ffn_up_gate.weight": (2 * f, d), p + "proj.ffn_down.weight": (d, f)}
    return s


def strip(name):
    for prefix in STRIP:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def check_transformer(tensors, config=None):
    """Raise ValueError, in words for the user, unless the tensors are exactly a MOSS-Image image model."""
    want = expected_shapes(config)
    have = {strip(k): tuple(v[1]) if v and isinstance(v[0], str) else tuple(v) for k, v in tensors.items()}
    have.pop("rope.bands", None)
    extra = sorted(k for k in have if k not in want)
    if extra:
        kinds = sorted({re.sub(r"\d+", "N", k) for k in extra})
        raise ValueError("This was made for a different model: it has parts MOSS-Image doesn't "
                         f"({', '.join(kinds[:3])}{', …' if len(kinds) > 3 else ''}).")
    missing = [k for k in want if k not in have]
    if missing:
        if len(missing) == len(want):
            raise ValueError("This isn't a MOSS-Image image model.")
        raise ValueError(f"This model is incomplete: {len(missing)} of its {len(want)} weights are missing.")
    wrong = [k for k in want if have[k] != want[k]]
    if wrong:
        raise ValueError(f"This was made for a different model: its sizes don't match MOSS-Image's ({wrong[0]}).")


def header_of(path):
    """The tensors of one .safetensors file, or of every shard a Diffusers index lists."""
    path = Path(path)
    if path.name.endswith(".index.json"):
        tensors = {}
        for shard in sorted(set(json.loads(path.read_text())["weight_map"].values())):
            tensors |= read_header(path.parent / shard)[0]
        return tensors
    return read_header(path)[0]


def transformer_weights(folder):
    """The file(s) holding a library model's image model: its single file, or its Diffusers index or file."""
    folder = Path(folder)
    if (folder / SINGLE).exists():
        return folder / SINGLE
    sub = folder / "transformer"
    for name in ("diffusion_pytorch_model.safetensors.index.json", "diffusion_pytorch_model.safetensors"):
        if (sub / name).exists():
            return sub / name
    found = sorted(sub.glob("*.safetensors.index.json")) or sorted(sub.glob("*.safetensors"))
    return found[0] if found else None


# what the card says

STEPS = re.compile(r"(\d{1,3})\s*(?:inference\s+|sampling\s+)?steps", re.I)
CFG = re.compile(r"(?:cfg|guidance(?:\s+scale)?|adherence)\s*(?:scale)?\s*(?:of|[:=]|is)?\s*(\d{1,2}(?:\.\d+)?)", re.I)


def recommended(card_text):
    """{'steps': n, 'cfg': x} where the card recommends them, as for fast ("turbo") fine-tunes; may be empty."""
    found = {}
    near = [m.start() for m in re.finditer(r"recommend|suggest|default|use|best", card_text or "", re.I)]
    for key, pattern, kind in (("steps", STEPS, int), ("cfg", CFG, float)):
        for m in pattern.finditer(card_text or ""):
            if any(0 <= m.start() - n < 200 for n in near):
                value = kind(m.group(1))
                if (key == "steps" and 1 <= value <= 200) or (key == "cfg" and 0 < value <= 20):
                    found[key] = value
                    break
    return found


# the library

def library():
    out = []
    for folder in sorted(library_dir().glob("*")) if library_dir().exists() else ():
        try:
            info = json.loads((folder / INFO).read_text())
        except (OSError, ValueError):
            continue
        if transformer_weights(folder) is not None:
            out.append({**info, "id": folder.name, "path": str(folder)})
    return sorted(out, key=lambda i: i.get("name", "").lower())


def find(model_id):
    return next((i for i in library() if i["id"] == model_id), None)


def folder_bytes(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob("*") if p.is_file())


def add(source, info, move=False):
    """Put a checked model into the library: `source` is one .safetensors file (the image model) or a folder
    holding any of the model's parts. Returns the stored info; a model already there is not added twice."""
    source = Path(source)
    weights = source if source.is_file() else transformer_weights(source)
    if weights is None:
        raise ValueError("There is no image model (transformer) in that folder.")
    if weights.name.endswith(".index.json"):
        weights = sorted(weights.parent.glob("*.safetensors"))[0]
    digest = sha256(weights)
    for existing in library():
        if existing.get("sha256") == digest:
            return existing
    folder = library_dir() / f"{_slug(info.get('name', 'model'))}-{digest[:8]}"
    folder.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        (shutil.move if move else shutil.copyfile)(str(source), str(folder / SINGLE))
    else:
        for part in PARTS:
            if (source / part).is_dir():
                (shutil.move if move else shutil.copytree)(str(source / part), str(folder / part))
    stored = {"name": info.get("name") or source.stem, "trained_on": info.get("trained_on", ""),
              "license": info.get("license", ""), "source": info.get("source", {}),
              "recommended": info.get("recommended", {}), "sha256": digest, "added": round(time.time())}
    (folder / INFO).write_text(json.dumps(stored, indent=2, ensure_ascii=False) + "\n")
    return {**stored, "id": folder.name, "path": str(folder)}


def update(model_id, **fields):
    path = library_dir() / model_id / INFO
    info = json.loads(path.read_text())
    info.update(fields)
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")


def remove(model_id):
    shutil.rmtree(library_dir() / model_id, ignore_errors=True)


def display_name(model):
    """What to call a model in the interface and on a picture's card."""
    if is_library(model):
        info = find(library_id(model))
        return info.get("name", library_id(model)) if info else f"{library_id(model)} (not in your library)"
    return model.rstrip("/").rsplit("/", 1)[-1]
