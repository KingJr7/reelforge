"""Vérification automatique de la vidéo finale : résolution, fps, codec, durée,
frames identiques, bascule claire/sombre, loudness, planche contact."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from audio_mixer import measure_audio_stats


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout + res.stderr


def probe(video: Path) -> dict:
    """Retourne les infos du flux vidéo via ffprobe."""
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,duration",
        "-of", "json", str(video),
    ])
    import json as _json
    return _json.loads(out)["streams"][0]


def probe_audio(video: Path) -> dict:
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,duration",
        "-of", "json", str(video),
    ])
    import json as _json
    return _json.loads(out)["streams"][0]


def load_audio_float(path: Path) -> np.ndarray:
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
        "-acodec", "pcm_f32le", "-ar", "48000", "-ac", "2", "-",
    ], capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.float32).reshape(-1, 2)


def check_audio_buses(bus_paths: dict[str, Path]) -> bool:
    """Contrôle séparé des bus exportés par make_reel."""
    ok = True
    for name, path in bus_paths.items():
        if not path.exists():
            print(f"  [AUDIO] {name}: absent ({path}) -> SKIP")
            continue
        stats = measure_audio_stats(load_audio_float(path))
        bus_ok = np.isfinite(list(stats.values())).all() and stats["peak_db"] <= 0.1
        ok = ok and bool(bus_ok)
        print(
            f"  [AUDIO] {name}: RMS {stats['rms_db']:.1f} dB, "
            f"peak {stats['peak_db']:.1f} dB, crest {stats['crest_db']:.1f} dB: "
            f"{'PASS' if bus_ok else 'FAIL'}"
        )
    return ok


def check_resolution_fps_codec(video: Path, preview: bool) -> bool:
    """Test 1 : résolution, 30 fps, h264."""
    s = probe(video)
    w, h = s["width"], s["height"]
    exp_w, exp_h = (540, 960) if preview else (1080, 1920)
    ok_res = (w, h) == (exp_w, exp_h)

    # r_frame_rate est "30/1"
    fps_str = s.get("r_frame_rate", "0/1")
    num, den = fps_str.split("/")
    fps = float(num) / float(den) if den != "0" else 0
    ok_fps = abs(fps - 30.0) < 0.01

    ok_codec = s.get("codec_name") == "h264"

    print(f"  [1] Résolution {w}x{h} (attendu {exp_w}x{exp_h}): {'PASS' if ok_res else 'FAIL'}")
    print(f"  [1] FPS {fps:.2f} (attendu 30): {'PASS' if ok_fps else 'FAIL'}")
    print(f"  [1] Codec {s.get('codec_name')} (attendu h264): {'PASS' if ok_codec else 'FAIL'}")
    return ok_res and ok_fps and ok_codec


def check_duration(video: Path, timeline: dict) -> bool:
    """Test 1 (suite) : durée = durée audio ± 0.1 s."""
    v = probe(video)
    a = probe_audio(video)
    v_dur = float(v.get("duration", 0))
    a_dur = float(a.get("duration", 0))
    tl_dur = timeline.get("duration", 0)
    ok = abs(v_dur - a_dur) < 0.1 and abs(v_dur - tl_dur) < 0.1
    print(f"  [1] Durée vidéo {v_dur:.2f}s ≈ audio {a_dur:.2f}s ≈ timeline {tl_dur:.2f}s: {'PASS' if ok else 'FAIL'}")
    return ok


def check_no_static_frames(video: Path, preview: bool) -> bool:
    """Test 2 : pas plus de 3 frames identiques consécutives."""
    w, h = (540, 960) if preview else (1080, 1920)
    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    )
    raw = res.stdout
    frame_size = w * h * 3
    n_frames = len(raw) // frame_size
    frames = np.frombuffer(raw[: n_frames * frame_size], dtype=np.uint8).reshape(n_frames, h, w, 3)

    max_identical = 1
    cur = 1
    for i in range(1, n_frames):
        if np.array_equal(frames[i], frames[i - 1]):
            cur += 1
            max_identical = max(max_identical, cur)
        else:
            cur = 1

    ok = max_identical <= 3
    print(f"  [2] Max frames identiques consécutives : {max_identical} (max 3): {'PASS' if ok else 'FAIL'}")
    return ok


def check_safe_zones(video: Path, preview: bool) -> bool:
    """Détecte une forte densité de contours dans les bandes de chrome plateforme."""
    width, height = (540, 960) if preview else (1080, 1920)
    small_w, small_h = width // 4, height // 4
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(video), "-vf",
        f"fps=2,scale={small_w}:{small_h},format=gray", "-f", "rawvideo", "-",
    ], capture_output=True, check=True)
    frame_size = small_w * small_h
    frames = np.frombuffer(result.stdout, dtype=np.uint8)
    if len(frames) < frame_size:
        print("  [SAFE] Frames insuffisantes -> SKIP")
        return True
    frames = frames[: len(frames) // frame_size * frame_size].reshape(-1, small_h, small_w)
    risks = {}
    bands = {
        "top_chrome": (slice(0, int(small_h * 0.08)), slice(None)),
        "bottom_chrome": (slice(int(small_h * 0.90), None), slice(None)),
        "left_chrome": (slice(None), slice(0, int(small_w * 0.04))),
        "right_chrome": (slice(None), slice(int(small_w * 0.96), None)),
    }
    for name, (ys, xs) in bands.items():
        band = frames[:, ys, xs].astype(np.int16)
        edges = np.abs(np.diff(band, axis=-1)) > 32 if band.shape[-1] > 1 else np.zeros_like(band, dtype=bool)
        risks[name] = float(edges.mean())
    ok = max(risks.values()) < 0.28
    details = ", ".join(f"{name}={value:.2f}" for name, value in risks.items())
    print(f"  [SAFE] {details}: {'PASS' if ok else 'WARN'}")
    return ok


def check_inversion(video: Path, timeline: dict, preview: bool) -> bool:
    """Test 3 : fond clair avant inversion, sombre après."""
    inv = timeline.get("invert")
    if inv is None:
        print("  [3] Pas d'inversion dans la timeline : PASS (non testé)")
        return True

    w, h = (540, 960) if preview else (1080, 1920)
    t_inv = inv["t"]
    f_inv = int(round(t_inv * 30))

    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    )
    raw = res.stdout
    frame_size = w * h * 3
    n_frames = len(raw) // frame_size

    if f_inv >= n_frames:
        print(f"  [3] Frame d'inversion {f_inv} hors vidéo ({n_frames} frames): FAIL")
        return False

    # Prend quelques frames avant et après
    def avg_brightness(idx: int) -> float:
        offset = idx * frame_size
        f = np.frombuffer(raw[offset:offset + frame_size], dtype=np.uint8).reshape(h, w, 3)
        return float(f.mean())

    # Avant : frame f_inv - 2 (si existe)
    f_before = max(0, f_inv - 2)
    f_after = min(n_frames - 1, f_inv + 2)

    b_before = avg_brightness(f_before)
    b_after = avg_brightness(f_after)

    ok = b_before > 100 and b_after < 150  # clair avant, sombre après
    print(f"  [3] Luminosité avant {b_before:.1f} / après {b_after:.1f} (inversion frame {f_inv}): {'PASS' if ok else 'FAIL'}")
    return ok


def check_loudness(video: Path, target_lufs: float) -> bool:
    """Test 4 : loudness via ebur128."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video),
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    output = res.stderr

    integrated = None
    true_peak = None

    # Parse les dernières lignes ebur128 qui contiennent I: (intégré) et TPK: (true peak)
    for line in output.splitlines():
        if "I:" in line and "LUFS" in line:
            # Format: ... I: -XX.X LUFS ...
            parts = line.split("I:")
            if len(parts) >= 2:
                after = parts[1].strip()
                # " -XX.X LUFS       LRA: ..."
                val_str = after.split("LUFS")[0].strip()
                try:
                    integrated = float(val_str)
                except ValueError:
                    pass
        if "TPK:" in line:
            parts = line.split("TPK:")
            if len(parts) >= 2:
                after = parts[1].strip()
                val_str = after.split()[0] if after.split() else ""
                try:
                    true_peak = float(val_str)
                except ValueError:
                    pass

    ok_lufs = integrated is not None and abs(integrated - target_lufs) <= 1.0
    ok_tp = true_peak is not None and true_peak <= -1.0

    print(f"  [4] Loudness intégrée {integrated if integrated is not None else 'N/A'} LUFS (cible {target_lufs} ± 1): {'PASS' if ok_lufs else 'FAIL'}")
    print(f"  [4] True Peak {true_peak if true_peak is not None else 'N/A'} dBTP (≤ -1): {'PASS' if ok_tp else 'FAIL'}")
    return ok_lufs and ok_tp


