---
title: Reference
nav_order: 3
has_children: true
has_toc: false
---

# Controls and menus

Click any control's bold name in the app for a one-line reminder.

## Prompt and negative prompt

What you want, and what you don't. Drag the small handle under a box to make it taller. See
[Writing prompts](prompts.md). **Layout…** opens the [layout editor](layouts.md); while a layout is in use, the
prompt box shows its description, and a click opens it.

## Size

Width (**W**) and height (**H**) in pixels, always multiples of 16. The rotate button swaps them.

**Aspect** picks a shape (16:9, 3:2, 4:3, 1:1 and their portrait versions) and **MP** a size in megapixels.
Both always show the current size: a shape that isn't on the list shows as its ratio, such as 1.37:1, and then
the MP menu offers it at ×1.5 to ×4 for [upscaling](from-a-picture.md#upscaling-making-a-picture-bigger).

MOSS-Image works best around 1 to 2 megapixels: proportions, hands, and lettering come out better there, even
allowing for the extra pixels. Smaller sizes are fine for trying out ideas. Bigger pictures take longer: twice the
pixels takes more than twice the time. See the [size examples](examples.md#size).

## Images

How many pictures to make, one after another, with the same settings. Each gets its own seed.

## Seed

The number the randomness starts from. **0** (the default) means a new random seed each time. The seed actually
used is saved with every picture, so the same seed and settings give the same picture again.

## Steps

How many refinement passes. More steps give cleaner detail and take longer. 20 is a good default and 30 is
usually all you need; MOSS-Image's authors recommend 50. See the [steps examples](examples.md#samplers-and-steps).

## Adherence

How literally the picture follows the prompt (often called CFG). 4 is the sweet spot, and anything from 3 to 6
gives much the same picture; much lower or higher values add artifacts. At 1, guidance is off: each step takes
half the time, but the prompt is barely followed. See the [adherence examples](examples.md#adherence).

## Output

The folder where pictures are saved, one sub-folder per picture. The folder button chooses another; Blokjutsu
offers to create it if it doesn't exist. The default is kept out of Time Machine backups and Spotlight; a folder
you choose follows your Mac's usual settings ([Backups and Spotlight](local.md#backups-and-spotlight)).

## Start from image

Switch on to start from a picture instead of from scratch. See [Working from a picture](from-a-picture.md).

## Variations

Switch on to make close variations of a picture. See [Variations](variations.md).

## Advanced options

Leave these alone unless you're curious. **Reset advanced** puts them back.

| control | what it does |
|---|---|
| Model | **SFT** is the polished model; **Base** is the raw one people train their own versions from |
| Sampler | the method that turns noise into a picture; see [Samplers](#samplers) |
| SDE noise η | only for the Euler SDE sampler: how much fresh randomness each step adds |
| Shift | balances effort between overall layout (higher) and fine detail (lower); default 5 |
| Uncond skip, SLG layers, SLG scale, Skip interval | MOSS-Image's built-in quality boosts; defaults are best |
| Max tokens | the longest prompt the model reads; longer prompts are cut |
| Size step | how much the W and H arrows change the size |
| Think first | Describe image and Enhance prompt plan before writing: slower, more accurate. Off each time Blokjutsu starts |
| Settings in PNG | also writes the prompt and settings inside each new PNG file; off by default, and asks you to confirm when turned on ([more](local.md#whats-inside-a-picture-file)) |
| Low memory | sets the text encoder aside after each prompt, to save memory; on automatically below 48 GB ([why](performance.md)) |

## Samplers

The sampler is the method that turns noise into a picture, one step at a time. **Steps** is how many steps it
takes.

| sampler | name in full | when to use it |
|---|---|---|
| **Euler** | Euler's method, the simplest way of following a path in small steps | the default, and what MOSS-Image was tested with; best at 20 to 50 steps |
| **Euler SDE** | Euler's method for a stochastic differential equation: some fresh randomness is added at each step | more varied texture, sometimes softer; **SDE noise η** sets how much randomness |
| **DPM++ 2M** | DPM-Solver++ (Diffusion Probabilistic Model solver), second order, multistep | far fewer steps: around 10 steps already gives a good picture, because each step also uses the one before |
| **UniPC** | Unified Predictor–Corrector: each step is predicted, then corrected | also for few steps; an alternative to DPM++ 2M |

DPM++ 2M and UniPC are general-purpose samplers rather than MOSS-Image's own, so results can differ a little from
Euler at the same seed. [Examples](examples.md#samplers-and-steps) shows all four side by side at 5 to 50 steps.

## Describe image and Enhance prompt

Both use MOSS-Image's own text encoder (the part that reads prompts) to write text. The first use asks to
download a 2 GB extra piece of it.

- **Describe image** (on each picture, and in Start from image) writes a short, a medium, and a long description
  of a picture; see [Describing images](describing.md).
- **Enhance prompt** (above the prompt box) rewrites your prompt in three lengths.

Each version has **Use as prompt** and **Copy** under it. A description takes from a few seconds to a minute;
with **Think first** on, several minutes.

## Menus

Everything in the menus, menu by menu. Items marked *macOS* are added by the Mac to every app.

### Blokjutsu

- **About Blokjutsu**: the version, credits, and license.
- **Settings…** (⌘-comma): preferences that aren't image settings.
  - **Live preview**: show the image forming while it generates.
  - **Image cache**: memory used to keep history images ready for smooth scrolling.
  - **App data**: the folder with Blokjutsu's settings, logs, models, and (by default) your images, with a
    button to show it in Finder.
- **Services** (*macOS*): lets other apps act on what you've selected in Blokjutsu. Select some prompt text, for
  example, and Services offers what your Mac's apps can do with text, such as making a note or searching the web.
  The list depends on the apps you have. **Services Settings…** opens System Settings, where the checkboxes turn
  each service on or off in every app's Services menu and right-click menu. Blokjutsu doesn't use Services
  itself.
- **Hide Blokjutsu** (⌘H), **Hide Others** (⌥⌘H), and **Show All** (*macOS*): hide or show windows.
- **Quit Blokjutsu** (⌘Q).

### File

- **Generate** (⌘-Return): the same as the **Generate** button.
- **Import Parameters…** (⌘O): sets the controls from a `parameters.json` file, or from a PNG made with
  **Settings in PNG** turned on. Use it to repeat or adjust an image someone sent you.
- **Show Output Folder in Finder**: opens the folder your images are saved in.
- **Show App Data in Finder**: opens the folder with Blokjutsu's settings, logs, and models.
- **Download Model…**: downloads the MOSS-Image model, or checks for and fetches only the files that have
  changed. It asks before anything is downloaded.
- **Download Captioning Head…**: downloads the extra piece that Describe image and Enhance prompt need. It asks
  before anything is downloaded.
- **Delete All History…**: permanently deletes your images and everything made from your prompts. See
  [Your history](history.md#clearing-out).

### Edit

These work in whichever text box you're typing in.

- **Undo** (⌘Z) and **Redo** (⇧⌘Z): step back and forward through your typing. After **Use as prompt**,
  ⌘Z brings back your own prompt.
- **Cut** (⌘X), **Copy** (⌘C), and **Paste** (⌘V). **Copy** also works on text you've selected on an image's
  card, such as its prompt.
- **Select All** (⌘A).
- **Start Dictation…** (*macOS*): type by speaking.
- **Emoji & Symbols** (*macOS*): insert special characters.

### View

- **Appearance**: **System** follows your Mac's light or dark setting; **Light** or **Dark** keeps Blokjutsu
  that way whatever the Mac uses.
- **Enter Full Screen** (*macOS*, ⌃⌘F).

### Window

- **Minimize** (⌘M): sends the window to the Dock.
- **Zoom**: makes the window fill the screen without going full screen; choose it again to restore it.
- Anything else in this menu, such as arranging windows on the screen, is added by macOS.

### Help

- **Search** (*macOS*): finds any menu item by name.
- **Blokjutsu User's Guide**: this guide, in your web browser.
- **MOSS-Image User Guide**, **MOSS-Image Technical Report (arXiv)**, and **MOSS-Image on GitHub**: the model
  authors' own pages, in your web browser.
- **Show Log**: opens Blokjutsu's log file. If something goes wrong, the full error is there; include it when
  [reporting a problem](faq.md#when-something-goes-wrong).
