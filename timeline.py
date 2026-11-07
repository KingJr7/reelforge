"""Chronologie des événements : source de vérité pour le rendu et le mixage audio."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from config import CARD_ENTRY_FRAMES, CARD_EXIT_FRAMES, FPS, DEFAULT_INVERT_AT
from flow import plan_sides
from script_parser import ParsedScript, ParsedMarker


@dataclass
class WordEvent:
    text: str
    size_level: str
    start: float
    end: float
    enter_side: str
    exit_side: str


@dataclass
class CardEvent:
    source: str
    kind: str        # 'photo' | 'video' | 'local'
    size: str        # 'small' | 'medium' | 'large'
    start: float
    duration: float
    enter_side: str
    exit_side: str


@dataclass
class InvertEvent:
    t: float


@dataclass
class CtaEvent:
    text: str
    start: float


@dataclass
class SfxEvent:
    name: str        # 'tick' | 'whoosh_in' | 'land' | 'whoosh_out' | 'invert' | 'cta'
    t: float         # secondes, instant de l'attaque visuelle
    pan: float       # -1 (gauche) à 1 (droite), 0 = centré
    gain_db: float = 0.0


@dataclass
class Timeline:
    words: list[WordEvent] = field(default_factory=list)
    cards: list[CardEvent] = field(default_factory=list)
    invert: Optional[InvertEvent] = None
    cta: Optional[CtaEvent] = None
    sfx: list[SfxEvent] = field(default_factory=list)
    duration: float = 0.0
    frames: int = 0

    def to_dict(self) -> dict:
        return {
            "duration": self.duration,
            "frames": self.frames,
            "words": [
                {"text": w.text, "size_level": w.size_level, "start": w.start,
                 "end": w.end, "enter_side": w.enter_side, "exit_side": w.exit_side}
                for w in self.words
            ],
            "cards": [
                {"source": c.source, "kind": c.kind, "size": c.size, "start": c.start,
                 "duration": c.duration, "enter_side": c.enter_side, "exit_side": c.exit_side}
                for c in self.cards
            ],
            "invert": {"t": self.invert.t} if self.invert else None,
            "cta": {"text": self.cta.text, "start": self.cta.start} if self.cta else None,
            "sfx": [
                {"name": s.name, "t": s.t, "pan": s.pan, "gain_db": s.gain_db}
                for s in self.sfx
            ],
        }


_BROLL_RE = re.compile(
    r"^(?P<query>.+?)\s*\|\s*(?P<duration>[\d.]+)s?\s*\|\s*(?P<size>small|medium|large)"
    r"(?:\s*\|\s*(?P<kind>photo|video))?$"
)


def _parse_broll_value(value: str) -> dict:
    """Parse la valeur d'un marqueur [BROLL: ...] en dictionnaire."""
    value = value.strip()
    # Chemin local (pas de ' | ')
    if "|" not in value:
        return {
            "query": value,
            "duration": 2.0,
            "size": "small",
            "kind": "local",
        }
    m = _BROLL_RE.match(value)
    if not m:
        # Fallback : prend la première partie comme query, durée 2s, medium
        return {
            "query": value.split("|")[0].strip(),
            "duration": 2.0,
            "size": "medium",
            "kind": "photo",
        }
    return {
        "query": m.group("query").strip(),
        "duration": float(m.group("duration")),
        "size": m.group("size"),
        "kind": m.group("kind") or "photo",
    }


