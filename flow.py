"""Machine à états de continuité directionnelle.

plan_sides(prev_exit_side, mode) -> (enter_side, exit_side)
Chaque côté vaut 'left' ou 'right'.
"""

from __future__ import annotations


def plan_sides(prev_exit_side: str | None, mode: str) -> tuple[str, str]:
    """Retourne (enter_side, exit_side).

    sweep (défaut) : balayage continu dans le même sens.
        prev None ou 'right' -> entre gauche, sort droite.
        prev 'left' -> entre droite, sort gauche (direction retournée).
    mirror : rebond gauche-droite.
        entre du côté où le précédent est sorti, sort du côté opposé.
    """
    if mode not in ("sweep", "mirror"):
        raise ValueError(f"mode inconnu: {mode}")

    if mode == "sweep":
        if prev_exit_side is None or prev_exit_side == "right":
            return ("left", "right")
        # prev_exit_side == 'left' : la direction a été retournée
        return ("right", "left")

    # mirror
    if prev_exit_side is None:
        enter_side = "left"
    else:
        enter_side = prev_exit_side
    exit_side = "right" if enter_side == "left" else "left"
    return (enter_side, exit_side)
