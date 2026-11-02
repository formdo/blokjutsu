"""Pipeline lifecycle and single-image generation. torch/diffusers are imported lazily, off the GUI thread."""
from __future__ import annotations

import importlib.metadata
import os
import time
import types
from pathlib import Path

import logging

from . import params as P
from . import img2img as I
from .preview import LinearPreview
from .vae_preview import VaePreview
from .samplers import make_scheduler
from .settings import app_home
from .moss_forward import mps_transformer_forward, reset_step_cache

PREVIEW_INTERVAL = 0.5   # seconds between live previews
log = logging.getLogger(__name__)


class Cancelled(Exception):
    pass


def pick_device():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


def compile_blocks(transformer, device):
    """Compile the repeated transformer blocks (where the time goes); the outer forward stays eager."""
    backend = "aot_eager" if device == "mps" else "inductor"
    for block in transformer.layers:
        block.compile(backend=backend)


def uncompile_blocks(transformer):
    for block in transformer.layers:
        block._compiled_call_impl = None


def _is_compile_error(exc):
    """Errors raised by torch.compile itself (dynamo / aot / inductor), not by the model."""
    return any(part in type(exc).__module__ for part in ("_dynamo", "_inductor", "_functorch"))


class PromptCache:
    """LRU of (embeds, mask) per (text, max_sequence_length), so repeated prompts skip the text encoder."""

    def __init__(self, size=16):
        self.size, self.items = size, {}

    def get(self, key):
        value = self.items.pop(key, None)
        if value is not None:
            self.items[key] = value
        return value

    def put(self, key, value):
        self.items.pop(key, None)
        self.items[key] = value
        while len(self.items) > self.size:
            self.items.pop(next(iter(self.items)))


def library_versions():
    names = ("torch", "diffusers", "transformers", "accelerate")
    out = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return out


def watch_steps(scheduler, on_step_output):
    """Wrap scheduler.step to report (x̂₀ = x_t − σ v, next latent) after each solver step."""
    original = scheduler.step
    train_steps = scheduler.config.num_train_timesteps

    def step(model_output, timestep, sample, *args, **kwargs):
        out = original(model_output, timestep, sample, *args, **kwargs)
        sigma = float(timestep) / train_steps
        on_step_output(sample - sigma * model_output, out[0] if isinstance(out, tuple) else out.prev_sample)
        return out

    scheduler.step = step


def clear_preview_stats():
    """Delete the live-preview decoder statistics (fitted from generated pictures); they are rebuilt as new
    pictures are made."""
    for path in (app_home() / "preview").glob("*"):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            log.warning("Could not delete %s", path)


class ModelNotDownloaded(Exception):
    pass


class CaptionHeadMissing(Exception):
    pass


def local_snapshot(model):
    """Path of the cached snapshot of a Hub repo id, resolved from the cache alone (no request).

    Not snapshot_download(local_files_only=True): recent huggingface_hub rejects a snapshot missing any repo file,
    and diffusers downloads only the files the pipeline needs (no LICENSE, .gitattributes, …)."""
    from huggingface_hub import try_to_load_from_cache
    from huggingface_hub.constants import HF_HUB_CACHE

    index = try_to_load_from_cache(model, "model_index.json", revision=P.model_revision(model))
    if not isinstance(index, str):
        log.warning("%s has no cached model_index.json in %s.", model, HF_HUB_CACHE)
        raise ModelNotDownloaded(
            f"{model} is not downloaded. Use File → Download Model… to fetch it.")
    folder = os.path.dirname(index)
    if missing := missing_files(folder):
        log.warning("%s is incomplete; missing %s.", model, ", ".join(missing[:5]))
        raise ModelNotDownloaded(
            f"{model} is incomplete ({len(missing)} files missing). Use File → Download Model… to fetch them; "
            "files already there are kept.")
    return folder


PARTS = ("transformer", "text_encoder", "vae", "scheduler", "tokenizer")
WEIGHTS = ("transformer", "text_encoder", "vae")


