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

## More

The [developer pages](https://formdo.github.io/blokjutsu/developers.html) cover the architecture, technical
notes, and the release checklist. Plans are in [ROADMAP.md](ROADMAP.md).
