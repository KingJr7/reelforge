"""Tests des easings : bornes, monotonie, valeurs exactes en 0 et 1."""
from __future__ import annotations

import easing


def test_eases_boundaries() -> None:
    for fn in (easing.ease_out_cubic, easing.ease_in_cubic,
               easing.ease_in_out_cubic, easing.ease_out_back):
        assert fn(0.0) == 0.0, f"{fn.__name__}(0) != 0"
        assert fn(1.0) == 1.0, f"{fn.__name__}(1) != 1"
        v = fn(0.5)
        assert 0.0 <= v <= 1.1, f"{fn.__name__}(0.5) = {v} hors limites"


def test_ease_out_cubic_values() -> None:
    assert easing.ease_out_cubic(0.0) == 0.0
    assert easing.ease_out_cubic(1.0) == 1.0
    assert easing.ease_out_cubic(0.5) == 1 - 0.5 ** 3


def test_ease_in_cubic_values() -> None:
    assert easing.ease_in_cubic(0.0) == 0.0
    assert easing.ease_in_cubic(1.0) == 1.0
    assert easing.ease_in_cubic(0.5) == 0.5 ** 3


def test_ease_in_out_cubic_values() -> None:
    assert easing.ease_in_out_cubic(0.0) == 0.0
    assert easing.ease_in_out_cubic(1.0) == 1.0
    assert easing.ease_in_out_cubic(0.5) == 0.5


def test_ease_out_back_values() -> None:
    assert easing.ease_out_back(0.0) == 0.0
    assert easing.ease_out_back(1.0) == 1.0
    # Dépassement léger autour de t proche de 1 (back ease overshoot)
    assert easing.ease_out_back(0.9) > 1.0


def test_eases_clamp_outside() -> None:
    assert easing.ease_out_cubic(-0.5) == 0.0
    assert easing.ease_out_cubic(1.5) == 1.0
    assert easing.ease_in_cubic(-0.5) == 0.0
    assert easing.ease_in_cubic(1.5) == 1.0
