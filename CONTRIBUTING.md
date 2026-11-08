# Contributing to Blokjutsu

Bug reports, ideas, and pull requests are welcome. For anything larger than a small fix, please open an issue
first so we can agree on the design before you write the code. Contributions are accepted under the project's
[Apache License 2.0](LICENSE).

## Setting up

You need a Mac with Apple silicon to run the model, and Python 3.10 or later. The releases are tested with
Python 3.12.

**1. Get the code.**

```sh
git clone https://github.com/formdo/blokjutsu
cd blokjutsu
```

**2. Create a virtual environment and activate it.** This keeps Blokjutsu's libraries apart from any other
Python on your Mac. Activate it again in each new Terminal window.

```sh
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install Blokjutsu in editable mode.** Your changes to the code take effect the next time the app starts,
with no reinstall. `constraints.txt` pins every library to the version the release was tested with, and `[dev]`
adds pytest. With [uv](https://docs.astral.sh/uv/), use `uv pip install` in place of `pip install`.

```sh
pip install -e ".[dev]" -c constraints.txt
```

## Running the tests

The tests need neither the model nor a graphics processor, and they also run on Linux.

```sh
pytest
```

## Running the app

```sh
python -m blokjutsu
```

The first time, it offers to download the model (about 30 GB).

**Trying the interface without the model.** This option draws placeholder images instead of running the model,
and `--first-run` simulates the downloads. Its settings, logs, and images go to
`~/Library/Application Support/Blokjutsu Trial.noindex`, so your real ones are never touched.

```sh
python -m blokjutsu --fake --first-run
```

**Building the Mac app.** Started from Terminal, the app appears in the Dock as "Python." This builds
`~/Applications/Blokjutsu.app`, which runs the Python in your virtual environment and appears as "Blokjutsu,"
with its icon, in the Dock, Spotlight, and Launchpad. Rebuild it only if you move the virtual environment.

```sh
python -m blokjutsu.macapp
```

## Updating MOSS-Image's code

`blokjutsu/moss_image.py` is MOSS-Image's pipeline code, copied unchanged from the model revision pinned in
`blokjutsu/params.py`. After changing that revision and downloading it, copy the new code in, review the
difference, and run the tests.

```sh
python scripts/vendor_moss.py
git diff blokjutsu/moss_image.py
pytest
```

## Design

- One window: controls on the left, a scrolling history of cards on the right.
- One worker thread owns the pipeline; Qt signals carry progress, previews, and results to the interface.
- Offline by default: `network.go_offline()` sets the Hugging Face offline switches before anything imports
  those libraries. Downloads run in a child process (`python -m blokjutsu.fetch`) after a confirmation dialog.
- Each picture is a folder with `image.png` and `parameters.json` (the MOSS-Image repository's schema 2, so
  folders from its Gradio app load too). The PNG holds only the image unless **Settings in PNG** is on.

## Modules

| module | role |
|---|---|
| `logs.py` | log files; `clear_logs` empties them in place for Delete all history |
| `network.py` | offline-by-default policy; environment and command for confirmed downloads |
| `fetch.py` | the download child process: model snapshot, captioning head (identity check, range read, resume), progress protocol |
| `describe.py` | Describe Image and Enhance Prompt: re-attach the output layer to the text encoder, MOSS's recaptioning prompt |
| `params.py` | `Params` dataclass, validation, seed expansion, `parameters.json` read/write, layout-JSON sanity checks |
| `samplers.py` | flow-matching schedulers (Euler native, Euler SDE with η re-noising, DPM++ 2M, UniPC) |
| `moss_image.py` | MOSS-Image's pipeline code, copied unchanged from the pinned revision by `scripts/vendor_moss.py` (Apache-2.0) |
| `moss_forward.py` | MOSS transformer forward adapted for MPS, with a per-image RoPE/text-projection cache (Apache-2.0, from MOSS-Image) |
| `backend.py` | pipeline load/unload, MPS forward patch with per-image RoPE/text-projection cache, prompt-embedding cache, low-memory text-encoder unloading, block compilation, progress, and cancellation; `FakeBackend` |
| `store.py` | output-folder layout and rescan |
| `preview.py` | linear latent→RGB patch decoder for live previews, fitted online by ridge regression |
| `img2img.py` | image to image: resize/crop, VAE encode to the normalized latent, truncated schedule; inpainting masks, known-region reset, outpaint canvas |
| `vae_preview.py` | exact live previews: real VAE decode of x̂₀ within a 5% time budget, self-checked against the pipeline |
| `worker.py` | daemon thread job queue with Qt signals |
| `single_instance.py` | one running instance per app-data folder; a second launch raises the first window |
| `ui/` | controls panel, history view, background image cache (`image_cache.py`), input policy (`input.py`), main window |

## Behavior notes

Per-control technical notes are in the User's Guide's [Technical notes](https://formdo.github.io/blokjutsu/technical-notes.html).

- **Variations:** a Variation strength above 0 keeps the seed and blends in noise from a per-image
  variation seed, ε = cos(πs/2)·ε_seed + sin(πs/2)·ε_var (exactly N(0, I) for all s). **Generate Similar Image** on a card
  makes Images-many variations of that exact image; repeating it builds a recorded chain.

- **Seed:** 0 means random; the seed actually used is always recorded. *Images = n* runs n
  separate jobs with seeds s, s+1, …, so every image is reproducible from its own record.
  The transformer's forward loops over the batch anyway, so batching would gain nothing.
- **Noise** is always drawn on the CPU, which matches the official Gradio app and reproduces across machines.
- **Compilation** of the transformer blocks is always on; if it fails, the app falls back to uncompiled.
- **Sampler:** Euler with `shift` rebuilds the native `MOSSImageScheduler`, as the Gradio app
  does. The other samplers are generic diffusers flow-matching schedulers and are untested
  against this pipeline. Ancestral samplers (Euler a) are DDPM-family noise-prediction
  schedulers and are incompatible with a rectified-flow velocity model.
- **Cancel** takes effect between denoising steps. The pipeline has no
  `callback_on_step_end`, so the app hooks `pipe.progress_bar`, as the repo's
  `inference_runtime.py` does.

## Images in the guide

Screenshots and examples live in `docs/assets/`. Example images are converted to lossless WebP, about a third
smaller than PNG; the script keeps a file only if it decodes to exactly the original pixels:

```sh
python scripts/lossless_webp.py ~/path/to/pngs docs/assets/examples/samplers
```

## Building the .dmg

`scripts/make_dmg.sh` builds a self-contained `Blokjutsu.app` (a standalone Python with the pinned libraries,
started by a small compiled launcher, `scripts/dmg/launcher.c`), signs every program file in it with the
Developer ID certificate in your keychain, notarizes it with Apple, and wraps it in a signed, notarized .dmg in
`dist/`. Run it from the repository root. To try the app before signing anything:

```sh
scripts/make_dmg.sh --no-sign
```

The release build needs the notarization credentials stored once in your keychain under the profile
`blokjutsu`:

```sh
xcrun notarytool store-credentials blokjutsu --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID
scripts/make_dmg.sh
```

Upload the .dmg to the GitHub release for the tag.

## Versions

- **Libraries:** `constraints.txt` lists the exact versions a release was tested with; the installer installs
  those. To move forward, install without it in a fresh environment, test, then regenerate it with
  `uv pip freeze` (leave out the `-e` line and the full `pyside6`, `pyside6-addons`, `-pdf` and `-webengine`).
- **Model:** `MODEL_REVISIONS` in `blokjutsu/params.py` pins the MOSS-Image commit the app downloads and loads.
  MOSS-Image's pipeline code is copied unchanged into `blokjutsu/moss_image.py`; after moving the pin, run
  `python scripts/vendor_moss.py` to copy the new revision's code, review the diff, and test.

## Releasing

1. On a branch, update `version` in `pyproject.toml`, `blokjutsu/__init__.py`, `CITATION.cff`, and
   `docs/install.sh`; update the download links in `README.md`, `docs/index.md`, and `docs/install.md`, which name
   the version; and add the release to `CHANGELOG.md`.
2. Run the tests, try `python -m blokjutsu --fake --first-run` and a real image, and build the disk image (see
   [Building the .dmg](#building-the-dmg)) to check it signs and notarizes.
3. Open a pull request, wait for the checks, and merge.
4. Tag `main` straight away: the installer on `main` now asks for the new version's source archive, which exists
   only once the tag does. The release workflow then builds the package, publishes it to PyPI (trusted
   publishing), and creates a GitHub release; tags containing `rc` are marked as pre-releases.

   ```sh
   git checkout main
   git pull
   git tag v1.0.0rc3
   git push origin v1.0.0rc3
   ```

5. Attach `dist/Blokjutsu-<version>.dmg` to the GitHub release (Edit, then drop it on "Attach binaries").

One-time setup: GitHub Pages deploys from GitHub Actions (the `pages.yml` workflow builds `docs/`, copying in the
app icon from `blokjutsu/resources/` so there is only one copy); the repository is a trusted publisher on pypi.org
(workflow `release.yml`, environment `pypi`).
