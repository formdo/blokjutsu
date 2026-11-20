import json
from dataclasses import replace

import pytest
from PIL import Image

from blokjutsu import lora as R
from blokjutsu import models as M
from blokjutsu import params as P


@pytest.fixture
def pictures(tmp_path):
    paths = []
    for name in ("cat.png", "hat.png", "park.png"):
        Image.new("RGB", (64, 48), (120, 80, 40)).save(tmp_path / name)
        paths.append(str(tmp_path / name))
    return paths


def edit(pictures, **changes):
    return replace(P.Params(prompt="put the hat from picture 2 on the cat", model=P.DEFAULT_EDIT_MODEL,
                            init_image=pictures[0], references=json.dumps(pictures[1:2])), **changes)


def test_edit_model_family():
    assert M.family_of(P.DEFAULT_EDIT_MODEL) == "qwen-image" and M.family_of(P.DEFAULT_MODEL) == "moss"
    assert P.is_edit(P.Params(model=P.DEFAULT_EDIT_MODEL)) and not P.is_edit(P.Params())


def test_edit_validation(pictures):
    p = edit(pictures)
    P.validate(p)
    with pytest.raises(ValueError, match="picture to edit"):
        P.validate(replace(p, init_image=""))
    with pytest.raises(ValueError, match="at most 2"):
        P.validate(replace(p, references=json.dumps(pictures)))
    with pytest.raises(ValueError, match="Describe the change"):
        P.validate(replace(p, prompt=" "))
    with pytest.raises(ValueError, match="Repaint"):
        P.validate(replace(p, mask_image=pictures[2]))
    with pytest.raises(ValueError, match="Schedule"):
        P.validate(replace(p, steps=4, sigmas="1, 0.9, 0.7, 0.02"))


def test_edit_record_round_trip(pictures):
    p = edit(pictures)
    record = P.to_record(p)
    assert record["blokjutsu"]["references"] == pictures[1:2]
    assert P.from_record(record) == p
    assert P.references(P.from_record(record)) == pictures[1:2]


def test_edit_pipeline_arguments(pictures):
    p = edit(pictures, cfg=4.0, negative_prompt="")
    k = P.edit_kwargs(p)
    assert k["negative_prompt"] == " " and k["true_cfg_scale"] == 4.0 and k["num_inference_steps"] == p.steps
    assert P.edit_kwargs(replace(p, cfg=1.0))["negative_prompt"] is None


def test_lora_family_must_match_edit_model(tmp_path, monkeypatch, pictures):
    from test_lora import peft, safetensors
    monkeypatch.setenv("BLOKJUTSU_HOME", str(tmp_path / "home"))
    info = R.add(safetensors(tmp_path / "gouache.safetensors", peft(layers=(0,))), {"name": "Gouache"})
    p = edit(pictures, loras=R.dumps([R.entry(info)]))
    with pytest.raises(ValueError, match="is for MOSS-Image, not Qwen-Image-Edit"):
        R.check_entries(p.loras, M.family_of(p.model))
