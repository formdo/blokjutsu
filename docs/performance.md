---
title: Speed and memory
parent: Reference
nav_order: 2
---

# Speed and memory

## How long a picture takes

Time grows with **Steps** and with picture size (a little faster than the number of pixels). The card for each
picture shows the time so far and an estimate of the time left, and the time taken is saved with it.

Measured one image at a time on two Macs, in minutes and seconds:

- **M3 Ultra:** Mac Studio (2025), 28-core CPU, 60-core GPU, 256 GB of memory
- **M5 Max:** 14-inch MacBook Pro (2026), 18-core CPU, 40-core GPU, 64 GB of memory

| size | megapixels | M3 Ultra, 20 steps | M3 Ultra, 50 steps | M5 Max, 20 steps | M5 Max, 50 steps |
|---|---|---|---|---|---|
| 256 × 256 | 0.07 | 0:11 | 0:27 | 0:05 | 0:11 |
| 512 × 512 | 0.26 | 0:33 | 1:23 | 0:15 | 0:40 |
| 512 × 768 | 0.39 | 0:50 | 2:04 | 0:24 | 1:01 |
| 1024 × 1024 | 1.0 | 2:17 | 5:42 | 1:15 | 3:17 |
| 1408 × 1408 | 2.0 | 4:50 | 12:05 | 3:24 | 8:27 |
| 2048 × 2048 | 4.2 | 12:55 | | 9:25 | |

Time follows the Mac's graphics processor, not its memory: once there's enough memory for the model, more doesn't
help. Within a chip generation, a Mac with half as many graphics cores takes roughly twice as long. Newer chips
are faster per core: the M5 family adds matrix units to each graphics core, which is exactly the arithmetic
MOSS-Image spends its time on. Here the M5 Max, with two thirds of the graphics cores, is about twice as fast as
the M3 Ultra for small images, and about 1.4 times as fast at 2 megapixels and up.

Ways to go faster:

- Fewer **Steps** while exploring (12–20), more (40–50) for the keeper
- Smaller sizes while exploring, then [make the favorite bigger](from-a-picture.md#upscaling-making-a-picture-bigger)
- A low **Change** when starting from a picture runs only the last few steps.
- Explore at few steps, then remake the one you like with more: **Reuse settings** on its card and raise
  **Steps**. With the same seed you get a similar picture with sharper detail and often higher contrast. From
  about 20 steps up the picture itself barely changes; below that, the composition can still shift, especially
  with DPM++ 2M and UniPC (see the [examples](examples.md#samplers-and-steps)).

The first picture after Blokjutsu starts is slower: the model is loaded from disk and prepared.

## Memory

MOSS-Image has two large parts: the picture model (about 10 GB) and the text encoder that reads prompts (about
17 GB). Together with everything else they need about 30 GB of memory; the most we have measured is 29 GB.

| Mac memory | what to expect |
|---|---|
| 64 GB or more | comfortable |
| 48 GB | fine |
| 32–36 GB | works; turn on **Low memory** (Blokjutsu does this for you); other apps open will slow it down |
| 24 GB or less | very slow or fails: macOS has to swap to disk |

**Low memory** (in Advanced options) sets the text encoder aside after reading each prompt. A new prompt then
pauses for a few seconds while it reloads; the same prompt again does not.

## Disk

About 5 GB for the app and its libraries, about 30 GB for the model, and 1–5 MB per picture.
