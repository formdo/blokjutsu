import pytest

from blokjutsu import models as M
from blokjutsu import params as P


def moss():
    return {k: ("BF16", s) for k, s in M.expected_shapes().items()}


def test_a_full_moss_image_model_passes_with_any_prefix():
    M.check_transformer(moss())
    M.check_transformer({"model.diffusion_model." + k: v for k, v in moss().items()} | {"rope.bands": ("F32", (16,))})


@pytest.mark.parametrize("edit, words", [
    (lambda t: t.pop("layers.3.proj.q.weight"), "incomplete"),
    (lambda t: t.update({"layers.0.attn.to_q.weight": ("BF16", (3072, 3072))}), "different model"),
    (lambda t: t.update({"layers.0.proj.q.weight": ("BF16", (2048, 3072))}), "sizes"),
    (lambda t: [t.pop(k) for k in list(t)] and t.update({"x": ("F32", (1,))}), "different model"),
])
def test_other_models_are_refused(edit, words):
    t = moss()
    edit(t)
    with pytest.raises(ValueError):
        M.check_transformer(t)
    try:
        M.check_transformer(t)
    except ValueError as exc:
        assert words in str(exc)


def test_recommended_settings_from_a_card():
    card = "A turbo fine-tune. Recommended: 8 steps, CFG 1.0, shift 3."
    assert M.recommended(card) == {"steps": 8, "cfg": 1.0}
    assert M.recommended("A watercolour fine-tune trained for 2000 steps.") == {}


def test_library_add_and_names(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOKJUTSU_HOME", str(tmp_path / "home"))
    weights = tmp_path / "turbo.safetensors"
    weights.write_bytes(b"\x08\x00\x00\x00\x00\x00\x00\x00{}      ")
    info = M.add(weights, {"name": "Turbo", "recommended": {"steps": 8}})
    assert M.add(weights, {"name": "again"})["id"] == info["id"]
    model = M.PREFIX + info["id"]
    assert M.is_library(model) and P.model_name(model) == "Turbo"
    assert P.model_name("OpenMOSS-Team/MOSS-Image-SFT") == "MOSS-Image-SFT"
    M.remove(info["id"])
    assert "not in your library" in P.model_name(model)