def missing_files(folder):
    """Files the pipeline needs that aren't readable in a snapshot (links are followed): each part's config and
    every weight shard its index lists."""
    import json

    folder, missing = Path(folder), []
    for part in PARTS:
        configs = [p for p in (folder / part).glob("*.json") if p.exists()]
        if not configs:
            missing.append(f"{part}/*.json")
        indexes = list((folder / part).glob("*.safetensors.index.json"))
        for index in indexes:
            shards = set(json.loads(index.read_text())["weight_map"].values()) if index.exists() else ()
            missing += [f"{part}/{s}" for s in sorted(shards) if not (folder / part / s).exists()]
        if part in WEIGHTS and not indexes and not any(p.exists() for p in (folder / part).glob("*.safetensors")):
            missing.append(f"{part}/*.safetensors")
    return missing


def model_cached(model):
    try:
        local_snapshot(model)
        return True
    except ModelNotDownloaded:
        return False


def load_local_first(model, on_stage):
    """Build the pipeline from the cached snapshot's weights and the pipeline code shipped in this package
    (moss_image.py), so no downloaded code runs and the Hub is never asked anything."""
    import torch
    import transformers
    from diffusers import AutoencoderKLFlux2

    from .moss_image import MOSSImagePipeline, MOSSImageScheduler, MOSSImageTransformer

    folder = local_snapshot(model)
    local = dict(local_files_only=True)
    pipe = MOSSImagePipeline(
        transformer=MOSSImageTransformer.from_pretrained(
            folder, subfolder="transformer", torch_dtype=torch.bfloat16, **local).eval(),
        scheduler=MOSSImageScheduler.from_pretrained(folder, subfolder="scheduler", **local),
        text_encoder=transformers.Qwen3_5Model.from_pretrained(
            folder, subfolder="text_encoder", dtype=torch.bfloat16, **local).eval(),
        tokenizer=transformers.Qwen2Tokenizer.from_pretrained(folder, subfolder="tokenizer", **local),
        vae=AutoencoderKLFlux2.from_pretrained(folder, subfolder="vae", torch_dtype=torch.float32, **local).eval())
    log.info("Loaded %s from %s; no network used.", model, folder)
    return pipe


