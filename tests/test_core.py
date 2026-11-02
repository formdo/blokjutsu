import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from blokjutsu import params as P
from blokjutsu import store
from blokjutsu.backend import FakeBackend

EXAMPLE = Path(__file__).with_name("example_parameters.json")


def test_repo_example_round_trip():
    p = P.from_record(json.loads(EXAMPLE.read_text()))
    assert (p.width, p.height, p.steps, p.cfg, p.shift, p.seed) == (1776, 1184, 50, 5.0, 5.0, 3072627948)
    assert p.model == "OpenMOSS-Team/MOSS-Image-SFT" and p.uncond_skip_layers == "22"
    P.validate(p, 42)
    assert P.from_record(P.to_record(p)) == p
    assert P.layout_warnings(p) == (None, [])


def test_layout_size_mismatch_warns():
    p = replace(P.from_record(json.loads(EXAMPLE.read_text())), width=1024, height=1024)
    assert P.layout_warnings(p)[1]


def test_bad_json_reported():
    assert P.layout_warnings(P.Params(prompt="{not json"))[0]


def test_realize_seeds():
    jobs = P.realize(P.Params(prompt="x", seed=P.SEED_MAX - 1, num_images=3))
    assert [j.seed for j in jobs] == [P.SEED_MAX - 1, P.SEED_MAX, 1]
    assert all(j.num_images == 1 for j in jobs)
    assert all(1 <= j.seed <= P.SEED_MAX for j in P.realize(P.Params(prompt="x", num_images=5)))


@pytest.mark.parametrize("bad", [dict(width=1000), dict(seed=-1), dict(slg_start=0.5, slg_stop=0.4),
                                 dict(uncond_skip_layers="22,22"), dict(prompt=" ")])
def test_validation(bad):
    with pytest.raises(ValueError):
        P.validate(replace(P.Params(prompt="x"), **bad))


def test_layer_bound():
    with pytest.raises(ValueError):
        P.validate(P.Params(prompt="x", slg_layers="42"), num_layers=42)


def test_store_save_scan(tmp_path):
    a = store.save(tmp_path, P.Params(prompt="a", seed=5), Image.new("RGB", (32, 16)), elapsed_seconds=1.5)
    b = store.save(tmp_path, P.Params(prompt="b", seed=6), Image.new("RGB", (32, 16)))
    (tmp_path / "junk").mkdir()
    entries = store.scan(tmp_path)
    assert [e.params.prompt for e in entries] == ["b", "a"]
    assert (a.folder.name, b.folder.name) == ("00001", "00002")
    assert entries[1].elapsed == 1.5


def test_store_reads_gradio_batch(tmp_path):
    folder = tmp_path / "abc"
    folder.mkdir()
    for name in ("01.png", "02.png"):
        Image.new("RGB", (16, 16)).save(folder / name)
    record = {"schema_version": 2, "model": "OpenMOSS-Team/MOSS-Image-Base",
              "parameters": {"prompt": "p", "seed": -1}, "images": ["01.png", "02.png"]}
    (folder / "parameters.json").write_text(json.dumps(record))
    assert len(store.scan(tmp_path)) == 2


def test_fake_backend():
    stages, steps = [], []
    image, meta = FakeBackend(0).generate(P.Params(prompt="x", width=64, height=32, steps=3, seed=1),
                                          lambda s, n: stages.append(s), lambda k, n: steps.append(k),
                                          lambda: False)
    assert image.size == (64, 32) and steps == [1, 2, 3] and stages == ["encode", "denoise", "decode"]


def test_settings_json_round_trip():
    p = P.Params(prompt="x", seed=9, compile_transformer=True, noise_device="mps")
    assert P.from_json(P.to_json(p)) == p


def test_settings_file(tmp_path, monkeypatch=None):
    from blokjutsu.settings import Settings
    s = Settings(tmp_path / "home" / "settings.json")
    s.set("output_dir", "/x")
    s.set("params", json.loads(P.to_json(P.Params(prompt="p"))))
    s.save()
    t = Settings(tmp_path / "home" / "settings.json")
    assert t.get("output_dir") == "/x"
    assert P.from_json(json.dumps(t.get("params"))).prompt == "p"


