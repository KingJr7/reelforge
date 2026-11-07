"""Mixage audio : voix, BGM avec ducking, bus SFX, écriture de mix.wav."""
from __future__ import annotations

import hashlib
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from config import AUDIO_SAMPLE_RATE, VOICE_PEAK_DB, BGM_PEAK_DB, DUCK_DB_DEFAULT, DUCK_DB_SILENCE
from sfx import build_sfx_bus


@dataclass
class AudioResult:
    mix_path: Path
    duration: float
    sample_rate: int


# --------------------------------------------------------------------------- #
# Voix factice (mode demo)
# --------------------------------------------------------------------------- #

def synth_demo_voice(words: list, duration: float) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Génère une voix factice : bruit modulé par syllabe, 3,2 mots/s.

    Retourne (audio_stereo_float32, word_times) où word_times est la liste des (start, end).
    """
    rng = np.random.default_rng(42)
    words_per_sec = 3.2
    word_duration = 0.25  # s, chaque mot dure ~0.25s
    gap = 1.0 / words_per_sec - word_duration  # silence entre mots

    total_samples = int(duration * AUDIO_SAMPLE_RATE)
    audio = np.zeros((total_samples, 2), dtype=np.float32)
    word_times: list[tuple[float, float]] = []

    t = 0.0
    for i, w in enumerate(words):
        start = t
        end = min(start + word_duration, duration)
        if start >= duration:
            break
        # Bruit modulé (formante grossière) pour simuler une parole
        seg_n = int((end - start) * AUDIO_SAMPLE_RATE)
        seg_t = np.arange(seg_n) / AUDIO_SAMPLE_RATE
        # Bruit passe-bande simple autour de 800-1500 Hz
        noise = rng.standard_normal(seg_n)
        # Modulation d'amplitude pour simuler des syllabes
        mod = np.sin(2.0 * np.pi * 6.0 * seg_t) ** 2 + 0.3
        carrier = np.sin(2.0 * np.pi * 1100.0 * seg_t)
        seg = (noise * 0.3 + carrier * 0.1) * mod * 0.4
        # Envelope d'attaque/douceur
        attack = int(0.02 * AUDIO_SAMPLE_RATE)
        env = np.ones(seg_n)
        env[:attack] = np.linspace(0, 1, attack)
        env[-attack:] = np.linspace(1, 0, attack)
        seg = seg * env
        s0 = int(start * AUDIO_SAMPLE_RATE)
        e0 = min(total_samples, s0 + seg_n)
        if e0 > s0:
            audio[s0:e0, 0] += seg[: e0 - s0]
            audio[s0:e0, 1] += seg[: e0 - s0]
        word_times.append((start, end))
        t = end + gap

    # Normalise la voix à -3 dBFS de crête
    audio = _normalize_peak_stereo(audio, VOICE_PEAK_DB)
    return audio, word_times


def _normalize_peak_stereo(audio: np.ndarray, peak_db: float) -> np.ndarray:
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        target = 10.0 ** (peak_db / 20.0)
        audio = audio * (target / peak)
    return np.clip(audio, -1.0, 1.0).astype(np.float32)


def _normalize_rms_stereo(audio: np.ndarray, target_db: float = -24.0) -> np.ndarray:
    """Aligne doucement un bus sur un RMS cible avant le peak limiting final."""
    if len(audio) == 0:
        return audio.astype(np.float32)
    rms = float(np.sqrt(np.mean(np.square(audio))))
    if rms <= 1e-8:
        return audio.astype(np.float32)
    target = 10.0 ** (target_db / 20.0)
    gain = np.clip(target / rms, 0.25, 2.0)
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


def measure_audio_stats(audio: np.ndarray) -> dict[str, float]:
    """Retourne des métriques simples pour détecter niveau faible ou clipping."""
    if len(audio) == 0:
        return {"rms_db": -120.0, "peak_db": -120.0, "crest_db": 0.0}
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    rms_db = 20.0 * np.log10(max(rms, 1e-8))
    peak_db = 20.0 * np.log10(max(peak, 1e-8))
    return {"rms_db": rms_db, "peak_db": peak_db, "crest_db": peak_db - rms_db}


# --------------------------------------------------------------------------- #
# Décodage voix (mp3 -> 48kHz stéréo float)
# --------------------------------------------------------------------------- #

def decode_voice(mp3_path: Path) -> np.ndarray:
    """Décode un MP3 en float32 stéréo 48 kHz via FFmpeg."""
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(mp3_path),
            "-f", "f32le", "-acodec", "pcm_f32le",
            "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2", "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg decode échoué: {proc.stderr.decode(errors='ignore')[-500:]}")
    raw = proc.stdout
    audio = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    return audio


def decode_voice_wav(path: Path) -> tuple[np.ndarray, int]:
    """Décode un WAV en float32 stéréo. Retourne (audio, sample_rate)."""
    sr, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    if data.ndim == 1:
        data = np.column_stack([data, data])
    return data, sr


# --------------------------------------------------------------------------- #
# Enveloppe de ducking (numpy, sans sidechaincompress)
# --------------------------------------------------------------------------- #

def compute_duck_envelope(duration: float, word_times: list[tuple[float, float]],
                          duck_db: float = DUCK_DB_DEFAULT,
                          silence_db: float = DUCK_DB_SILENCE) -> np.ndarray:
    """Calcule l'enveloppe de gain de la BGM en fonction des timestamps de la voix.

    Retourne un tableau float32 (n_samples,) avec le gain linéaire (1.0 = pas de ducking).
    """
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE

    # Cible de gain par défaut (silence) et pendant la parole
    silence_gain = 10.0 ** (silence_db / 20.0)
    speech_gain = 10.0 ** (duck_db / 20.0)
    target_gain = np.ones(n, dtype=np.float64) * silence_gain

    # Fusionne les mots rapprochés (silence < 0.30s entre deux mots -> on considère une seule zone parlée)
    speech_zones: list[tuple[float, float]] = []
    for start, end in word_times:
        zone_start = max(0.0, start - 0.05)
        zone_end = end + 0.10
        if speech_zones and zone_start <= speech_zones[-1][1] + 0.30:
            speech_zones[-1] = (speech_zones[-1][0], max(speech_zones[-1][1], zone_end))
        else:
            speech_zones.append((zone_start, zone_end))

    for zs, ze in speech_zones:
        mask = (t >= zs) & (t <= ze)
        target_gain[mask] = 10.0 ** (duck_db / 20.0)

    # Attaque 80 ms, relâchement 400 ms, lissage (pas de crans)
    attack_s = 0.08
    release_s = 0.40
    gain = np.ones(n, dtype=np.float64) * silence_gain
    for i in range(1, n):
        target = target_gain[i]
        prev = gain[i - 1]
        if target < prev:
            # Attaque (baisse rapide)
            coeff = np.exp(-1.0 / (attack_s * AUDIO_SAMPLE_RATE))
            gain[i] = target + (prev - target) * coeff
        else:
            # Relâchement (montée plus lente)
            coeff = np.exp(-1.0 / (release_s * AUDIO_SAMPLE_RATE))
            gain[i] = target + (prev - target) * coeff

    return gain.astype(np.float32)


def apply_ducking(bgm: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Applique l'enveloppe de gain à la BGM."""
    n = min(len(bgm), len(gain))
    result = bgm[:n].copy()
    result[:, 0] *= gain[:n]
    result[:, 1] *= gain[:n]
    return result


