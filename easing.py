"""Fonctions d'easing : t dans [0,1] -> valeur dans [0,1].
Chaque fonction clampe t dans [0,1], vaut exactement 0 en 0 et 1 en 1.
"""
from __future__ import annotations


def _clamp(t: float) -> float:
    if t < 0.0:
        return 0.0
    if t > 1.0:
        return 1.0
    return t


def ease_out_cubic(t: float) -> float:
    t = _clamp(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_cubic(t: float) -> float:
    t = _clamp(t)
    return t ** 3


def ease_in_out_cubic(t: float) -> float:
    t = _clamp(t)
    if t < 0.5:
        return 4.0 * t ** 3
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_out_back(t: float, c1: float = 1.20) -> float:
    t = _clamp(t)
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2