def build_timeline(
    parsed: ParsedScript,
    word_times: list[tuple[float, float]],
    flow_mode: str = "sweep",
    invert_at: Optional[float] = None,
) -> Timeline:
    """Construit la Timeline à partir du script parsé et des timestamps des mots.

    word_times[i] = (start, end) en secondes pour parsed.words[i].
    """
    words = parsed.words
    n = len(words)

    # --- 1. Crée les WordEvent avec leurs temps ---
    word_events: list[WordEvent] = []
    for i, w in enumerate(words):
        start, end = word_times[i] if i < len(word_times) else (0.0, 0.5)
        word_events.append(
            WordEvent(
                text=w.text,
                size_level=w.size_level,
                start=start,
                end=end,
                enter_side="",
                exit_side="",
            )
        )

    # --- 2. Traite les marqueurs ---
    cards: list[CardEvent] = []
    invert_event: Optional[InvertEvent] = None
    cta_event: Optional[CtaEvent] = None
    hidden_word_starts: set[float] = set()

    fin_voix = max((wt[1] for wt in word_times), default=0.0)

    for m in parsed.markers:
        if m.kind == "broll":
            info = _parse_broll_value(m.value)
            wi = m.word_index
            if wi < n:
                start = word_times[wi][0]
            else:
                start = fin_voix
            duration = info["duration"]
            cards.append(
                CardEvent(
                    source=info["query"],
                    kind=info["kind"],
                    size=info["size"],
                    start=start,
                    duration=duration,
                    enter_side="",
                    exit_side="",
                )
            )
            # Marque les mots cachés : start dans [card.start, card.start + duration]
            card_end = start + duration
            for we in word_events:
                if start <= we.start <= card_end:
                    hidden_word_starts.add(we.start)

        elif m.kind == "invert":
            wi = m.word_index
            if wi < n:
                t = word_times[wi][0]
            else:
                t = fin_voix
            invert_event = InvertEvent(t=t)

        elif m.kind == "cta":
            wi = m.word_index
            if wi < n:
                start = word_times[wi][0]
            else:
                start = max(fin_voix - 0.2, 0.0)
            cta_event = CtaEvent(text=m.value, start=start)

    # --- 3. Inversion par défaut à 50 % si pas de [INVERT] ---
    if invert_event is None and fin_voix > 0:
        ratio = DEFAULT_INVERT_AT if invert_at is None else invert_at
        ratio = min(max(ratio, 0.0), 1.0)
        invert_event = InvertEvent(t=fin_voix * ratio)

    # --- 4. Retire les mots cachés par les cartes ---
    visible_words = [we for we in word_events if we.start not in hidden_word_starts]

    # --- 5. Assigne les côtés via la machine à états (flux chronologique) ---
    # On fusionne mots et cartes, triés par start, et on assigne les côtés.
    elements: list[tuple[float, str, object]] = []
    for we in visible_words:
        elements.append((we.start, "word", we))
    for c in cards:
        elements.append((c.start, "card", c))
    elements.sort(key=lambda e: e[0])

    prev_exit: Optional[str] = None
    for _, kind, el in elements:
        enter, exit_ = plan_sides(prev_exit, flow_mode)
        if kind == "word":
            el.enter_side = enter
            el.exit_side = exit_
        else:
            el.enter_side = enter
            el.exit_side = exit_
        prev_exit = exit_

    # --- 6. Génère les événements SFX ---
    sfx: list[SfxEvent] = []
    entry_mid_frame = CARD_ENTRY_FRAMES // 2  # frame 5 sur 10

    for we in visible_words:
        pan = -1.0 if we.enter_side == "left" else 1.0
        sfx.append(SfxEvent(name="tick", t=we.start, pan=0.0))

    for c in cards:
        pan = -1.0 if c.enter_side == "left" else 1.0
        sfx.append(SfxEvent(name="whoosh_in", t=c.start + entry_mid_frame / FPS, pan=pan))
        sfx.append(SfxEvent(name="land", t=c.start + CARD_ENTRY_FRAMES / FPS, pan=0.0))
        sfx.append(SfxEvent(name="whoosh_out", t=c.start + c.duration, pan=-pan))

    if invert_event is not None:
        sfx.append(SfxEvent(name="invert", t=invert_event.t, pan=0.0))

    if cta_event is not None:
        sfx.append(SfxEvent(name="cta", t=cta_event.start, pan=0.0))

    # --- 7. Durée de la vidéo ---
    if cta_event is not None:
        duration = max(fin_voix + 0.6, cta_event.start + 1.9)
    else:
        duration = fin_voix + 0.6

    frames = math.ceil(duration * FPS)

    return Timeline(
        words=visible_words,
        cards=cards,
        invert=invert_event,
        cta=cta_event,
        sfx=sfx,
        duration=duration,
        frames=frames,
    )


def export_timeline(timeline: Timeline, path: str) -> None:
    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump(timeline.to_dict(), f, indent=2, ensure_ascii=False)