def compute_sfx_duck_envelope(duration: float, word_times: list[tuple[float, float]],
                              duck_db: float = -4.0) -> np.ndarray:
    """Réduit légèrement les SFX pendant les mots sans les faire disparaître."""
    n = int(duration * AUDIO_SAMPLE_RATE)
    target = np.ones(n, dtype=np.float64)
    speech_gain = 10.0 ** (duck_db / 20.0)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    for start, end in word_times:
        mask = (t >= max(0.0, start - 0.015)) & (t <= end + 0.04)
        target[mask] = speech_gain

    gain = np.ones(n, dtype=np.float64)
    attack = max(1, int(0.012 * AUDIO_SAMPLE_RATE))
    release = max(1, int(0.080 * AUDIO_SAMPLE_RATE))
    attack_coeff = np.exp(-1.0 / attack)
    release_coeff = np.exp(-1.0 / release)
    for i in range(1, n):
        coeff = attack_coeff if target[i] < gain[i - 1] else release_coeff
        gain[i] = target[i] + (gain[i - 1] - target[i]) * coeff
    return gain.astype(np.float32)


def _smooth_control(control: np.ndarray, attack_s: float, release_s: float) -> np.ndarray:
    """Lisse un contrôle audio avec attaque courte et relâchement naturel."""
    result = np.empty_like(control, dtype=np.float32)
    if len(control) == 0:
        return result
    result[0] = control[0]
    attack_coeff = np.exp(-1.0 / max(1.0, attack_s * AUDIO_SAMPLE_RATE))
    release_coeff = np.exp(-1.0 / max(1.0, release_s * AUDIO_SAMPLE_RATE))
    for i in range(1, len(control)):
        coeff = attack_coeff if control[i] < result[i - 1] else release_coeff
        result[i] = control[i] + (result[i - 1] - control[i]) * coeff
    return result


