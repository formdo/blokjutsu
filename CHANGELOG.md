# Changelog

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
