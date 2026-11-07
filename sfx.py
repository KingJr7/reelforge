"""Synthèse des SFX (48 kHz, float32, stéréo, seed 42) et placement au sample près sur un bus unique."""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from scipy import signal

from config import AUDIO_SAMPLE_RATE, SEED, SFX_DIR


@dataclass
class SfxSample:
    name: str
    data: np.ndarray       # float32 stereo (n, 2)
    impact_offset: float   # secondes, instant de l'attaque dans le fichier
    peak_db: float


IMPACT_OFFSETS = {
    "tick": 0.0015,
    "whoosh_in": 0.20,
    "land": 0.0,
    "whoosh_out": 0.05,
    "invert": 0.55,
    "cta": 0.0,
}

PEAK_DBS = {
    "tick": -26.0,
    "whoosh_in": -20.0,
    "land": -20.0,
    "whoosh_out": -24.0,
    "invert": -8.0,
    "cta": -20.0,
}

# Niveau relatif par événement. Les impacts importants restent audibles sans
# laisser les ticks prendre le dessus sur la voix.
EVENT_GAIN_DB = {
    "tick": -2.0,
    "whoosh_in": 0.0,
    "land": 0.0,
    "whoosh_out": -1.0,
    "invert": 0.0,
    "cta": -1.0,
}

# Plus le nombre est petit, plus la priorité est haute (gardé en cas de bouillie)
PRIORITY = {
    "invert": 0,
    "whoosh_in": 1,
    "land": 2,
    "whoosh_out": 3,
    "cta": 4,
    "tick": 5,
}

TICK_VARIANTS_FREQ = [1900.0, 2150.0, 2400.0, 2000.0]

_WINDOW_MS = 40       # fenêtre de détection de bouillie (ms)
_MAX_SFX_PER_WINDOW = 3


