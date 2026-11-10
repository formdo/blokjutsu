---
title: Your history
parent: Making images
nav_order: 6
---

# Your history

The right half of the window lists every picture in the **Output** folder, newest first, with its settings and
prompt. The text can be selected and copied.

| button | does |
|---|---|
| Generate similar image | [variations](variations.md) of this picture |
| Use as input | [starts a new picture](from-a-picture.md) from this one |
| Describe image | writes descriptions of it |
| Reuse settings | puts its prompt and all settings back in the controls |
| Edit layout | for a picture made from a [layout](layouts.md): its settings back, and its layout open over it |
| Copy seed, Copy prompt | to the clipboard |
| Open in Preview | opens it in the Mac's Preview app |
| Show in Finder | its folder |
| Delete | removes it, permanently, after asking |

## Where pictures are kept

Each picture has its own numbered folder in the Output folder, holding `image.png` and `parameters.json` (its
settings), plus the input picture and selection if it had them. **File → Show Output Folder in Finder** opens the Output folder in Finder.
The default Output folder is kept out of backups and Spotlight; choose another Output folder to allow Time
Machine backups and Spotlight
([Backups and Spotlight](local.md#backups-and-spotlight)).

## Settings travel with the picture, if you want

Each picture's settings are in the `parameters.json` beside it; the PNG itself holds only the picture. Turn on
**Settings in PNG** in Advanced options to write the settings into the PNG too, so a picture you share or move
still says how it was made. **File → Import Parameters…** reads them back from a `parameters.json`, or from a
PNG saved with that setting on.

## Clearing out

**Delete all history…** (at the bottom of the controls, or in the File menu) asks first, then deletes the following.
**They are deleted permanently, not moved to the Trash, so this can't be undone.**


- every picture folder in every Output folder Blokjutsu has saved to
- the app's log
- scratch files from Select area to change
- the small file the live preview builds from your pictures
- the prompt and settings in the controls, and prompts cached in memory

Your Settings and the downloaded models are kept. Files of your own in an Output folder are never touched: only
folders Blokjutsu made (each with a `parameters.json`) are deleted. See [Running locally](local.md#where-blokjutsu-keeps-things)
for a list of every file Blokjutsu writes.