def test_linear_preview_recovers_linear_decoder(tmp_path):
    import numpy as np
    from blokjutsu.preview import LinearPreview, PATCH
    rng = np.random.default_rng(0)
    c, h, w = 8, 6, 5
    W = rng.normal(0, 0.05, (c + 1, PATCH * PATCH * 3))
    W[-1] += 0.5

    def render(z):
        x = np.hstack([z.reshape(c, -1).T, np.ones((h * w, 1))]) @ W
        x = np.clip(x, 0, 1).reshape(h, w, PATCH, PATCH, 3).transpose(0, 2, 1, 3, 4)
        return (x.reshape(h * PATCH, w * PATCH, 3) * 255).round().astype(np.uint8)

    dec = LinearPreview(tmp_path / "m.npz")
    assert not dec.ready
    for _ in range(4):
        z = rng.normal(size=(c, h, w))
        dec.add(z, render(z))
    z = rng.normal(size=(c, h, w))
    err = np.abs(dec.decode(z).astype(int) - render(z).astype(int))
    assert err.mean() < 3
    assert LinearPreview(tmp_path / "m.npz").ready


def test_store_delete_only_image_folders(tmp_path):
    entry = store.save(tmp_path, P.Params(prompt="a"), Image.new("RGB", (16, 16)))
    other = tmp_path / "keep"
    other.mkdir()
    assert not store.delete(other) and other.exists()
    assert store.delete(entry.folder) and not entry.folder.exists()


def test_defaults():
    d = P.Params()
    assert (d.width, d.height, d.steps, d.cfg) == (512, 768, 20, 4.0)


def test_size_presets():
    from blokjutsu import sizes as S
    for aspect in S.ASPECTS:
        a, b = S.ratio(aspect)
        listed = S.presets(aspect)
        assert 5 <= len(listed) <= 16
        for w, h in listed:
            assert w % 16 == 0 and h % 16 == 0 and w * b == h * a
            assert S.aspect_of(w, h) == aspect
    assert (512, 768) in S.presets("2:3")
    assert S.aspect_of(1000, 600) is None


def test_preset_labels_unique():
    from blokjutsu import sizes as S
    for aspect in S.ASPECTS:
        labels = [S.label(w, h) for w, h in S.presets(aspect)]
        assert len(set(labels)) == len(labels)


def test_variation_batch_and_chain():
    p = P.Params(prompt="x", seed=7, num_images=3, variation=0.1)
    jobs = P.realize(p)
    assert {j.seed for j in jobs} == {7}
    assert len({j.variation_seed for j in jobs}) == 3 and all(j.variation_seed for j in jobs)
    fixed = P.realize(replace(p, variation_seed=100))
    assert [j.variation_seed for j in fixed] == [100, 101, 102]
    child = P.vary_from(fixed[1], 0.05, 4)
    assert child.variation_base == "101:0.1" and child.num_images == 4 and child.seed == 7
    grandchild = P.realize(child)[0]
    assert P.variation_chain(grandchild)[0] == (101, 0.1) and P.variation_chain(grandchild)[1][1] == 0.05
    assert P.from_record(P.to_record(grandchild)) == grandchild


def test_no_variation_keeps_consecutive_seeds():
    jobs = P.realize(P.Params(prompt="x", seed=5, num_images=3))
    assert [j.seed for j in jobs] == [5, 6, 7] and all(j.variation_seed == 0 for j in jobs)


def test_exact_preview_budget_spacing():
    from blokjutsu.vae_preview import VaePreview
    v = VaePreview()
    v.verified, v.cost = True, 0.6
    spent, shown = 0.0, []
    for step in range(1, 21):
        if v.due(step, 20, spent, 1.6):
            spent += v.cost
            shown.append(step)
    assert shown and shown[0] >= 6 and all(b - a > 1 for a, b in zip(shown, shown[1:]))
    assert spent <= 0.05 * 1.6 * 20 + 1e-9
    v.verified = False
    assert not v.due(10, 20, 0.0, 1.6, nothing_shown=True)      # failed check: never


