"""Parse du script annoté : texte propre pour TTS, liste des mots, marqueurs ancrés."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedWord:
    text: str            # texte du mot (ponctuation incluse, cas original)
    size_level: str      # 'normal' | 'emphasis' | 'strong'


@dataclass
class ParsedMarker:
    kind: str            # 'broll' | 'invert' | 'pause' | 'cta'
    value: str           # contenu brut du marqueur
    word_index: int      # index du mot auquel le marqueur est ancré (-1 si aucun)


@dataclass
class ParsedScript:
    clean_text: str      # texte à envoyer au TTS (markers retirés, pauses en <break>)
    words: list[ParsedWord] = field(default_factory=list)
    markers: list[ParsedMarker] = field(default_factory=list)


# Patron maître : marqueurs d'abord, puis spans emphase/forte, puis mots simples.
_TOKEN_RE = re.compile(
    r"""\[BROLL:[^\]]*\]          # [BROLL: ...]
    |   \[INVERT\]                # [INVERT]
    |   \[PAUSE[^\]]*\]           # [PAUSE ...]
    |   \[CTA:[^\]]*\]            # [CTA: ...]
    |   \*\*[^*]+\*\*             # **MOT** (forte)
    |   \*[^*]+\*                 # *mot* (emphase)
    |   \S+                       # mot simple (ponctuation collée incluse, apostrophes)
    """,
    re.VERBOSE,
)

_MARKER_RE = re.compile(r"^\[(\w+):?([^\]]*)\]$")


def _parse_marker_content(raw: str) -> tuple[str, str]:
    """Extrait (kind, value) du contenu d'un marqueur (sans crochets).
    Ex: 'BROLL: robot hand typing | 1.8s | medium' -> ('broll', 'robot hand typing | 1.8s | medium')
    """
    m = re.match(r"^(\w+):?(.*)$", raw)
    if not m:
        return ("unknown", raw)
    kind = m.group(1).lower()
    value = m.group(2).strip()
    return (kind, value)


def _split_span_words(content: str) -> list[str]:
    """Découpe le contenu d'un span *...* ou **...** en mots (ponctuation collée)."""
    return [w for w in content.split() if w]


def parse_script(text: str) -> ParsedScript:
    """Parse le script annoté et retourne ParsedScript."""
    words: list[ParsedWord] = []
    markers: list[ParsedMarker] = []
    speech_parts: list[str] = []

    for m in _TOKEN_RE.finditer(text):
        token = m.group(0)

        # --- Marqueurs ---
        if token.startswith("[") and token.endswith("]"):
            kind, value = _parse_marker_content(token[1:-1])

            if kind == "broll":
                # Ancre au prochain mot (index actuel de words)
                markers.append(ParsedMarker(kind="broll", value=value, word_index=len(words)))
                # Pas de parole pour les B-roll
                continue

            if kind == "invert":
                markers.append(ParsedMarker(kind="invert", value="", word_index=len(words)))
                continue

            if kind == "cta":
                markers.append(ParsedMarker(kind="cta", value=value, word_index=len(words)))
                continue

            if kind == "pause":
                markers.append(ParsedMarker(kind="pause", value=value, word_index=len(words)))
                # Pause -> <break> pour le TTS
                speech_parts.append(f'<break time="{value}s" />')
                continue

            # Marqueur inconnu : ignoré
            continue

        # --- Span forte **...** ---
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            content = token[2:-2]
            for w in _split_span_words(content):
                words.append(ParsedWord(text=w, size_level="strong"))
                speech_parts.append(w)
            continue

        # --- Span emphase *...* ---
        if token.startswith("*") and token.endswith("*") and len(token) > 2:
            content = token[1:-1]
            for w in _split_span_words(content):
                words.append(ParsedWord(text=w, size_level="emphasis"))
                speech_parts.append(w)
            continue

        # --- Mot simple ---
        words.append(ParsedWord(text=token, size_level="normal"))
        speech_parts.append(token)

    clean_text = " ".join(speech_parts)
    return ParsedScript(clean_text=clean_text, words=words, markers=markers)