def _process_voice(audio: np.ndarray) -> np.ndarray:
    """Chaîne vocale offline : HPF, de-esser, compression et peak cible."""
    if len(audio) == 0:
        return audio.astype(np.float32)

    # Coupe le rumble sans supprimer le corps de la voix.
    sos = signal.butter(2, 80.0, btype="highpass", fs=AUDIO_SAMPLE_RATE, output="sos")
    processed = signal.sosfilt(sos, audio, axis=0).astype(np.float32)

    # De-esser : réduit uniquement la bande sifflante au-dessus de 4.5 kHz.
    sibilant_sos = signal.butter(
        2, [4500.0, 10000.0], btype="bandpass", fs=AUDIO_SAMPLE_RATE, output="sos"
    )
    sibilant = signal.sosfilt(sibilant_sos, processed, axis=0).astype(np.float32)
    sibilant_level = np.max(np.abs(sibilant), axis=1)
    sibilant_db = 20.0 * np.log10(np.maximum(sibilant_level, 1e-8))
    deess_amount = np.clip((sibilant_db + 32.0) / 12.0, 0.0, 0.45).astype(np.float32)
    deess_amount = _smooth_control(deess_amount, 0.002, 0.045)
    processed -= sibilant * deess_amount[:, None]

    # Présence légère : intelligibilité des consonnes sans booster toute la bande aiguë.
    presence_sos = signal.butter(
        2, [1800.0, 4200.0], btype="bandpass", fs=AUDIO_SAMPLE_RATE, output="sos"
    )
    presence = signal.sosfilt(presence_sos, processed, axis=0).astype(np.float32)
    processed += presence * 0.10

    # Compresseur dynamique : ratio 3:1, seuil -18 dBFS, relâchement musical.
    detector = np.max(np.abs(processed), axis=1)
    detector_db = 20.0 * np.log10(np.maximum(detector, 1e-8))
    over = np.maximum(detector_db - (-18.0), 0.0)
    gain_db = -(over * (1.0 - 1.0 / 3.0))
    gain = 10.0 ** (gain_db / 20.0)
    gain = _smooth_control(gain.astype(np.float32), 0.006, 0.090)
    processed *= gain[:, None]
    return _normalize_peak_stereo(processed, VOICE_PEAK_DB)


# --------------------------------------------------------------------------- #
# BGM : chargement, boucle, fondu entrée/sortie
# --------------------------------------------------------------------------- #

def load_bgm(path: str | None, duration: float) -> np.ndarray:
    """Charge ou génère une BGM de la durée demandée (float32 stéréo 48kHz).

    Si path est None : génère une boucle synthétique discrète (mode demo/test).
    """
    if path is not None and Path(path).exists():
        audio = decode_voice(Path(path))  # même décodeur (PCM f32le)
    else:
        audio = _synth_bgm_loop(duration)

    # Répète/coupe pour couvrir la durée avec crossfade entre les boucles.
    n_target = int(duration * AUDIO_SAMPLE_RATE)
    if len(audio) == 0:
        return np.zeros((n_target, 2), dtype=np.float32)

    audio = _loop_with_crossfades(audio, n_target)

    # Fondu d'entrée 1 s, sortie 1.5 s, borné aux très courtes vidéos.
    fade_in = min(int(1.0 * AUDIO_SAMPLE_RATE), n_target)
    fade_out = min(int(1.5 * AUDIO_SAMPLE_RATE), n_target)
    env = np.ones(n_target, dtype=np.float32)
    if fade_in > 0:
        env[:fade_in] = np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    if fade_out > 0:
        env[-fade_out:] = np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
    result = audio.copy()
    result[:, 0] *= env
    result[:, 1] *= env

    # D'abord un alignement RMS, puis un plafond de crête pour éviter qu'un BGM
    # très silencieux ou très dense ne change brutalement le rapport voix/musique.
    result = _normalize_rms_stereo(result, target_db=-25.0)
    return _normalize_peak_stereo(result, BGM_PEAK_DB)


