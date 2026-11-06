# Changelog

## 1.0.0rc2 (unreleased)

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
