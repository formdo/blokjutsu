# Roadmap

## 2.0

- LoRA training

## Later

- Windows and Linux (NVIDIA first; needs test machines)
- Organizing outputs into folders
- Upscaling beyond 4 MP
- Separate strength for the negative prompt
- Faster generation
- Colorizing old photos

## Done

- Layout editor (1.0)
- Your own models (1.0)
- LoRAs, including LoKr (1.0)
- Writing Tools, AutoFill, Dictation and Emoji & Symbols out of the Edit menu (1.0)

## Not planned

- Mac App Store
- ControlNet: none exists for MOSS-Image; the layout editor and image to image cover much of it
- Smaller-memory versions of the model (8-bit or 4-bit): on Apple silicon they save memory only if the weights
  stay compressed while computing, which MPS doesn't support well, and they cost speed and quality
- Animation: at minutes per picture, even a few seconds of video would take hours

Designs and discussion for each item are in the [GitHub issues](https://github.com/formdo/blokjutsu/issues).
