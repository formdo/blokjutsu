---
title: Questions
nav_order: 14
---

# Questions

**Is it really free?** Yes. Blokjutsu, MOSS-Image's code, and its model weights are all open source under the
Apache License 2.0. See [Credits and licenses](credits.md#open-source).

**Can I use the pictures commercially?** MOSS-Image's weights are released under the Apache License 2.0, which
does not restrict what you make with them. You are responsible for what your pictures show, as with any tool.
This is not legal advice.

**Does it work on Intel Macs, Windows, or Linux?** No: it needs a Mac with Apple silicon (M1 or later). Windows
and Linux versions are planned.

**How long does a picture take?** From ten seconds to forty-five minutes, depending on the image size, the number
of steps, and the speed of your Mac. See the measured times in [Speed and memory](performance.md).

**Why does it need so much memory?** The model is large: about 15 billion numbers in all, and it uses about
30 GB of memory while it works. That is why Blokjutsu needs a Mac with at least 32 GB, and 48 GB or more is
comfortable. See [What you need](index.md#what-you-need) and [Speed and memory](performance.md).

**Why are two pictures with the same prompt different?** Each picture starts from a different random seed. Use
the same **Seed** to repeat a picture, or [Variations](variations.md) to stay close to one.

**Can it make video?** Not yet.

**Why the name?** *Blok* is Danish for block and *jutsu* (術) Japanese for art: the art of the block, after the
way MOSS-Image builds an image from blocks of pixels. See [Etymology](index.md#etymology) and
[Design inspiration](index.md#design-inspiration).
