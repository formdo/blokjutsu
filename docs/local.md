---
title: Running locally
nav_order: 12
---

# Running locally

Blokjutsu runs the model locally, on your Mac's own processor and memory. Your prompts, pictures, and settings
stay on it. The internet is used only to download models, when you ask.

The model comes from [Hugging Face](https://huggingface.co), a site that hosts open AI models.

## When Blokjutsu uses the internet

Blokjutsu only uses the internet when you click **Download** in a dialog that says exactly what will be fetched:

| download | when | size |
|---|---|---|
| the MOSS-Image model | first launch, or **File → Download Model…** | about 30 GB |
| the captioning head | first use of Describe image or Enhance prompt | 2 GB |

The Hugging Face libraries
Blokjutsu uses are told never to connect on their own, so they cannot check for updates or report usage.

## What a download sends

The names of the files requested, your Mac's internet address (as with any web request), and a short note of the
software versions. You are not logged in to anything. Nothing about your pictures or prompts is sent.

## Other connections

The Help menu's links open in your web browser. The installer downloads Python and the libraries from their
usual sources (astral.sh, python.org builds, the Python Package Index, and GitHub).

## What's inside a picture file

Pictures are saved as plain PNG files holding only the picture: no prompt, no settings, no date, no software
name. Each picture's settings are kept in a separate `parameters.json` beside it.

**Settings in PNG** (in Advanced options) writes the prompt and settings into each new PNG as well, so they travel
with the file. Blokjutsu asks you to confirm when you turn it on, because anyone you give the file to can read
them.

## Where Blokjutsu keeps things

Everything Blokjutsu writes, and what **Delete all history** does with it:

| what | where | Delete all history |
|---|---|---|
| pictures: one folder each with `image.png`, `parameters.json`, and any input picture and selection | the Output folder (by default `~/Library/Application Support/Blokjutsu.noindex/images/`), and any earlier Output folders | deleted |
| the log, `blokjutsu.log` and `console.log` | `…/Blokjutsu.noindex/logs/` | emptied |
| scratch files from Select area to change | `…/Blokjutsu.noindex/work/` | deleted (otherwise after 30 days) |
| a small file the live preview needs, built from your pictures | `…/Blokjutsu.noindex/preview/` | deleted |
| prompt encodings | memory only | cleared |
| settings, including the last prompt | `…/Blokjutsu.noindex/settings.json` | prompt and controls reset; preferences kept |
| a lock that keeps Blokjutsu to one window | `…/Blokjutsu.noindex/instance.lock` | kept (holds no content) |
| the captioning head | `…/Blokjutsu.noindex/caption/` | kept |
| the MOSS-Image model | `…/Blokjutsu.noindex/models/` | kept |
| the app and the Python it runs on | `~/Applications/Blokjutsu.app`, `…/Blokjutsu.noindex/tools/`, `…/Blokjutsu.noindex/runtime/` | kept |

`…/Blokjutsu.noindex` is `~/Library/Application Support/Blokjutsu.noindex`.

## Backups and Spotlight

Blokjutsu's folder, `~/Library/Application Support/Blokjutsu.noindex`, is kept out of Time Machine backups and out
of Spotlight search. So by default:

- the model (about 30 GB, and downloadable again at any time) doesn't fill your backups
- your pictures, prompts, and settings aren't copied to a backup disk, and Spotlight doesn't index them

Folders in your home folder are normally backed up by Time Machine and indexed by Spotlight, so Blokjutsu marks
its own folder to opt out: Time Machine's exclusion flag (as set by `tmutil addexclusion`), and a name ending in
`.noindex`, which Spotlight skips. Nothing leaves your Mac either way: Spotlight's index stays on it, and Time
Machine copies only to the backup disk you set up.

**To back up your pictures**, choose an Output folder elsewhere, such as `~/Pictures/Blokjutsu`. Your Mac's usual
settings then apply to it: Time Machine backs it up and Spotlight indexes it, and if you choose a folder in
Documents with Desktop & Documents in iCloud turned on, it is copied to iCloud. Pictures already made stay in the
old folder; move them in Finder if you want them in the history.


macOS itself also keeps traces outside Blokjutsu's control: Recent Items, the last folder used in Open and Save
panels, and the history of whatever app you double-click a picture into. Text you copied stays on the clipboard
until you copy something else.