def make_contact_sheet(video: Path, out_path: Path) -> None:
    """Test 5 : planche contact 1 image/seconde, 8 colonnes."""
    import tempfile

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    w, h = map(int, res.stdout.strip().split(","))

    # Extrait 1 frame par seconde vers des fichiers temporaires (plus fiable que le pipe)
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video),
             "-vf", "fps=1,scale=160:288",
             str(td_path / "f%03d.png")],
            capture_output=True,
        )
        files = sorted(td_path.glob("f*.png"))
        n_frames = len(files)

        cols = 8
        rows = max(1, (n_frames + cols - 1) // cols)
        sheet = Image.new("RGB", (160 * cols, 288 * rows), (255, 255, 255))

        for i, fp in enumerate(files):
            img = Image.open(fp).convert("RGB")
            img = img.resize((160, 288))
            r = i // cols
            c = i % cols
            sheet.paste(img, (c * 160, r * 288))

        sheet.save(str(out_path))
        print(f"  [5] Planche contact : {out_path} ({n_frames} frames, {cols}x{rows})")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Vérifie la vidéo finale de reelforge")
    p.add_argument("video", help="Fichier MP4 à vérifier")
    p.add_argument("--timeline", default=None, help="Fichier timeline.json")
    p.add_argument("--lufs", type=float, default=-14.0, help="Cible loudness")
    p.add_argument("--voice", default=None, help="Bus voix WAV exporté")
    p.add_argument("--bgm", default=None, help="Bus BGM WAV exporté")
    p.add_argument("--sfx", default=None, help="Bus SFX WAV exporté")
    p.add_argument("--safe-zones", action="store_true", help="Active l'analyse des zones à risque")
    args = p.parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"ERREUR : vidéo introuvable : {video}", file=sys.stderr)
        sys.exit(1)

    preview = video.stat().st_size > 0  # hint : on détermine preview par la résolution
    # Détermine preview via la résolution
    s = probe(video)
    preview = (s["width"], s["height"]) == (540, 960)

    timeline = {}
    if args.timeline:
        tl_path = Path(args.timeline)
        if tl_path.exists():
            with open(tl_path) as f:
                timeline = json.load(f)

    results = []

    r1 = check_resolution_fps_codec(video, preview)
    results.append(r1)

    r1b = check_duration(video, timeline)
    results.append(r1b)

    r2 = check_no_static_frames(video, preview)
    results.append(r2)

    r3 = check_inversion(video, timeline, preview)
    results.append(r3)

    r4 = check_loudness(video, args.lufs)
    results.append(r4)

    if any((args.voice, args.bgm, args.sfx)):
        buses = {name: Path(value) for name, value in {
            "voice": args.voice, "bgm": args.bgm, "sfx": args.sfx,
        }.items() if value}
        results.append(check_audio_buses(buses))

    if args.safe_zones:
        results.append(check_safe_zones(video, preview))

    make_contact_sheet(video, video.parent / "contact_sheet.png")

    print()
    if all(results):
        print("=== RÉSULTAT GLOBAL : PASS ===")
        sys.exit(0)
    else:
        print("=== RÉSULTAT GLOBAL : FAIL ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