class Backend:
    def __init__(self):
        self.low_memory = False          # unload the text encoder after encoding; reload on a new prompt
        self.prompts = PromptCache()
        self.text_encoder_cls = None
        self.decoders = {}
        self.exact = VaePreview()
        self.pipe = None
        self.native_scheduler = None
        self.key = None
        self.device = None

    def ensure_loaded(self, model, compile_transformer, on_stage):
        key = (model, compile_transformer)
        if key == self.key:
            return
        log.info("Loading %s from the local Hugging Face cache (offline; local_files_only=True)…", model)
        start = time.monotonic()
        on_stage("load", 0)
        self.unload()
        self.device = pick_device()
        pipe = load_local_first(model, on_stage)
        if self.device == "mps":
            pipe.transformer.forward = types.MethodType(mps_transformer_forward, pipe.transformer)
        pipe = pipe.to(self.device)
        if hasattr(pipe.vae, "enable_tiling"):
            pipe.vae.enable_tiling()
        if compile_transformer:
            compile_blocks(pipe.transformer, self.device)
        self.text_encoder_cls = type(pipe.text_encoder)
        self.exact = VaePreview()
        self.prompts = PromptCache()
        self.pipe, self.native_scheduler, self.key = pipe, pipe.scheduler, key
        log.info("Model ready on %s in %.1f s.", self.device, time.monotonic() - start)

    def unload(self):
        self.pipe = self.native_scheduler = self.key = None
        import gc
        gc.collect()
        self._empty_cache()

    def _empty_cache(self):
        import torch
        if self.device == "mps":
            torch.mps.empty_cache()
        elif self.device == "cuda":
            torch.cuda.empty_cache()

    def _text_encoder(self):
        if self.pipe.text_encoder is None:
            import torch
            log.info("Reloading the text encoder (low-memory mode).")
            encoder = self.text_encoder_cls.from_pretrained(
                local_snapshot(self.key[0]), subfolder="text_encoder", dtype=torch.bfloat16, local_files_only=True)
            self.pipe.text_encoder = encoder.to(self.device)
        return self.pipe.text_encoder

    def encode(self, text, max_sequence_length):
        """(embeds, mask) for one prompt, from the cache when possible."""
        key = (text, max_sequence_length)
        cached = self.prompts.get(key)
        if cached is None:
            import torch
            self._text_encoder()
            with torch.no_grad():
                cached = self.pipe.encode_prompt(text, max_sequence_length=max_sequence_length)
            self.prompts.put(key, cached)
        return cached

    def release_text_encoder(self):
        if self.low_memory and self.pipe.text_encoder is not None:
            self.pipe.text_encoder = None
            import gc
            gc.collect()
            self._empty_cache()

    fake = False

    def forget(self):
        """Drop everything derived from past prompts and pictures: cached prompt encodings and the fitted
        live-preview decoders (in memory and on disk)."""
        self.prompts = PromptCache()
        self.decoders = {}
        clear_preview_stats()

    def has(self, what, model=None):
        """Whether 'model' (that repo id) or the 'caption' head is available locally."""
        from . import describe as D
        return model_cached(model) if what == "model" else D.head_ready()

    def downloaded(self, what):
        if what == "model":
            self.key = None              # reload from the cache at the next generation

    def describe(self, model, path, thinking, on_stage, on_token, cancelled, request=None):
        """Captions {'short', 'medium', 'long'} of an image, or of `request` expanded (Enhance Prompt), from the
        pipeline's own text encoder."""
        from . import describe as D

        if not D.head_ready():
            raise CaptionHeadMissing("Captioning needs a one-time download: File → Download Captioning Head…")
        self.ensure_loaded(model, True, on_stage)
        on_stage("describe", D.MAX_TOKENS[thinking])
        try:
            return D.describe(self._text_encoder(), path, thinking, on_token, cancelled, request)
        finally:
            self.release_text_encoder()
            self._empty_cache()

    def initial_noise(self, p, noise_device):
        """Starting noise with the variation chain applied: ε ← cos(πs/2)·ε + sin(πs/2)·ε(seed_s), exactly N(0, I).

        Drawn exactly as the pipeline draws it (fp32 on the generator's device), so strength 0 reproduces
        the original image.
        """
        import math

        import torch

        shape = (1, self.pipe.transformer.config.latent_channels, p.height // 16, p.width // 16)

        def draw(seed):
            generator = torch.Generator(noise_device).manual_seed(seed)
            return torch.randn(shape, generator=generator, device=noise_device, dtype=torch.float32)

        eps = draw(p.seed)
        for seed, strength in P.variation_chain(p):
            angle = math.pi * strength / 2
            eps = math.cos(angle) * eps + math.sin(angle) * draw(seed)
        return eps.to(self.device)

    def image_latents(self, p, source, noise_device, keep=None):
        """x_σ₀ = (1 − σ₀)·z₀ + σ₀·ε at the first kept step, σ₀ read from the same schedule the run will use.
        z₀ and ε are stored in `keep` (a dict) for inpainting."""
        probe = make_scheduler(p.sampler, self.native_scheduler, p.shift)
        probe.set_timesteps(p.steps, device=self.device)
        sigma = float(probe.sigmas[I.start_index(probe.sigmas, p.init_strength)])
        z0 = I.encode(self.pipe.vae, source).to(self.device)
        eps = self.initial_noise(p, noise_device)
        if keep is not None and p.mask_image:
            keep.update(z0=z0, eps=eps)
        return (1 - sigma) * z0 + sigma * eps

    def num_layers(self):
        return self.pipe.transformer.config.num_layers

    def decoder(self, model):
        name = P.model_name(model)
        if name not in self.decoders:
            self.decoders[name] = LinearPreview(app_home() / "preview" / f"{name}.npz")
        return self.decoders[name]

    def generate(self, p, on_stage, on_step, cancelled, on_preview=None):
        """Run one image; returns (PIL.Image, app-metadata dict). on_preview receives (H, W, 3) uint8."""
        import numpy as np
        import torch
        from PIL import Image

        self.ensure_loaded(p.model, p.compile_transformer, on_stage)
        P.validate(p, self.num_layers())
        inpaint = {}                     # z0, eps, cells (torch) and the pixel mask, when a mask is given

        def fresh_scheduler():
            scheduler = make_scheduler(p.sampler, self.native_scheduler, p.shift, p.sde_eta, p.seed)
            if p.init_image:
                I.truncate_schedule(scheduler, p.init_strength)
            if inpaint:
                I.keep_known(scheduler, inpaint["z0"], inpaint["eps"], inpaint["cells"])
            watch_steps(scheduler, on_step_output)
            return scheduler

        reset_step_cache(self.pipe.transformer)
        decoder = self.decoder(p.model)
        state = {"final": None, "shown": 0.0, "step": 0, "total": 0, "denoise_start": None, "exact_spent": 0.0,
                 "exact_shown": False}

        def on_step_output(x0, latent):
            if inpaint:
                x0 = inpaint["cells"] * x0 + (1 - inpaint["cells"]) * inpaint["z0"]
            state["final"] = latent
            state["step"] += 1
            if on_preview is None:
                return
            try:
                show_preview(x0)
            except Exception:  # a preview must never cost the image
                log.exception("Preview failed; exact previews off for this session.")
                self.exact.verified = False

        def show_preview(x0):
            now = time.monotonic()
            per_step = (now - state["denoise_start"]) / state["step"] if state["denoise_start"] else 0.0
            nothing_shown = not state["exact_shown"] and not decoder.ready
            if self.exact.due(state["step"], state["total"], state["exact_spent"], per_step, nothing_shown):
                on_preview(self.exact.decode(self.pipe.vae, x0), True)
                state["exact_spent"] += self.exact.cost
                state["exact_shown"] = True
            elif not state["exact_shown"] and decoder.ready and now - state["shown"] >= PREVIEW_INTERVAL:
                state["shown"] = now
                on_preview(decoder.decode(x0[0].float().cpu().numpy()), False)

        noise_device = p.noise_device if p.noise_device in ("cpu", self.device) else "cpu"
        generator = torch.Generator(noise_device).manual_seed(p.seed)
        original = self.pipe.progress_bar

        def progress(items):
            items = list(items)
            state["total"], state["denoise_start"] = len(items), time.monotonic()
            on_stage("denoise", len(items))
            for i, t in enumerate(items):
                if cancelled():
                    raise Cancelled
                yield t
                on_step(i + 1, len(items))
            if cancelled():
                raise Cancelled
            on_stage("decode", 0)

        start = time.monotonic()
        self.pipe.progress_bar = progress
        restore_decode = self.exact.watch_decode(self.pipe.vae)
        try:
            on_stage("encode", 0)
            kwargs = P.pipeline_kwargs(p)
            embeds, mask = self.encode(kwargs.pop("prompt"), p.max_sequence_length)
            negative = kwargs.pop("negative_prompt")
            kwargs.update(prompt_embeds=embeds, prompt_attention_mask=mask)
            if p.cfg != 1.0:
                neg_embeds, neg_mask = self.encode(negative, p.max_sequence_length)
                kwargs.update(negative_prompt_embeds=neg_embeds, negative_prompt_attention_mask=neg_mask)
            self.release_text_encoder()
            source = None
            if p.init_image:
                on_stage("encode_image", 0)
                source = I.cover(Image.open(p.init_image), p.width, p.height)
                kwargs["latents"] = self.image_latents(p, source, noise_device, inpaint)
                if p.mask_image:
                    inpaint["pixels"] = I.mask_array(p.mask_image, p.width, p.height)
                    inpaint["cells"] = torch.from_numpy(I.latent_mask(inpaint["pixels"]))[None, None].to(self.device)
            elif P.variation_chain(p):
                kwargs["latents"] = self.initial_noise(p, noise_device)
            self.pipe.scheduler = fresh_scheduler()
            try:
                image = self.pipe(**kwargs, generator=generator).images[0]
            except Exception as exc:
                if not (p.compile_transformer and _is_compile_error(exc)):
                    raise
                log.warning("Compilation failed (%s); continuing uncompiled.", exc)
                uncompile_blocks(self.pipe.transformer)
                reset_step_cache(self.pipe.transformer)
                state.update(step=0, exact_spent=0.0, exact_shown=False)
                self.pipe.scheduler = fresh_scheduler()
                image = self.pipe(**kwargs, generator=torch.Generator(noise_device).manual_seed(p.seed)).images[0]
            if "pixels" in inpaint:
                image = I.composite(image.convert("RGB"), source, inpaint["pixels"])
            self.exact.check(self.pipe.vae, state["final"])
            if state["final"] is not None:
                decoder.add(state["final"][0].float().cpu().numpy(), np.asarray(image.convert("RGB")))
        finally:
            restore_decode()
            self.pipe.progress_bar = original
            reset_step_cache(self.pipe.transformer)
            self._empty_cache()
        return image, dict(elapsed_seconds=round(time.monotonic() - start, 2), device=self.device,
                           versions=library_versions())


class FakeBackend:
    """Draws seeded noise with simulated progress; for UI work without loading the model."""

    fake = True

    def __init__(self, step_seconds=0.02, first_run=False):
        self.step_seconds = step_seconds
        self.missing = {"model", "caption"} if first_run else set()

    def forget(self):
        clear_preview_stats()

    def has(self, what, model=None):
        return what not in self.missing

    def downloaded(self, what):
        self.missing.discard(what)

    def describe(self, model, path, thinking, on_stage, on_token, cancelled, request=None):
        from PIL import Image

        if "caption" in self.missing:
            raise CaptionHeadMissing("Captioning needs a one-time download: File → Download Captioning Head…")
        if request is not None:
            size = "imagined"
        else:
            with Image.open(path) as image:
                size = f"{image.width}×{image.height}"
        on_stage("describe", 60)
        for k in range(1, 61):
            if cancelled():
                raise Cancelled
            time.sleep(self.step_seconds)
            on_token(k, 60)
        return {"short": f"A placeholder description of a {size} image.",
                "medium": f"A placeholder one-paragraph description of a {size} image, written by the fake "
                          "backend so the interface can be tried without the model.",
                "long": f"A placeholder long description of a {size} image. The real one describes the "
                        "composition, subjects, setting, colors, lighting, style and any visible text."}

    def generate(self, p, on_stage, on_step, cancelled, on_preview=None):
        import numpy as np
        from PIL import Image

        P.validate(p, 42)
        if "model" in self.missing:
            raise ModelNotDownloaded(f"{p.model} is not downloaded. Use File → Download Model… to fetch it.")
        on_stage("encode", 0)
        rng = np.random.default_rng(p.seed)
        y, x = np.mgrid[0:p.height, 0:p.width]
        base = rng.uniform(0, 255, 3)
        final = np.clip(base + 80 * np.sin(x[..., None] / (20 + 40 * rng.random(3)))
                        + 80 * np.cos(y[..., None] / (20 + 40 * rng.random(3))), 0, 255)
        for seed, strength in P.variation_chain(p):
            other = np.random.default_rng(seed).uniform(0, 255, final.shape)
            final = (1 - strength) * final + strength * other
        if p.init_image:
            source = np.asarray(I.cover(Image.open(p.init_image), p.width, p.height), dtype=np.float64)
            final = (1 - p.init_strength) * source + p.init_strength * final
            if p.mask_image:
                m = I.mask_array(p.mask_image, p.width, p.height)[..., None]
                final = m * final + (1 - m) * source
        noise = rng.uniform(0, 255, final.shape)
        on_stage("denoise", p.steps)
        for i in range(p.steps):
            if cancelled():
                raise Cancelled
            time.sleep(self.step_seconds)
            if on_preview is not None:
                t = (i + 1) / p.steps
                on_preview(((1 - t) * noise + t * final).astype("uint8"), t > 0.5)
            on_step(i + 1, p.steps)
        on_stage("decode", 0)
        return Image.fromarray(final.astype("uint8")), dict(elapsed_seconds=0.0, device="fake")
