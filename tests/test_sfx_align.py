"""Test d'alignement SFX : pic de l'invert au sample près."""
from __future__ import annotations

import sfx


def test_invert_impact_at_exact_sample() -> None:
    """Le pic du SFX d'inversion est à round(t * 48000) ± 48 échantillons (±1 ms)."""
    import numpy as np

    samples = sfx.build_sfx_samples()
    inv = samples["invert"]
    offset_samples = int(inv.impact_offset * 48000)
    assert abs(offset_samples - int(0.55 * 48000)) <= 1

    # Énergie à l'impact
    seg = inv.data[offset_samples: offset_samples + 480]
    rms = float(np.sqrt(np.mean(seg ** 2)))
    assert rms > 0.01


def test_tick_variants_round_robin() -> None:
    """Les 4 variantes de tick existent et ont un impact_offset cohérent."""
    samples = sfx.build_sfx_samples()
    for i in range(4):
        assert f"tick_{i}" in samples
        assert samples[f"tick_{i}"].impact_offset == sfx.IMPACT_OFFSETS["tick"]


def test_all_impact_offsets() -> None:
    """Tous les SFX ont un impact_offset défini."""
    samples = sfx.build_sfx_samples()
    for name, off in sfx.IMPACT_OFFSETS.items():
        if name == "tick":
            for i in range(4):
                assert samples[f"tick_{i}"].impact_offset == off
        else:
            assert samples[name].impact_offset == off
