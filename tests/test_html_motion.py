"""Contrats légers du prototype HTML frame-driven."""
from __future__ import annotations

from html_motion_renderer import HTML_TEMPLATE, _scene_template, resolve_template
from hybrid_test import _semantic_labels


def test_html_scene_is_frame_driven() -> None:
    assert "window.renderFrame" in HTML_TEMPLATE
    assert "URLSearchParams" in HTML_TEMPLATE
    assert "Math.random" not in HTML_TEMPLATE


def test_html_scene_contains_motion_layers() -> None:
    for layer in ("grid", "orb", "beam", "title", "number", "card", "bars", "scan"):
        assert f'class="{layer}"' in HTML_TEMPLATE or f".{layer}" in HTML_TEMPLATE


def test_html_templates_have_distinct_composition_hooks() -> None:
    for template in ("hero", "numbers", "split", "cta"):
        rendered = _scene_template(
            "KICKER", ("A", "B", "C"), "01", "CARD", "SUB", "SCENE", template,
            ("A", "B", "C"), ("LEFT", "RIGHT"), "", [0.1, 0.4], [],
        )
        assert f"template-{template}" in rendered


def test_html_template_rejects_unknown_variant() -> None:
    from pathlib import Path
    import pytest
    from html_motion_renderer import render_html_motion

    with pytest.raises(ValueError, match="template inconnu"):
        render_html_motion(Path("/tmp/unused.mp4"), duration=0.1, template="unknown")


def test_auto_template_follows_editorial_content() -> None:
    assert resolve_template("auto", ("GAGNE", "3000", "FCFA")) == "numbers"
    assert resolve_template("auto", ("AVANT", "OU", "APRÈS")) == "comparison"
    assert resolve_template("auto", ("COMMENT", "ÇA", "MARCHE")) == "diagram"
    assert resolve_template("auto", ("UNE", "IMAGE", "FORTE"), "B-ROLL") == "broll"
    assert resolve_template("auto", ("APPEL", "ACTION", "FINAL"), has_cta=True) == "cta"


def test_semantic_labels_are_deterministic_and_compact() -> None:
    diagram, comparison = _semantic_labels(
        ["Tu", "perds", "du", "temps", "avec", "une", "mauvaise", "méthode", "pour", "gagner", "plus"]
    )
    assert diagram[0] == "PERDS TEMPS"
    assert diagram[1] == "MAUVAISE MÉTHODE"
    assert diagram[2] == "GAGNER PLUS"
    assert all(len(label) <= 18 for label in (*diagram, *comparison))