def test_exact_preview_when_nothing_else_shows():
    from blokjutsu.vae_preview import VaePreview
    v = VaePreview()                                             # first picture: cost still the 1 s guess
    due = [s for s in range(1, 21) if v.due(s, 20, 0.0, 0.3, nothing_shown=True)]
    assert due and due[0] == 10
    assert not any(v.due(s, 20, 0.0, 0.3) for s in range(1, 21))


def test_img2img_helpers(tmp_path):
    import numpy as np
    from blokjutsu import img2img as I
    z = np.arange(2 * 3 * 4 * 6, dtype=float).reshape(2, 3, 4, 6)
    assert np.array_equal(I.unpatchify(I.patchify(z)), z)
    assert I.patchify(z).shape == (2, 12, 2, 3)
    w, h = I.fit_size(4000, 3000)
    assert w % 16 == 0 and h % 16 == 0 and w * h <= 2.1e6 and abs(w / h - 4 / 3) < 0.02
    assert I.fit_size(640, 480) == (640, 480)
    sig = [1.0, 0.9, 0.7, 0.5, 0.3, 0.1, 0.0]
    assert I.start_index(sig, 1.0) == 0 and I.start_index(sig, 0.5) == 3 and I.start_index(sig, 0.0) == 5
    assert I.cover(Image.new("RGB", (300, 100)), 64, 64).size == (64, 64)


def test_store_copies_input(tmp_path):
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (32, 32)).save(src)
    out = tmp_path / "out"
    entry = store.save(out, P.Params(prompt="x", init_image=str(src), init_strength=0.4), Image.new("RGB", (16, 16)))
    assert (entry.folder / "input.jpg").is_file()
    loaded = store.scan(out)[0]
    assert loaded.params.init_image == str(entry.folder / "input.jpg") and loaded.params.init_strength == 0.4


def test_network_policy():
    import os
    from blokjutsu import network
    network.go_offline()
    assert os.environ["HF_HUB_OFFLINE"] == "1" and os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    env = network.download_environment()
    assert "HF_HUB_OFFLINE" not in env and env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert network.download_command("model", "a/b")[-3:] == ["blokjutsu.fetch", "model", "a/b"]


def write_safetensors(path, tensors):
    """Minimal writer: {name: numpy array (float32 or uint16 as BF16)}."""
    import struct
    header, blobs, offset = {}, [], 0
    for name, array in tensors.items():
        data = array.tobytes()
        header[name] = {"dtype": "BF16" if array.dtype.name == "uint16" else "F32",
                        "shape": list(array.shape), "data_offsets": [offset, offset + len(data)]}
        blobs.append(data)
        offset += len(data)
    meta = json.dumps(header).encode()
    meta += b" " * (-len(meta) % 8)
    path.write_bytes(struct.pack("<Q", len(meta)) + meta + b"".join(blobs))


def checkpoint(folder, prefix, tweak=False):
    import numpy as np
    rng = np.random.default_rng(0)
    folder.mkdir(parents=True)
    tensors = {f"{prefix}language_model.layers.{i}.input_layernorm.weight": rng.normal(size=8).astype("float32")
               for i in range(4)}
    tensors[f"{prefix}language_model.norm.weight"] = rng.normal(size=8).astype("float32")
    tensors[f"{prefix}language_model.embed_tokens.weight"] = rng.integers(0, 65535, (16, 8)).astype("uint16")
    tensors[f"{prefix}visual.blocks.0.norm1.weight"] = rng.normal(size=8).astype("float32")
    if prefix:
        tensors["lm_head.weight"] = rng.integers(0, 65535, (16, 8)).astype("uint16")
    if tweak:
        tensors[f"{prefix}language_model.norm.weight"][3] += 1
    names = sorted(tensors)
    shards = {"a.safetensors": names[::2], "b.safetensors": names[1::2]}
    for file, keys in shards.items():
        write_safetensors(folder / file, {k: tensors[k] for k in keys})
    (folder / "model.safetensors.index.json").write_text(json.dumps(
        {"weight_map": {k: f for f, keys in shards.items() for k in keys}}))
    return tensors


