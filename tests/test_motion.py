"""Tests des primitives de motion design réutilisables."""
from __future__ import annotations

import audio_mixer
import motion
import numpy as np
from renderer import apply_blur_reveal_np, apply_flash_np, apply_wipe_np, apply_zoom_cut_np, make_motion_accent_np


def test_motion_styles_have_valid_endpoints() -> None:
    for name in ("premium", "energetic", "minimal"):
        style = motion.get_motion_style(name)
        assert motion.entry_progress(0.0, style) == 0.0
        assert motion.entry_progress(1.0, style) >= 1.0
        assert motion.exit_progress(0.0, style) == 0.0
        assert motion.exit_progress(1.0, style) == 1.0


def test_unknown_motion_style_falls_back_to_premium() -> None:
    assert motion.get_motion_style("unknown").name == "premium"


def test_sfx_ducking_reduces_sfx_during_voice() -> None:
    gain = audio_mixer.compute_sfx_duck_envelope(2.0, [(0.5, 1.0)])
    assert float(gain[int(0.75 * 48000)]) < 1.0
    assert float(gain[int(1.8 * 48000)]) > float(gain[int(0.75 * 48000)])


def test_bgm_loop_crossfade_keeps_requested_length() -> None:
    source = np.ones((48000, 2), dtype=np.float32)
    looped = audio_mixer._loop_with_crossfades(source, 72000)
    assert looped.shape == (72000, 2)
    assert np.isfinite(looped).all()


def test_flash_transition_is_bounded() -> None:
    canvas = np.zeros((4, 4, 3), dtype=np.uint8)
    flashed = apply_flash_np(canvas, 0)
    assert flashed.max() <= 255
    assert flashed.mean() > 0
    assert np.array_equal(apply_flash_np(canvas, 4), canvas)


def test_visual_transitions_preserve_canvas_shape() -> None:
    canvas = np.zeros((12, 20, 3), dtype=np.uint8)
    for transition in (apply_wipe_np, apply_zoom_cut_np, apply_blur_reveal_np):
        result = transition(canvas, 1)
        assert result.shape == canvas.shape
        assert result.dtype == np.uint8


def test_voice_processing_is_finite_and_bounded() -> None:
    source = np.zeros((4800, 2), dtype=np.float32)
    source[100:400] = 0.5
    processed = audio_mixer._process_voice(source)
    assert np.isfinite(processed).all()
    assert float(np.max(np.abs(processed))) <= 1.0


def test_rms_normalization_is_finite_and_bounded() -> None:
    source = np.ones((4800, 2), dtype=np.float32) * 0.02
    normalized = audio_mixer._normalize_rms_stereo(source, target_db=-24.0)
    assert np.isfinite(normalized).all()
    assert float(np.max(np.abs(normalized))) <= 1.0


def test_audio_stats_detect_peak_and_rms() -> None:
    stats = audio_mixer.measure_audio_stats(np.ones((100, 2), dtype=np.float32) * 0.5)
    assert stats["peak_db"] < 0
    assert stats["rms_db"] == stats["peak_db"]
    assert stats["crest_db"] == 0.0


def test_motion_accent_reveals_progressively() -> None:
    empty = make_motion_accent_np(100, 80, (255, 0, 0), 0.0)
    full = make_motion_accent_np(100, 80, (255, 0, 0), 1.0)
    assert full.shape == empty.shape
    assert int(full[:, :, 3].sum()) > int(empty[:, :, 3].sum())

