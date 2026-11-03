"""Client Pexels : recherche et téléchargement de B-rolls (photos et vidéos) avec cache."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from config import (
    BROLL_CACHE_DIR, PEXELS_API_KEY, PEXELS_REQUEST_DELAY,
)


def sha1_hash(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def search_photo(query: str) -> str | None:
    """Recherche une photo portrait sur Pexels. Retourne l'URL de l'image ou None."""
    if not PEXELS_API_KEY:
        return None

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "orientation": "portrait", "per_page": 15}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None

    data = resp.json()
    photos = data.get("photos", [])
    for photo in photos:
        src = photo.get("src", {})
        url_img = src.get("portrait") or src.get("large2x")
        if url_img:
            return url_img
    return None


def search_video(query: str, min_duration: float = 0.0) -> str | None:
    """Recherche une vidéo portrait sur Pexels. Retourne l'URL du fichier MP4 ou None."""
    if not PEXELS_API_KEY:
        return None

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "orientation": "portrait", "per_page": 15, "size": "medium"}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None

    data = resp.json()
    videos = data.get("videos", [])
    for video in videos:
        video_files = video.get("video_files", [])
        # Choisit le fichier MP4 dont la largeur est la plus proche de 720 et <= 1080
        best = None
        best_diff = float("inf")
        for vf in video_files:
            if vf.get("file_type") != "video/mp4":
                continue
            vw = vf.get("width", 0)
            vh = vf.get("height", 0)
            vdur = vf.get("duration") or 0
            if vw > 1080:
                continue
            if min_duration is not None and min_duration > 0 and vdur < min_duration:
                continue
            diff = abs(vw - 720)
            if diff < best_diff:
                best_diff = diff
                best = vf.get("link")
        if best:
            return best
    return None


def download_broll(
    source: str,
    kind: str = "photo",
    size: str = "medium",
    used_urls: set[str] | None = None,
) -> str | None:
    """Télécharge un B-roll depuis Pexels ou un fichier local.

    Retourne le chemin du fichier cached, ou None en cas d'échec.
    """
    used_urls = used_urls or set()

    # Fichier local
    path = Path(source)
    if path.exists():
        return str(path)

    # Requête Pexels
    if not PEXELS_API_KEY:
        return None

    # Cache par hash de la requête
    cache_key = sha1_hash(source, kind, size)
    ext = ".mp4" if kind == "video" else ".jpg"
    cache_path = BROLL_CACHE_DIR / f"{cache_key}{ext}"

    if cache_path.exists():
        return str(cache_path)

    # Recherche (évite les URLs déjà utilisées)
    query = source
    attempts = 0
    while attempts < 15:
        if kind == "video":
            url = search_video(query, min_duration=0)
        else:
            url = search_photo(query)

        if url is None:
            # Retente avec les 2 premiers mots
            words = query.split()
            if len(words) > 2:
                query = " ".join(words[:2])
                attempts += 1
                time.sleep(PEXELS_REQUEST_DELAY)
                continue
            return None

        if url in used_urls:
            # URL déjà utilisée, essaye le résultat suivant (pas possible avec l'API simple)
            # On tente une requête légèrement modifiée
            query = query + " broll"
            attempts += 1
            time.sleep(PEXELS_REQUEST_DELAY)
            continue

        break

    if url is None or url in used_urls:
        return None

    used_urls.add(url)

    # Téléchargement
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        BROLL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(resp.content)
        time.sleep(PEXELS_REQUEST_DELAY)
        return str(cache_path)
    except Exception:
        return None
