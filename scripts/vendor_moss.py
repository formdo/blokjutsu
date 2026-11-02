"""Copy MOSS-Image's pipeline code into the package as blokjutsu/moss_image.py, unchanged under a header.

Usage: python scripts/vendor_moss.py [SNAPSHOT_FOLDER_OR_FILE]
Default source: the pinned MOSS-Image-SFT snapshot in the Hugging Face cache. Run again after changing
MODEL_REVISIONS in params.py.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blokjutsu import params as P  # noqa: E402

REPO = P.DEFAULT_MODEL
NAME = "pipeline_moss_image.py"
COPIES = (NAME, f"scheduler/{NAME}", f"transformer/{NAME}")
TARGET = ROOT / "blokjutsu" / "moss_image.py"
SEPARATOR = "# ---\n"


def default_snapshot():
    from blokjutsu.settings import models_dir
    folder = "models--" + REPO.replace("/", "--")
    return models_dir() / folder / "snapshots" / P.model_revision(REPO)


def original(source):
    """The file's bytes; for a snapshot folder, all three copies must agree."""
    if source.is_file():
        return source.read_bytes()
    texts = {(source / copy).read_bytes() for copy in COPIES}
    if len(texts) != 1:
        sys.exit(f"The copies of {NAME} in {source} differ.")
    return texts.pop()


def header(digest):
    return (f"# Copied unchanged from {REPO} (https://huggingface.co/{REPO}), file {NAME} at revision\n"
            f"# {P.model_revision(REPO)}; SHA-256 of the original {digest}.\n"
            "# Copyright the OpenMOSS Team / MOSI.AI. Licensed under the Apache License, Version 2.0 (see LICENSE\n"
            "# and NOTICE). Everything below the separator is the original file; scripts/vendor_moss.py writes it.\n"
            + SEPARATOR)


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else default_snapshot()
    body = original(source)
    digest = hashlib.sha256(body).hexdigest()
    TARGET.write_bytes(header(digest).encode() + body)
    print(f"Wrote {TARGET.relative_to(ROOT)} (SHA-256 {digest}).")


if __name__ == "__main__":
    main()
