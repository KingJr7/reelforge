"""Client ElevenLabs : voix + alignement mot par mot avec cache disque."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import requests

from config import (
    AUDIO_SAMPLE_RATE, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
    ELEVENLABS_MODEL_ID, ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST,
    ELEVENLABS_STYLE, ELEVENLABS_SPEED, VOICE_CACHE_DIR,
)
from audio_mixer import decode_voice


def sha1_hash(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def list_voices() -> list[dict]:
    """Liste les voix ElevenLabs disponibles."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY manquante dans .env")

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    voices = data.get("voices", [])
    result = []
    for v in voices:
        labels = v.get("labels", {})
        result.append({
            "name": v.get("name", "?"),
            "voice_id": v.get("voice_id", "?"),
            "language": labels.get("language", "?"),
        })
    return result


def generate_voice(
    script_text: str,
    voice_id: str,
    model_id: str | None = None,
    force: bool = False,
) -> tuple[Path, float, list[tuple[float, float]]]:
    """Génère la voix via ElevenLabs avec cache.

    Retourne (chemin_mp3, durée_secondes, word_times) où word_times est
    la liste des (start, end) pour chaque mot du script.
    """
    model_id = model_id or ELEVENLABS_MODEL_ID
    VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    settings = f"s{ELEVENLABS_STABILITY}_b{ELEVENLABS_SIMILARITY_BOOST}_st{ELEVENLABS_STYLE}_sp{ELEVENLABS_SPEED}"
    cache_key = sha1_hash(script_text, voice_id, model_id, settings)
    mp3_path = VOICE_CACHE_DIR / f"{cache_key}.mp3"
    json_path = VOICE_CACHE_DIR / f"{cache_key}.json"

    if mp3_path.exists() and json_path.exists() and not force:
        from script_parser import parse_script
        parsed = parse_script(script_text)
        audio = decode_voice(mp3_path)
        duration = len(audio) / AUDIO_SAMPLE_RATE
        with open(json_path) as f:
            align = json.load(f)
        word_times = _alignment_to_word_times(align)
        if len(word_times) != len(parsed.words):
            raise RuntimeError(
                f"Désalignement cache: {len(word_times)} mots alignés vs {len(parsed.words)} mots script"
            )
        return mp3_path, duration, word_times

    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY manquante dans .env")
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID manquant. Utilisez --list-voices pour choisir une voix.")

    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        f"?output_format=mp3_44100_128"
    )
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": script_text,
        "model_id": model_id,
        "voice_settings": {
            "stability": ELEVENLABS_STABILITY,
            "similarity_boost": ELEVENLABS_SIMILARITY_BOOST,
            "style": ELEVENLABS_STYLE,
            "speed": ELEVENLABS_SPEED,
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    audio_b64 = data.get("audio_base64")
    if audio_b64 is None:
        raise RuntimeError(f"Champ 'audio_base64' absent. Clés reçues: {list(data.keys())}")

    audio_bytes = base64.b64decode(audio_b64)
    with open(mp3_path, "wb") as f:
        f.write(audio_bytes)

    align = data.get("alignment")
    if align is None:
        raise RuntimeError(f"Champ 'alignment' absent. Clés reçues: {list(data.keys())}")

    with open(json_path, "w") as f:
        json.dump(align, f)

    audio = decode_voice(mp3_path)
    duration = len(audio) / AUDIO_SAMPLE_RATE

    word_times = _alignment_to_word_times(align)

    # Contrôle (warning uniquement : ElevenLabs peut segmenter différemment du parser)
    from script_parser import parse_script
    parsed = parse_script(script_text)
    n_script = len(parsed.words)
    n_align = len(word_times)
    if n_script != n_align:
        print(f"ATTENTION : désalignement mots script ({n_script}) vs alignment ({n_align}), on garde les timestamps ElevenLabs", file=sys.stderr)

    return mp3_path, duration, word_times


def _alignment_to_word_times(align: dict) -> list[tuple[float, float]]:
    """Convertit l'alignement ElevenLabs (caracteres) en temps par mot."""
    chars = align.get("characters", [])
    starts = align.get("character_start_times_seconds", [])
    ends = align.get("character_end_times_seconds", [])

    if not chars:
        return []

    word_times: list[tuple[float, float]] = []
    i = 0
    n = len(chars)
    while i < n:
        if chars[i] == "<":
            while i < n and chars[i] != ">":
                i += 1
            i += 1
            continue

        word_start = starts[i] if i < len(starts) else 0.0
        word_end = word_start

        while i < n and chars[i] != " " and chars[i] != "<":
            word_end = ends[i] if i < len(ends) else word_end
            i += 1

        if word_end > word_start:
            word_times.append((word_start, word_end))

        if i < n and chars[i] == " ":
            i += 1

    return word_times
