import json
from dataclasses import replace

import pytest

from blokjutsu import layout as L
from blokjutsu import params as P


def explore():
    """MOSS-Image's USERGUIDE example as a draft; its compiled boxes are given in the guide."""
    d = L.new(1024, 1024)
    d["summary"] = {"meta": ["poster"], "canvas": "single", "caption": "A minimalist travel poster."}
    d["items"] = [
        {"label": "text", "caption": "Large dark-blue title.", "text": "EXPLORE", "bbox": [128, 96, 896, 224]},
        {"label": "object", "caption": "A flat blue mountain.", "bbox": [224, 320, 800, 896]},
    ]
    return d


def test_compiles_to_the_guides_boxes():
    prompt = L.compile_prompt(explore())
    data = json.loads(prompt)
    assert [it["bbox"] for it in data["items"]] == [[-416, -384, -288, 384], [-192, -288, 384, 288]]
    assert (data["bbox_coord_space"], data["bbox_format"]) == ("abs_centralized", "yxyx")
    assert "width" not in data and "\n" not in prompt and ", " not in prompt.split('"caption"')[0]


def test_moss_compiler_landscape_case():
    """The landscape case from MOSS-Image's own compiler tests."""
    d = L.new(1536, 1024)
    d["summary"] = {"caption": "A ceramic campaign."}
    d["items"] = [{"label": "text", "caption": "Dark-green lettering.", "text": "把日常，过成诗。",
                   "bbox": [928, 272, 1408, 448]}]
    data = json.loads(L.compile_prompt(d))
    assert data["items"][0]["bbox"] == [-240, 160, -64, 640]
    assert data["items"][0]["text"] == "把日常，过成诗。"


def test_fractional_boxes_enclose_whole_pixels():
    assert L._centered([10.9, 20.1, 100.01, 200.99], 768, 1344) == [-652, -374, -471, -283]


def test_boxes_follow_the_picture_size():
    prompt = json.loads(L.compile_prompt(explore(), 2048, 1024))
    assert prompt["items"][0]["bbox"] == [-416, -768, -288, 768]


def test_round_trip_from_the_centred_form():
    d = explore()
    back = L.from_prompt(L.compile_prompt(d), 1024, 1024)
    assert back == d


def test_plain_prompts_are_not_layouts():
    assert L.from_prompt("a cat on a mat", 512, 512) is None
    assert L.from_prompt('{"scene_type": "x"}', 512, 512) is None


@pytest.mark.parametrize("edit, words", [
    (lambda d: d["summary"].update(caption=" "), "whole picture"),
    (lambda d: d.update(items=[]), "at least one box"),
    (lambda d: d["items"][0].update(text=""), "words"),
    (lambda d: d["items"][1].update(caption=""), "description"),
    (lambda d: d["items"][1].update(bbox=[224, 320, 1100, 896]), "edge"),
    (lambda d: d["items"][1].update(bbox=[300, 320, 300, 896]), "no area"),
    (lambda d: d["items"][1].update(label="shape"), "kind"),
    (lambda d: d["items"][1].update(font_size=32), "fields"),
])
def test_problems_are_named(edit, words):
    d = explore()
    edit(d)
    with pytest.raises(ValueError):
        L.compile_prompt(d)
    try:
        L.compile_prompt(d)
    except ValueError as exc:
        assert words in str(exc)


def test_params_record_round_trip():
    d = explore()
    p = P.Params(prompt=L.compile_prompt(d), width=1024, height=1024, layout=L.dumps(d))
    P.validate(p)
    record = P.to_record(p)
    assert record["blokjutsu"]["layout"] == d
    assert P.from_record(record) == p


def test_validate_reports_an_unfinished_layout():
    d = explore()
    d["items"][0]["text"] = ""
    with pytest.raises(ValueError):
        P.validate(P.Params(prompt="x", layout=L.dumps(d)))
    assert P.validate(replace(P.Params(prompt="x"), layout="")) is None


def test_signature_ignores_rescaling_round_trips_but_not_edits():
    d = explore()
    assert L.signature(L.scaled(L.scaled(d, 2048, 2048), 1024, 1024)) == L.signature(d)
    moved = explore()
    moved["items"][1]["bbox"][0] += 16
    assert L.signature(moved) != L.signature(d)
