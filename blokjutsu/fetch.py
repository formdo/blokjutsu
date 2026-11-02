"""Downloads. Run only as a child process, after the user confirms (network.py, ui/download_dialog.py):

    python -m blokjutsu.fetch model REPO
    python -m blokjutsu.fetch caption-head TEXT_ENCODER_DIR OUT_DIR
    python -m blokjutsu.fetch fake SECONDS

Writes one line per event to stdout: STATUS text | PROGRESS done total | DONE path | ERROR text.
"""
from __future__ import annotations

import json
import platform
import struct
import sys
import threading
import time
from pathlib import Path

HUB = "https://huggingface.co"
CAPTION_CANDIDATES = ("Qwen/Qwen3.5-9B", "Qwen/Qwen3.5-9B-Base")
CAPTION_SMALL_FILES = ("config.json", "generation_config.json", "preprocessor_config.json",
                       "video_preprocessor_config.json", "processor_config.json", "chat_template.jinja",
                       "chat_template.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                       "vocab.json", "merges.txt")
HEAD = "lm_head.weight"
HEAD_FILE = "lm_head.safetensors"
SOURCE_FILE = "source.json"
PROBE_ELEMENTS = 1 << 20
ITEMSIZE = {"BF16": 2, "F16": 2, "F32": 4}
CHUNK = 8 << 20


def emit(kind, *fields):
    print(kind, *fields, flush=True)


def status(text):
    emit("STATUS", text)


class Throttle:
    def __init__(self, seconds=0.25):
        self.seconds, self.last = seconds, 0.0

    def __call__(self, done, total):
        now = time.monotonic()
        if now - self.last >= self.seconds or done >= total:
            self.last = now
            emit("PROGRESS", done, total)


# safetensors over byte ranges

class Safetensors:
    """Header and byte ranges of one .safetensors file, read through read(start, stop) with stop exclusive."""

    def __init__(self, read):
        self.read = read
        n = struct.unpack("<Q", read(0, 8))[0]
        self.header = json.loads(read(8, 8 + n))
        self.header.pop("__metadata__", None)
        self.data_start = 8 + n

    def info(self, name):
        return self.header[name]["dtype"], list(self.header[name]["shape"])

    def span(self, name):
        a, b = self.header[name]["data_offsets"]
        return self.data_start + a, self.data_start + b

    def prefix(self, name, limit):
        a, b = self.span(name)
        return self.read(a, min(b, a + limit))

    def values(self, name, count):
        """The first `count` elements as float32 (BF16, F16 or F32 storage)."""
        dtype = self.info(name)[0]
        return decode(self.prefix(name, count * ITEMSIZE[dtype]), dtype)


def local_reader(path):
    def read(start, stop):
        with open(path, "rb") as f:
            f.seek(start)
            return f.read(stop - start)
    return read


def http_reader(client, url):
    def read(start, stop):
        with client.stream("GET", url, headers={"Range": f"bytes={start}-{stop - 1}"}) as r:
            r.raise_for_status()
            if r.status_code != 206:      # never fall through to downloading a whole multi-GB shard
                raise OSError(f"{url} ignored the byte range")
            return r.read()
    return read


def tensor_header(name, dtype, shape, nbytes):
    """Bytes before the data of a one-tensor .safetensors file."""
    meta = json.dumps({name: {"dtype": dtype, "shape": shape, "data_offsets": [0, nbytes]}}).encode()
    meta += b" " * (-len(meta) % 8)
    return struct.pack("<Q", len(meta)) + meta


# numerics

def decode(raw, dtype):
    import numpy as np
    if dtype == "BF16":
        return (np.frombuffer(raw, "<u2").astype("<u4") << 16).view("<f4")
    return np.frombuffer(raw, {"F16": "<f2", "F32": "<f4"}[dtype]).astype("<f4")


def round_to(x, dtype):
    """float32 values rounded to the precision of `dtype` (round to nearest even), still as float32."""
    if dtype == "BF16":
        u = x.astype("<f4").view("<u4")
        return (((u + 0x7FFF + ((u >> 16) & 1)) >> 16) << 16).astype("<u4").view("<f4")
    if dtype == "F16":
        return x.astype("<f2").astype("<f4")
    return x


def coarser(a, b):
    return "BF16" if "BF16" in (a, b) else "F16" if "F16" in (a, b) else "F32"


def compare(local, name, remote, other, count=PROBE_ELEMENTS):
    """Agreement of one tensor in two checkpoints, after rounding both to the coarser storage precision."""
    import numpy as np
    (da, sa), (db, sb) = local.info(name), remote.info(other)
    result = dict(name=name, local=f"{da}{sa}", remote=f"{db}{sb}", same=False)
    if sa != sb:
        return result
    x, y = local.values(name, count), remote.values(other, count)
    precision = coarser(da, db)
    x, y = round_to(x, precision), round_to(y, precision)
    scale = float(np.sqrt(np.mean(x.astype("f8") ** 2))) or 1.0
    result.update(same=bool(np.array_equal(x.view("<u4"), y.view("<u4"))),     # bitwise: NaN == NaN
                  max_abs=float(np.nanmax(np.abs(x - y))),
                  rel_rms=float(np.sqrt(np.mean((x.astype("f8") - y) ** 2))) / scale,
                  offset=float(np.mean(y.astype("f8") - x)))
    return result


def describe_comparison(r):
    if "max_abs" not in r:
        return f"{r['name']}: shape or presence differs (MOSS {r['local']}, Qwen {r.get('remote', 'missing')})"
    verdict = "identical" if r["same"] else "DIFFERENT"
    return (f"{r['name']}: {verdict} (MOSS {r['local']}, Qwen {r['remote']}; max |Δ| {r['max_abs']:.3g}, "
            f"relative RMS {r['rel_rms']:.3g}, mean offset {r['offset']:.3g})")


# caption head

def probe_names(weight_map):
    """Small, fine-tuning-sensitive tensors (norms across the depth) plus the start of the token embedding."""
    names = sorted(n for n in weight_map if not n.startswith("visual."))
    norms = [n for n in names if n.endswith("norm.weight")]
    picked = norms[:2] + norms[len(norms) // 2:len(norms) // 2 + 1] + norms[-1:]
    picked += [n for n in names if n.endswith("embed_tokens.weight")][:1]
    return list(dict.fromkeys(picked))


def canonical(name):
    for prefix in ("model.", "language_model."):
        name = name.removeprefix(prefix)
    return name


def remote_name(name, remote_map):
    """The remote tensor for a local one, ignoring 'model.' / 'language_model.' prefixes."""
    if name in remote_map:
        return name
    wanted = canonical(name)
    found = [n for n in remote_map if canonical(n) == wanted and n.startswith("visual") == name.startswith("visual")]
    return found[0] if len(found) == 1 else None


class ShardSet:
    """Lazily opened shards of one checkpoint, addressed by tensor name."""

    def __init__(self, weight_map, open_file):
        self.weight_map, self.open_file, self.files = weight_map, open_file, {}

    def __getitem__(self, name):
        file = self.weight_map[name]
        if file not in self.files:
            self.files[file] = Safetensors(self.open_file(file))
        return self.files[file]


def comparisons(local, remote, remote_map, names):
    out = []
    for name in names:
        other = remote_name(name, remote_map)
        if other is None:
            out.append(dict(name=name, local="".join(map(str, local[name].info(name))), remote="missing",
                            same=False))
        else:
            out.append(compare(local[name], name, remote[other], other))
    return out


def identical(local, remote, remote_map, names):
    """Whether every probe tensor has the same shape and values (at the coarser storage precision)."""
    return all(r["same"] for r in comparisons(local, remote, remote_map, names))


def stream_tensor(client, url, shard, name, dest, on_progress):
    """Copy one tensor out of a remote shard into a one-tensor .safetensors file; resumes a partial copy."""
    dtype, shape = shard.info(name)
    a, b = shard.span(name)
    head = tensor_header(name, dtype, shape, b - a)
    part = dest.with_suffix(".part")
    done = 0
    if part.exists() and part.stat().st_size >= len(head) and local_reader(part)(0, len(head)) == head:
        done = part.stat().st_size - len(head)
    else:
        part.write_bytes(head)
    with open(part, "ab") as f:
        if done < b - a:
            with client.stream("GET", url, headers={"Range": f"bytes={a + done}-{b - 1}"}) as r:
                r.raise_for_status()
                if r.status_code != 206:
                    raise OSError(f"{url} ignored the byte range")
                for chunk in r.iter_bytes(CHUNK):
                    f.write(chunk)
                    done += len(chunk)
                    on_progress(done, b - a)
    if part.stat().st_size != len(head) + (b - a):
        raise OSError(f"{part} has the wrong size; run the download again")
    part.replace(dest)
    return dtype, shape


def http_client():
    import httpx
    from . import __version__

    agent = f"blokjutsu/{__version__}; python/{platform.python_version()}; httpx/{httpx.__version__}"
    return httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0), headers={"User-Agent": agent})