class RangeClient:
    """Stands in for httpx.Client.stream over local files; can fail once after `fail_after` bytes."""

    def __init__(self, root, fail_after=None):
        self.root, self.fail_after = root, fail_after

    def stream(self, method, url, headers):
        import contextlib
        a, b = map(int, headers["Range"].removeprefix("bytes=").split("-"))
        data = (self.root / url).read_bytes()[a:b + 1]
        client = self

        class Response:
            status_code = 206

            def raise_for_status(self):
                return self

            def read(self):
                return data

            def iter_bytes(self, n):
                for i in range(0, len(data), 4):
                    if client.fail_after is not None and i >= client.fail_after:
                        client.fail_after = None
                        raise OSError("connection reset")
                    yield data[i:i + 4]

        return contextlib.nullcontext(Response())


def test_caption_head_identity_and_resumable_copy(tmp_path):
    import numpy as np
    from blokjutsu import fetch as F
    local = checkpoint(tmp_path / "moss", "")
    remote = checkpoint(tmp_path / "qwen", "model.")
    other = checkpoint(tmp_path / "base", "model.", tweak=True)
    local_map = json.loads((tmp_path / "moss/model.safetensors.index.json").read_text())["weight_map"]
    probes = F.probe_names(local_map)
    assert "language_model.norm.weight" in probes and not any(p.startswith("visual.") for p in probes)
    mine = F.ShardSet(local_map, lambda f: F.local_reader(tmp_path / "moss" / f))

    def theirs(name):
        m = json.loads((tmp_path / name / "model.safetensors.index.json").read_text())["weight_map"]
        return m, F.ShardSet(m, lambda f: F.http_reader(RangeClient(tmp_path / name), f))

    assert F.identical(mine, theirs("qwen")[1], theirs("qwen")[0], probes)
    assert not F.identical(mine, theirs("base")[1], theirs("base")[0], probes)

    remote_map, shards = theirs("qwen")
    dest = tmp_path / "out.safetensors"
    flaky = RangeClient(tmp_path / "qwen", fail_after=100)
    with pytest.raises(OSError):
        F.stream_tensor(flaky, remote_map[F.HEAD], shards[F.HEAD], F.HEAD, dest, lambda d, t: None)
    assert dest.with_suffix(".part").exists() and not dest.exists()
    F.stream_tensor(flaky, remote_map[F.HEAD], shards[F.HEAD], F.HEAD, dest, lambda d, t: None)
    copied = F.Safetensors(F.local_reader(dest))
    assert copied.info(F.HEAD) == ("BF16", [16, 8])
    assert np.array_equal(np.frombuffer(copied.prefix(F.HEAD, 1 << 20), "uint16"), remote[F.HEAD].ravel())
    assert local and other


def test_describe_parse():
    from blokjutsu.describe import parse
    reply = 'thinking…</think>\n```json\n{"caption": {"long": "L", "medium": "M", "short": ""}}\n```'
    assert parse(reply) == {"short": "M", "medium": "M", "long": "L", "watermarks": []}
    marked = '{"caption": {"long": "L", "medium": "M", "short": "S"}, "watermark": ["GETTY", {"label": "logo"}, ""]}'
    assert parse(marked)["watermarks"] == ["GETTY", "logo"]
    assert parse("just prose")["medium"] == "just prose"


def test_fetch_fake_protocol():
    import contextlib
    import io
    from blokjutsu import fetch as F
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert F.main(["fake", "0.05"]) == 0
    lines = out.getvalue().splitlines()
    assert lines[0].startswith("STATUS") and lines[-1].startswith("DONE")
    done, total = map(int, lines[-2].split()[1:])
    assert done == total


