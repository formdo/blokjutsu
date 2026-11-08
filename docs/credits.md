---
title: Credits and licenses
parent: About
nav_order: 4
---

# Credits and licenses

## MOSS-Image

Blokjutsu is an independent app for **MOSS-Image**, the open-weight text-to-image model and pipeline by the OpenMOSS
Team and MOSI.AI. All of the picture-making is theirs. Blokjutsu is not affiliated with or endorsed by them.

- Repository: [github.com/OpenMOSS/MOSS-Image](https://github.com/OpenMOSS/MOSS-Image)
- Technical report: [arxiv.org/abs/2610.23374](https://arxiv.org/abs/2610.23374)
- User guide: [USERGUIDE.md](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md)

If you use pictures or results from Blokjutsu in research, please cite MOSS-Image:

```bibtex
@misc{mossimage2026,
  title        = {MOSS-Image},
  author       = {{OpenMOSS Team}},
  year         = {2026},
  howpublished = {\url{https://github.com/OpenMOSS/MOSS-Image}}
}
@misc{mossimage2026report,
  title         = {MOSS-Image Technical Report},
  author        = {{MOSI.AI}},
  year          = {2026},
  eprint        = {2610.23374},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2610.23374}
}
```

## Models

MOSS-Image's model is published on Hugging Face as MOSS-Image-SFT (and the untuned MOSS-Image-Base). Its text
encoder and image decoder, from Qwen and FLUX.2, are included in that download.

| model | by | license |
|---|---|---|
| [MOSS-Image-SFT](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT), [MOSS-Image-Base](https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base) | OpenMOSS Team | Apache-2.0 |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B): MOSS-Image's text encoder; its output layer is downloaded separately for describing | Qwen Team, Alibaba Cloud | Apache-2.0 |
| [FLUX.2 VAE](https://github.com/black-forest-labs/flux2): MOSS-Image's image decoder | Black Forest Labs | Apache-2.0 |

## Libraries

PyTorch and torchvision (BSD-3-Clause), Diffusers, Transformers, Accelerate, huggingface_hub, and safetensors
(Apache-2.0, Hugging Face), PySide6 / Qt (LGPL-3.0), Pillow (MIT-CMU), NumPy and httpx (BSD-3-Clause), PyObjC
(MIT), and uv (Apache-2.0 / MIT, Astral) for installing.

## Open source

Blokjutsu, MOSS-Image's code, and MOSS-Image's model weights (including the Qwen3.5-9B text encoder and FLUX.2
image decoder inside them) are all released under the Apache License 2.0. Anyone may use, study, change, and
share them, for any purpose, commercial or not, provided the license and copyright notices are kept and changes
are noted. The license also grants the patent rights needed to use them.

## Pictures in this guide

The ice cream pictures and the examples were made with Blokjutsu. The baseball card used as a starting picture in
[Examples](examples.md#starting-from-a-picture) is [Cy Young, Cleveland Naps, baseball card portrait], card set
White Borders (T206), issued by the American Tobacco Company, 1909–1911, from the Library of Congress, Prints and
Photographs Division (Benjamin K. Edwards Collection), with no known restrictions on publication
([loc.gov/pictures/item/2008676577](https://www.loc.gov/pictures/item/2008676577/)).

The photograph in [Describing images](describing.md) is "Sunday cyclists in East Potomac Park, Washington, D.C." by Marjory Collins, June–July 1942, from the Library
of Congress's Farm Security Administration/Office of War Information collection, which is in the public domain
([loc.gov/item/2017825632](https://www.loc.gov/item/2017825632/)).

## Blokjutsu

Written by Bob Carpenter together with Claude, Anthropic's AI model. Copyright 2026 Bob Carpenter, Apache
License 2.0. Two files come from MOSS-Image's own code (also Apache-2.0): `blokjutsu/moss_image.py`, copied
unchanged, and `blokjutsu/moss_forward.py`, adapted from it. To cite Blokjutsu itself, use the "Cite this repository" button on
[GitHub](https://github.com/formdo/blokjutsu).

"MOSS-Image" is the OpenMOSS Team's name and is used here only to say what Blokjutsu runs.

## Etymology

**Blokjutsu** (BLOK-joot-soo, /ˈblɒk.dʒuː.tsuː/), *noun*. The art of the block.

From Danish *blok*, "block," and Japanese *jutsu* (術, じゅつ), "art" or "technique." The name comes from how
MOSS-Image works: it treats an image as blocks of pixels, each 16 × 16 square one unit for the model, and
transforms them step by step from noise into the finished image.

## Design inspiration

The block designs in the icon and the app draw on

- the [Kohs block design test](https://en.wikipedia.org/wiki/Kohs_block_design_test){:target="_blank"},
  introduced by Samuel C. Kohs in 1920: colored cubes, some faces split diagonally, arranged to match a pattern
- [Froebel's gifts](https://en.wikipedia.org/wiki/Froebel_gifts){:target="_blank"}, the wooden building blocks of
  Friedrich Fröbel's first kindergartens
- the primary colors and simple geometry of the [Bauhaus](https://en.wikipedia.org/wiki/Bauhaus){:target="_blank"}
