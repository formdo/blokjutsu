---
title: Frequently asked questions
short_title: FAQ
nav_order: 4
---

# Frequently asked questions

## Using Blokjutsu

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
comfortable. See [What you need](install.md#what-you-need) and [Speed and memory](performance.md).

**Why are two pictures with the same prompt different?** Each picture starts from a different random seed. Use
the same **Seed** to repeat a picture, or [Variations](variations.md) to stay close to one.

**Can it make video?** Not yet.

**Why the name?** *Blok* is Danish for block and *jutsu* (術) Japanese for art: the art of the block, after the
way MOSS-Image builds an image from blocks of pixels. See [Etymology](credits.md#etymology) and
[Design inspiration](credits.md#design-inspiration).

## When something goes wrong

**Where do I look first?** **Help → Show Log** opens Blokjutsu's log, which shows errors in full. Please include
the end of it in a bug report.

**It says "The model is not downloaded yet."** Use **File → Download Model…**. If you downloaded it before, it
fetches only what's missing.

**A download failed or stopped.** Click **Try again** or **Resume**; it continues where it stopped. **Show
details** in the download window says what went wrong.

**Pictures take very long, or my Mac becomes sluggish.** Memory is short. Turn on **Low memory**, close other
large apps, and use smaller sizes. See [Speed and memory](performance.md).

**Describing or enhancing seems to run forever.** With **Think first** on it can take several minutes; the token
count shows it's working. Turn Think first off for quicker answers.

**Blokjutsu won't open.** Download it again and replace the copy in Applications. If it still won't open, the
reason is at the end of `console.log` in the `logs` folder of `~/Library/Application Support/Blokjutsu.noindex`;
include it when you report the problem.

**Why does opening it again just bring the window forward?** Only one Blokjutsu runs at a time, on purpose.

**How do I reset the settings?** Blokjutsu keeps them in one file, `settings.json`: the controls as you last left
them (prompt included), the Output folder, the appearance, and **Blokjutsu → Settings…**. To put them all back to
their defaults:

1. Quit Blokjutsu.
2. In Finder, choose **Go → Go to Folder…**, type `~/Library/Application Support/Blokjutsu.noindex`, and press
   Return.
3. Move `settings.json` to the Trash.

Your pictures and the downloaded models are kept. To delete your pictures, use
[Delete all history](history.md#clearing-out); to remove everything, see [Uninstalling](install.md#uninstalling).

**How do I report a problem?** Open an issue at
[github.com/formdo/blokjutsu/issues](https://github.com/formdo/blokjutsu/issues){:target="_blank"} with what you
did, what happened, your Mac model and memory, and the end of the log.
