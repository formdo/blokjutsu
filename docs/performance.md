---
title: Speed and memory
nav_order: 11
---

# Speed and memory

## How long a picture takes

Time grows with **Steps** and with picture size (a little faster than the number of pixels). The card for each
picture shows the time so far and an estimate of the time left, and the time taken is saved with it.

Measured on a Mac Studio with an M3 Ultra (28-core CPU, 60-core GPU) and 256 GB of memory, one picture at a time:

| size | MP | 20 steps | 50 steps |
|---|---|---|---|
| 256 × 256 | 0.07 | 0:11 | 0:27 |
| 512 × 512 | 0.26 | 0:33 | 1:23 |
| 512 × 768 | 0.39 | 0:50 | 2:04 |
| 1024 × 1024 | 1.0 | 2:17 | 5:42 |
| 1408 × 1408 | 2.0 | 4:50 | 12:05 |
| 2048 × 2048 | 4.2 | 12:55 | |

Time follows the Mac's graphics cores, not its memory: once there's enough memory for the model, more doesn't
help. A Mac with half as many graphics cores takes roughly twice as long.

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
