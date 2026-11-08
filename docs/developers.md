---
title: For developers
nav_order: 6
---

# For developers

Blokjutsu's source code and everything about working on it are on
[GitHub](https://github.com/formdo/blokjutsu){:target="_blank"}:

- [README](https://github.com/formdo/blokjutsu#readme){:target="_blank"}: installing from Terminal or with
  Python, the libraries and models it uses, and their licenses
- [CONTRIBUTING.md](https://github.com/formdo/blokjutsu/blob/main/CONTRIBUTING.md){:target="_blank"}: setting
  up, running the tests, the design and modules, building the .dmg, and releasing
- [ROADMAP.md](https://github.com/formdo/blokjutsu/blob/main/ROADMAP.md){:target="_blank"}: what comes next
- [Issues](https://github.com/formdo/blokjutsu/issues){:target="_blank"}: bug reports and feature requests

## Technical notes

How each control works. In the app, clicking a label shows a one-line summary.

### Prompt

**Prompt.** Natural language, comma-separated tags, or a JSON layout pasted verbatim (see
[JSON layouts](#json-layouts)).

Up to 4096 tokens; **Max tokens** in Advanced options lowers the limit. The model is multilingual: English has the
most training data, and Chinese and other languages are also supported.

### JSON layouts

A prompt that starts with `{` is a layout: an overall caption plus boxes, each with a label, a description, and,
for text, the exact words. The model reads the JSON as text; Blokjutsu only checks that it parses and that the
boxes fit the canvas. For a 1024 × 1024 image:

```json
{
  "summary": {"meta": ["poster"], "canvas": "single",
              "caption": "A minimalist travel poster, cream background, a blue mountain, the title EXPLORE."},
  "items": [
    {"label": "text", "caption": "Large dark-blue capitals, centered at the top.", "text": "EXPLORE",
     "bbox": [-416, -384, -288, 384]},
    {"label": "object", "caption": "A flat blue mountain illustration.", "bbox": [-192, -288, 384, 288]}
  ],
  "bbox_coord_space": "abs_centralized",
  "bbox_format": "yxyx"
}
```

- `bbox_format: "yxyx"`: each box is `[y_min, x_min, y_max, x_max]`.
- `bbox_coord_space: "abs_centralized"`: pixels with the origin at the canvas center, *x* to the right and *y*
  downward, so a W × H canvas spans −W/2…W/2 and −H/2…H/2. Subtract W/2 and H/2 from top-left-origin
  coordinates to convert.
- These are the only values MOSS-Image documents. Set Width and Height to the canvas the layout was written for.
- Layouts can be combined with natural language in the same prompt. Layout control is experimental; see the
  [MOSS-Image User Guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#layout-prompts-experimental).

### Negative prompt

**Negative prompt.** Text for the unconditional branch of classifier-free guidance; sampling is pushed away from it. Suggested by the authors: `nsfw, worst quality, bad anatomy, watermark, jpeg artifact`.

With uncond-skip layers active (default), the negative branch is also run through a deliberately weakened network; see Advanced.

### Size

**Size.** Type width and height, or step them with the arrows (see Size step in Advanced), or choose from the Aspect menus below. The rotate button swaps width and height. Width × height are in pixels, positive multiples of 16 (the latent grid is 1/16 resolution; each 16×16 patch is one transformer token). The line below shows aspect ratio, megapixels, and raw RGB size; a saved PNG is typically a third to two thirds of that.

Recommended 1–2 MP. The Aspect and MP menus offer sizes from 256 × 256 (0.07 MP) to about 4 MP, and smaller sizes can be typed in; below about 0.25 MP the model has less room for detail. Cost per step grows faster than linearly in pixel count because attention is quadratic in tokens.

### Aspect and megapixels

**Aspect and megapixels.** Choose an aspect ratio, then an image size by megapixels; the width and height above update to match. Both menus go blank when the current size isn't one of their entries. The line under the size boxes shows aspect ratio, megapixels, and raw (uncompressed RGB) size.

### Images

**Number of images.** Runs the request this many times with consecutive seeds *s, s+1, …*; each image is saved with its own parameters.json and is reproducible alone. (The transformer processes batch members serially anyway, so nothing is lost by not batching.)

### Seed

**Seed** for the initial Gaussian noise. **0 means a new random seed for each image**; the seed actually used is always recorded. The same seed with the same parameters, model, noise device, and library versions gives the same image.

### Steps

**Sampling steps**: number of integration steps for the flow ODE from noise to image. Time is linear in steps. The authors recommend ≥ 50; in practice 30 is usually enough.

### Adherence (CFG)

**Adherence** (classifier-free guidance scale, CFG) *w*: prediction = uncond + *w*·(cond − uncond). Larger values follow the prompt more literally at the cost of diversity and, eventually, oversaturation. *w* = 1 disables guidance and halves the time per step, since the unconditional pass is skipped.

Recommended 3–6; 3 suffices for long prompts, raise it for short ones.

### Output folder

**Output folder.** Each image gets a numbered subfolder containing `image.png` and `parameters.json` (same schema as the MOSS-Image repo and Gradio app). The history on the right is rebuilt from this folder.

### Model

**Model.** **SFT** is MOSS-Image-Base after supervised fine-tuning on curated data; it is the better default for generation. **Base** is the pretrained model, intended mainly as a starting point for LoRA training. A local model folder path also works.

Changing model reloads tens of GB of weights at the next generation.

### Sampler

**Sampler** (ODE solver for the flow-matching schedule).

- **Euler**: the model's native scheduler; snaps the noise schedule to the training grid. Recommended.

- **Euler SDE**: Euler with fresh noise injected each step, controlled by **SDE noise η**. Same cost as Euler; more varied texture, sometimes softer.

- **DPM++ 2M**, **UniPC**: multistep solvers; can tolerate fewer steps. Experimental: they do not use the training-grid snapping.
The diffusers ancestral scheduler (Euler a) is for noise-prediction models and does not fit MOSS-Image's velocity prediction; Euler SDE is the flow-matching equivalent.

### SDE noise η

**SDE noise η** (Euler SDE only). Each step predicts the clean image x̂₀ and its noise ε̂, then moves to the next noise level σ′ using √(1−η²)·ε̂ + η·z with fresh noise z. η = 0 is plain Euler; η = 1 discards the predicted noise entirely (fully ancestral). The extra noise is seeded, so results stay reproducible.

### Shift

**Shift** *s* of the noise schedule: σ ↦ *s*σ / (1 + (*s*−1)σ). Larger *s* spends more steps at high noise (global composition); smaller spends more at low noise (fine detail). Default 5.

### Uncond skip layers

**Uncond skip layers** (zero-based transformer block indices, comma-separated). These blocks are dropped from the *unconditional* forward pass, so guidance pushes away from both the negative prompt and a deliberately degraded network. No extra cost.

Default 22; 22, 24, and 26 all help. Empty gives plain CFG: more photographic but details may collapse.

### SLG layers

**SLG layers** (standard skip-layer guidance). Adds a third forward pass of the *conditional* branch with these blocks dropped, and adds scale·(cond − cond_skipped) to the prediction (+50% time per step). Empty disables it.

### SLG scale

**SLG scale** for the correction above. 0 disables it.

Standard SLG is off by default: the default already uses *uncond skip* (layer 22), which the authors recommend and which costs nothing extra, whereas standard SLG adds a third forward pass per step (+50% time). If you turn it on (e.g. SLG layers 22), the authors suggest scale 3 with skip interval 0.01–1.0.

### Skip interval

**Skip interval** [start, stop) as fractions of the denoising trajectory, 0 = pure noise, 1 = finished image. Both uncond skipping and SLG apply only inside it; outside, sampling uses plain CFG.

### Size step

**Size step**: how much the width and height arrows (and ↑/↓ keys) change the size. Sizes must be multiples of 16, so 16 is the finest step.

### Max tokens

**Max sequence length**: prompt token cap for the text encoder; longer prompts are truncated. Maximum 4096. Lowering it only matters for very long prompts.

### Noise device

**Noise device**: where the initial noise is drawn. **cpu** is reproducible across machines and matches the official Gradio app. **mps** matches seeds from your original script.

### Compile

**Compile transformer**: compiles the 42 transformer blocks with `torch.compile` (aot_eager on Apple GPUs), typically about 10% faster per step. The first image and each new resolution pay a one-time compile cost. Takes effect on the next model load.

### Live preview

**Live preview** while sampling shows each step's predicted clean latent x̂₀ = x_t − σ·v, in two ways.

- **Approximate:** a linear patch decoder (latent → 16×16 RGB patch), fitted by ridge regression to the app's own
  finished images, at most twice a second. Cost is one small matrix multiply, far under 1% of a step. It is
  fitted after the first image with each model (and again after Delete all history), and is blurrier than the
  VAE.
- **Exact:** x̂₀ decoded with the real VAE, between 30% and 90% of the steps, only while their total time stays
  under 5% of sampling time. When no approximate decoder exists yet, one exact preview is shown halfway through
  regardless of the budget. The decode recipe is checked once against the pipeline's own; a mismatch turns exact
  previews off. Once an exact preview has been shown, approximate ones stop for that image.

### Low memory

**Low memory**: after encoding a prompt, unload the 9B text encoder (about 17 GB), leaving the transformer and VAE (about 11 GB). Encoded prompts are cached, so repeating a prompt (new seeds, other settings) costs nothing; a new prompt reloads the encoder from disk first (a few seconds).

### Image cache

**Image cache**: memory for decoded history images at display size. Every image in the history is decoded in the background, nearest to the view first, so scrolling never waits. About 4 MB per 1-megapixel image on a Retina display; the least recently viewed are dropped when the budget is exceeded.

### App data

**App data**: settings, logs, live-preview decoders, the models (a Hugging Face cache of Blokjutsu's own, set with `HF_HUB_CACHE` so other software's cache is never touched) and, by default, your images. Created once with Time Machine's exclusion flag, and named `.noindex` so Spotlight skips it. Deleting this folder and the app removes everything.

### Variation and variation seed

Small variations keep the prompt, settings, and seed of an image and blend a second starting noise into the
first: ε = cos(πs/2)·ε_seed + sin(πs/2)·ε_var, where s is the variation strength. For independent standard
normal ε_seed and ε_var this is exactly standard normal for every s, so the model always sees correctly
distributed noise. s = 0 is the original image; 0.05–0.15 changes details; 0.3–0.5 keeps composition and
palette; s = 1 is a new seed. In a batch every image gets its own variation seed (consecutive from the given
one, or random if 0). **Generate Similar Image** on a history card starts from that exact image, including any variations it
already had (they are kept as a chain and applied in order), so you can refine step by step.

The slider is quadratic (strength = position²), giving most of its travel to the small values.

### Start from image (image to image)

SDEdit for a rectified-flow model. The input is resized to the output size (scaled to cover, center cropped,
EXIF rotation applied), encoded by the VAE to the normalized latent z₀, and placed on the noise path at
σ₀ = √Change: x_σ₀ = (1 − σ₀)·z₀ + σ₀·ε. Only the solver steps with σ ≤ σ₀ run. With shift *s*, the steps are
uniform in *t* with σ = *s*t/(1 + (*s*−1)t), so the fraction that runs is σ₀/(*s* − (*s*−1)σ₀): with the default
*s* = 5, about 2 of 20 steps at Change 0.16 (σ₀ = 0.4), 7 at Change 0.5, and 13 at Change 0.81 (σ₀ = 0.9).
That is why the control shows σ₀² rather than σ₀: a linear σ₀ crowds nearly all the visible effect into its top
tenth. Settings files store σ₀ itself, as `init_strength`, so they mean the same whichever way the control shows
it. Low Change keeps layout and identity; high Change keeps only rough color and arrangement; 1 is
text-to-image. Variations work on top (they perturb ε).

The input is copied into each image's folder as `input.*`, so results stay reproducible after the original
moves. **Match Image Size** sets the output to the input's aspect ratio at up to about 2 MP.

### Network

The app never connects to the internet on its own. At startup it puts the Hugging Face libraries in offline
mode (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1`, with telemetry and implicit login
tokens also switched off) before any of them is imported, so even library code that would check for
updates fails locally instead of sending a request. The pipeline is built from the cached snapshot's weights
and MOSS-Image's pipeline code shipped in the package (`moss_image.py`), so `model_index.json` is never read,
no downloaded code runs and `trust_remote_code` is never used.

Every download goes through one dialog (`ui/download_dialog.py`): what, size, source, destination, and what is
sent, then **Download** or **Not Now**; then progress with Cancel; then the outcome. It appears

- at launch when the selected model is not in the cache (a new user's first run),
- for **File → Download Model…**,
- for **File → Download Captioning Head…**, or when **Describe Image** is first used.

The download runs in a child process (`python -m blokjutsu.fetch …`) with offline mode lifted for that process
only. Requests reveal the file names, your IP address, and a User-Agent with library versions; no login token,
prompts, images, or settings are sent. Cancelled downloads keep what arrived and resume.

To preview the whole flow without the model or the network (downloads are simulated; settings and images go to
`~/Library/Application Support/Blokjutsu Trial.noindex`):

```sh
python -m blokjutsu --fake --first-run
```

### Describe Image

MOSS's text encoder is Qwen3.5-9B, a vision-language model, but the checkpoint omits its output layer
(`lm_head`, 248320×4096, 2.0 GB in bf16). The captioning-head download compares the leading bytes of a few
tensors (norms across the depth, the start of the token embedding) between MOSS's encoder and
`Qwen/Qwen3.5-9B`, then `Qwen/Qwen3.5-9B-Base`, using HTTP range reads of the safetensors shards. Only from a
bit-identical checkpoint does it range-read `lm_head.weight` alone into `<app data>/caption/lm_head.safetensors`,
with Qwen's tokenizer and processor settings and a `source.json` recording repo, revision, and the tensors checked.

Describing wraps the loaded encoder in `Qwen3_5ForConditionalGeneration` (built on the meta device, so its
weights are shared, not copied), attaches the head, and asks MOSS's own recaptioning prompt (USERGUIDE.md,
without the reference caption) for long, medium, and short captions in JSON. As in MOSS's training captions,
watermarks are kept out of the captions, so a prompt made from them doesn't ask for one; their text is listed
separately and shown under the descriptions. Images are scaled to at most 1 MP.
**Think first** (Advanced options) turns on Qwen's thinking mode for Describe image and Enhance prompt
(MOSS's recommendation; slower). Generation stops as soon as a complete JSON reply has been written. The head is freed afterwards.

### Inpainting and outpainting

In **Start from image**, **Select area to change…** (or a click on the picture) opens the area editor on the input as the model will see it
(fitted to ≤ 2.1 MP, multiples of 16). Paint where the image may change; **Erase** or ⌥ removes paint;
**Feather size** softens the edge; **Extend (+) or crop (−)** adds or removes margins (or drag the
dashed frame: outwards extends, inwards crops; the boxes follow), with cropped-away parts shown faint on any side for outpainting (the margins are always
regenerated; they start as the image's edges stretched and blurred).

At run time the masked region follows the usual image-to-image path from σ₀ = √Change, while every other latent
cell is reset after each solver step to the input on its own noise path, (1 − σ)·z₀ + σ·ε, with the same ε as the
start. A cell is regenerated if any of its 16×16 pixels is masked, grown by one cell, so the feathered pixel edge
lies inside regenerated latent; finally the input's pixels are pasted back outside the feathered mask. Change 1.0
replaces the area outright; lower values keep its colors and layout. The selection is kept however the editor is closed, saved with the image as
`mask.png`, and shown as a red overlay on the input. **Remove** takes the picture out of the box without
deleting the file; **Replace image…** chooses another.

### Enhance Prompt

Expands the prompt into long, medium, and short descriptions written by MOSS's own text encoder (same
captioning head as Describe Image), following the caption style MOSS was trained on. The technical report's
best human-preference scores used detailed, enhanced prompts. **Think first** in Advanced options lets the model
plan before writing: slower, often better.

### Image files

By default `image.png` holds only the picture: no text, time, color-profile, or physical-size chunks (the image
is copied with an empty `info` so Pillow cannot carry any over). With **Settings in PNG** on, it also carries
the full `parameters.json` as an iTXt chunk named `parameters`.

To reuse an image's settings, choose **File → Import Parameters…** and select either its `parameters.json` or a
PNG saved with **Settings in PNG** on.

### Size menus and upscaling

The Aspect and MP menus always show the current size. A size matching no preset shows its ratio rounded to
x.xx:1, and the MP menu then offers it at ×1, ×1.5, ×2, ×2.5, ×3, and ×4 (each side rounded to a multiple of 16,
area ≤ 4.2 MP). With **Start from image** on and a low **Change**, that upscales: the input is resized (Lanczos)
to the new size, encoded, re-noised to σ₀ = √Change, and denoised. At the lowest Change, 0.01 (σ₀ = 0.1), shift 5
leaves about 1 step in 50, so the time is mostly prompt and VAE encoding and decoding. Change 0.05–0.1
(σ₀ ≈ 0.22–0.32) runs a few more steps and lets the model add new detail.
