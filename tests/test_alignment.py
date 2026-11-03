"""Test d'alignement caractères -> mots (script_parser avec ElevenLabs-like alignment)."""
from __future__ import annotations

import script_parser


def test_char_to_word_alignment_counts_match() -> None:
    """Le nombre de mots du script propre doit égaler le nombre de mots parsés."""
    script = (
        "Tu savais qu'il existe [BROLL: robot hand typing | 1.8s | medium] "
        "une façon de gagner *deux heures* par jour ? [PAUSE 0.3]\n"
        "Et le plus fou, c'est que tu peux la tester dès **aujourd'hui**."
    )
    s = script_parser.parse_script(script)
    assert len(s.words) > 0
    # Aucun marqueur ne reste
    for bad in ["[BROLL", "[INVERT", "[PAUSE", "[CTA"]:
        assert bad not in s.clean_text
    # Les pauses sont en <break>
    assert s.clean_text.count('<break time="0.3s" />') == 1


def test_french_accents_preserved() -> None:
    s = script_parser.parse_script("résultats d'envoi qu'il aujourd'hui")
    texts = [w.text for w in s.words]
    assert "résultats" in texts
    assert "d'envoi" in texts
    assert "qu'il" in texts
    assert "aujourd'hui" in texts
