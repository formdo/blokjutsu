"""Generation parameters, validation, and the parameters.json record (schema 2, repo-compatible)."""
from __future__ import annotations

import json
import math
import secrets
from dataclasses import asdict, dataclass, fields, replace

MODELS = {
    "MOSS-Image-SFT": "OpenMOSS-Team/MOSS-Image-SFT",
    "MOSS-Image-Base": "OpenMOSS-Team/MOSS-Image-Base",
}
DEFAULT_MODEL = MODELS["MOSS-Image-SFT"]
# Tested model versions (Hugging Face commit hashes). Downloads fetch exactly these, and the app loads exactly
# these, so an upstream change can't alter the app. The pipeline code is copied from the SFT revision into
# moss_image.py (scripts/vendor_moss.py). None: newest.
MODEL_REVISIONS = {
    "OpenMOSS-Team/MOSS-Image-SFT": "2c7954437269461767f533b006823e8f85973a60",
}


def model_revision(model):
    return MODEL_REVISIONS.get(model)
SEED_MAX = 2**32 - 1
DEFAULT_VARIATION = 0.2
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Params:
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 512
    height: int = 768
    steps: int = 20
    cfg: float = 4.0
    seed: int = 0
    num_images: int = 1
    model: str = DEFAULT_MODEL
    sampler: str = "Euler"
    shift: float = 5.0
    uncond_skip_layers: str = "22"
    slg_layers: str = ""
    slg_scale: float = 0.0
    slg_start: float = 0.0
    slg_stop: float = 1.0
    max_sequence_length: int = 4096
    noise_device: str = "cpu"
    compile_transformer: bool = True
    sde_eta: float = 0.5
    variation: float = 0.0          # strength s of the newest variation; 0 = none
    variation_seed: int = 0         # 0 = random per image
    variation_base: str = ""        # earlier variations, "seed:strength;..." applied in order before this one
    init_image: str = ""            # image-to-image input (path); "" = text-to-image
    init_strength: float = 0.5      # how much the input may change: σ₀ of the noise path
    mask_image: str = ""            # inpainting: path to a grayscale PNG framed like init_image; white is
                                    # regenerated, black kept, gray (the feathered edge) blended


ADVANCED = ("model", "sampler", "shift", "uncond_skip_layers", "slg_layers", "slg_scale",
            "slg_start", "slg_stop", "max_sequence_length", "noise_device", "compile_transformer", "sde_eta")
FIELD_NAMES = tuple(f.name for f in fields(Params))


def parse_layers(text):
    text = str(text).strip()
    if not text:
        return ()
    try:
        layers = tuple(int(s) for s in text.replace(" ", "").split(","))
    except ValueError as exc:
        raise ValueError(f"Layer list must be comma-separated integers, got {text!r}.") from exc
    if any(i < 0 for i in layers) or len(set(layers)) != len(layers):
        raise ValueError("Layer indices must be nonnegative and distinct.")
    return layers


def validate(p, num_layers=None):
    if not p.prompt.strip():
        raise ValueError("Enter a prompt.")
    if p.width <= 0 or p.height <= 0 or p.width % 16 or p.height % 16:
        raise ValueError("Width and height must be positive multiples of 16.")
    if p.steps < 1 or p.num_images < 1:
        raise ValueError("Steps and number of images must be positive.")
    if not (math.isfinite(p.cfg) and p.cfg >= 0):
        raise ValueError("CFG must be finite and nonnegative.")
    if not (math.isfinite(p.shift) and p.shift > 0):
        raise ValueError("Shift must be finite and positive.")
    if not 0 <= p.seed <= SEED_MAX:
        raise ValueError(f"Seed must be in [0, {SEED_MAX}]; 0 means random.")
    if p.init_image:
        from pathlib import Path
        if not Path(p.init_image).is_file():
            raise ValueError(f"Input image not found: {p.init_image}")
        if not 0 < p.init_strength <= 1:
            raise ValueError("Change must be in (0, 1].")
    if p.mask_image:
        from pathlib import Path
        if not p.init_image:
            raise ValueError("A mask needs an input image.")
        if not Path(p.mask_image).is_file():
            raise ValueError(f"Mask not found: {p.mask_image}")
    if not 0 <= p.variation <= 1:
        raise ValueError("Variation must be in [0, 1].")
    if not 0 <= p.sde_eta <= 1:
        raise ValueError("SDE noise η must be in [0, 1].")
    if not 1 <= p.max_sequence_length <= 4096:
        raise ValueError("Max sequence length must be in [1, 4096].")
    if not (math.isfinite(p.slg_scale) and p.slg_scale >= 0):
        raise ValueError("SLG scale must be finite and nonnegative.")
    if not 0 <= p.slg_start <= p.slg_stop <= 1:
        raise ValueError("Require 0 ≤ skip start ≤ skip stop ≤ 1.")
    layers = parse_layers(p.uncond_skip_layers) + parse_layers(p.slg_layers)
    if num_layers is not None and any(i >= num_layers for i in layers):
        raise ValueError(f"Layer indices must be below {num_layers}.")


