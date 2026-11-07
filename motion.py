"""Primitives de motion design réutilisables pour le renderer."""
from __future__ import annotations

from dataclasses import dataclass

from easing import ease_in_cubic, ease_out_back, ease_out_cubic


@dataclass(frozen=True)
class MotionStyle:
    name: str
    entry_ease: str
    exit_ease: str
    overshoot: float
    card_slide: int
    word_slide: int


MOTION_STYLES = {
    "premium": MotionStyle("premium", "cubic", "cubic", 0.0, 96, 36),
    "energetic": MotionStyle("energetic", "back", "cubic", 0.06, 140, 48),
    "minimal": MotionStyle("minimal", "cubic", "cubic", 0.0, 48, 20),
}


def get_motion_style(name: str) -> MotionStyle:
    """Retourne un style connu, avec premium comme fallback sûr."""
    return MOTION_STYLES.get(name, MOTION_STYLES["premium"])


def entry_progress(t: float, style: MotionStyle) -> float:
    """Progression d'entrée avec un seul point de décision réutilisable."""
    if style.entry_ease == "back":
        return min(1.0 + style.overshoot, ease_out_back(t))
    return ease_out_cubic(t)


def exit_progress(t: float, style: MotionStyle) -> float:
    """Progression de sortie : accélère vers la disparition."""
    return ease_in_cubic(t)