def _db_to_amplitude(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _normalize_peak(mono: np.ndarray, peak_db: float) -> np.ndarray:
    peak = float(np.max(np.abs(mono)))
    if peak > 0:
        mono = mono / peak * _db_to_amplitude(peak_db)
    return mono


def _to_stereo(mono: np.ndarray) -> np.ndarray:
    return np.column_stack([mono, mono]).astype(np.float32)


def _hpf_one_pole(x: np.ndarray, fc: float, fs: int) -> np.ndarray:
    """Passe-haut un pôle (blocage continu)."""
    rc = 1.0 / (2.0 * np.pi * fc)
    dt = 1.0 / fs
    alpha = rc / (rc + dt)
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = alpha * (y[i - 1] + x[i] - x[i - 1])
    return y


def _lpf_one_pole_varying(x: np.ndarray, coeffs: np.ndarray) -> np.ndarray:
    """Passe-bas un pôle à coefficient variable par échantillon."""
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        c = coeffs[i]
        y[i] = (1.0 - c) * x[i] + c * y[i - 1]
    return y


def _apply_pan(mono: np.ndarray, pan: float) -> np.ndarray:
    """pan: -1 = gauche uniquement, 0 = centré, 1 = droite uniquement (puissance constante)."""
    # Pan law à puissance constante
    angle = (pan + 1.0) * np.pi / 4.0
    left = np.cos(angle)
    right = np.sin(angle)
    stereo = np.column_stack([mono * left, mono * right]).astype(np.float32)
    return stereo


def _synth_tick(rng: np.random.Generator, freq: float, duration: float = 0.035) -> np.ndarray:
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    pitch = 1.0 + rng.uniform(-0.03, 0.03)
    f = freq * pitch
    sine = np.sin(2.0 * np.pi * f * t) * np.exp(-t / 0.006)
    noise = rng.standard_normal(n)
    hpf_noise = _hpf_one_pole(noise, 150.0, AUDIO_SAMPLE_RATE)
    noise_part = 0.30 * hpf_noise * np.exp(-t / 0.002)
    mono = sine + noise_part
    mono = _normalize_peak(mono, PEAK_DBS["tick"])
    return _to_stereo(mono)


def _synth_whoosh(rng: np.random.Generator, duration: float, sweep_dir: float,
                  peak_db: float, start_coeff: float, end_coeff: float) -> np.ndarray:
    """sweep_dir: +1 = montant (brightness up), -1 = descendant."""
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    noise = rng.standard_normal(n)

    # Coefficient de passe-bas qui balaye
    if sweep_dir > 0:
        coeffs = np.linspace(start_coeff, end_coeff, n)
    else:
        coeffs = np.linspace(end_coeff, start_coeff, n)
    lpf = _lpf_one_pole_varying(noise, coeffs)

    # Version très lente (quasi-DC) soustraite = passe-haut
    slow_coeff = 0.002
    slow = _lpf_one_pole_varying(noise, np.full(n, slow_coeff))
    mono = lpf - slow

    # Envelope sin² montant jusqu'à 70 % puis redescendant
    env = np.sin(np.pi * t / duration) ** 2
    env = env * 0.70
    env[0] = 0.0
    env[-1] = 0.0
    mono = mono * env

    mono = _normalize_peak(mono, peak_db)
    return _to_stereo(mono)


def _synth_land(rng: np.random.Generator, duration: float = 0.12) -> np.ndarray:
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    # Sinus descendant 140 -> 70 Hz
    freq = np.linspace(140.0, 70.0, n)
    phase = 2.0 * np.pi * np.cumsum(freq) / AUDIO_SAMPLE_RATE
    sine = np.sin(phase) * np.exp(-t / 0.04)
    # Clic de 2 ms
    click_n = int(0.002 * AUDIO_SAMPLE_RATE)
    click = np.zeros(n)
    click[:click_n] = np.linspace(1.0, 0.0, click_n) * 0.5
    mono = sine + click
    mono = _normalize_peak(mono, PEAK_DBS["land"])
    return _to_stereo(mono)


def _synth_invert(rng: np.random.Generator, duration: float = 0.90) -> np.ndarray:
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    impact_time = IMPACT_OFFSETS["invert"]  # 0.55
    impact_sample = int(impact_time * AUDIO_SAMPLE_RATE)

    mono = np.zeros(n)

    # Riser de 0 à impact_time : sinus 200 -> 2000 Hz + bruit filtré montant, amplitude croissante
    riser_n = impact_sample
    if riser_n > 0:
        t_r = np.arange(riser_n) / AUDIO_SAMPLE_RATE
        f_r = 200.0 + (2000.0 - 200.0) * (t_r / impact_time)
        phase_r = 2.0 * np.pi * np.cumsum(f_r) / AUDIO_SAMPLE_RATE
        riser_sine = np.sin(phase_r)
        riser_noise = _hpf_one_pole(rng.standard_normal(riser_n), 300.0, AUDIO_SAMPLE_RATE)
        # Coeff de LPF montant pour le bruit
        coeffs_r = np.linspace(0.05, 0.6, riser_n)
        riser_noise = _lpf_one_pole_varying(rng.standard_normal(riser_n), coeffs_r)
        amp_env = (t_r / impact_time) ** 2  # amplitude croissante
        mono[:riser_n] = (riser_sine + 0.5 * riser_noise) * amp_env * 0.4

    # Impact à impact_time : sinus 50 Hz (decay tau=0.18s) + rafale de bruit 80 ms
    impact_env = np.exp(-(t - impact_time) / 0.18)
    impact_env[t < impact_time] = 0.0
    impact_sine = np.sin(2.0 * np.pi * 50.0 * t) * impact_env
    burst_n = int(0.08 * AUDIO_SAMPLE_RATE)
    burst_start = impact_sample
    burst_end = min(n, burst_start + burst_n)
    if burst_end > burst_start:
        burst_t = np.arange(burst_start, burst_end) / AUDIO_SAMPLE_RATE
        burst_env = np.exp(-(burst_t - impact_time) / 0.02)
        mono[burst_start:burst_end] += 0.8 * rng.standard_normal(burst_end - burst_start) * burst_env
    mono += impact_sine * 0.6

    # Queue glitch de impact_time à fin : bitcrush 5 bits + sample-and-hold x6
    glitch_start = impact_sample
    if glitch_start < n:
        t_g = np.arange(glitch_start, n) / AUDIO_SAMPLE_RATE
        seg = mono[glitch_start:].copy()
        # Bitcrush 5 bits
        levels = 32.0
        seg = np.round(seg * levels) / levels
        # Sample-and-hold x6 : répète chaque échantillon 6 fois puis ré-échantillonne
        hold = np.repeat(seg, 6)[: len(seg)]
        mono[glitch_start:] = hold * 0.3

    mono = _normalize_peak(mono, PEAK_DBS["invert"])
    return _to_stereo(mono)


def _synth_cta(rng: np.random.Generator, duration: float = 0.30) -> np.ndarray:
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    mono = np.zeros(n)

    # Carillon 1318.5 Hz à t=0
    mono += np.sin(2.0 * np.pi * 1318.5 * t) * np.exp(-t / 0.12)
    # Carillon 1975.5 Hz à t=0.09
    t2 = t - 0.09
    mask2 = t2 >= 0
    mono[mask2] += np.sin(2.0 * np.pi * 1975.5 * t2[mask2]) * np.exp(-t2[mask2] / 0.12)

    mono = _normalize_peak(mono, PEAK_DBS["cta"])
    return _to_stereo(mono)


# --------------------------------------------------------------------------- #
# Génération de tous les SFX (cache en mémoire)
# --------------------------------------------------------------------------- #

_sfx_cache: dict[str, SfxSample] | None = None


def _load_from_assets(name: str) -> np.ndarray | None:
    """Charge un SFX depuis assets/sfx/ s'il existe. tick -> tick_0.wav .. tick_3.wav."""
    def read_wav(path) -> np.ndarray:
        import wave

        with wave.open(str(path), "rb") as w:
            n = w.getnframes()
            channels = w.getnchannels()
            source_rate = w.getframerate()
            data = w.readframes(n)
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        if channels == 2:
            arr = arr.reshape(-1, 2)
        else:
            arr = np.column_stack([arr, arr])
        if source_rate != AUDIO_SAMPLE_RATE:
            gcd = np.gcd(source_rate, AUDIO_SAMPLE_RATE)
            up = AUDIO_SAMPLE_RATE // gcd
            down = source_rate // gcd
            arr = signal.resample_poly(arr, up, down, axis=0).astype(np.float32)
        edge = min(int(0.004 * AUDIO_SAMPLE_RATE), len(arr) // 2)
        if edge > 0:
            env = np.ones(len(arr), dtype=np.float32)
            env[:edge] = np.linspace(0.0, 1.0, edge, dtype=np.float32)
            env[-edge:] = np.linspace(1.0, 0.0, edge, dtype=np.float32)
            arr *= env[:, None]
        return arr

    if name == "tick":
        variants = []
        for i in range(4):
            path = SFX_DIR / f"tick_{i}.wav"
            if not path.exists():
                path = SFX_DIR / f"tick{i}.wav"
            if path.exists():
                variants.append(read_wav(path))
        if len(variants) == 4:
            return variants  # type: ignore[return-value]
        return None
    path = SFX_DIR / f"{name}.wav"
    if path.exists():
        return read_wav(path)
    return None


def build_sfx_samples() -> dict[str, SfxSample]:
    """Construit (ou charge depuis assets) tous les SFX. Mise en cache mémoire."""
    global _sfx_cache
    if _sfx_cache is not None:
        return _sfx_cache

    rng = np.random.default_rng(SEED)
    samples: dict[str, SfxSample] = {}

    # tick : 4 variantes
    tick_variants = _load_from_assets("tick")
    if tick_variants is not None:
        for i, var in enumerate(tick_variants):
            samples[f"tick_{i}"] = SfxSample(
                name=f"tick_{i}", data=var,
                impact_offset=IMPACT_OFFSETS["tick"],
                peak_db=PEAK_DBS["tick"],
            )
    else:
        for i, freq in enumerate(TICK_VARIANTS_FREQ):
            samples[f"tick_{i}"] = SfxSample(
                name=f"tick_{i}",
                data=_synth_tick(rng, freq),
                impact_offset=IMPACT_OFFSETS["tick"],
                peak_db=PEAK_DBS["tick"],
            )

    # whoosh_in
    asset_wi = _load_from_assets("whoosh_in")
    if asset_wi is not None:
        samples["whoosh_in"] = SfxSample("whoosh_in", asset_wi,
                                         IMPACT_OFFSETS["whoosh_in"],
                                         PEAK_DBS["whoosh_in"])
    else:
        samples["whoosh_in"] = SfxSample(
            "whoosh_in",
            _synth_whoosh(rng, 0.30, +1.0, PEAK_DBS["whoosh_in"], 0.02, 0.50),
            IMPACT_OFFSETS["whoosh_in"],
            PEAK_DBS["whoosh_in"],
        )

    # land
    asset_land = _load_from_assets("land")
    if asset_land is not None:
        samples["land"] = SfxSample("land", asset_land,
                                    IMPACT_OFFSETS["land"],
                                    PEAK_DBS["land"])
    else:
        samples["land"] = SfxSample(
            "land", _synth_land(rng),
            IMPACT_OFFSETS["land"],
            PEAK_DBS["land"],
        )

    # whoosh_out
    asset_wo = _load_from_assets("whoosh_out")
    if asset_wo is not None:
        samples["whoosh_out"] = SfxSample("whoosh_out", asset_wo,
                                          IMPACT_OFFSETS["whoosh_out"],
                                          PEAK_DBS["whoosh_out"])
    else:
        samples["whoosh_out"] = SfxSample(
            "whoosh_out",
            _synth_whoosh(rng, 0.20, -1.0, PEAK_DBS["whoosh_out"], 0.02, 0.50),
            IMPACT_OFFSETS["whoosh_out"],
            PEAK_DBS["whoosh_out"],
        )

    # invert
    asset_inv = _load_from_assets("invert")
    if asset_inv is not None:
        samples["invert"] = SfxSample("invert", asset_inv,
                                      IMPACT_OFFSETS["invert"],
                                      PEAK_DBS["invert"])
    else:
        samples["invert"] = SfxSample(
            "invert", _synth_invert(rng),
            IMPACT_OFFSETS["invert"],
            PEAK_DBS["invert"],
        )

    # cta
    asset_cta = _load_from_assets("cta")
    if asset_cta is not None:
        samples["cta"] = SfxSample("cta", asset_cta,
                                   IMPACT_OFFSETS["cta"],
                                   PEAK_DBS["cta"])
    else:
        samples["cta"] = SfxSample(
            "cta", _synth_cta(rng),
            IMPACT_OFFSETS["cta"],
            PEAK_DBS["cta"],
        )

    _sfx_cache = samples
    return samples


# --------------------------------------------------------------------------- #
# Bus SFX : placement au sample près avec filtre de bouillie
# --------------------------------------------------------------------------- #

def build_sfx_bus(sfx_events: list, total_samples: int) -> np.ndarray:
    """Construit le bus SFX (float32 stéréo) à partir des SfxEvent.

    sfx_events : liste d'objets ayant .name, .t (secondes), .pan
    total_samples : longueur du bus en échantillons
    Retourne un tableau float32 (total_samples, 2).
    """
    samples = build_sfx_samples()

    # Placement brut
    placements: list[dict] = []
    for ev in sfx_events:
        base_name = ev.name
        # tick_0, tick_1... -> on choisit la variante en round-robin selon l'index dans la liste
        if base_name == "tick":
            # round-robin sur les 4 variantes
            tick_index = sum(1 for e in sfx_events if e.name == "tick" and e.t <= ev.t) - 1
            variant = tick_index % 4
            sample_name = f"tick_{variant}"
        else:
            sample_name = base_name

        if sample_name not in samples:
            continue

        sx = samples[sample_name]
        start_sample = int(ev.t * AUDIO_SAMPLE_RATE) - int(sx.impact_offset * AUDIO_SAMPLE_RATE)
        placements.append({
            "name": sample_name,
            "start": start_sample,
            "data": sx.data,
            "pan": ev.pan,
            "gain_db": EVENT_GAIN_DB.get(base_name, 0.0) + getattr(ev, "gain_db", 0.0),
            "priority": PRIORITY.get(base_name, 9),
        })

    # --- Filtre de bouillie : si >3 SFX démarrent dans 40 ms, garde les prioritaires ---
    window_samples = int(_WINDOW_MS / 1000.0 * AUDIO_SAMPLE_RATE)
    placements.sort(key=lambda p: p["start"])
    kept: list[dict] = []
    for p in placements:
        # Compte combien de placements déjà gardés démarrent dans la fenêtre autour de p
        count_in_window = sum(
            1 for k in kept
            if abs(k["start"] - p["start"]) <= window_samples
        )
        if count_in_window < _MAX_SFX_PER_WINDOW:
            kept.append(p)
        else:
            # Remplace le moins prioritaire dans la fenêtre si p est plus prioritaire
            window_kept = [k for k in kept if abs(k["start"] - p["start"]) <= window_samples]
            if window_kept:
                worst = max(window_kept, key=lambda k: k["priority"])
                if p["priority"] < worst["priority"]:
                    kept.remove(worst)
                    kept.append(p)

    # --- Mixage dans deux sous-bus ---
    # Les whooshes/ticks sont filtrés, mais les impacts conservent leur assise.
    filtered_bus = np.zeros((total_samples, 2), dtype=np.float32)
    impact_bus = np.zeros((total_samples, 2), dtype=np.float32)
    for p in kept:
        data = p["data"]
        start = p["start"]
        end = start + len(data)
        if end <= 0 or start >= total_samples:
            continue
        s0 = max(0, start)
        e0 = min(total_samples, end)
        d0 = s0 - start
        d1 = d0 + (e0 - s0)
        seg = data[d0:d1]
        pan = p["pan"]
        gain = 10.0 ** (p.get("gain_db", 0.0) / 20.0)
        if seg.ndim == 2:
            # Préserve l'image stéréo de l'asset, puis applique un pan doux.
            angle = (pan + 1.0) * np.pi / 4.0
            seg_stereo = seg * np.array([np.cos(angle), np.sin(angle)], dtype=np.float32)
        else:
            seg_stereo = _apply_pan(seg, pan)
        seg_stereo = seg_stereo * gain
        target = impact_bus if p["name"] in ("land", "invert") else filtered_bus
        target[s0:e0] += seg_stereo

    # Passe-haut uniquement sur les effets non graves.
    sos = signal.butter(2, 150.0, btype="high", fs=AUDIO_SAMPLE_RATE, output="sos")
    filtered_bus = signal.sosfilt(sos, filtered_bus, axis=0).astype(np.float32)

    return (filtered_bus + impact_bus).astype(np.float32)
