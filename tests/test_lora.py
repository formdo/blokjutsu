import json
import struct

import pytest

from blokjutsu import lora as R
from blokjutsu import params as P

D, F = 3072, 8192


def safetensors(path, shapes, metadata=None):
    """A .safetensors file with zero-filled BF16 tensors of the given shapes."""
    header, offset = {}, 0
    for name, shape in shapes.items():
        n = 2
        for s in shape:
            n *= s
        header[name] = {"dtype": "BF16", "shape": list(shape), "data_offsets": [offset, offset + n]}
        offset += n
    if metadata:
        header["__metadata__"] = metadata
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + bytes(offset))
    return path


def peft(rank=16, layers=(0, 1)):
    shapes = {}
    for i in layers:
        for n in ("q", "k", "v", "o"):
            shapes[f"transformer.layers.{i}.proj.{n}.lora_A.weight"] = (rank, D)
            shapes[f"transformer.layers.{i}.proj.{n}.lora_B.weight"] = (D, rank)
        shapes[f"transformer.layers.{i}.proj.ffn_down.lora_A.weight"] = (rank, F)
        shapes[f"transformer.layers.{i}.proj.ffn_down.lora_B.weight"] = (D, rank)
    return shapes


def test_peft_names_fit_moss():
    found, ranks = R.layers(peft())
    assert ranks == [16] and "layers.1.proj.ffn_down" in found and len(found) == 10


def test_kohya_names_with_alpha_fit_moss():
    shapes = {"lora_unet_layers_3_proj_ffn_up_gate.lora_down.weight": (8, D),
              "lora_unet_layers_3_proj_ffn_up_gate.lora_up.weight": (2 * F, 8),
              "lora_unet_layers_3_proj_ffn_up_gate.alpha": ()}
    found, ranks = R.layers(shapes)
    assert set(found["layers.3.proj.ffn_up_gate"]) == {"A", "B", "alpha", "targets", "kind"} and ranks == [8]


def test_fused_qkv_maps_onto_q_k_v():
    shapes = {"diffusion_model.layers.5.proj.qkv.lora_A.weight": (16, D),
              "diffusion_model.layers.5.proj.qkv.lora_B.weight": (3 * D, 16)}
    found, ranks = R.layers(shapes)
    assert found["layers.5.proj.qkv"]["targets"] == ["layers.5.proj.q", "layers.5.proj.k", "layers.5.proj.v"]
    with pytest.raises(ValueError):
        R.layers({**shapes, "diffusion_model.layers.5.proj.qkv.lora_B.weight": (D, 16)})


@pytest.mark.parametrize("shapes, words", [
    ({"transformer_blocks.0.attn.to_q.lora_A.weight": (16, 3072),
      "transformer_blocks.0.attn.to_q.lora_B.weight": (3072, 16)}, "different model"),
    ({"layers.0.proj.q.lora_A.weight": (16, 2048), "layers.0.proj.q.lora_B.weight": (3072, 16)}, "sizes"),
    ({"layers.0.proj.q.lora_A.weight": (16, 3072)}, "only one of the two"),
    ({"model.embed.weight": (10, 10)}, "LoRA"),
])
def test_other_models_are_refused(shapes, words):
    with pytest.raises(ValueError):
        R.layers(shapes)
    try:
        R.layers(shapes)
    except ValueError as exc:
        assert words in str(exc)


def test_header_and_metadata_from_a_file(tmp_path):
    path = safetensors(tmp_path / "a.safetensors", peft(layers=(0,)), {"modelspec.trigger_phrase": "ink wash"})
    tensors, meta = R.read_header(path)
    assert R.layers(tensors)[1] == [16]
    assert R.find_trigger("", {}, meta) == "ink wash"


@pytest.mark.parametrize("text, data, trigger", [
    ("", {"instance_prompt": "moss_vgouache_style"}, "moss_vgouache_style"),
    ("## Usage\nTrigger word: `moss_vgouache_style` at the start of the prompt.", {}, "moss_vgouache_style"),
    ('Use the trigger phrase "in the style of linocut" for best results.', {}, "in the style of linocut"),
    ("A style LoRA. No special words needed.", {}, ""),
])
def test_trigger_words(text, data, trigger):
    assert R.find_trigger(text, data, {}) == trigger


