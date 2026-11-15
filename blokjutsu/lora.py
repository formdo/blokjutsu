"""LoRAs: reading and checking .safetensors adapters, finding trigger words, the LoRA library, and attaching
LoRAs to the MOSS-Image transformer.

A LoRA adds, to some of the transformer's linear layers, a low-rank change ΔW = (α/r)·B·A, scaled by a
strength. The file names each layer; the check here requires every named layer to exist in MOSS-Image with
matching dimensions, so adapters made for other models are refused. MOSS-Image-Base and -SFT share their
structure, so a LoRA trained on either works with both.

Layers are wrapped, not changed: y = W·x + Σ sᵢ·(α/r)ᵢ·Bᵢ·(Aᵢ·x). Turning a LoRA off or changing its strength is
exact and needs no reload. Names follow Diffusers/PEFT (lora_A, lora_B) or kohya/ComfyUI (lora_down, lora_up,
alpha), with the usual prefixes.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import time
from pathlib import Path

from .settings import app_home

PREFIXES = ("base_model.model.", "model.diffusion_model.", "diffusion_model.", "transformer.", "model.",
            "lora_unet_", "lora_transformer_")
PARTS = {"lora_A": "A", "lora_B": "B", "lora_down": "A", "lora_up": "B", "lora.down": "A", "lora.up": "B"}
DEFAULT_CONFIG = dict(dim=3072, ffn_dim=8192, num_heads=24, num_layers=42, text_dim=4096, freq_dim=256,
                      latent_channels=128)
MAX_STRENGTH = 2.0
INFO = "info.json"
FILE = "lora.safetensors"


# the file

def read_header(path_or_read):
    """({tensor name: (dtype, shape)}, metadata) of a .safetensors file, from its path or a read(start, stop)."""
    read = path_or_read
    if not callable(read):
        def read(start, stop, path=path_or_read):
            with open(path, "rb") as f:
                f.seek(start)
                return f.read(stop - start)
    size = struct.unpack("<Q", read(0, 8))[0]
    if not 0 < size < 1 << 27:
        raise ValueError("This isn't a .safetensors file.")
    header = json.loads(read(8, 8 + size))
    metadata = header.pop("__metadata__", None) or {}
    return {k: (v["dtype"], tuple(v["shape"])) for k, v in header.items()}, metadata


def split_name(name):
    """'transformer.layers.0.proj.q.lora_A.weight' → ('layers.0.proj.q', 'A'); alpha tensors → (layer, 'alpha');
    anything else → (None, None)."""
    if name.endswith(".alpha"):
        return _strip(name[:-len(".alpha")]), "alpha"
    m = re.fullmatch(r"(.+)\.lokr_(w1|w2|w1_a|w1_b|w2_a|w2_b|t2)(?:\.weight)?", name)
    if m:
        return _strip(m.group(1)), m.group(2)
    m = re.fullmatch(r"(.+)\.hada_\w+", name)
    if m:
        return _strip(m.group(1)), "hada"
    for marker, part in PARTS.items():
        m = re.fullmatch(rf"(.+)\.{re.escape(marker)}(?:\.[\w-]+)?\.weight", name)
        if m:
            return _strip(m.group(1)), part
    return None, None


def _strip(module):
    changed = True
    while changed:
        changed = False
        for prefix in PREFIXES:
            if module.startswith(prefix):
                module, changed = module[len(prefix):], True
    return module


def linear_shapes(config=None):
    """{layer name: (out, in)} for every linear layer of the MOSS-Image transformer."""
    c = {**DEFAULT_CONFIG, **(config or {})}
    d, f, t = c["dim"], c["ffn_dim"], c["text_dim"]
    shapes = {"video_embedder": (d, c["latent_channels"]), "text_embedder.proj": (d, t),
              "time_embedding.0": (d, c["freq_dim"]), "time_embedding.2": (d, d),
              "shared_block_modulation": (6 * d, d), "final_linear_video": (c["latent_channels"], d),
              "video_head_modulation": (2 * d, d)}
    for b in range(2):
        shapes |= {f"text_embedder.blocks.{b}.qkv": (3 * d, d), f"text_embedder.blocks.{b}.proj": (d, d),
                   f"text_embedder.blocks.{b}.ffn_gate": (f, d), f"text_embedder.blocks.{b}.ffn_up": (f, d),
                   f"text_embedder.blocks.{b}.ffn_down": (d, f)}
    for i in range(c["num_layers"]):
        shapes |= {f"layers.{i}.proj.{n}": (d, d) for n in "qkvo"}
        shapes |= {f"layers.{i}.proj.ffn_up_gate": (2 * f, d), f"layers.{i}.proj.ffn_down": (d, f)}
    return shapes


def fused_layers(config=None):
    """Layers some trainers fuse into one: {fused name: [the model's layers, in order]}. Their B matrix is the
    model layers' B matrices stacked, with one shared A."""
    c = {**DEFAULT_CONFIG, **(config or {})}
    return {f"layers.{i}.proj.qkv": [f"layers.{i}.proj.{n}" for n in "qkv"] for i in range(c["num_layers"])}


def layers(tensors, config=None):
    """Check a LoRA's tensors against MOSS-Image. Returns {file layer: {'A': name, 'B': name, 'alpha': name?,
    'targets': [model layers]}} and the ranks used; raises ValueError, in words for the user, if it doesn't fit."""
    known = linear_shapes(config)
    targets = {name: [name] for name in known} | fused_layers(config)
    underscored = {name.replace(".", "_"): name for name in targets}
    found, other, unknown = {}, [], set()
    for name in tensors:
        module, part = split_name(name)
        if module is None:
            other.append(name)
            continue
        layer = module if module in targets else underscored.get(module)
        if layer is None:
            unknown.add(re.sub(r"\d+", "N", module))
            continue
        found.setdefault(layer, {"targets": targets[layer]})[part] = name
    if unknown:
        names = ", ".join(sorted(unknown)[:3]) + (", …" if len(unknown) > 3 else "")
        raise ValueError(f"This LoRA was made for a different model: it changes layers MOSS-Image doesn't have "
                         f"({names}).")
    if not found:
        raise ValueError("This file has no LoRA layers in it." if not other else
                         "This doesn't look like a LoRA: none of its tensors are LoRA layers.")
    ranks = set()
    for layer, parts in list(found.items()):
        if set(parts) <= {"targets", "alpha"}:
            del found[layer]                     # a scale with no weights (some trainers store one per q, k, v)
            continue
        out = sum(known[t][0] for t in parts["targets"])
        inp = known[parts["targets"][0]][1]
        if "hada" in parts:
            raise ValueError("This LoRA is a LoHa, a kind Blokjutsu can't use yet.")
        if "t2" in parts:
            raise ValueError("This LoRA is a LoKr with a Tucker core, a kind Blokjutsu can't use yet.")
        if any(k in parts for k in ("w1", "w1_a", "w2", "w2_a")):
            m, p = _factor(tensors, parts, "w1", layer)
            n, q = _factor(tensors, parts, "w2", layer)
            parts["kind"] = "lokr"
            if (m * n, p * q) != (out, inp):
                raise ValueError("This LoRA was made for a different model: its layer sizes don't match "
                                 f"MOSS-Image's ({layer}).")
            continue
        if "A" not in parts or "B" not in parts:
            names = [n for n in tensors if layer in _strip(n) or layer.replace(".", "_") in n][:4]
            raise ValueError(f"Blokjutsu can't read this LoRA's layer {layer}: it found only one of the two "
                             f"weights it needs. Its tensors for that layer are: {', '.join(names)}.")
        a, b = _shape(tensors[parts["A"]]), _shape(tensors[parts["B"]])
        if len(a) != 2 or len(b) != 2 or a[1] != inp or b[0] != out or a[0] != b[1]:
            raise ValueError("This LoRA was made for a different model: its layer sizes don't match "
                             f"MOSS-Image's ({layer}).")
        parts["kind"] = "lora"
        ranks.add(a[0])
    if not found:
        raise ValueError("This file has no LoRA layers in it.")
    return found, sorted(ranks)


def _factor(tensors, parts, w, layer):
    """The (rows, columns) of a LoKr factor: given whole (w1) or as a product (w1_a · w1_b)."""
    if w in parts:
        shape = _shape(tensors[parts[w]])
    elif f"{w}_a" in parts and f"{w}_b" in parts:
        a, b = _shape(tensors[parts[f"{w}_a"]]), _shape(tensors[parts[f"{w}_b"]])
        if len(a) != 2 or len(b) != 2 or a[1] != b[0]:
            raise ValueError(f"This LoRA's layer {layer} is damaged: its factors don't fit together.")
        shape = (a[0], b[1])
    else:
        raise ValueError(f"Blokjutsu can't read this LoRA's layer {layer}: part of it is missing.")
    if len(shape) != 2:
        raise ValueError(f"Blokjutsu can't read this LoRA's layer {layer}.")
    return shape


def _shape(value):
    """A tensor's shape from read_header's (dtype, shape), or the shape itself."""
    return tuple(value[1]) if value and isinstance(value[0], str) else tuple(value)


def model_config(snapshot_folder):
    """The transformer's config.json from a downloaded model, or None."""
    try:
        return json.loads((Path(snapshot_folder) / "transformer" / "config.json").read_text())
    except (OSError, ValueError, TypeError):
        return None


# what the card says

TRIGGER_KEYS = ("modelspec.trigger_phrase", "ss_trigger", "trigger_phrase", "trigger_word", "trigger",
                "instance_prompt")
TRIGGER_TEXT = re.compile(
    r"(?:trigger|activation|instance)[ \t]*(?:word|phrase|token|prompt)s?\b[^`\"'\n]{0,40}?[`\"“']([^`\"”'\n]{2,60})[`\"”']",
    re.IGNORECASE)
STRENGTH_TEXT = re.compile(
    r"(?:recommended|suggested|default)[^\n.]{0,30}?(?:lora[ \t]+)?(?:scale|strength|weight)[^\n0-9]{0,20}"
    r"(\d(?:\.\d+)?)", re.IGNORECASE)


def card_data_of(card_text):
    """The simple fields of a model card's YAML header (key: value, and key: followed by '- item' lines)."""
    m = re.match(r"\ufeff?---\s*\n(.*?)\n---", card_text or "", re.S)
    data, key = {}, None
    for line in (m.group(1).splitlines() if m else ()):
        item = re.match(r"\s*-\s+(.+)", line)
        if item and key:
            data.setdefault(key, []).append(item.group(1).strip().strip("'\""))
            continue
        pair = re.match(r"([A-Za-z_][\w-]*):\s*(.*)", line)
        if pair:
            key, value = pair.group(1), pair.group(2).strip().strip("'\"")
            if value:
                data[key] = value
    return data


def find_trigger(card_text="", card_data=None, metadata=None):
    """The trigger word, from the card's metadata, the file's metadata or the card's text; '' if none is given."""
    for source in (card_data or {}, metadata or {}):
        for key in TRIGGER_KEYS:
            value = source.get(key)
            if isinstance(value, list):
                value = value[0] if value else ""
            if isinstance(value, str) and value.strip():
                return value.strip()
    m = TRIGGER_TEXT.search(card_text or "")
    return m.group(1).strip() if m else ""


def find_strength(card_text=""):
    m = STRENGTH_TEXT.search(card_text or "")
    if m:
        value = float(m.group(1))
        if 0 < value <= MAX_STRENGTH:
            return value
    return 1.0


def trained_on(card_data=None):
    base = (card_data or {}).get("base_model")
    if isinstance(base, list):
        base = base[0] if base else ""
    return base or ""


def repo_of(text):
    """'owner/name' from a Hugging Face link or id, or None."""
    text = text.strip()
    m = re.match(r"(?:https?://)?(?:www\.)?(?:huggingface\.co|hf\.co)/([\w.-]+/[\w.-]+)", text)
    if m:
        return m.group(1)
    return text if re.fullmatch(r"[\w.-]+/[\w.-]+", text) else None


def pick_file(files):
    """The adapter to download from a repo's [(name, size)]: Diffusers/PEFT weights first, never a ComfyUI copy."""
    candidates = [(n, s) for n, s in files if n.endswith(".safetensors")]
    for n, s in candidates:
        if n.rsplit("/", 1)[-1] == "pytorch_lora_weights.safetensors":
            return n, s
    plain = [(n, s) for n, s in candidates if "comfy" not in n.lower()]
    return min(plain or candidates, key=lambda f: (f[0].count("/"), f[0]), default=(None, None))


def alpha_from(adapter_config):
    """(alpha, rank) from a PEFT adapter_config.json, if it gives them."""
    if not adapter_config:
        return None
    alpha, rank = adapter_config.get("lora_alpha"), adapter_config.get("r")
    return (float(alpha), int(rank)) if alpha and rank else None


# the library: one folder per LoRA under the app's home, holding the file and what is known about it

def library_dir():
    return app_home() / "loras"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(name):
    return re.sub(r"[^\w-]+", "-", name).strip("-").lower()[:40] or "lora"


def library():
    """Every LoRA added, as info dicts with 'id' and 'path', by name."""
    out = []
    for folder in sorted(library_dir().glob("*")) if library_dir().exists() else ():
        try:
            info = json.loads((folder / INFO).read_text())
        except (OSError, ValueError):
            continue
        if (folder / FILE).exists():
            out.append({**info, "id": folder.name, "path": str(folder / FILE)})
    return sorted(out, key=lambda i: i.get("name", "").lower())


def find(lora_id=None, digest=None):
    for info in library():
        if info["id"] == lora_id or (digest and info.get("sha256") == digest):
            return info
    return None


def add(source_file, info, move=False):
    """Copy (or move) a checked LoRA file into the library with its info; returns the stored info. A file already
    in the library (same contents) is not added twice."""
    digest = sha256(source_file)
    if existing := find(digest=digest):
        return existing
    folder = library_dir() / f"{_slug(info.get('name', 'lora'))}-{digest[:8]}"
    folder.mkdir(parents=True, exist_ok=True)
    (shutil.move if move else shutil.copyfile)(str(source_file), str(folder / FILE))
    stored = {"name": info.get("name") or Path(source_file).stem, "trigger": info.get("trigger", ""),
              "strength": info.get("strength", 1.0), "trained_on": info.get("trained_on", ""),
              "license": info.get("license", ""), "source": info.get("source", {}), "alpha": info.get("alpha"),
              "ranks": info.get("ranks", []), "sha256": digest, "added": round(time.time())}
    (folder / INFO).write_text(json.dumps(stored, indent=2, ensure_ascii=False) + "\n")
    return {**stored, "id": folder.name, "path": str(folder / FILE)}


def update(lora_id, **fields):
    path = library_dir() / lora_id / INFO
    info = json.loads(path.read_text())
    info.update(fields)
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")


def remove(lora_id):
    shutil.rmtree(library_dir() / lora_id, ignore_errors=True)


# a picture's LoRAs: [{"id", "name", "sha256", "strength", "trigger"}] as JSON in Params.loras

def entries(text):
    try:
        value = json.loads(text) if text else []
    except ValueError:
        return []
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def dumps(items):
    return json.dumps(items, ensure_ascii=False, separators=(",", ":")) if items else ""


def entry(info, strength=None):
    return {"id": info["id"], "name": info.get("name", ""), "sha256": info.get("sha256", ""),
            "strength": info.get("strength", 1.0) if strength is None else strength,
            "trigger": info.get("trigger", "")}


def locate(e):
    """The library's info for a picture's LoRA entry (by contents first, then id), or None."""
    return find(digest=e.get("sha256")) or find(lora_id=e.get("id"))


def check_entries(text):
    """Raise ValueError if a picture's LoRAs can't be used: strength out of range, or not in the library."""
    for e in entries(text):
        s = e.get("strength", 1.0)
        if not (isinstance(s, (int, float)) and -MAX_STRENGTH <= s <= MAX_STRENGTH):
            raise ValueError(f"The strength of LoRA {e.get('name')} must be between −2 and 2.")
        if locate(e) is None:
            raise ValueError(f"The LoRA “{e.get('name')}” isn't in your LoRAs any more. Add it again "
                             "(LoRAs → Add LoRA…), or turn it off.")


# attaching to the transformer (torch)

def load_weights(path, adapter_config=None):
    """{model layer: [terms]} from a LoRA file (CPU tensors). A term is ("lora", A, B, α/r, None) or, for LoKr,
    ("kron", W1, W2, scale, (first, last)), whose change is the rows first:last of W1 ⊗ W2 (all of them unless the
    file's layer is several fused model layers)."""
    from safetensors.torch import load_file

    tensors = load_file(path)
    shapes = {k: (str(v.dtype), tuple(v.shape)) for k, v in tensors.items()}
    found, _ = layers(shapes)
    known = linear_shapes()
    default_alpha = alpha_from(adapter_config)

    def alpha_of(parts):
        name = parts.get("alpha")
        return float(tensors[name].float().reshape(-1)[0]) if name else None

    out = {}
    for parts in found.values():
        sizes = [known[t][0] for t in parts["targets"]]
        if parts["kind"] == "lora":
            a, b = tensors[parts["A"]], tensors[parts["B"]]
            rank = a.shape[0]
            alpha = alpha_of(parts)
            if alpha is None:
                alpha = default_alpha[0] * rank / default_alpha[1] if default_alpha else float(rank)
            for target, chunk in zip(parts["targets"], b.split(sizes)):    # a fused layer's B, one block each
                out.setdefault(target, []).append(("lora", a, chunk, alpha / rank, None))
            continue
        w1 = tensors[parts["w1"]] if "w1" in parts else tensors[parts["w1_a"]] @ tensors[parts["w1_b"]]
        w2 = tensors[parts["w2"]] if "w2" in parts else tensors[parts["w2_a"]] @ tensors[parts["w2_b"]]
        dim = (tensors[parts["w1_b"]].shape[0] if "w1_b" in parts else
               tensors[parts["w2_b"]].shape[0] if "w2_b" in parts else None)
        alpha = alpha_of(parts)
        scale = alpha / dim if alpha and dim else 1.0          # as LyCORIS: whole factors take no α
        start = 0
        for target, size in zip(parts["targets"], sizes):
            out.setdefault(target, []).append(("kron", w1, w2, scale, (start, start + size)))
            start += size
    return out


_WRAPPER = []


def wrapper_class():
    """The wrapping layer class, made once (torch is imported only when LoRAs are used)."""
    if _WRAPPER:
        return _WRAPPER[0]
    import torch
    from torch import nn

    class LoraLinear(nn.Module):
        """A linear layer plus its LoRAs: low-rank changes stacked into one pair of matrices, and LoKr changes
        (W1 ⊗ W2)·x computed as W1 · X · W2ᵀ with x reshaped to X, never as the full matrix."""

        def __init__(self, base):
            super().__init__()
            self.base = base
            self.register_buffer("down", torch.zeros(0, base.in_features, dtype=base.weight.dtype,
                                                     device=base.weight.device), persistent=False)
            self.register_buffer("up", torch.zeros(base.out_features, 0, dtype=base.weight.dtype,
                                                   device=base.weight.device), persistent=False)
            self.krons = []

        @property
        def weight(self):
            return self.base.weight

        @property
        def bias(self):
            return self.base.bias

        def set(self, terms):
            """terms: [(kind, X, Y, factor, rows)] as from load_weights, factor including the strength."""
            w = self.base.weight
            pairs = [(a, b, f) for kind, a, b, f, _ in terms if kind == "lora"]
            self.down = torch.cat([a.to(w.device, w.dtype) * f for a, _, f in pairs]) if pairs else self.down[:0]
            self.up = torch.cat([b.to(w.device, w.dtype) for _, b, _ in pairs], 1) if pairs else self.up[:, :0]
            self.krons = [(w1.to(w.device, w.dtype) * f, w2.to(w.device, w.dtype), rows)
                          for kind, w1, w2, f, rows in terms if kind == "kron"]

        def forward(self, x):
            y = self.base(x)
            if self.up.shape[1]:
                y = y + nn.functional.linear(nn.functional.linear(x, self.down), self.up)
            for w1, w2, (first, last) in self.krons:
                change = (w1 @ x.unflatten(-1, (w1.shape[1], w2.shape[1])) @ w2.T).flatten(-2)
                y = y + change[..., first:last]
            return y

    _WRAPPER.append(LoraLinear)
    return LoraLinear


def attach(transformer, loaded):
    """Put LoRAs on the transformer: loaded = [(weights from load_weights, strength)]. An empty list takes them all
    off, leaving the original layers in place."""
    LoraLinear = wrapper_class()
    per_layer = {}
    for weights, strength in loaded:
        for layer, terms in weights.items():
            per_layer.setdefault(layer, []).extend((k, a, b, strength * f, r) for k, a, b, f, r in terms)
    modules = dict(transformer.named_modules())
    for name, module in list(modules.items()):
        if isinstance(module, LoraLinear) and name not in per_layer:
            _replace(transformer, name, module.base)
    for name, terms in per_layer.items():
        module = transformer.get_submodule(name)
        if not isinstance(module, LoraLinear):
            module = LoraLinear(module)
            _replace(transformer, name, module)
        module.set(terms)


def _replace(root, name, new):
    parent_name, _, child = name.rpartition(".")
    parent = root.get_submodule(parent_name) if parent_name else root
    parent._modules[child] = new          # works for plain modules, ModuleDict, ModuleList and Sequential