def _loop_with_crossfades(audio: np.ndarray, target_samples: int,
                          crossfade_s: float = 0.25) -> np.ndarray:
    """Boucle une piste sans clic ni rupture de phase trop brutale."""
    if len(audio) >= target_samples:
        return audio[:target_samples].copy()

    result = np.zeros((target_samples, 2), dtype=np.float32)
    position = 0
    crossfade_samples = int(crossfade_s * AUDIO_SAMPLE_RATE)
    first = min(len(audio), target_samples)
    result[:first] = audio[:first]
    position = first

    while position < target_samples and len(audio) > 0:
        overlap = min(crossfade_samples, position, len(audio), target_samples - position)
        if overlap > 0:
            fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)[:, None]
            fade_in = np.linspace(0.0, 1.0, overlap, dtype=np.float32)[:, None]
            result[position - overlap:position] = (
                result[position - overlap:position] * fade_out
                + audio[:overlap] * fade_in
            )
        start = overlap
        available = min(len(audio) - start, target_samples - position)
        if available <= 0:
            break
        result[position:position + available] = audio[start:start + available]
        position += available

    return result


def _synth_bgm_loop(duration: float) -> np.ndarray:
    """Boucle synthétique discrète (pads doux) pour les tests sans BGM."""
    rng = np.random.default_rng(42)
    n = int(duration * AUDIO_SAMPLE_RATE)
    t = np.arange(n) / AUDIO_SAMPLE_RATE
    # Trois pads en baisse très lente
    pad = (
        0.15 * np.sin(2.0 * np.pi * 110.0 * t) *
        np.exp(-t / 30.0) +
        0.10 * np.sin(2.0 * np.pi * 165.0 * t) +
        0.08 * np.sin(2.0 * np.pi * 220.0 * t)
    )
    # Léger mouvement de filtre
    lfo = 0.5 + 0.5 * np.sin(2.0 * np.pi * 0.05 * t)
    pad = pad * lfo
    stereo = np.column_stack([pad, pad]).astype(np.float32)
    return stereo


# --------------------------------------------------------------------------- #
# Mix final
# --------------------------------------------------------------------------- #

def mix_audio(voice_audio: np.ndarray, sfx_bus: np.ndarray, bgm_audio: np.ndarray,
              duration: float, word_times: list[tuple[float, float]] | None = None) -> Path:
    """Mélange voix + SFX + BGM, écrit mix.wav, retourne le chemin."""
    n = int(duration * AUDIO_SAMPLE_RATE)

    def pad_or_truncate(audio: np.ndarray) -> np.ndarray:
        if len(audio) >= n:
            return audio[:n].copy()
        out = np.zeros((n, 2), dtype=np.float32)
        out[:len(audio)] = audio
        return out

    voice = _process_voice(pad_or_truncate(voice_audio))
    sfx = pad_or_truncate(sfx_bus)
    if word_times:
        sfx *= compute_sfx_duck_envelope(duration, word_times)[:, None]
    bgm = pad_or_truncate(bgm_audio)

    mix = voice + bgm + sfx
    # Réduction de gain globale seulement si la somme dépasse le headroom.
    # La limitation finale est ensuite effectuée par FFmpeg/loudnorm.
    peak = float(np.max(np.abs(mix)))
    if peak > 0.98:
        mix *= np.float32(0.98 / peak)
    mix = np.clip(mix, -1.0, 1.0).astype(np.float32)

    with tempfile.NamedTemporaryFile(prefix="reelforge_mix_", suffix=".wav", delete=False) as tmp:
        mix_path = Path(tmp.name)
    wavfile.write(str(mix_path), AUDIO_SAMPLE_RATE, mix)
    return mix_path
