"""Live previews from a linear latent→RGB patch decoder, fitted online from the app's own finished images.

Each latent position (C channels at 1/16 resolution) maps affinely to its 16×16×3 pixel patch:
    patch ≈ [z, 1] W,   W ∈ R^{(C+1)×768},
estimated by ridge regression from accumulated sufficient statistics (XᵀX, XᵀY) over (final latent, decoded
image) pairs. Applied to the flow model's x̂₀ = x_t − σ v at each step, it costs one small matmul per preview,
versus a full VAE decode.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

PATCH = 16
RIDGE = 1e-4


def patches(image):
    """(H, W, 3) uint8 → (H/16 · W/16, 768) float in [0, 1]."""
    h, w = image.shape[0] // PATCH, image.shape[1] // PATCH
    x = image[:h * PATCH, :w * PATCH].reshape(h, PATCH, w, PATCH, 3).transpose(0, 2, 1, 3, 4)
    return x.reshape(h * w, PATCH * PATCH * 3).astype(np.float64) / 255.0


def design(latent):
    """(C, h, w) → (h·w, C+1) with intercept column."""
    c = latent.shape[0]
    x = latent.reshape(c, -1).T.astype(np.float64)
    return np.hstack([x, np.ones((x.shape[0], 1))])


class LinearPreview:
    def __init__(self, path):
        self.path = Path(path)
        self.xtx = self.xty = self.weights = None
        self.count = 0
        try:
            saved = np.load(self.path)
            self.xtx, self.xty, self.count = saved["xtx"], saved["xty"], int(saved["count"])
            self._solve()
        except Exception:  # missing, partial or incompatible file: start afresh
            pass

    @property
    def ready(self):
        return self.weights is not None

    def add(self, latent, image):
        """latent (C, h, w) float; image (h·16, w·16, 3) uint8."""
        x, y = design(latent), patches(image)
        if x.shape[0] != y.shape[0]:
            return
        if self.xtx is not None and self.xtx.shape[0] != x.shape[1]:
            self.xtx = self.xty = None
            self.count = 0
        if self.xtx is None:
            self.xtx, self.xty = x.T @ x, x.T @ y
        else:
            self.xtx += x.T @ x
            self.xty += x.T @ y
        self.count += 1
        self._solve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            np.savez(f, xtx=self.xtx, xty=self.xty, count=self.count)
        tmp.replace(self.path)

    def _solve(self):
        k = self.xtx.shape[0]
        penalty = RIDGE * np.trace(self.xtx) / k * np.eye(k)
        self.weights = np.linalg.solve(self.xtx + penalty, self.xty).astype(np.float32)

    def decode(self, latent):
        """(C, h, w) → (h·16, w·16, 3) uint8."""
        c, h, w = latent.shape
        x = np.hstack([latent.reshape(c, -1).T.astype(np.float32), np.ones((h * w, 1), np.float32)])
        y = np.clip(x @ self.weights, 0, 1).reshape(h, w, PATCH, PATCH, 3).transpose(0, 2, 1, 3, 4)
        return np.ascontiguousarray((y.reshape(h * PATCH, w * PATCH, 3) * 255).astype(np.uint8))
