"""Exact previews: decode the predicted clean latent x̂₀ with the real VAE, within a small time budget.

The pipeline's own decode is: un-normalize with the VAE's batch-norm statistics, unpatchify 2×2, VAE decode.
That recipe is reproduced here from the pipeline code shipped in moss_image.py, so previews are on from the first
picture; it is also checked once against what the pipeline actually feeds the VAE, and a mismatch turns them off.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)
BUDGET = 0.05            # at most this fraction of sampling time spent on exact previews
WINDOW = (0.3, 0.9)      # only between these fractions of the steps (earlier x̂₀ is too blurry to be worth it)


def to_vae_input(vae, latent):
    """[B, 4C, h, w] normalized latent → [B, C, 2h, 2w] VAE input."""
    import torch

    bn = vae.bn
    mean = bn.running_mean.view(1, -1, 1, 1)
    std = torch.sqrt(bn.running_var.view(1, -1, 1, 1) + vae.config.batch_norm_eps)
    z = latent.to(mean.dtype) * std + mean
    b, c, h, w = z.shape
    z = z.reshape(b, c // 4, 2, 2, h, w).permute(0, 1, 4, 2, 5, 3).reshape(b, c // 4, h * 2, w * 2)
    return z.to(vae.dtype)


class VaePreview:
    def __init__(self):
        self.verified = True      # False once the check finds a mismatch or a preview fails
        self.checked = False
        self.cost = 1.0           # seconds per preview decode, updated from measurements
        self._captured = None

    def watch_decode(self, vae):
        """Capture the pipeline's VAE input for the one-time check; returns an undo function."""
        if self.checked:
            return lambda: None
        original = vae.decode

        def decode(z, *args, **kwargs):
            self._captured = z.detach()
            return original(z, *args, **kwargs)

        vae.decode = decode
        return lambda: vae.__dict__.pop("decode", None)

    def check(self, vae, final_latent):
        if self.checked or self._captured is None or final_latent is None:
            return
        self.checked = True
        try:
            ours = to_vae_input(vae, final_latent)
            theirs = self._captured.to(ours.dtype)
            scale = theirs.abs().max().clamp_min(1e-6)
            self.verified = ours.shape == theirs.shape and bool(((ours - theirs).abs().max() / scale) < 1e-3)
        except Exception as exc:  # missing attributes etc.
            log.info("Exact previews unavailable (%s).", exc)
            self.verified = False
        self._captured = None
        log.info("Exact previews %s.", "enabled" if self.verified else "disabled (decode recipe mismatch)")

    def due(self, step, total, spent, step_seconds, nothing_shown=False):
        """Whether an exact preview fits the budget so far: it accrues with elapsed steps, spacing previews out.
        With nothing shown yet (no fast preview available) one is due halfway, whatever the budget."""
        if not self.verified or total <= 0 or not (WINDOW[0] <= step / total <= WINDOW[1]):
            return False
        return (nothing_shown and step / total >= 0.5) or spent + self.cost <= BUDGET * step_seconds * step

    def decode(self, vae, x0):
        import torch

        start = time.monotonic()
        with torch.no_grad():
            image = vae.decode(to_vae_input(vae, x0), return_dict=False)[0]
            rgb = ((image[0].float() / 2 + 0.5).clamp(0, 1).permute(1, 2, 0) * 255).round().byte().contiguous().cpu().numpy()
        self.cost = time.monotonic() - start
        return rgb
