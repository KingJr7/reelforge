"""Tests du parseur de script annoté (script_parser.py)."""
from __future__ import annotations

import script_parser


def test_basic_words() -> None:
    s = script_parser.parse_script("Bonjour le monde")
    assert [w.text for w in s.words] == ["Bonjour", "le", "monde"]
    assert [w.size_level for w in s.words] == ["normal", "normal", "normal"]
    assert s.clean_text == "Bonjour le monde"
    assert s.markers == []


def test_french_apostrophes_single_word() -> None:
    s = script_parser.parse_script("qu'il d'envoi AUJOURD'HUI")
    assert [w.text for w in s.words] == ["qu'il", "d'envoi", "AUJOURD'HUI"]
    assert len(s.words) == 3


def test_punctuation_attached() -> None:
    s = script_parser.parse_script("jour? cristal.")
    assert [w.text for w in s.words] == ["jour?", "cristal."]


def test_emphasis_span() -> None:
    s = script_parser.parse_script("gagner *deux heures* par jour")
    levels = [w.size_level for w in s.words]
    assert levels == ["normal", "emphasis", "emphasis", "normal", "normal"]
    assert [w.text for w in s.words] == ["gagner", "deux", "heures", "par", "jour"]


def test_strong_span() -> None:
    s = script_parser.parse_script("test dès **aujourd'hui** maintenant")
    levels = [w.size_level for w in s.words]
    assert levels == ["normal", "normal", "strong", "normal"]
    assert s.words[2].text == "aujourd'hui"


def test_broll_marker_anchors_to_next_word() -> None:
    s = script_parser.parse_script(
        "Tu savais [BROLL: robot hand typing | 1.8s | medium] une façon"
    )
    assert len(s.markers) == 1
    m = s.markers[0]
    assert m.kind == "broll"
    assert m.word_index == 2  # "une" est le 3e mot (index 2)
    assert s.words[2].text == "une"
    assert "[BROLL" not in s.clean_text


def test_invert_marker() -> None:
    s = script_parser.parse_script("Fin de phrase. [INVERT] Nouvelle phrase.")
    invert_ms = [m for m in s.markers if m.kind == "invert"]
    assert len(invert_ms) == 1
    assert invert_ms[0].word_index == 3  # "Nouvelle"
    assert "[INVERT" not in s.clean_text


def test_pause_marker() -> None:
    s = script_parser.parse_script("Bonjour [PAUSE 0.3] le monde")
    pause_ms = [m for m in s.markers if m.kind == "pause"]
    assert len(pause_ms) == 1
    assert pause_ms[0].value == "0.3"
    assert pause_ms[0].word_index == 1  # "le" est le 2e mot (index 1)
    assert '<break time="0.3s" />' in s.clean_text


def test_cta_marker_at_end() -> None:
    s = script_parser.parse_script("Dernier mot [CTA: EXEMPLE.COM]")
    cta_ms = [m for m in s.markers if m.kind == "cta"]
    assert len(cta_ms) == 1
    assert cta_ms[0].value == "EXEMPLE.COM"
    assert cta_ms[0].word_index == 2  # aucun mot après, index == len(words)
    assert "[CTA" not in s.clean_text


def test_markers_at_start_and_end() -> None:
    s = script_parser.parse_script("[INVERT] Seul mot [CTA: FIN.COM]")
    assert [w.text for w in s.words] == ["Seul", "mot"]
    kinds = [m.kind for m in s.markers]
    assert kinds == ["invert", "cta"]
    assert s.markers[0].word_index == 0  # "Seul"
    assert s.markers[1].word_index == 2  # aucun mot après


def test_full_example() -> None:
    script = (
        "Tu savais qu'il existe [BROLL: robot hand typing | 1.8s | medium] "
        "une façon de gagner *deux heures* par jour ? [PAUSE 0.3]\n"
        "Et le plus fou, c'est que tu peux la tester dès **aujourd'hui**. "
        "[BROLL: laptop coding | 2.0s | medium video]\n"
        "Pas de magie, pas de boule de cristal. [PAUSE 0.3]\n"
        "Juste des outils qui font le travail à ta place. [INVERT] "
        "Fini la fatigue, fini les tâches répétitives.\n"
        "[BROLL: sunrise mountains | 2.0s | medium] Tu gagnes du temps, "
        "tu respires, tu avances.\n"
        "[CTA: EXEMPLE.COM]"
    )
    s = script_parser.parse_script(script)
    assert len(s.words) > 20
    # Vérifie qu'aucun marqueur ne reste dans le texte propre
    for bad in ["[BROLL", "[INVERT", "[PAUSE", "[CTA"]:
        assert bad not in s.clean_text
    # Vérifie que les pauses sont en <break>
    assert s.clean_text.count('<break time="0.3s" />') == 2
    # Vérifie les niveaux
    strong = [w for w in s.words if w.size_level == "strong"]
    emphasis = [w for w in s.words if w.size_level == "emphasis"]
    assert len(strong) == 1
    assert len(emphasis) == 2
