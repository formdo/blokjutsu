---
title: Your own models
parent: Making images
nav_order: 7
---

# Your own models

Besides the two MOSS-Image models, Blokjutsu can use fine-tuned versions of MOSS-Image that people share on
Hugging Face, such as models trained for a style or for faster pictures. They are kept in your **model library**,
which works like the [LoRA library](loras.md).

## Adding a model

1. Click **Change…** beside **Model**, then **Manage Model Library…** (it's also in the File menu).
2. Click **From Hugging Face…**, paste the model's link, and click **Download**. Blokjutsu reads its page and the
   outline of its files, checks that it is a MOSS-Image model, checks there is room on your disk, and only then
   downloads it.
3. Or add one you already have: **From a folder…** for a model folder (with a `transformer` folder in it), or
   **From a file…** for a single `.safetensors` file holding the image model.
4. Close the library and choose the new model under **Local models**.

Most fine-tunes change only the image model and keep MOSS-Image's text encoder and image decoder. Blokjutsu
downloads only the parts that differ from what you already have, so a fine-tune usually takes about 10 GB rather
than 30. Parts a model doesn't include come from MOSS-Image-SFT (or -Base), so one of them must be downloaded.

Only models with exactly MOSS-Image's structure can be added. Blokjutsu always runs them with its own copy of
MOSS-Image's code, never with code from a model's page. **Find models on Hugging Face** opens their site in your
browser, showing fine-tunes of MOSS-Image.

## Recommended settings

Some models need different settings, such as fast models that want 8 steps and an Adherence of 1. When a model's
page recommends them, a button under **Model** offers **Use its settings**. If the page doesn't say, type them
as the model's **Settings** in **Manage Model Library…**, such as `8 steps, adherence 1`.

## Managing your models

**Manage Model Library…** lists the two original models and your own. Rename your models there, and delete any
of them (select several to delete them together). It always asks first, saying how much space deleting frees
and whether the model can be downloaded again. A deleted original stays in the list as *not
downloaded*, with **Download again…**.

Each picture records the model it was made with, and LoRAs work with fine-tuned models too.