def previous_source(out):
    """The repo and revision recorded by an earlier verified download, or None."""
    try:
        source = json.loads((Path(out) / SOURCE_FILE).read_text())
        return source if source.get("repo") and source.get("revision") else None
    except (OSError, ValueError):
        return None


def verify_candidates(client, local, probes):
    """The first candidate Qwen checkpoint identical to MOSS's encoder on every probe tensor."""
    for repo in CAPTION_CANDIDATES:
        status(f"Checking whether {repo} matches the MOSS text encoder…")
        sha = client.get(f"{HUB}/api/models/{repo}/revision/main").raise_for_status().json()["sha"]
        base = f"{HUB}/{repo}/resolve/{sha}/"
        remote_map = client.get(base + "model.safetensors.index.json").raise_for_status().json()["weight_map"]
        remote = ShardSet(remote_map, lambda f, base=base: http_reader(client, base + f))
        results = comparisons(local, remote, remote_map, probes)
        for r in results:
            emit("DETAIL", f"{repo} · " + describe_comparison(r))
        if all(r["same"] for r in results):
            return repo, sha, base, remote_map, remote
    raise RuntimeError("Neither " + " nor ".join(CAPTION_CANDIDATES) + " matches the MOSS text encoder exactly, "
                       "so no captioning head was downloaded.")


