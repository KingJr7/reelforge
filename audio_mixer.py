"""Mixage audio : voix, BGM avec ducking, bus SFX, écriture de mix.wav."""
from __future__ import annotations

import hashlib
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
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

    # Répète/coupe pour couvrir la durée
    n_target = int(duration * AUDIO_SAMPLE_RATE)
    if len(audio) == 0:
        return np.zeros((n_target, 2), dtype=np.float32)

    if len(audio) >= n_target:
        audio = audio[:n_target]
    else:
        repeats = math.ceil(n_target / len(audio))
        audio = np.tile(audio, (repeats, 1))[:n_target]

    # Fondu d'entrée 1 s, sortie 1.5 s
    fade_in = int(1.0 * AUDIO_SAMPLE_RATE)
    fade_out = int(1.5 * AUDIO_SAMPLE_RATE)
    env = np.ones(n_target, dtype=np.float32)
    if fade_in > 0:
        env[:fade_in] = np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    if fade_out > 0:
        env[-fade_out:] = np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
    result = audio.copy()
    result[:, 0] *= env
    result[:, 1] *= env

    # Normalise à -10 dBFS de crête
    return _normalize_peak_stereo(result, BGM_PEAK_DB)


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
              duration: float) -> Path:
    """Mélange voix + SFX + BGM, écrit mix.wav, retourne le chemin."""
    n = int(duration * AUDIO_SAMPLE_RATE)

    def pad_or_truncate(audio: np.ndarray) -> np.ndarray:
        if len(audio) >= n:
            return audio[:n].copy()
        out = np.zeros((n, 2), dtype=np.float32)
        out[:len(audio)] = audio
        return out

    voice = pad_or_truncate(voice_audio)
    sfx = pad_or_truncate(sfx_bus)
    bgm = pad_or_truncate(bgm_audio)

    mix = voice + bgm + sfx
    # Limite douce pour éviter le clipping avant loudnorm
    mix = np.tanh(mix * 0.95) * 0.95
    mix = np.clip(mix, -1.0, 1.0).astype(np.float32)

    mix_path = Path(tempfile.gettempdir()) / "reelforge_mix.wav"
    wavfile.write(str(mix_path), AUDIO_SAMPLE_RATE, mix)
    return mix_path
