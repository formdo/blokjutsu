# Changelog

## 1.0.0 (2026-11-15)

- A layout set aside shows as a line under the prompt; one in use says **Layout in use:**
- Delete all history also deletes a layout set aside
- Closing Layout… on an empty layout (no boxes, no description) no longer leaves an empty layout in use
- Quitting stops background work first and skips Python's teardown, where macOS sometimes reported a crash
- Downloads show time so far, speed, and about how long is left
- **Output** moved into Advanced options
- **Model** is a row of its own, always showing the model in use, with **Change…**
- Closed sections say what they hold: Advanced options **Defaults** or which settings are changed; Start from
  image, Variations and LoRAs **Off**, and what they keep while off
- **Random** checkbox beside Seed, in place of “0 = random”; the number shows only when it's unticked
- Sizes below 1 MP shown to one figure (0.4 MP)
- Delete all history is in the File menu only
- Deleting a model always asks first, saying how much space it frees and whether it can be downloaded again
- **Your own models**: fine-tunes of MOSS-Image from Hugging Face, a folder, or a file, checked before
  download and sharing the parts they don't change. A **Model** section of its own (out of Advanced options)
  with **Choose model…** and **Manage Model Library…**, and a button for a model's recommended settings. The original models can be deleted and downloaded again
- User's Guide: a Your own models page
- Writing Tools, AutoFill, Dictation and Emoji & Symbols no longer appear in the Edit menu
- **LoRAs**: add them from Hugging Face (looked up and checked against MOSS-Image before anything is
  downloaded) or from a file, use several at once with a strength each, and see their trigger words tinted in
  the prompt. **Choose LoRAs…** ticks which to use; **Manage LoRA Library…** adds, renames, sets trigger words, and
  deletes. Each picture records its LoRAs. LoKr adapters work too
- User's Guide: a LoRAs page
- Text in the windows can be selected and copied, for error reports
- A busy indicator in the icon's colours while a LoRA is looked up and downloaded
- Buttons that open a window end in “…” (Describe image…, Enhance prompt…, Edit layout…)

## 1.0.0rc4 (2026-11-10)

- **Layout editor** (Layout… beside the prompt): draw boxes for text and things on a canvas the size of the
  picture, give each a description and, for text, its words; the layout becomes the prompt, in MOSS-Image's
  compact form, and its boxes follow the picture's size. **Edit layout** on a picture's card opens its layout
  with the picture behind the boxes. **Remove layout** sets it aside, kept for later; **Delete layout** throws it
  away, asking first only if no picture keeps it
- User's Guide: a Layouts page, with an example on the home page
- **Open in Preview** is a button on each picture, in place of double-clicking it
- User's Guide: a shorter home page that leads straight into getting started; the app's name beside the icon
  in the header; the search under the menu, with no bar above the page; Examples under Making images; Install and Uninstall and
  Running locally under Reference; one page of frequently asked questions, troubleshooting included; one page
  for developers, with the technical notes; the BibTeX citation shows its authors again
- A local preview of the User's Guide (`docs/serve.sh`)
- The disk image opens on a window that says how to install, with larger icons

## 1.0.0rc3 (2026-11-08)

- Generate stays at the top of the controls while they scroll
- The Change control shows σ₀², spreading its useful range; older settings files keep their meaning
- A larger picture in the empty history
- User's Guide: the download button first; the sidebar grouped into Getting started, Making images, Reference,
  and About; a page on describing images; menus merged into Controls; timings for an M5 Max; the install page
  for the disk image only; and the developer material moved to CONTRIBUTING.md
- New baseball-card examples across the Change range and across seeds, and the Change guide redrawn from them
- Continuous integration moved to the current GitHub Actions, which run on Node.js 24

## 1.0.0rc2 (2026-11-06)

- A signed and notarized .dmg for installing without Terminal (`scripts/make_dmg.sh`), with Download for Mac
  buttons in the README and the User's Guide

## 1.0.0rc1 (2026-11-02)

First release candidate.

- Text to image, image to image, variations, inpainting, outpainting, cropping, and upscaling with MOSS-Image
- Describe image and Enhance prompt, using MOSS-Image's own text encoder
- Live previews, a history with each image's settings, and optional settings inside PNGs
- Local by design: models downloaded once, on request, with MOSS-Image pinned to a tested version and its pipeline
  code shipped in the package
- Everything kept in one folder, out of Time Machine backups and Spotlight by default
- One-line installer with tested library versions
- User's Guide with menus, examples of each setting, and measured timings
