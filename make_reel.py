"""CLI + orchestration : parse le script, génère la voix, construit la timeline,
mixe l'audio, rend la vidéo frame par frame."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import numpy as np
from scipy.io import wavfile

from config import (
    ROOT, OUT_DIR, CACHE_DIR, VOICE_CACHE_DIR, BROLL_CACHE_DIR, FPS,
    DEFAULT_WIDTH, DEFAULT_HEIGHT, PREVIEW_WIDTH, PREVIEW_HEIGHT,
    DEFAULT_INVERT_AT, GLITCH_FRAMES_DEFAULT, DUCK_DB_DEFAULT,
    SEED, ensure_dirs, AUDIO_SAMPLE_RATE,
)
from script_parser import parse_script
from timeline import build_timeline, export_timeline
from audio_mixer import (
    synth_demo_voice, decode_voice, decode_voice_wav, load_bgm, compute_duck_envelope,
    apply_ducking, mix_audio,
)
from sfx import build_sfx_bus
from renderer import render_timeline
from html_motion_renderer import render_html_motion
from hybrid_test import run_hybrid, _editorial_from_timeline
from elevenlabs_client import generate_voice as generate_voice_elevenlabs, list_voices as list_voices_elevenlabs
from pexels_client import download_broll
from assemblyai_client import transcribe_words


def check_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print(f"ERREUR : {tool} introuvable. Installez FFmpeg (sudo apt install ffmpeg ou brew install ffmpeg).", file=sys.stderr)
            sys.exit(1)


def detect_nvenc() -> bool:
    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True)
        return "h264_nvenc" in res.stdout
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="reelforge - moteur de montage vidéo programmatique")
    p.add_argument("--script", required=False, help="Chemin du fichier script annoté")
    p.add_argument("--out", default="out/reel.mp4", help="Fichier MP4 de sortie")
    p.add_argument("--bgm", default=None, help="Chemin du fichier musique de fond (optionnel)")
    p.add_argument("--flow", choices=["sweep", "mirror"], default="sweep")
    p.add_argument("--invert-at", type=float, default=None)
    p.add_argument("--lufs", type=float, default=-14.0)
    p.add_argument("--glitch-frames", type=int, default=GLITCH_FRAMES_DEFAULT)
    p.add_argument("--motion-style", choices=["premium", "energetic", "minimal"], default="premium")
    p.add_argument("--transition", choices=["glitch", "flash", "wipe", "zoom", "blur", "clean"], default="glitch")
    p.add_argument("--engine", choices=["classic", "html", "hybrid"], default="classic",
                   help="Backend visuel : classic (défaut), html frame-driven ou hybrid")
    p.add_argument("--html-template", choices=["auto", "hero", "numbers", "split", "cta", "diagram", "comparison", "broll"], default="auto",
                   help="Template de scène (auto ou variante) pour les backends html/hybrid")
    p.add_argument("--scene-plan", default=None,
                   help="Plan JSON utilisateur pour choisir les scènes HTML/classic")
    p.add_argument("--duck-db", type=float, default=DUCK_DB_DEFAULT)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--keep-temp", action="store_true")
    p.add_argument("--export-audio-buses", action="store_true",
                   help="Exporte voice/bgm/sfx WAV séparés pour analyse")
    p.add_argument("--force-voice", action="store_true")
    p.add_argument("--list-voices", action="store_true")
    p.add_argument("--nvenc", action="store_true")
    p.add_argument("--voice-file", default=None, help="Fichier MP3 de voix pré-généré (écrase ElevenLabs)")
    p.add_argument("--tts", choices=["elevenlabs", "pocket-tts"], default="elevenlabs", help="Moteur de synthèse vocale (défaut: elevenlabs)")
    p.add_argument("--assemblyai", action="store_true", help="Utiliser AssemblyAI pour les vrais timestamps des mots")
    p.add_argument("--auto-broll", action="store_true", help="Insère automatiquement des B-rolls dans les gaps sans carte")
    return p


def main() -> None:
    try:
        _main()
    except Exception as e:
        print(f"FATAL ERROR in main: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

def _main() -> None:
    load_dotenv()
    ensure_dirs()
    check_ffmpeg()

    print("DEBUG: Starting _main()", flush=True)

    parser = build_parser()
    args = parser.parse_args()
    print(f"DEBUG: args parsed, script={args.script}", flush=True)

    if args.list_voices:
        try:
            voices = list_voices_elevenlabs()
            print(f"\n{len(voices)} voix disponibles :\n")
            for v in voices:
                print(f"  {v['name']:30s} id={v['voice_id']:20s} lang={v['language']}")
            print()
        except RuntimeError as e:
            print(f"ERREUR : {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.script:
        print("ERREUR : --script est requis (sauf avec --list-voices).", file=sys.stderr)
        sys.exit(1)

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERREUR : script introuvable : {script_path}", file=sys.stderr)
        sys.exit(1)

    script_text = script_path.read_text(encoding="utf-8")
    nvenc_available = detect_nvenc() if args.nvenc else False
    if args.nvenc and not nvenc_available:
        print("AVERTISSEMENT : --nvenc demandé mais h264_nvenc non disponible, utilisation de libx264.")

    width = PREVIEW_WIDTH if args.preview else DEFAULT_WIDTH
    height = PREVIEW_HEIGHT if args.preview else DEFAULT_HEIGHT

    print(f"reelforge - {'démo' if args.demo else 'production'} - {width}x{height} @ {FPS} fps")
    print(f"  Script : {script_path}")
    print(f"  Sortie : {args.out}")

    # 1. Parse du script
    parsed = parse_script(script_text)
    print(f"  {len(parsed.words)} mots parsés, {len(parsed.markers)} marqueurs")

    # 2. Télécharge les B-rolls (mode production uniquement)
    used_urls: set[str] = set()
    broll_paths: list[str | None] = []
    if not args.demo:
        for m in parsed.markers:
            if m.kind == "broll":
                kind = "video" if " video" in m.value else "photo"
                size = "medium"
                for part in m.value.split("|"):
                    part = part.strip()
                    if part in ("small", "medium", "large"):
                        size = part
                print(f"  Téléchargement B-roll: {m.value[:60]}...")
                path = download_broll(m.value.split("|")[0].strip(), kind=kind, size=size, used_urls=used_urls)
                broll_paths.append(path)
                if path:
                    print(f"    -> {path}")
                else:
                    print(f"    -> ÉCHEC (carte de secours utilisée)")

    print("DEBUG: Starting voice generation", flush=True)
    if args.demo:
        pause_total = sum(float(m.value) for m in parsed.markers if m.kind == "pause")
        est_duration = len(parsed.words) / 3.2 + pause_total
        VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        def sha1_hash(*parts):
            h = hashlib.sha1()
            for p in parts:
                h.update(p.encode("utf-8"))
                h.update(b"\x00")
            return h.hexdigest()

        cache_key = sha1_hash(script_text, "demo", "demo")
        wav_path = VOICE_CACHE_DIR / f"{cache_key}.wav"
        if wav_path.exists():
            audio, sr = decode_voice_wav(wav_path)
            voice_duration = len(audio) / sr
            word_times = []
            t = 0.0
            word_dur = 0.25
            gap = 1.0 / 3.2 - word_dur
            for _ in parsed.words:
                if t >= voice_duration:
                    break
                end = min(t + word_dur, voice_duration)
                word_times.append((t, end))
                t = end + gap
        else:
            audio_demo, word_times = synth_demo_voice(parsed.words, est_duration)
            wavfile.write(str(wav_path), AUDIO_SAMPLE_RATE, audio_demo)
            voice_duration = len(audio_demo) / AUDIO_SAMPLE_RATE
        voice_path = wav_path
    elif args.voice_file:
        vp = Path(args.voice_file)
        if not vp.exists():
            print(f"ERREUR : fichier voix introuvable : {vp}", file=sys.stderr)
            sys.exit(1)
        audio = decode_voice(vp)
        voice_duration = len(audio) / AUDIO_SAMPLE_RATE
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        word_times = []
        if args.assemblyai and api_key:
            try:
                print("  Transcription AssemblyAI (vrais timestamps des mots)...")
                aa_words = transcribe_words(vp, api_key)
                n_words = len(parsed.words)
                n_aa = len(aa_words)
                if n_aa > 0 and n_words > 0:
                    # Alignement séquentiel par contenu des mots (nettoyés)
                    import re as _re

                    def _clean(w: str) -> str:
                        return _re.sub(r"[^\wàâäéèêëîïôöùûüçñ]", "", w.lower())

                    script_clean = [_clean(w.text) for w in parsed.words]
                    aa_clean = [_clean(t) for _, _, t in aa_words]

                    word_times = []
                    j = 0
                    for i in range(n_words):
                        # Avance j jusqu'à trouver un mot AA qui correspond ou dépasse
                        while j < n_aa and aa_clean[j] and aa_clean[j] != script_clean[i]:
                            j += 1
                        if j < n_aa and aa_clean[j] == script_clean[i]:
                            start, end, _t = aa_words[j]
                            word_times.append((start, end))
                            j += 1
                        else:
                            # Pas de correspondance : interpolation sur la durée restante
                            remaining_words = n_words - i
                            remaining_aa = max(n_aa - j, 1)
                            slot = (voice_duration - (word_times[-1][1] if word_times else 0)) / remaining_words if word_times else voice_duration / n_words
                            start = word_times[-1][1] if word_times else 0.0
                            end = min(start + slot, voice_duration)
                            word_times.append((start, end))
                    print(f"  AssemblyAI : {n_aa} mots détectés, alignés sur {n_words} mots du script")
                else:
                    raise ValueError("AssemblyAI a retourné 0 mots")
            except Exception as e:
                print(f"  AssemblyAI échec ({e}), fallback division égale", file=sys.stderr)
                n_words = len(parsed.words)
                word_times = []
                if n_words > 0:
                    slot = voice_duration / n_words
                    for i in range(n_words):
                        start = i * slot
                        end = min((i + 1) * slot, voice_duration)
                        word_times.append((start, end))
        else:
            n_words = len(parsed.words)
            word_times = []
            if n_words > 0:
                slot = voice_duration / n_words
                for i in range(n_words):
                    start = i * slot
                    end = min((i + 1) * slot, voice_duration)
                    word_times.append((start, end))
        # Sauvegarde en WAV pour cohérence du pipeline
        wavfile.write(str(VOICE_CACHE_DIR / "voice_file_input.wav"), AUDIO_SAMPLE_RATE, audio)
        voice_path = VOICE_CACHE_DIR / "voice_file_input.wav"
        print(f"  Voix importée : {voice_duration:.2f}s, {len(word_times)} mots avec timestamps")
    elif args.tts == "pocket-tts":
        print("DEBUG: Calling generate_voice_pocket_tts", flush=True)
        voice_duration, word_times = generate_voice_pocket_tts(script_text, parsed.words, args.assemblyai)
        print(f"DEBUG: generate_voice_pocket_tts returned", flush=True)
        print(f"  Voix Pocket-TTS : {voice_duration:.2f}s, {len(word_times)} mots avec timestamps")
    else:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        try:
            voice_path, voice_duration, word_times = generate_voice_elevenlabs(
                script_text, voice_id, model_id, args.force_voice)
        except RuntimeError as e:
            print(f"ERREUR : {e}", file=sys.stderr)
            sys.exit(1)

        # Ré-alignement AssemblyAI si demandé (vrais timestamps, contournement du désalignement ElevenLabs)
        if args.assemblyai:
            api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
            if api_key:
                try:
                    import re as _re

                    print("  Ré-alignement AssemblyAI sur la voix ElevenLabs...")
                    aa_words = transcribe_words(voice_path, api_key)
                    n_words = len(parsed.words)
                    n_aa = len(aa_words)
                    if n_aa > 0 and n_words > 0:

                        def _clean(w: str) -> str:
                            return _re.sub(r"[^\wàâäéèêëîïôöùûüçñ]", "", w.lower())

                        script_clean = [_clean(w.text) for w in parsed.words]
                        aa_clean = [_clean(t) for _, _, t in aa_words]

                        new_word_times = []
                        j = 0
                        for i in range(n_words):
                            while j < n_aa and aa_clean[j] and aa_clean[j] != script_clean[i]:
                                j += 1
                            if j < n_aa and aa_clean[j] == script_clean[i]:
                                start, end, _t = aa_words[j]
                                new_word_times.append((start, end))
                                j += 1
                            else:
                                remaining_words = n_words - i
                                remaining_aa = max(n_aa - j, 1)
                                slot = (voice_duration - (new_word_times[-1][1] if new_word_times else 0)) / remaining_words if new_word_times else voice_duration / n_words
                                start = new_word_times[-1][1] if new_word_times else 0.0
                                end = min(start + slot, voice_duration)
                                new_word_times.append((start, end))
                        word_times = new_word_times
                        print(f"  AssemblyAI : {n_aa} mots détectés, alignés sur {n_words} mots du script")
                except Exception as e:
                    print(f"  AssemblyAI échec ({e}), maintien timestamps ElevenLabs", file=sys.stderr)
            else:
                print("  Clé ASSEMBLYAI_API_KEY manquante, maintien timestamps ElevenLabs", file=sys.stderr)

    print(f"  Voix : {voice_duration:.2f}s, {len(word_times)} mots avec timestamps")

    # 4. Timeline
    print("DEBUG: Building timeline", flush=True)
    invert_at = args.invert_at if args.invert_at is not None else DEFAULT_INVERT_AT
    tl = build_timeline(parsed, word_times, flow_mode=args.flow, invert_at=invert_at)

    # S'assurer que la durée couvre toute la voix (AssemblyAI peut couper avant la fin du fichier audio,
    # surtout quand le dernier segment est le CTA). On se cale sur la vraie durée du fichier vocal.
    tl.duration = max(tl.duration, voice_duration + 0.6)
    tl.frames = math.ceil(tl.duration * FPS)

    # Remplace les sources B-roll dans la timeline par les chemins locaux téléchargés
    broll_idx = 0
    for c in tl.cards:
        if broll_idx < len(broll_paths) and broll_paths[broll_idx] is not None:
            c.source = broll_paths[broll_idx]
        broll_idx += 1

    print(f"  Timeline : {tl.frames} frames, {tl.duration:.2f}s, {len(tl.words)} mots, {len(tl.cards)} cartes")

    if tl.invert:
        print(f"  Inversion à t={tl.invert.t:.2f}s")
    if tl.cta:
        print(f"  CTA '{tl.cta.text}' à t={tl.cta.start:.2f}s")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    timeline_json = out_path.parent / "timeline.json"
    export_timeline(tl, str(timeline_json))
    print(f"  Timeline exportée : {timeline_json}")

    # 5. SFX bus
    print("  Génération du bus SFX...")
    n_audio_samples = int(tl.duration * AUDIO_SAMPLE_RATE)
    sfx_bus = build_sfx_bus(tl.sfx, n_audio_samples)
    print(f"  Bus SFX : {len(tl.sfx)} événements")

    # 6. Mix audio
    print("  Mixage audio...")
    voice_audio = decode_voice(voice_path)
    if args.demo or args.bgm is None:
        bgm_audio = np.zeros((n_audio_samples, 2), dtype=np.float32)
    else:
        bgm_audio = load_bgm(args.bgm, tl.duration)
        gain = compute_duck_envelope(tl.duration, word_times, duck_db=args.duck_db)
        bgm_audio = apply_ducking(bgm_audio, gain)

    mix_path = mix_audio(voice_audio, sfx_bus, bgm_audio, tl.duration, word_times=word_times)
    print(f"  Mix écrit : {mix_path}")

    if args.export_audio_buses:
        bus_base = out_path.with_suffix("")
        bus_files = {
            "voice": bus_base.with_suffix(".voice.wav"),
            "bgm": bus_base.with_suffix(".bgm.wav"),
            "sfx": bus_base.with_suffix(".sfx.wav"),
        }
        wavfile.write(str(bus_files["voice"]), AUDIO_SAMPLE_RATE, voice_audio.astype(np.float32))
        wavfile.write(str(bus_files["bgm"]), AUDIO_SAMPLE_RATE, bgm_audio.astype(np.float32))
        wavfile.write(str(bus_files["sfx"]), AUDIO_SAMPLE_RATE, sfx_bus.astype(np.float32))
        print(f"  Bus audio exportés : {', '.join(str(path) for path in bus_files.values())}")

    # 7. Rendu vidéo
    print(f"  Rendu vidéo avec le backend '{args.engine}'...")
    print(f"DEBUG: Starting render_timeline with engine={args.engine}", flush=True)
    if args.engine == "classic":
        render_timeline(
            tl, Path(mix_path), out_path, width, height,
            demo=args.demo, debug=args.debug,
            target_lufs=args.lufs,
            motion_style=args.motion_style,
            transition=args.transition,
            glitch_frames=args.glitch_frames,
            nvenc=nvenc_available,
        )
    elif args.engine == "html":
        editorial = _editorial_from_timeline(timeline_json)
        render_html_motion(
            out_path, duration=tl.duration, fps=FPS, width=width, height=height,
            audio_path=Path(mix_path), template=args.html_template, has_cta=bool(tl.cta), **editorial,
        )
    else:
        # Le backend hybride rend le classic une seule fois dans un temporaire,
        # puis compose l'intro HTML avec le même mix et la même timeline.
        with tempfile.TemporaryDirectory(prefix="reelforge_hybrid_render_") as temp_dir:
            classic_path = Path(temp_dir) / "classic_source.mp4"
            render_timeline(
                tl, Path(mix_path), classic_path, width, height,
                demo=args.demo, debug=args.debug,
                target_lufs=args.lufs,
                motion_style=args.motion_style,
                transition=args.transition,
                glitch_frames=args.glitch_frames,
                nvenc=nvenc_available,
            )
            html_duration = min(3.0, max(0.8, tl.duration * 0.25))
            classic_duration = max(0.8, tl.duration - html_duration)
            run_hybrid(
                out_path, classic_path, Path(voice_path),
                html_duration=html_duration,
                classic_duration=classic_duration,
                timeline_path=timeline_json,
                audio_source=classic_path,
                template=args.html_template,
                scene_plan_path=Path(args.scene_plan) if args.scene_plan else None,
            )

    if not args.keep_temp:
        try:
            Path(mix_path).unlink(missing_ok=True)
        except Exception:
            pass

    print("DEBUG: main() completed successfully", flush=True)
    print("  Terminé.")


def generate_voice_pocket_tts(script_text: str, words: list, use_assemblyai: bool) -> tuple[float, list[tuple[float, float]]]:
    """Génère la voix avec Pocket-TTS (Kyutai Labs) via CLI et retourne (durée, word_times)."""
    import re as _re
    import subprocess
    import sys

    VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = VOICE_CACHE_DIR / "pocket_tts_voice.wav"

    # --- 1. S'assurer que pocket-tts est installé ---
    try:
        import pocket_tts  # noqa: F401
    except ImportError:
        print("  Installation de pocket-tts (Kyutai Labs)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pocket-tts", "--quiet"],
            check=True,
            timeout=300,
        )

    # --- 2. Générer le fichier audio via CLI pocket-tts generate ---
    # Utilise le modèle français par défaut (voice 'estelle' pour le français)
    cmd = [
        "pocket-tts", "generate",
        "--text", script_text,
        "--language", "french",
        "--output-path", str(wav_path),
        "--device", "cpu",
        "--no-quantize",
    ]
    print(f"  Pocket-TTS : génération via CLI ({' '.join(cmd[:5])}...)")
    try:
        subprocess.run(cmd, check=True, timeout=300, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        raise RuntimeError(f"Pocket-TTS CLI échoué (code {e.returncode}): {stderr}")
    except Exception as e:
        raise RuntimeError(f"Pocket-TTS CLI échoué: {e}")

    if not wav_path.exists() or wav_path.stat().st_size == 0:
        raise RuntimeError("Pocket-TTS n'a pas généré de fichier audio valide.")

    # --- 3. Décoder le WAV ---
    audio = decode_voice(wav_path)
    voice_duration = len(audio) / AUDIO_SAMPLE_RATE

    # --- 4. Timestamps des mots ---
    n_words = len(words)
    word_times = []
    if n_words > 0:
        slot = voice_duration / n_words
        for i in range(n_words):
            start = i * slot
            end = min((i + 1) * slot, voice_duration)
            word_times.append((start, end))

    # Ré-alignement AssemblyAI si demandé
    if use_assemblyai:
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        if api_key:
            try:
                print("  Ré-alignement AssemblyAI sur la voix Pocket-TTS...")
                from assemblyai_client import transcribe_words

                aa_words = transcribe_words(wav_path, api_key)
                n_aa = len(aa_words)
                if n_aa > 0 and n_words > 0:

                    def _clean(w: str) -> str:
                        return _re.sub(r"[^\wàâäéèêëîïôöùûüçñ]", "", w.lower())

                    script_clean = [_clean(w.text) for w in words]
                    aa_clean = [_clean(t) for _, _, t in aa_words]

                    new_word_times = []
                    j = 0
                    for i in range(n_words):
                        while j < n_aa and aa_clean[j] and aa_clean[j] != script_clean[i]:
                            j += 1
                        if j < n_aa and aa_clean[j] == script_clean[i]:
                            start, end, _t = aa_words[j]
                            new_word_times.append((start, end))
                            j += 1
                        else:
                            remaining_words = n_words - i
                            remaining_aa = max(n_aa - j, 1)
                            slot2 = (
                                (voice_duration - (new_word_times[-1][1] if new_word_times else 0))
                                / remaining_words
                                if new_word_times
                                else voice_duration / n_words
                            )
                            start = new_word_times[-1][1] if new_word_times else 0.0
                            end = min(start + slot2, voice_duration)
                            new_word_times.append((start, end))
                    word_times = new_word_times
                    print(f"  AssemblyAI : {n_aa} mots détectés, alignés sur {n_words} mots du script")
            except Exception as e:
                print(f"  AssemblyAI échec ({e}), maintien timestamps estimés", file=sys.stderr)
        else:
            print("  Clé ASSEMBLYAI_API_KEY manquante, maintien timestamps estimés", file=sys.stderr)

    # --- 5. Sauvegarder dans le cache pour cohérence ---
    wavfile.write(str(VOICE_CACHE_DIR / "voice_file_input.wav"), AUDIO_SAMPLE_RATE, audio)
    return voice_duration, word_times


if __name__ == "__main__":
    main()

