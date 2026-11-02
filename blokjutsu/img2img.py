"""Image-to-image (SDEdit) for a rectified-flow model.

Encode the input to the normalized latent z₀, put it on the noise path at σ₀ = strength,
    x_σ₀ = (1 − σ₀)·z₀ + σ₀·ε,
and run only the solver steps with σ ≤ σ₀. Low strength keeps the input; strength 1 is plain text-to-image.

With a mask (inpainting/outpainting) the masked region follows that path while the rest is reset after every
step to the input on its own noise path, and the input's pixels are pasted back outside the feathered mask.

Latent conventions are the inverse of the pipeline's decode (verified at run time by vae_preview):
normalize with the VAE batch-norm statistics after a 2×2 patchify.
"""
from __future__ import annotations

from PIL import Image, ImageOps

MIN_STRENGTH = 0.02


def cover(image, width, height):
    """Upright (EXIF), scaled to cover width×height and center-cropped: no distortion, no borders."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    return ImageOps.fit(image, (width, height), Image.LANCZOS, centering=(0.5, 0.5))


def oriented_size(path):
    """(width, height) as displayed, i.e. after EXIF rotation."""
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).size


def fit_size(width, height, max_megapixels=2.1, multiple=16):
    """Output size with the input's aspect ratio, area at most max_megapixels, sides multiples of 16."""
    scale = min(1.0, (max_megapixels * 1e6 / (width * height)) ** 0.5)
    return tuple(max(multiple, int(round(side * scale / multiple)) * multiple) for side in (width, height))