def fetch_caption_head(te_dir, out_dir):
    te_dir, out = Path(te_dir), Path(out_dir)
    local_map = json.loads((te_dir / "model.safetensors.index.json").read_text())["weight_map"]
    local = ShardSet(local_map, lambda f: local_reader(te_dir / f))
    probes = probe_names(local_map)
    emit("DETAIL", f"MOSS text encoder: {te_dir}")
    pinned = previous_source(out)
    with http_client() as client:
        if pinned:                     # verified before: the same repo and revision, no second comparison
            repo, sha = pinned["repo"], pinned["revision"]
            status(f"Using {repo} (revision {sha[:8]}), verified when first downloaded…")
            base = f"{HUB}/{repo}/resolve/{sha}/"
            remote_map = client.get(base + "model.safetensors.index.json").raise_for_status().json()["weight_map"]
            remote = ShardSet(remote_map, lambda f: http_reader(client, base + f))
            probes = pinned.get("verified_identical", probes)
        else:
            repo, sha, base, remote_map, remote = verify_candidates(client, local, probes)
        if HEAD not in remote_map:
            raise RuntimeError(f"{repo} has no {HEAD}")
        out.mkdir(parents=True, exist_ok=True)
        status("Downloading tokenizer and image-processor settings…")
        for name in CAPTION_SMALL_FILES:
            r = client.get(base + name)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            (out / name).write_bytes(r.content)
        status(f"Downloading the captioning head from {repo}…")
        dtype, shape = stream_tensor(client, base + remote_map[HEAD], remote[HEAD], HEAD, out / HEAD_FILE,
                                     Throttle())
    (out / SOURCE_FILE).write_text(json.dumps(
        {"repo": repo, "revision": sha, "tensor": HEAD, "dtype": dtype, "shape": shape,
         "verified_identical": probes}, indent=2))
    return out / HEAD_FILE


# model

def folder_bytes(folder):
    try:
        return sum(p.stat().st_size for p in Path(folder).iterdir() if p.is_file())
    except OSError:
        return 0


def fetch_model(repo):
    """Download `repo` at its tested revision (params.MODEL_REVISIONS), or the newest one if it has none."""
    from huggingface_hub import HfApi, snapshot_download
    from huggingface_hub.constants import HF_HUB_CACHE

    from .params import model_revision

    revision = model_revision(repo)
    status(f"Asking huggingface.co for the file list of {repo}…")
    info = HfApi().model_info(repo, revision=revision, files_metadata=True)
    total = sum(s.size or 0 for s in info.siblings)
    blobs = Path(HF_HUB_CACHE) / ("models--" + repo.replace("/", "--")) / "blobs"
    report, stop = Throttle(0.5), threading.Event()

    def watch():
        while not stop.wait(0.5):
            report(min(folder_bytes(blobs), total), total)

    threading.Thread(target=watch, daemon=True).start()
    status(f"Downloading {repo} (files already in the cache are skipped)…")
    path = snapshot_download(repo, revision=info.sha)
    stop.set()
    emit("PROGRESS", total, total)
    return path


def fake(seconds):
    """Simulated download for --fake: no network."""
    status("Simulated download (fake backend): nothing is contacted.")
    total, steps = 2_034_237_440, max(1, int(seconds * 10))
    for k in range(1, steps + 1):
        time.sleep(seconds / steps)
        emit("PROGRESS", total * k // steps, total)
    return "(fake)"


def main(argv):
    try:
        kind, *args = argv
        path = {"model": fetch_model, "caption-head": fetch_caption_head,
                "fake": lambda s: fake(float(s))}[kind](*args)
        emit("DONE", path)
        return 0
    except Exception as exc:
        emit("ERROR", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    import os
    from .settings import models_dir
    os.environ.setdefault("HF_HUB_CACHE", str(models_dir()))
    sys.exit(main(sys.argv[1:]))
