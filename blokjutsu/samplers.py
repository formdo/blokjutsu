"""Scheduler choices. MOSS-Image is a rectified-flow (velocity) model, so only flow-matching schedulers apply.

Euler SDE is the stochastic analogue of DDIM-η for the linear path x_σ = (1−σ)x₀ + σε: from the model's
velocity v at (x, σ), take x̂₀ = x − σv and ε̂ = x + (1−σ)v, then
    x_σ' = (1−σ')x̂₀ + σ'(√(1−η²) ε̂ + η z),   z ~ N(0, I).
η = 0 is exactly the deterministic Euler step; η = 1 replaces the predicted noise by fresh noise (ancestral).
"""
from __future__ import annotations

import inspect
import math


def _euler(native, shift):
    cls = type(native)
    accepted = inspect.signature(cls.__init__).parameters
    if any(p.kind is p.VAR_KEYWORD for p in accepted.values()):
        return cls.from_config(native.config, shift=shift)
    return cls.from_config({k: v for k, v in native.config.items() if k in accepted}, shift=shift)


def _multistep(cls_name, **kwargs):
    def make(native, shift):
        import diffusers
        cls = getattr(diffusers, cls_name)
        return cls(num_train_timesteps=native.config.num_train_timesteps, use_flow_sigmas=True,
                   prediction_type="flow_prediction", flow_shift=shift, **kwargs)
    return make


SAMPLERS = {
    "Euler": _euler,
    "Euler SDE": _euler,
    "DPM++ 2M": _multistep("DPMSolverMultistepScheduler", algorithm_type="dpmsolver++", solver_order=2),
    "UniPC": _multistep("UniPCMultistepScheduler"),
}


def add_sde_noise(scheduler, eta, seed):
    """Wrap a flow-matching Euler scheduler's step with η-controlled re-noising (see module docstring)."""
    import torch

    original = scheduler.step
    generator = torch.Generator("cpu").manual_seed((seed + 0x5DE) % 2**63)
    keep = math.sqrt(max(0.0, 1.0 - eta * eta))

    def step(model_output, timestep, sample, *args, **kwargs):
        out = original(model_output, timestep, sample, *args, **kwargs)
        i = scheduler.step_index - 1
        sigma, sigma_next = float(scheduler.sigmas[i]), float(scheduler.sigmas[i + 1])
        if sigma_next <= 0 or eta <= 0:
            return out
        v, x = model_output.float(), sample.float()
        x0, eps = x - sigma * v, x + (1 - sigma) * v
        z = torch.randn(x.shape, generator=generator).to(x.device)
        prev = out[0] if isinstance(out, tuple) else out.prev_sample
        nxt = ((1 - sigma_next) * x0 + sigma_next * (keep * eps + eta * z)).to(prev.dtype)
        if isinstance(out, tuple):
            return (nxt, *out[1:])
        out.prev_sample = nxt
        return out

    scheduler.step = step
    return scheduler


def make_scheduler(name, native, shift, eta=0.0, seed=0):
    try:
        scheduler = SAMPLERS[name](native, shift)
    except KeyError:
        raise ValueError(f"Unknown sampler {name!r}; choose one of {', '.join(SAMPLERS)}.") from None
    return add_sde_noise(scheduler, eta, seed) if name == "Euler SDE" else scheduler