def patchify(z):
    """[B, C, 2h, 2w] → [B, 4C, h, w]; exact inverse of the pipeline's unpatchify. Works on torch and numpy."""
    b, c, hh, ww = z.shape
    z = z.reshape(b, c, hh // 2, 2, ww // 2, 2)
    z = z.permute(0, 1, 3, 5, 2, 4) if hasattr(z, "permute") else z.transpose(0, 1, 3, 5, 2, 4)
    return z.reshape(b, c * 4, hh // 2, ww // 2)


def unpatchify(z):
    """[B, 4C, h, w] → [B, C, 2h, 2w], as the pipeline does before VAE decode."""
    b, c, h, w = z.shape
    z = z.reshape(b, c // 4, 2, 2, h, w)
    z = z.permute(0, 1, 4, 2, 5, 3) if hasattr(z, "permute") else z.transpose(0, 1, 4, 2, 5, 3)
    return z.reshape(b, c // 4, h * 2, w * 2)


def encode(vae, image):
    """PIL image (already at the output size) → normalized latent [1, 4C, H/16, W/16] (fp32, on the VAE's device)."""
    import numpy as np
    import torch

    pixels = torch.from_numpy(np.asarray(image, dtype=np.float32) / 127.5 - 1.0).permute(2, 0, 1)[None]
    pixels = pixels.to(device=vae.device, dtype=vae.dtype)
    with torch.no_grad():
        posterior = vae.encode(pixels).latent_dist
        z = patchify(posterior.mode().float())
    bn = vae.bn
    mean = bn.running_mean.view(1, -1, 1, 1).float()
    std = torch.sqrt(bn.running_var.view(1, -1, 1, 1).float() + vae.config.batch_norm_eps)
    return (z - mean) / std


def start_index(sigmas, strength):
    """First solver step whose σ is at most the strength (σ₀); sigmas include the terminal 0."""
    strength = max(MIN_STRENGTH, min(1.0, strength))
    for i, sigma in enumerate(sigmas[:-1]):
        if float(sigma) <= strength + 1e-6:
            return i
    return len(sigmas) - 2


def truncate_schedule(scheduler, strength):
    """Make scheduler.set_timesteps drop the steps above σ₀. Returns a dict filled with the start σ."""
    original = scheduler.set_timesteps
    info = {}

    def set_timesteps(*args, **kwargs):
        original(*args, **kwargs)
        k = start_index(scheduler.sigmas, strength)
        scheduler.timesteps = scheduler.timesteps[k:]
        scheduler.sigmas = scheduler.sigmas[k:]
        scheduler._step_index = None
        scheduler._begin_index = None
        info["sigma"] = float(scheduler.sigmas[0])
        info["steps"] = len(scheduler.timesteps)

    scheduler.set_timesteps = set_timesteps
    return info


# inpainting: regenerate only where the mask is white, keep the rest on the input's own noise path

def mask_array(path, width, height):
    """Mask as float32 [height, width] in [0, 1], framed exactly like the input (cover)."""
    import numpy as np

    with Image.open(path) as mask:
        mask = ImageOps.fit(ImageOps.exif_transpose(mask).convert("L"), (width, height), Image.LANCZOS,
                            centering=(0.5, 0.5))
    return np.asarray(mask, dtype=np.float32) / 255.0


def latent_mask(mask, factor=16, grow=1):
    """[H, W] pixel mask → [H/16, W/16] cell mask: a cell is regenerated if any of its pixels is, then grown by
    `grow` cells so the pixel composite's feathered edge lies inside regenerated latent."""
    import numpy as np

    h, w = mask.shape[0] // factor, mask.shape[1] // factor
    cells = (mask[:h * factor, :w * factor].reshape(h, factor, w, factor).max(axis=(1, 3)) > 0.02)
    cells = cells.astype(np.float32)
    for _ in range(grow):
        padded = np.pad(cells, 1)
        cells = np.max([padded[i:i + h, j:j + w] for i in range(3) for j in range(3)], axis=0)
    return cells


def keep_known(scheduler, z0, eps, cells):
    """After each solver step, reset unmasked latent cells to the input at the next σ: (1 − σ)·z₀ + σ·ε."""
    original = scheduler.step
    count = [0]

    def step(model_output, timestep, sample, *args, **kwargs):
        out = original(model_output, timestep, sample, *args, **kwargs)
        prev = out[0] if isinstance(out, tuple) else out.prev_sample
        count[0] += 1
        sigma = float(scheduler.sigmas[min(count[0], len(scheduler.sigmas) - 1)])
        known = (1 - sigma) * z0 + sigma * eps
        prev.copy_((cells * prev + (1 - cells) * known).to(prev.dtype))
        return out

    scheduler.step = step


def composite(result, source, mask):
    """Paste the input back outside the (feathered) mask, so untouched pixels are exactly the input's."""
    import numpy as np

    m = mask[..., None]
    out = m * np.asarray(result, dtype=np.float32) + (1 - m) * np.asarray(source, dtype=np.float32)
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8))


def feather(mask, radius):
    """Soften a 0/1 mask's edge by a Gaussian of `radius` pixels (float32 in, float32 out)."""
    import numpy as np
    from PIL import ImageFilter

    if radius <= 0:
        return mask
    image = Image.fromarray(np.clip(mask * 255 + 0.5, 0, 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def reframe(image, left, top, right, bottom, blur=24):
    """Extend (positive) or crop (negative) each side. The added area starts as the picture's edges stretched and
    blurred (a color-plausible start). Returns (canvas, mask) with mask 1 on the added area."""
    import numpy as np
    from PIL import ImageFilter

    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    pl, pt, pr, pb = (max(0, m) for m in (left, top, right, bottom))
    array = np.pad(np.asarray(image), ((pt, pb), (pl, pr), (0, 0)), mode="edge")
    canvas = Image.fromarray(array)
    if blur and (pl or pt or pr or pb):
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
        canvas.paste(image, (pl, pt))
    mask = np.ones(array.shape[:2], dtype=np.float32)
    mask[pt:pt + h, pl:pl + w] = 0.0
    x0, y0 = max(0, -left), max(0, -top)
    x1, y1 = array.shape[1] - max(0, -right), array.shape[0] - max(0, -bottom)
    return canvas.crop((x0, y0, x1, y1)), mask[y0:y1, x0:x1]


def place(dst, src, x, y):
    """Write array `src` into `dst` with its top-left corner at (x, y), clipped to `dst`."""
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = src[y0 - y:y1 - y, x0 - x:x1 - x]
    return dst
