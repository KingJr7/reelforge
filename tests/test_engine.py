"""Contrats CLI des backends de rendu."""
from __future__ import annotations

from pathlib import Path

import pytest

from hybrid_test import _editorial_from_timeline, load_scene_plan
from make_reel import build_parser


def test_engine_backend_choices_are_exposed() -> None:
    parser = build_parser()
    assert parser.parse_args(["--engine", "classic"]).engine == "classic"
    assert parser.parse_args(["--engine", "html"]).engine == "html"
    assert parser.parse_args(["--engine", "hybrid"]).engine == "hybrid"


def test_classic_remains_the_default_engine() -> None:
    assert build_parser().parse_args([]).engine == "classic"


def test_user_scene_plan_is_loaded_and_keeps_boundaries() -> None:
    plan = load_scene_plan(Path("html-scene-plan.example.json"), 0.35)
    assert plan["duration"] == 20.0
    assert [scene["engine"] for scene in plan["scenes"]] == ["html", "classic", "html"]
    assert plan["scenes"][0]["template"] == "hero"
    assert plan["scenes"][2]["template"] == "cta"


def test_user_scene_plan_rejects_unknown_engine(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"scenes": [{"engine": "html", "start": 0, "end": 1}, {"engine": "weird", "start": 1, "end": 2}]}')
    with pytest.raises(ValueError, match="html ou classic"):
        load_scene_plan(path, 0.35)


def test_html_editorial_is_sliced_to_scene_window(tmp_path: Path) -> None:
    path = tmp_path / "timeline.json"
    path.write_text(
        '{"duration": 4, "words": ['
        '{"text":"INTRO","start":0,"end":1},'
        '{"text":"CORPS","start":1.2,"end":2},'
        '{"text":"CTA","start":3,"end":3.5}],'
        '"cards": [], "cta": {"text":"GO","start":3}}'
    )
    intro = _editorial_from_timeline(path, start=0, end=1.1)
    outro = _editorial_from_timeline(path, start=2.5, end=4)
    assert intro["headline"][0] == "INTRO"
    assert intro["number"] == "01"
    assert outro["headline"][0] == "CTA"
    assert outro["has_cta"] is True
