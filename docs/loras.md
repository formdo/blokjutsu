---
title: LoRAs
parent: Making images
nav_order: 6
---

# LoRAs

A LoRA is a small add-on that teaches MOSS-Image a style or a subject: gouache painting, a comic artist's line,
a particular product. People share them on Hugging Face, and Blokjutsu can use several at once, each at its own
strength.

## Adding a LoRA

1. Switch on **LoRAs** in the controls and click **Choose LoRAs…**. It lists the LoRAs on this Mac; tick the
   ones to use, untick the ones not to, and **Close**.
2. To add a new one, click **Manage LoRA Library…** (also in the File menu), then **From Hugging Face…**, paste its link, such as
   `https://huggingface.co/axiomofmind/Moss-image-gouache-lora`, and click **Download**. Blokjutsu reads its page
   and the outline of its file, checks that it was made for MOSS-Image, and only then downloads it. Check the
   name and trigger word it found, then click **Done**.
3. Or click **From a file…** to add a `.safetensors` file you already have. From a Hugging Face page, download
   the LoRA's `.safetensors` file (on the **Files** tab, usually `pytorch_lora_weights.safetensors`); put the
   page's `README.md` beside it and Blokjutsu reads the trigger word and other details from it too.
4. Close the library; the new LoRA is in the list to tick.

Only LoRAs made for MOSS-Image can be added: Blokjutsu checks every layer in the file against the model, and
says so if a LoRA was made for something else. Both ordinary LoRAs and LoKr adapters (another way of
storing the same kind of add-on) work. A LoRA trained on MOSS-Image-Base works with MOSS-Image-SFT too:
the two models have the same structure. **Find LoRAs on Hugging Face** opens their site in your browser, showing
only those.

Clicking **Download** is the only time Blokjutsu contacts Hugging Face for a LoRA.

## Trigger words

Many LoRAs are trained to respond to a **trigger word**, such as `moss_vgouache_style`. When you add one,
Blokjutsu puts its trigger word at the start of your prompt, shown tinted, so you can see what the model reads.
If you edit the word it is no longer the trigger, and the tint goes; the LoRA's row then offers **Add to prompt**.
Taking a LoRA off removes its trigger word from the prompt.

Some LoRAs have no trigger word: they change every picture they are used for. Their row says so.

Blokjutsu finds the trigger word on the LoRA's page or in its file. If it can't find one, or finds the wrong one,
type it as its **Trigger** in **Manage LoRA Library…**. From then on it is added to the
prompt whenever you add that LoRA.

## Strength

Each LoRA has a strength: 0 is off, 1 is as it was trained. Most LoRAs look best between 0.6 and 1.2; past that
they tend to overpower the picture. When a LoRA's page recommends a strength, it starts there.

Switching **LoRAs** off makes pictures without them; the list is kept for when you switch it on again.

## Your LoRAs

LoRAs are copied into Blokjutsu's own folder, so a picture made with one can always be made again. Each picture
records the LoRAs it used and their strengths; **Reuse settings** puts them back.

**Manage LoRA Library…** renames them, sets their trigger words and the strength they start at, and deletes
them (select several to delete them together). It asks first only if one came from a file, since a LoRA from
Hugging Face can be downloaded again.