def test_compare_across_storage_precision(tmp_path):
    import numpy as np
    from blokjutsu import fetch as F
    x = np.random.default_rng(1).normal(size=64).astype("float32")
    as_bf16 = (F.round_to(x, "BF16").view("<u4") >> 16).astype("uint16")
    write_safetensors(tmp_path / "f32.safetensors", {"w": x})
    write_safetensors(tmp_path / "bf16.safetensors", {"w": as_bf16})
    write_safetensors(tmp_path / "other.safetensors", {"w": x + 0.01})
    f32, bf16, other = (F.Safetensors(F.local_reader(tmp_path / f"{n}.safetensors")) for n in ("f32", "bf16", "other"))
    assert F.compare(bf16, "w", f32, "w")["same"]
    r = F.compare(bf16, "w", other, "w")
    assert not r["same"] and abs(r["offset"] - 0.01) < 0.005
    assert F.remote_name("language_model.norm.weight", {"model.language_model.norm.weight": 0}) \
        == "model.language_model.norm.weight"


def test_complete_json():
    from blokjutsu.describe import complete_json
    assert complete_json('{"caption": {"short": "a {b} \\"c\\""}}', False)
    assert not complete_json('{"caption": {"short": "a"', False)
    assert not complete_json('<think>{"x": 1}', True)
    assert complete_json('<think>plan {</think>\n```json\n{"caption": {}}', True)


def test_inpaint_helpers():
    import numpy as np
    from blokjutsu import img2img as I
    mask = np.zeros((64, 96), np.float32)
    mask[20, 40] = 1.0
    cells = I.latent_mask(mask)
    assert cells.shape == (4, 6) and cells[1, 2] == 1 and cells.sum() == 9      # one cell grown to 3×3
    source = Image.new("RGB", (96, 64), (10, 20, 30))
    result = Image.new("RGB", (96, 64), (200, 200, 200))
    out = np.asarray(I.composite(result, source, mask))
    assert tuple(out[0, 0]) == (10, 20, 30) and tuple(out[20, 40]) == (200, 200, 200)
    canvas, m = I.reframe(Image.new("RGB", (32, 16), (5, 6, 7)), 16, 0, 0, 16)
    assert canvas.size == (48, 32) and m[0, 0] == 1 and m[0, 20] == 0 and m[20, 20] == 1
    assert canvas.getpixel((20, 5)) == (5, 6, 7)
    cropped, m = I.reframe(Image.new("RGB", (32, 16)), -8, 0, 16, -4)       # crop left/bottom, extend right
    assert cropped.size == (40, 12) and m[:, :24].max() == 0 and m[:, 24:].min() == 1
    dst = I.place(np.zeros((4, 4)), np.ones((3, 3)), -1, 2)
    assert dst.sum() == 4 and dst[2:, :2].sum() == 4


def test_keep_known_resets_unmasked_cells():
    class Out:
        def __init__(self, prev):
            self.prev_sample = prev

    class Scheduler:
        def step(self, v, t, x):
            return Out(x - 0.5 * v)

    try:
        import torch
    except ImportError:          # runs where torch is installed
        return
    from blokjutsu import img2img as I
    z0, eps = torch.full((1, 1, 2, 2), 3.0), torch.full((1, 1, 2, 2), -1.0)
    cells = torch.tensor([[[[1.0, 0.0], [0.0, 0.0]]]])
    s = Scheduler()
    s.sigmas = torch.tensor([1.0, 0.5, 0.0])
    I.keep_known(s, z0, eps, cells)
    x = s.step(torch.zeros(1, 1, 2, 2), 1000, torch.full((1, 1, 2, 2), 7.0)).prev_sample
    assert x[0, 0, 0, 0] == 7.0 and x[0, 0, 1, 1] == 0.5 * 3.0 + 0.5 * -1.0


