<p align="center"><img src="blokjutsu/resources/icon.png" width="128" alt="Blokjutsu icon"></p>

# Blokjutsu

**A local, permissively licensed, open-source Mac app for generating and editing images from text prompts with
the open-weight [MOSS-Image](https://github.com/OpenMOSS/MOSS-Image) model.**

- **Local.** The model runs locally on your Mac. Prompts and images never leave your machine.
- **Permissive open source ([Apache 2.0](https://en.wikipedia.org/wiki/Apache_License)).** The app, MOSS-Image's
  code, and MOSS-Image's model weights are all under the Apache License 2.0. Use them for anything, commercial or
  not, and change and share them, with no restrictions on what you make.
- **Download once.** The image model (about 30 GB) and the optional captioning model (2 GB) are downloaded once,
  when you ask. After that, everyday use doesn't go online at all.

**Simple on purpose:** a small set of controls designed to work together and to be quick to learn.

[![Download for Mac](https://img.shields.io/badge/-Download_for_Mac-2f6fde?style=flat)](https://github.com/formdo/blokjutsu/releases/download/v1.0.0rc2/Blokjutsu-1.0.0rc2.dmg)

**Using Blokjutsu?** Start with the [User's Guide](https://formdo.github.io/blokjutsu/): installing, a tour of the
window, writing prompts, and every control explained.

![The Blokjutsu window: controls on the left; on the right, an image of three bowls of ice cream on a diner counter with handwritten cards reading CHOCOLATE, CHERRY, and PLAIN](docs/assets/screenshots/main-window.webp)

## What Blokjutsu does

- Text to image, image to image, variations, inpainting, outpainting, cropping, and upscaling
- Describe image and Enhance prompt, written by MOSS-Image's own text encoder
- Live previews, a scrolling history, and each image's settings saved beside it

## Open source all the way down

With Blokjutsu, the model, the code that runs it, and the app around it are all yours to run, keep, and adapt.

Every part of Blokjutsu is released under the [Apache License 2.0](LICENSE), a
[permissive](https://en.wikipedia.org/wiki/Comparison_of_free_and_open-source_software_licenses) open-source
license:

- **Blokjutsu's source code**, in this repository
- **MOSS-Image's code**, the pipeline that turns a prompt into an image
- **MOSS-Image's model weights**, including the Qwen3.5-9B text encoder and FLUX.2 image decoder they contain

Apache 2.0 lets anyone use, study, change, and share all of it, for any purpose, commercial or not, at no cost,
and with no sign-up. The conditions are light: keep the license and copyright notices, and say what you changed.
It also grants the patent rights needed to use the code. The libraries Blokjutsu builds on are open source too
(see [What it uses](#what-it-uses)).

## Requirements

- A Mac with Apple silicon (M1 or later) and macOS 12.3 or later
- 32 GB of memory or more; 48 GB or more is comfortable, and smaller Macs work slowly, if at all
- About 40 GB of free disk space, mostly for the model

## Install

**Mac users:** download the disk image with the **Download for Mac** button at the top (1.0.0rc2, 375 MB), open it, and drag Blokjutsu to
Applications. Or install from Terminal by pasting

```sh
curl -LsSf https://formdo.github.io/blokjutsu/install.sh | sh
```

This installs Python and Blokjutsu into `~/Library/Application Support/Blokjutsu.noindex/` and puts
**Blokjutsu** in your Applications folder. Nothing else on your Mac is changed. See the
[User's Guide](https://formdo.github.io/blokjutsu/install.html) for details and uninstalling.

**Python developers:** Blokjutsu needs Python 3.10 or later. We strongly suggest installing it in its own virtual
environment. The exact library versions it was tested with are in [constraints.txt](constraints.txt), which pip
can use with `-c constraints.txt`.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install blokjutsu
blokjutsu
```

## Built on MOSS-Image

Blokjutsu is an independent desktop front end for **MOSS-Image**, the text-to-image model and pipeline by the
[OpenMOSS Team](https://github.com/OpenMOSS) and [MOSI.AI](https://mosi.cn/). Blokjutsu is not affiliated with or
endorsed by them. All of the image-making is theirs.

- Repository: https://github.com/OpenMOSS/MOSS-Image
- Technical report: https://arxiv.org/abs/2610.23374
- User guide: https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md

If you use images or results from Blokjutsu in research, please cite MOSS-Image:

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

## What it uses

The models are downloaded from [Hugging Face](https://huggingface.co), a site that hosts open AI models, and
only when you ask. MOSS-Image's model is published there as MOSS-Image-SFT; its text encoder and image decoder
come from Qwen and FLUX.2 and are included in that download.

| model | by | license | role |
|---|---|---|---|
| [MOSS-Image-SFT](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT) | OpenMOSS Team | Apache-2.0 | MOSS-Image's model, used by default |
| [MOSS-Image-Base](https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base) | OpenMOSS Team | Apache-2.0 | the untuned model, for people training their own versions (optional) |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | Qwen Team, Alibaba Cloud | Apache-2.0 | reads prompts (part of MOSS-Image); with its output layer, downloaded separately, writes descriptions |
| [FLUX.2 VAE](https://github.com/black-forest-labs/flux2) | Black Forest Labs | Apache-2.0 | turns the model's output into pixels (part of MOSS-Image) |

Python libraries, installed alongside:

| library | license | role |
|---|---|---|
| [PyTorch](https://pytorch.org), torchvision | BSD-3-Clause | numerical engine on the Apple GPU |
| [Diffusers](https://github.com/huggingface/diffusers) | Apache-2.0 | runs the MOSS-Image pipeline |
| [Transformers](https://github.com/huggingface/transformers), Accelerate | Apache-2.0 | text encoder, describing |
| [huggingface_hub](https://github.com/huggingface/huggingface_hub), safetensors | Apache-2.0 | model files and downloads |
| [httpx](https://www.python-httpx.org) | BSD-3-Clause | the confirmed downloads |
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | LGPL-3.0 | the window and controls |
| [Pillow](https://python-pillow.org) | MIT-CMU | image files |
| [NumPy](https://numpy.org) | BSD-3-Clause | arrays |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) | MIT | macOS system icons and app name |

## Local by design

Blokjutsu runs the model on your Mac's own processor and memory. It uses the internet only once to initially
download the models, and then, only after a confirmation dialog. After the models are downloaded once, Blokjutsu
works completely offline. It does not go online to generate, edit, or store images. It does not go online to
check for updates to itself.

Images are saved as plain PNG files that hold only the image. If you want, a setting in Advanced options also
writes each image's prompt and settings into the PNG.

### What Blokjutsu keeps on your Mac

| what | where | Delete all history |
|---|---|---|
| your images, each with its settings and any image you started from | the Output folder you choose (by default `~/Library/Application Support/Blokjutsu.noindex/images/`) | deleted, in every Output folder used |
| the log, for troubleshooting | `~/Library/Application Support/Blokjutsu.noindex/logs/` | emptied |
| working copies from Select area to change | `…/Blokjutsu.noindex/work/` | deleted |
| a small file the live preview needs, built from your images | `…/Blokjutsu.noindex/preview/` | deleted |
| your settings, including the last prompt | `…/Blokjutsu.noindex/settings.json` | prompt reset, preferences kept |
| the captioning model | `…/Blokjutsu.noindex/caption/` | kept |
| the image model | `…/Blokjutsu.noindex/models/` | kept |
| the app and the Python it runs on | `~/Applications/Blokjutsu.app`, `…/Blokjutsu.noindex/tools/`, and `…/Blokjutsu.noindex/runtime/` | kept |

The whole `…/Blokjutsu.noindex` folder is kept out of Time Machine backups and Spotlight. To back up your images,
choose an Output folder elsewhere, such as `~/Pictures/Blokjutsu`.

**Delete all history** (in the File menu) removes everything made from your prompts and images and keeps your
preferences and the models. The [User's Guide](https://formdo.github.io/blokjutsu/local.html) has the details, including what macOS itself
remembers.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up a development environment, run the tests, and build the
Mac app. Architecture and technical notes are in the [developer pages](https://formdo.github.io/blokjutsu/developers.html).

## Roadmap

What comes next is in [ROADMAP.md](ROADMAP.md).

## Bug reports and feature requests

Please report bugs and request features as [GitHub issues](https://github.com/formdo/blokjutsu/issues). For help
using Blokjutsu, see the [User's Guide](https://formdo.github.io/blokjutsu/) and its
[Troubleshooting](https://formdo.github.io/blokjutsu/troubleshooting.html) page.

## Etymology

**Blokjutsu** (BLOK-joot-soo, /ˈblɒk.dʒuː.tsuː/), *noun*. The art of the block.

From Danish *blok*, "block," and Japanese *jutsu* (術, じゅつ), "art" or "technique." The name comes from how
MOSS-Image works: it treats an image as blocks of pixels, each 16 × 16 square one unit for the model, and
transforms them step by step from noise into the finished image.

## Design inspiration

The block designs in the icon and the app draw on

- the [Kohs block design test](https://en.wikipedia.org/wiki/Kohs_block_design_test), introduced by Samuel C.
  Kohs in 1920: colored cubes, some faces split diagonally, arranged to match a pattern
- [Froebel's gifts](https://en.wikipedia.org/wiki/Froebel_gifts), the wooden building blocks of Friedrich
  Fröbel's first kindergartens
- the primary colors and simple geometry of the [Bauhaus](https://en.wikipedia.org/wiki/Bauhaus)

## Authors

Blokjutsu was written by Bob Carpenter together with Claude, Anthropic's AI model.

## License

Copyright 2026 Bob Carpenter. Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).
`blokjutsu/moss_image.py` is MOSS-Image's pipeline code, copied unchanged, and `blokjutsu/moss_forward.py` is
adapted from it (both Apache-2.0). "MOSS-Image" is the OpenMOSS Team's name and is used here only to say what
this app runs.
