"""Tests de la machine à états de continuité directionnelle (flow.py)."""
from __future__ import annotations

import flow


def test_first_element_enters_left() -> None:
    enter, exit_ = flow.plan_sides(None, "sweep")
    assert enter == "left"
    assert exit_ == "right"


def test_sweep_chain_5() -> None:
    # Tous les éléments entrent gauche, sortent droite (sauf retournement)
    prev = None
    results = []
    for _ in range(5):
        enter, exit_ = flow.plan_sides(prev, "sweep")
        results.append((enter, exit_))
        prev = exit_
    assert results == [("left", "right")] * 5


def test_sweep_reversal() -> None:
    # Si prev_exit == 'left', on entre droite et sort gauche
    enter, exit_ = flow.plan_sides("left", "sweep")
    assert enter == "right"
    assert exit_ == "left"


def test_mirror_chain_5() -> None:
    # A sort droite -> B entre droite sort gauche -> C entre gauche sort droite...
    prev = None
    results = []
    for _ in range(5):
        enter, exit_ = flow.plan_sides(prev, "mirror")
        results.append((enter, exit_))
        prev = exit_
    assert results == [
        ("left", "right"),
        ("right", "left"),
        ("left", "right"),
        ("right", "left"),
        ("left", "right"),
    ]


def test_invalid_mode_raises() -> None:
    try:
        flow.plan_sides(None, "inconnu")
    except ValueError:
        return
    raise AssertionError("plan_sides devrait lever ValueError pour un mode inconnu")