def test_mask_saved_with_image_and_png_metadata(tmp_path):
    src, mask = tmp_path / "in.png", tmp_path / "m.png"
    Image.new("RGB", (32, 32)).save(src)
    Image.new("L", (32, 32), 255).save(mask)
    p = P.Params(prompt="x", init_image=str(src), init_strength=1.0, mask_image=str(mask))
    P.validate(p)
    entry = store.save(tmp_path / "out", p, Image.new("RGB", (16, 16)))
    assert (entry.folder / "mask.png").is_file()
    loaded = store.scan(tmp_path / "out")[0].params
    assert loaded.mask_image == str(entry.folder / "mask.png")
    with pytest.raises(ValueError):                     # off by default: nothing inside the PNG
        store.png_parameters(entry.image)
    embedded_entry = store.save(tmp_path / "out", p, Image.new("RGB", (16, 16)), embed=True)
    embedded = P.from_record(json.loads(store.png_parameters(embedded_entry.image)))
    assert store.resolve_files(embedded, embedded_entry.folder).mask_image == str(embedded_entry.folder / "mask.png")
    with pytest.raises(ValueError):
        P.validate(P.Params(prompt="x", mask_image=str(mask)))


def test_fake_backend_inpaint_keeps_unmasked(tmp_path):
    import numpy as np
    src, mask = tmp_path / "in.png", tmp_path / "m.png"
    Image.new("RGB", (64, 32), (1, 2, 3)).save(src)
    m = Image.new("L", (64, 32), 0)
    m.paste(255, (0, 0, 16, 16))
    m.save(mask)
    p = P.Params(prompt="x", width=64, height=32, steps=2, seed=3, init_image=str(src), init_strength=1.0,
                 mask_image=str(mask))
    image, _ = FakeBackend(0).generate(p, lambda *a: None, lambda *a: None, lambda: False)
    a = np.asarray(image)
    assert tuple(a[31, 63]) == (1, 2, 3) and tuple(a[2, 2]) != (1, 2, 3)


def test_ratio_label():
    from blokjutsu import sizes as S
    assert S.ratio_label(1024, 768) == "4:3" and S.ratio_label(1000, 730) == "1.37:1"


def test_upscale_choices():
    from blokjutsu import sizes as S
    choices = S.scaled(1024, 960)
    assert choices[0] == (1, 1024, 960) and (2, 2048, 1920) in choices
    assert all(w % 16 == 0 and h % 16 == 0 and w * h <= S.MAX_MP * 1e6 for _, w, h in choices)
    assert S.scale_label(2, 2048, 1920) == "3.9 MP (×2)"


def test_caption_source_pin(tmp_path):
    from blokjutsu import fetch as F
    assert F.previous_source(tmp_path) is None
    (tmp_path / F.SOURCE_FILE).write_text(json.dumps({"repo": "Qwen/Qwen3.5-9B", "revision": "abc"}))
    assert F.previous_source(tmp_path)["revision"] == "abc"



def test_png_without_metadata(tmp_path):
    source = Image.new("RGB", (16, 16))
    source.info["icc_profile"] = b"x" * 64
    source.info["parameters"] = "leaked"
    entry = store.save(tmp_path, P.Params(prompt="secret"), source)
    data = entry.image.read_bytes()
    for chunk in (b"tEXt", b"iTXt", b"zTXt", b"tIME", b"iCCP", b"eXIf", b"pHYs"):
        assert chunk not in data
    assert b"secret" not in data


def test_clear_logs(tmp_path):
    import logging
    from logging.handlers import RotatingFileHandler
    from blokjutsu.logs import clear_logs
    folder = tmp_path / "logs"
    folder.mkdir()
    handler = RotatingFileHandler(folder / "blokjutsu.log", encoding="utf-8")
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        root.warning("secret prompt")
        handler.flush()
        (folder / "blokjutsu.log.1").write_text("older secret")
        (folder / "console.log").write_text("console secret")
        clear_logs(folder)
        assert (folder / "blokjutsu.log").read_text() == ""
        assert not (folder / "blokjutsu.log.1").exists()
        assert (folder / "console.log").read_text() == ""
        root.warning("after")
        handler.flush()
        assert "after" in (folder / "blokjutsu.log").read_text()
    finally:
        root.removeHandler(handler)
        handler.close()