def layout_warnings(p):
    """Soft checks for JSON layout prompts; returns (parse_error | None, [warnings])."""
    text = p.prompt.strip()
    if not text.startswith("{"):
        return None, []
    try:
        layout = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"line {exc.lineno}, column {exc.colno}: {exc.msg}", []
    if layout.get("bbox_coord_space") != "abs_centralized":
        return None, []
    boxes = [e.get("bbox") for key in ("items", "elements") for e in layout.get(key, []) if isinstance(e, dict)]
    boxes = [b for b in boxes if isinstance(b, list) and len(b) == 4]
    if not boxes:
        return None, []
    ymax = max(max(abs(b[0]), abs(b[2])) for b in boxes)
    xmax = max(max(abs(b[1]), abs(b[3])) for b in boxes)
    hh, hw = p.height / 2, p.width / 2
    if ymax > hh or xmax > hw:
        return None, [f"Layout boxes extend to ±{xmax:g}×±{ymax:g} but the canvas is ±{hw:g}×±{hh:g}; "
                      f"layout coordinates are pixels, so width/height should match the layout."]
    if ymax < 0.8 * hh and xmax < 0.8 * hw:
        return None, [f"Layout boxes span only ±{xmax:g}×±{ymax:g} of a ±{hw:g}×±{hh:g} canvas; "
                      f"was the layout written for a smaller image?"]
    return None, []


def realize(p):
    """Expand a request into single-image jobs with concrete seeds.

    Without variations, images get consecutive seeds. With variations, every image keeps the same seed and gets
    its own variation seed (consecutive from the given one, or random if 0).
    """
    def concrete(seed, i):
        return (seed - 1 + i) % SEED_MAX + 1

    base = p.seed or secrets.randbelow(SEED_MAX) + 1
    if p.variation <= 0:
        return [replace(p, seed=concrete(base, i), num_images=1, variation_seed=0) for i in range(p.num_images)]
    if p.variation_seed:
        seeds = [concrete(p.variation_seed, i) for i in range(p.num_images)]
    else:
        seeds = list({secrets.randbelow(SEED_MAX) + 1: None for _ in range(4 * p.num_images)})[:p.num_images]
    return [replace(p, seed=base, num_images=1, variation_seed=s) for s in seeds]


def variation_chain(p):
    """[(seed, strength), ...] to apply to the base noise, oldest first, including this image's own."""
    chain = [(int(a), float(b)) for a, b in (link.split(":") for link in p.variation_base.split(";") if link)]
    if p.variation > 0 and p.variation_seed:
        chain.append((p.variation_seed, p.variation))
    return chain


def vary_from(p, strength, count):
    """Settings for `count` new variations of the image p describes (its own variation becomes the base)."""
    base = ";".join(f"{s}:{v:g}" for s, v in variation_chain(p))
    return replace(p, variation=strength, variation_seed=0, variation_base=base, num_images=count)


def pipeline_kwargs(p):
    return dict(
        prompt=p.prompt, negative_prompt=p.negative_prompt, width=p.width, height=p.height,
        num_inference_steps=p.steps, guidance_scale=p.cfg, num_images_per_prompt=1,
        max_sequence_length=p.max_sequence_length,
        uncond_skip_layers=parse_layers(p.uncond_skip_layers), slg_layers=parse_layers(p.slg_layers),
        slg_scale=p.slg_scale, slg_start=p.slg_start, slg_stop=p.slg_stop,
    )


def model_name(model):
    return model.rstrip("/").rsplit("/", 1)[-1]


_REPO_KEYS = ("prompt", "negative_prompt", "height", "width", "steps", "cfg", "shift", "num_images", "seed",
              "uncond_skip_layers", "slg_layers", "slg_scale", "slg_start", "slg_stop",
              "max_sequence_length", "compile_transformer")


def to_record(p, image_name="image.png", **extra):
    parameters = {k: getattr(p, k) for k in _REPO_KEYS}
    parameters["offload"] = "none"
    return {
        "schema_version": SCHEMA_VERSION,
        "model_repo": p.model,
        "model": model_name(p.model),
        "parameters": parameters,
        "sampler": p.sampler,
        "image": image_name,
        "blokjutsu": {"noise_device": p.noise_device, "sde_eta": p.sde_eta, "variation": p.variation,
                   "variation_seed": p.variation_seed, "variation_base": p.variation_base,
                   "init_image": p.init_image, "init_strength": p.init_strength, "mask_image": p.mask_image,
                   **extra},
    }


def _coerce(name, value):
    kind = type(getattr(Params(), name))
    if kind is str and isinstance(value, (list, tuple)):
        return ",".join(map(str, value))
    if kind is bool:
        return bool(value)
    return kind(value)


def from_record(record):
    """Read parameters.json from this app, the Gradio app, or the repo's example assets."""
    version = record.get("schema_version", 1)
    if version not in (1, 2):
        raise ValueError(f"Unsupported schema_version {version}.")
    raw = dict(record.get("parameters", {}))
    if version == 1:
        layers = raw.pop("slg_layers", "")
        raw["uncond_skip_layers"] = layers if raw.pop("slg", True) else ""
    if raw.get("seed") in (None, -1):
        raw["seed"] = 0
    raw["model"] = record.get("model_repo") or MODELS.get(record.get("model"), record.get("model") or DEFAULT_MODEL)
    raw["sampler"] = record.get("sampler", "Euler")
    raw.update({k: v for k, v in record.get("blokjutsu", {}).items() if k in FIELD_NAMES})
    return Params(**{k: _coerce(k, v) for k, v in raw.items() if k in FIELD_NAMES})


def to_json(p):
    return json.dumps(asdict(p), ensure_ascii=False)


def from_json(text):
    raw = json.loads(text)
    return Params(**{k: _coerce(k, v) for k, v in raw.items() if k in FIELD_NAMES})
