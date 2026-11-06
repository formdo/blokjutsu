# Roadmap

## 1.0

- Notarized, signed .dmg with a download button on the home page (rc2)
- Remove Writing Tools and AutoFill from the Edit menu
- Move the GitHub Actions workflows to their Node.js 24 versions

## 2.0

- Windows and Linux
- Smaller-memory versions of the model (8-bit or 4-bit)
- Your own models: fine-tuned MOSS-Image weights loaded from local `.safetensors` files
- LoRA use
- LoRA training

## Later

- Layout editor
- Upscaling beyond 4 MP
- Separate strength for the negative prompt
- Faster generation
- Colorizing old photos
- Animation

## Not planned

- Mac App Store
- ControlNet: none exists for MOSS-Image; the layout editor and image to image cover much of it

# Issues

Designs for the items above, to move to GitHub issues once the repository exists.

**Notarized .dmg.** A self-contained app bundle (standalone Python plus the pinned libraries); every executable
file signed with the Developer ID, timestamped, hardened runtime; entitlements found by testing (PyObjC probably
needs `allow-unsigned-executable-memory`); `notarytool` and stapling in the release workflow.

**Windows and Linux.** CUDA path using the stock MOSS forward pass; a non-Apple icon set (SF Symbols are licensed
for Apple platforms only); per-platform `app_home`, memory query and installer (PowerShell with uv on Windows).
Testers: friends on Linux and Windows.

**Smaller-memory model.** Check for an existing int8 MOSS-Image first; otherwise quantize with torchao (int8 image
model, 4-bit text encoder) and offload to CPU memory as needed, to fit 12–24 GB graphics cards and 16–24 GB Macs.
Measure the quality loss against bf16 on a fixed set of prompts and seeds.

**Your own models.** A model choice in Advanced options for MOSS-Image weights fine-tuned elsewhere: a
`.safetensors` file (or a folder in diffusers layout) for the transformer, with MOSS-Image-SFT's text encoder,
VAE, and scheduler. Check the tensor names and shapes against the transformer before offering it; record the
file's SHA-256 with each image so results stay reproducible.

**LoRA use.** PEFT adapters on the transformer's attention and feed-forward layers, merged into the weights when
chosen so generating is no slower. No download browser: `.safetensors` files added to a folder or dropped on the
window; a Style menu and strength control appear in Advanced options only once one exists. Includes
step-distillation LoRAs (fewer steps) if any appear for MOSS-Image; show the step count they expect.

**LoRA training.** "Teach it a subject": choose a folder of 10–30 pictures; Describe image captions them and adds
a trigger word; train the image model only (text encoder frozen, text embeddings and latents cached once, bf16,
gradient checkpointing); progress and time left; the result appears in the Style menu. Measure hours per LoRA on
32, 64, and 128 GB Macs.

**Layout editor.** Draw boxes on a canvas of the chosen size and attach text to each; write MOSS-Image's JSON layout
prompt from them; reopen a layout from a picture's saved settings.

**Upscaling beyond 4 MP.** Overlapping tiles run as image to image at low Change, each prompted by Describe image
of its tile plus the overall prompt; blend the overlaps.

**Separate negative strength.** v = v_u + w₊(v₊ − v_u) − w₋(v₋ − v_u): a third pass, about 1.5× the time; shown
only when a negative prompt is present.

**Faster generation.** Run the conditional and unconditional passes as one batch (patch the per-sample loop);
measure on MPS and CUDA.

**Colorizing.** DDColor as an optional download; one button on a history card.

**Animation.** Interpolation between two pictures first, then image-to-image chains with camera moves; expect
minutes per second of video.
