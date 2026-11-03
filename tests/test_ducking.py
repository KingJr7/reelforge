"""Tests du timeline, du ducking et de l'alignement SFX."""
from __future__ import annotations

import math

import numpy as np

import timeline
import sfx
import audio_mixer


def np_log10(x: float) -> float:
    return math.log10(max(x, 1e-12))


def test_ducking_speech_vs_silence() -> None:
    """Le gain pendant la parole vaut duck_db ± 0.5 dB, plus élevé dans un silence de 0.5 s."""
    duration = 2.0
    word_times = [(0.4, 0.6)]
    gain = audio_mixer.compute_duck_envelope(
        duration, word_times, duck_db=-22.0, silence_db=-12.0
    )

    idx_speech = int(0.65 * 48000)
    gain_db = 20 * np_log10(float(gain[idx_speech]))
    assert abs(gain_db - (-22.0)) < 0.5, f"gain pendant parole = {gain_db} dB"

    idx_silence = int(1.5 * 48000)
    gain_db_sil = 20 * np_log10(float(gain[idx_silence]))
    assert gain_db_sil > -13.0, f"gain silence = {gain_db_sil} dB"
    assert gain_db_sil > gain_db, "le silence devrait être plus fort que la parole"


def test_sfx_invert_alignment() -> None:
    """Le pic d'impact de l'invert est à round(t * 48000) ± 48 échantillons (±1 ms)."""
    samples = sfx.build_sfx_samples()
    inv = samples["invert"]
    offset_samples = int(inv.impact_offset * 48000)
    assert abs(offset_samples - int(0.55 * 48000)) <= 1

    seg = inv.data[offset_samples: offset_samples + 480]
    rms = float(np.sqrt(np.mean(seg ** 2)))
    assert rms > 0.01


def test_sfx_priorities() -> None:
    assert sfx.PRIORITY["invert"] < sfx.PRIORITY["whoosh_in"]
    assert sfx.PRIORITY["whoosh_in"] < sfx.PRIORITY["land"]
    assert sfx.PRIORITY["land"] < sfx.PRIORITY["whoosh_out"]
    assert sfx.PRIORITY["whoosh_out"] < sfx.PRIORITY["cta"]
    assert sfx.PRIORITY["cta"] < sfx.PRIORITY["tick"]


def test_timeline_basic_structure() -> None:
    from script_parser import ParsedScript, ParsedWord, ParsedMarker

    parsed = ParsedScript(
        clean_text="Bonjour le monde",
        words=[
            ParsedWord(text="Bonjour", size_level="normal"),
            ParsedWord(text="le", size_level="normal"),
            ParsedWord(text="monde", size_level="normal"),
        ],
        markers=[],
    )
    word_times = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.8)]
    tl = timeline.build_timeline(parsed, word_times, flow_mode="sweep")

    assert len(tl.words) == 3
    assert tl.frames == math.ceil(tl.duration * 30)
    assert tl.duration >= 0.8 + 0.6
    assert tl.words[0].enter_side == "left"
    assert tl.words[0].exit_side == "right"
    assert tl.invert is not None
    assert abs(tl.invert.t - 0.8 * 0.5) < 0.01

    ticks = [s for s in tl.sfx if s.name == "tick"]
    assert len(ticks) == 3


def test_timeline_with_broll() -> None:
    from script_parser import ParsedScript, ParsedWord, ParsedMarker

    parsed = ParsedScript(
        clean_text="Premier deuxieme troisieme",
        words=[
            ParsedWord(text="Premier", size_level="normal"),
            ParsedWord(text="deuxieme", size_level="normal"),
            ParsedWord(text="troisieme", size_level="normal"),
        ],
        markers=[
            ParsedMarker(kind="broll", value="robot hand | 1.0s | medium", word_index=1),
        ],
    )
    word_times = [(0.0, 0.3), (0.5, 0.8), (1.0, 1.3)]
    tl = timeline.build_timeline(parsed, word_times, flow_mode="sweep")

    hidden = [w for w in tl.words if w.text == "deuxieme"]
    assert len(hidden) == 0

    assert len(tl.cards) == 1
    assert tl.cards[0].start == 0.5
    assert tl.cards[0].duration == 1.0

    assert len([s for s in tl.sfx if s.name == "whoosh_in"]) == 1
    assert len([s for s in tl.sfx if s.name == "land"]) == 1
    assert len([s for s in tl.sfx if s.name == "whoosh_out"]) == 1


def test_timeline_mirror_mode() -> None:
    from script_parser import ParsedScript, ParsedWord

    parsed = ParsedScript(
        clean_text="A B C D E",
        words=[ParsedWord(text=l, size_level="normal") for l in ["A", "B", "C", "D", "E"]],
        markers=[],
    )
    word_times = [(i * 0.3, i * 0.3 + 0.2) for i in range(5)]
    tl = timeline.build_timeline(parsed, word_times, flow_mode="mirror")

    sides = [(w.enter_side, w.exit_side) for w in tl.words]
    assert sides == [
        ("left", "right"),
        ("right", "left"),
        ("left", "right"),
        ("right", "left"),
        ("left", "right"),
    ]


def test_timeline_invert_marker() -> None:
    from script_parser import ParsedScript, ParsedWord, ParsedMarker

    parsed = ParsedScript(
        clean_text="Avant apres",
        words=[ParsedWord(text="Avant", size_level="normal"),
               ParsedWord(text="apres", size_level="normal")],
        markers=[ParsedMarker(kind="invert", value="", word_index=1)],
    )
    word_times = [(0.0, 0.3), (1.0, 1.3)]
    tl = timeline.build_timeline(parsed, word_times, flow_mode="sweep")
    assert tl.invert is not None
    assert abs(tl.invert.t - 1.0) < 0.01


def test_cta_duration() -> None:
    from script_parser import ParsedScript, ParsedWord, ParsedMarker

    parsed = ParsedScript(
        clean_text="Dernier",
        words=[ParsedWord(text="Dernier", size_level="normal")],
        markers=[ParsedMarker(kind="cta", value="SITE.COM", word_index=0)],
    )
    word_times = [(5.0, 5.3)]
    tl = timeline.build_timeline(parsed, word_times, flow_mode="sweep")
    assert tl.cta is not None
    assert tl.cta.start == 5.0
    assert tl.duration >= 5.0 + 1.9
