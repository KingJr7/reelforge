"""Client AssemblyAI : transcription d'un fichier audio avec timestamps mots."""
from __future__ import annotations

import time
from pathlib import Path

import requests

BASE = "https://api.assemblyai.com/v2"


def transcribe_words(audio_path: str | Path, api_key: str,
                     poll_interval: float = 2.0, timeout_s: float = 120.0):
    """Retourne une liste de (start_sec, end_sec, word) triée par start."""
    audio_path = str(audio_path)
    headers = {"authorization": api_key}

    # 1. Upload
    with open(audio_path, "rb") as f:
        resp = requests.post(f"{BASE}/upload", headers=headers,
                             data=f, timeout=60)
    resp.raise_for_status()
    upload_url = resp.json()["upload_url"]

    # 2. Soumettre la transcription avec word timestamps
    resp = requests.post(f"{BASE}/transcript", headers=headers, json={
        "audio_url": upload_url,
        "word_boost": [],
        "disfluencies": False,
    }, timeout=60)
    resp.raise_for_status()
    transcript_id = resp.json()["id"]

    # 3. Poller jusqu'à completion
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(f"{BASE}/transcript/{transcript_id}",
                            headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "completed":
            break
        if status in ("error", "failed"):
            raise RuntimeError(f"AssemblyAI error: {data.get('error')}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError("AssemblyAI transcription timeout")

    # 4. Extraire les mots avec timestamps (ms -> s)
    words = data.get("words") or []
    result = []
    for w in words:
        start = w.get("start", 0) / 1000.0
        end = w.get("end", 0) / 1000.0
        text = (w.get("text") or "").strip()
        if text:
            result.append((start, end, text))
    return result