def test_strength_and_base_from_the_card():
    assert R.find_strength("Recommended LoRA scale: 0.8, tested from 0.7 to 1.2") == 0.8
    assert R.find_strength("nothing here") == 1.0
    assert R.trained_on({"base_model": ["OpenMOSS-Team/MOSS-Image-Base"]}) == "OpenMOSS-Team/MOSS-Image-Base"


def test_links_and_file_choice():
    assert R.repo_of("https://huggingface.co/axiomofmind/Moss-image-gouache-lora") == \
        "axiomofmind/Moss-image-gouache-lora"
    assert R.repo_of("https://huggingface.co/a/b/tree/main") == "a/b"
    assert R.repo_of("a/b") == "a/b" and R.repo_of("not a repo") is None
    files = [("MOSS-Image-Gouache-LoRA-ComfyUI.safetensors", 74_000_000),
             ("pytorch_lora_weights.safetensors", 74_000_000), ("images/a.png", 1)]
    assert R.pick_file(files)[0] == "pytorch_lora_weights.safetensors"
    assert R.pick_file([("x-comfyui.safetensors", 1), ("style.safetensors", 1)])[0] == "style.safetensors"


def test_library_add_find_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOKJUTSU_HOME", str(tmp_path / "home"))
    src = safetensors(tmp_path / "gouache.safetensors", peft(layers=(0,)))
    info = R.add(src, {"name": "Gouache", "trigger": "moss_vgouache_style", "strength": 1.0})
    assert R.add(src, {"name": "again"})["id"] == info["id"]          # same file, not added twice
    assert [i["name"] for i in R.library()] == ["Gouache"]
    e = R.entry(info, 0.7)
    text = R.dumps([e])
    R.check_entries(text)
    p = P.Params(prompt="moss_vgouache_style, a harbour", loras=text)
    assert P.from_record(P.to_record(p)) == p
    assert P.to_record(p)["blokjutsu"]["loras"][0]["name"] == "Gouache"
    R.remove(info["id"])
    with pytest.raises(ValueError):
        R.check_entries(text)


def test_card_header_fields():
    card = "---\nlicense: apache-2.0\nbase_model:\n- OpenMOSS-Team/MOSS-Image-Base\ninstance_prompt: ink_style\n---\n# Ink"
    data = R.card_data_of(card)
    assert data["license"] == "apache-2.0" and R.trained_on(data) == "OpenMOSS-Team/MOSS-Image-Base"
    assert R.find_trigger(card, data, {}) == "ink_style"


def test_lokr_on_fused_qkv_and_mlp():
    """The layout of aoleg/MOSS-Image-Kodachrome: whole Kronecker factors, qkv fused, alpha stored per q, k, v."""
    shapes = {}
    for i in (0, 1):
        pre = f"diffusion_model.layers.{i}.proj."
        shapes |= {pre + "qkv.lokr_w1": (16, 16), pre + "qkv.lokr_w2": (576, 192),
                   pre + "o.lokr_w1": (16, 16), pre + "o.lokr_w2": (192, 192),
                   pre + "ffn_up_gate.lokr_w1": (16, 16), pre + "ffn_up_gate.lokr_w2": (1024, 192),
                   pre + "ffn_down.lokr_w1": (16, 16), pre + "ffn_down.lokr_w2": (192, 512)}
        shapes |= {pre + f"{n}.alpha": () for n in ("q", "k", "v", "o", "ffn_up_gate", "ffn_down")}
    found, ranks = R.layers(shapes)
    assert found["layers.1.proj.qkv"]["kind"] == "lokr" and "layers.0.proj.q" not in found
    with pytest.raises(ValueError):
        R.layers({**shapes, "diffusion_model.layers.0.proj.o.lokr_w2": (192, 191)})
    with pytest.raises(ValueError):
        R.layers({"layers.0.proj.o.hada_w1_a": (8, 3072), "layers.0.proj.o.hada_w1_b": (8, 3072)})