def test_clear_preview_stats(tmp_path, monkeypatch=None):
    import os
    from blokjutsu.backend import clear_preview_stats
    old = os.environ.get("BLOKJUTSU_HOME")
    os.environ["BLOKJUTSU_HOME"] = str(tmp_path)
    try:
        (tmp_path / "preview").mkdir()
        (tmp_path / "preview" / "MOSS-Image-SFT.npz").write_bytes(b"x")
        clear_preview_stats()
        assert not any((tmp_path / "preview").iterdir())
    finally:
        if old is None:
            os.environ.pop("BLOKJUTSU_HOME")
        else:
            os.environ["BLOKJUTSU_HOME"] = old


def test_constraints_cover_dependencies():
    import re
    root = Path(__file__).resolve().parents[1]
    pinned = {re.split(r"==", line)[0].lower().replace("_", "-")
              for line in (root / "constraints.txt").read_text().splitlines() if "==" in line}
    text = (root / "pyproject.toml").read_text()
    deps = re.search(r"dependencies = \[(.*?)\]", text, re.S).group(1)
    names = {re.match(r"[A-Za-z0-9_.-]+", d.strip().strip('"')).group(0).lower().replace("_", "-")
             for d in re.findall(r'"([^"]+)"', deps)}
    assert names <= pinned, names - pinned


def test_sft_revision_pinned():
    assert len(P.model_revision(P.DEFAULT_MODEL) or "") == 40


def test_vendored_moss_code_unchanged():
    import hashlib
    import re
    root = Path(__file__).resolve().parents[1]
    text = (root / "blokjutsu" / "moss_image.py").read_bytes()
    header, body = text.split(b"# ---\n", 1)
    recorded = re.search(rb"SHA-256 of the original ([0-9a-f]{64})", header).group(1).decode()
    assert hashlib.sha256(body).hexdigest() == recorded
    assert P.model_revision(P.DEFAULT_MODEL).encode() in header
    sources = (root / "blokjutsu").rglob("*.py")
    assert not [p for p in sources if b"trust_remote_code=True" in p.read_bytes() and p.name != "moss_image.py"]


def test_home_layout_and_backup_flag(tmp_path, monkeypatch):
    from blokjutsu import settings as S
    monkeypatch.setenv("BLOKJUTSU_HOME", str(tmp_path / "home"))
    assert S.models_dir() == tmp_path / "home" / "models"
    assert S.default_output() == tmp_path / "home" / "images"
    assert S.tilde(Path.home() / "a" / "b") == "~/a/b" and S.tilde("/opt/x") == "/opt/x"
    calls = []
    monkeypatch.setattr(S, "keep_out_of_backups", lambda path: calls.append(path) or True)
    S.prepare_home()
    S.prepare_home()
    assert calls == [tmp_path / "home"] and (tmp_path / "home" / S.BACKUP_MARKER).exists()
    monkeypatch.delenv("BLOKJUTSU_HOME")
    assert S.app_home().name in (S.HOME_NAME, "blokjutsu")


def test_missing_model_files_follow_links(tmp_path):
    from blokjutsu.backend import missing_files
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    snap = tmp_path / "snap"
    for part in ("transformer", "text_encoder", "vae", "scheduler", "tokenizer"):
        (snap / part).mkdir(parents=True)
        (snap / part / "config.json").write_text("{}")
    (snap / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"x")
    (snap / "text_encoder" / "model.safetensors").write_bytes(b"x")
    shards = {"a": "m-1.safetensors", "b": "m-2.safetensors"}
    (snap / "transformer" / "m.safetensors.index.json").write_text(json.dumps({"weight_map": shards}))
    (blobs / "one").write_bytes(b"x")
    (snap / "transformer" / "m-1.safetensors").symlink_to(blobs / "one")
    (snap / "transformer" / "m-2.safetensors").symlink_to(blobs / "gone")
    assert missing_files(snap) == ["transformer/m-2.safetensors"]
    (blobs / "gone").write_bytes(b"x")
    assert missing_files(snap) == []
