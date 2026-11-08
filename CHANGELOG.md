# Changelog

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
