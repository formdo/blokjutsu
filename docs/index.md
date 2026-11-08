---
title: Welcome
nav_order: 1
description: A local, permissively licensed, open-source Mac app for generating and editing images from text prompts with the open-weight MOSS-Image model.
---

## What is Blokjutsu?

<div class="intro" markdown="1">
<div markdown="1">
- Blokjutsu **generates images** from text descriptions.
- Blokjutsu **edits and extends** any image based on a text description ([more](from-a-picture.md)).
- Blokjutsu **adds captions** to any image ([more](describing.md)).
</div>
<div markdown="1">
- Blokjutsu is **simple on purpose**, with lightweight controls that work together.
- Blokjutsu is **local**, so prompts and images never leave your Mac ([more](local.md)).
- Blokjutsu is **permissive open source**, so you can use the images for anything ([more](credits.md)).
</div>
</div>

<p class="download">
  <a class="btn btn-download" href="https://github.com/formdo/blokjutsu/releases/download/v1.0.0rc3/Blokjutsu-1.0.0rc3.dmg">Download for Mac</a><br>
  <span>Blokjutsu 1.0.0rc3 (360 MB) · Mac with Apple silicon, 32 GB memory, 40 GB disk</span>
</p>

## Getting started

![The Blokjutsu window: controls on the left; on the right, a picture of three bowls of ice cream on a diner counter with handwritten cards reading CHOCOLATE, CHERRY, and PLAIN](assets/screenshots/main-window.webp)

1. Type a description in **Prompt**, for example:

   > three glass bowls of ice cream on a diner counter in the morning light, chocolate ice cream on the left,
   > black cherry ice cream in the middle, and vanilla ice cream on the right, with folding handwritten cards in
   > front of them saying "CHOCOLATE", "CHERRY" and "PLAIN"

2. Press **Generate** (or ⌘-Return).
3. A card appears on the right. It shows the step it's on, the time taken so far, and the time left, and a
   preview that sharpens as it goes. **Cancel** stops it.

Every picture is saved automatically, with all of its settings, in the **Output** folder.

### What to try next

- Press **Generate** again: you get a different picture, because the **Seed** is new each time.
- Make the prompt longer and more specific. MOSS-Image rewards detail; see [Writing prompts](prompts.md).
- Click **Enhance prompt** to have the model write a more detailed version of your prompt.
- On a picture you like, click **Generate similar image** for close [variations](variations.md).
- Click **Use as input** to [start a new picture from it](from-a-picture.md).
- Click the bold name of any control, such as **Seed** or **Change**, for a one-line explanation.
- See what each setting does, side by side, in the [Examples](examples.md).
