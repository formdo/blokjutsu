---
title: Welcome
layout: landing
nav_order: 1
description: A Mac app for making and editing pictures from a written description with the open-weight MOSS-Image model. Free, open source, and local.
image: /assets/hero/ice-cream.webp
---

<section class="hero">
  <h1>Make and edit pictures from a description, on your Mac.</h1>
  <figure>
    <img src="assets/hero/ice-cream.webp" width="768" height="432"
         alt="Three glass bowls of ice cream on a diner counter in morning light, with handwritten cards reading CHOCOLATE, CHERRY, and PLAIN">
    <figcaption>
      <span class="prompt">three glass bowls of ice cream on a diner counter in the morning light, chocolate ice
      cream on the left, black cherry ice cream in the middle, and vanilla ice cream on the right, with folding
      handwritten cards in front of them saying “CHOCOLATE”, “CHERRY” and “PLAIN”</span>
      <span class="meta">768 × 432 · 20 steps · 44 seconds on a Mac Studio (M3 Ultra) ·
      <a href="performance.html">other Macs</a></span>
    </figcaption>
  </figure>
</section>

{% include download.html %}

<aside class="based-on">
  <p><strong>Built on MOSS-Image.</strong> Blokjutsu is a Mac app for
  <a href="https://github.com/OpenMOSS/MOSS-Image">MOSS-Image</a>, an open-weight image model from the OpenMOSS
  Team and MOSI.AI. All of the picture-making is theirs. Blokjutsu is an independent project and is not
  affiliated with either.</p>
  <p class="more"><a href="credits.html">Credits and licenses</a></p>
</aside>

## Change a picture

<div class="pair">
  <figure><img src="assets/examples/from-image/cy-young-000.jpg" width="369" height="640" loading="lazy"
    alt="A 1909–1911 baseball card of Cy Young"><figcaption>Start from a picture: a 1909–1911 baseball card</figcaption></figure>
  <figure><img src="assets/examples/from-image/cy-young-085.webp" width="368" height="640" loading="lazy"
    alt="The same pose redone as a modern color card with a red hat and a sunset"><figcaption>Describe the picture you want: a modern color card, red hat, golden-hour sunset</figcaption></figure>
</div>

Keep the pose and change everything else, or paint over one part and change only that.

[Working from a picture](from-a-picture.md) [More examples](examples.md#starting-from-a-picture)
{: .more}

## Describe a picture

![The Describe image window: a 1942 photograph of two women and a child cycling in a park, with short, medium, and long descriptions beside it](assets/screenshots/describe.webp)

Three descriptions of a 1942 photograph, short to long, each ready to use as a prompt.

[Describing images](describing.md)
{: .more}

## The whole app

![The Blokjutsu window: the controls on the left; on the right, the ice cream picture with its settings and buttons beneath it](assets/screenshots/main-window.webp)

One window. Every picture is saved with its prompt and settings, and any of them can be the start of the next.

[Getting started](making-images.md)
{: .more}

## Stays on your Mac

Blokjutsu runs MOSS-Image on your Mac's own processor and memory. Prompts and pictures never leave it; the
internet is used only to download the model, when you ask.

[What runs where](local.md)
{: .more}
