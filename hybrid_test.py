"""Génère un test hybride piloté par une timeline de scènes commune."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import subprocess
import tempfile
from pathlib import Path

from html_motion_renderer import render_html_motion


@dataclass(frozen=True)
class SceneSpec:
    """Fenêtre temporelle d'une scène dans la timeline finale."""

    name: str
    start: float
    duration: float
    engine: str


HYBRID_SCENES = (
    SceneSpec("html_intro", start=0.0, duration=3.0, engine="html"),
    SceneSpec("classic_body", start=3.0, duration=7.0, engine="classic"),
)


_STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "cette", "dans", "de", "des",
    "du", "en", "et", "la", "le", "les", "mais", "ne", "par", "pour",
    "que", "qui", "sur", "un", "une", "tu", "te", "ton", "ta", "tes",
}


def _compact_label(words: list[str], fallback: str) -> str:
    """Résume une portion de script en label court et lisible à l'écran."""
    meaningful = [word.strip(".,!?;:()[]\"").upper() for word in words
                  if word.strip(".,!?;:()[]\"").lower() not in _STOPWORDS]
    label = " ".join(meaningful[:3])
    return (label[:18] or fallback).strip()


def _semantic_labels(words: list[str]) -> tuple[tuple[str, str, str], tuple[str, str]]:
    """Déduit des labels éditoriaux stables à partir des mots du script."""
    clean = [word.strip(".,!?;:()[]\"").lower() for word in words]
    joined = " ".join(clean)
    problem_terms = ("problème", "fatigue", "perdre", "difficile", "erreur", "temps")
    method_terms = ("comment", "méthode", "système", "étape", "astuce", "outil")
    result_terms = ("gagner", "résultat", "économiser", "meilleur", "plus", "fcfa", "euros")

    def first_segment(terms: tuple[str, ...], fallback: str, lookback: int = 1) -> str:
        for index, token in enumerate(clean):
            if token in terms:
                return _compact_label(words[max(0, index - lookback): index + 2], fallback)
        return fallback

    diagram = (
        first_segment(problem_terms, _compact_label(words[:4], "PROBLÈME"), lookback=2),
        first_segment(method_terms, _compact_label(words[len(words) // 3: len(words) // 3 + 3], "MÉTHODE")),
        first_segment(result_terms, _compact_label(words[-4:], "RÉSULTAT")),
    )

    contrast_index = next(
        (index for index, token in enumerate(clean) if token in {"mais", "après", "avant", "versus", "vs"}),
        None,
    )
    if contrast_index is not None:
        comparison = (
            _compact_label(words[max(0, contrast_index - 3):contrast_index], "AVANT"),
            _compact_label(words[contrast_index + 1:contrast_index + 4], "APRÈS"),
        )
    else:
        comparison = (
            _compact_label(words[:4], "AVANT"),
            _compact_label(words[-4:], "APRÈS"),
        )
    return diagram, comparison


def _editorial_from_timeline(timeline_path: Path | None, start: float = 0.0,
                             end: float | None = None) -> dict[str, object]:
    """Transforme la timeline réelle en données éditoriales pour la scène HTML."""
    if timeline_path is None or not timeline_path.exists():
        return {}
    data = json.loads(timeline_path.read_text(encoding="utf-8"))
    scene_end = float(end) if end is not None else float(data.get("duration", 0.0))
    word_records = [word for word in data.get("words", [])
                    if float(word.get("start", 0.0)) < scene_end
                    and float(word.get("end", 0.0)) > start]
    words = [str(word.get("text", "")) for word in word_records]
    words = [word for word in words if word]
    headline = tuple((words + ["", "", ""])[:3])
    diagram_labels, comparison_labels = _semantic_labels(words)
    cards = [card for card in data.get("cards", [])
             if float(card.get("start", 0.0)) < scene_end
             and float(card.get("start", 0.0)) + float(card.get("duration", 0.0)) > start]
    first_card = cards[0] if cards else {}
    sfx_events = [round(float(event.get("t", 0.0)) - start, 4)
                  for event in data.get("sfx", [])
                  if start <= float(event.get("t", 0.0)) < scene_end]
    raw_source = str(first_card.get("source", ""))
    card_source = Path(raw_source).stem
    if not raw_source or "/" in raw_source or len(card_source) > 24:
        card_source = "MOMENT CLÉ"
    media_path = Path(raw_source) if Path(raw_source).exists() else None
    return {
        "headline": headline,
        "number": f"{len(words):02d}",
        "card_title": card_source.replace("_", " ").upper()[:24],
        "card_subtitle": f"{len(words)} MOTS · {max(0.0, scene_end - start):.1f}S",
        "has_cta": bool(data.get("cta")) and start <= float(data["cta"].get("start", 0.0)) < scene_end,
        "diagram_labels": diagram_labels,
        "comparison_labels": comparison_labels,
        "media_path": media_path,
        "sfx_events": sfx_events,
    }


def load_scene_plan(path: Path, fallback_transition: float) -> dict[str, object]:
    """Charge un plan utilisateur et vérifie ses fenêtres temporelles."""
    data = json.loads(path.read_text(encoding="utf-8"))
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 2:
        raise ValueError("Le plan doit contenir au moins 2 scènes")
    parsed = []
    previous_end = 0.0
    for index, scene in enumerate(scenes):
        if scene.get("engine") not in {"html", "classic"}:
            raise ValueError("Chaque scène doit utiliser le moteur html ou classic")
        start = float(scene["start"])
        end = float(scene["end"])
        if abs(start - previous_end) > 1e-6 or end <= start:
            raise ValueError("Les scènes doivent être contiguës et avoir une durée positive")
        parsed.append({
            "name": str(scene.get("name", f"scene_{index + 1}")),
            "start": start,
            "end": end,
            "duration": end - start,
            "engine": scene["engine"],
            "template": str(scene.get("template", "hero")),
        })
        previous_end = end
    return {
        "scenes": parsed,
        "duration": previous_end,
        "transition_duration": float(data.get("transition_duration", fallback_transition)),
    }


def run_hybrid(out_path: Path, source_video: Path, voice_path: Path,
               html_duration: float = 3.0, classic_duration: float = 7.0,
               transition_duration: float = 0.35,
               timeline_path: Path | None = None,
               audio_source: Path | None = None,
               template: str = "hero",
               scene_plan_path: Path | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    user_plan = load_scene_plan(scene_plan_path, transition_duration) if scene_plan_path else None
    if user_plan:
        total_duration = float(user_plan["duration"])
        transition_duration = float(user_plan["transition_duration"])
        scenes = tuple(
            SceneSpec(str(scene["name"]), float(scene["start"]), float(scene["duration"]), str(scene["engine"]))
            for scene in user_plan["scenes"]
        )
    else:
        total_duration = html_duration + classic_duration
        outro_duration = min(2.0, max(0.8, classic_duration * 0.18))
        middle_duration = classic_duration - outro_duration
        if middle_duration < 0.8:
            outro_duration = max(0.4, classic_duration - 0.8)
            middle_duration = classic_duration - outro_duration
        scenes = (
            SceneSpec("html_intro", start=0.0, duration=html_duration, engine="html"),
            SceneSpec("classic_body", start=html_duration, duration=middle_duration, engine="classic"),
            SceneSpec("html_outro", start=html_duration + middle_duration,
                       duration=outro_duration, engine="html"),
        )
    if transition_duration <= 0 or any(transition_duration >= scene.duration for scene in scenes):
        raise ValueError("transition_duration doit être positive et plus courte que chaque scène")

    with tempfile.TemporaryDirectory(prefix="reelforge_hybrid_") as temp_dir:
        temp = Path(temp_dir)
        scene_paths: list[Path] = []
        print(f"  Génération de {len(scenes)} scènes selon le plan utilisateur..." if user_plan else "  Génération des scènes hybrides...")
        for index, scene in enumerate(scenes):
            scene_path = temp / f"scene_{index:02d}.mp4"
            render_duration = scene.duration + (transition_duration if index > 0 else 0.0)
            if scene.engine == "html":
                scene_editorial = _editorial_from_timeline(
                    timeline_path, start=scene.start, end=scene.start + scene.duration,
                )
                scene_editorial["scene_label"] = scene.name.upper()[:18]
                if index == len(scenes) - 1:
                    scene_editorial.update({
                        "card_title": "CTA FINAL",
                        "card_subtitle": "PASSE À L'ACTION",
                        "has_cta": True,
                    })
                scene_template = (
                    str(user_plan["scenes"][index]["template"])
                    if user_plan else (template if index == 0 else "cta")
                )
                print(f"    HTML {scene.name} ({scene.duration:.2f}s, template={scene_template})")
                render_html_motion(
                    scene_path, duration=render_duration, fps=30, width=540, height=960,
                    template=scene_template, **scene_editorial,
                )
            else:
                print(f"    Classic {scene.name} ({scene.duration:.2f}s)")
                subprocess.run([
                    "ffmpeg", "-y", "-v", "error", "-ss", str(scene.start),
                    "-i", str(source_video), "-t", str(render_duration), "-an",
                    "-vf", "scale=540:960:force_original_aspect_ratio=decrease,"
                           "pad=540:960:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    str(scene_path),
                ], check=True)
            scene_paths.append(scene_path)

        audio_track = temp / "timeline_audio.m4a"
        audio_input = audio_source or source_video
        print(f"  Extraction audio de la timeline : {audio_input}")
        audio_result = subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(audio_input),
            "-t", str(total_duration), "-vn", "-ac", "2", "-ar", "48000",
            "-c:a", "aac", "-b:a", "192k", str(audio_track),
        ], capture_output=True, text=True)
        if audio_result.returncode != 0:
            print("  Audio source indisponible, fallback voix fournie.")
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(voice_path),
                "-t", str(total_duration), "-vn", "-ac", "2", "-ar", "48000",
                "-c:a", "aac", "-b:a", "192k", str(audio_track),
            ], check=True)

        filter_parts = []
        current_label = "0:v"
        cumulative_duration = scenes[0].duration
        for index in range(1, len(scenes)):
            next_label = f"v{index}"
            offset = cumulative_duration - transition_duration
            filter_parts.append(
                f"[{current_label}][{index}:v]xfade=transition=fade:"
                f"duration={transition_duration}:offset={offset}[{next_label}]"
            )
            current_label = next_label
            cumulative_duration += scenes[index].duration

        print("  Fusion des scènes avec transitions + audio continu...")
        ffmpeg_cmd = ["ffmpeg", "-y", "-v", "error"]
        for scene_path in scene_paths:
            ffmpeg_cmd += ["-i", str(scene_path)]
        ffmpeg_cmd += ["-i", str(audio_track), "-filter_complex", ";".join(filter_parts),
                       "-t", str(total_duration), "-map", f"[{current_label}]",
                       "-map", f"{len(scene_paths)}:a:0",
                       "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                       "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        subprocess.run(ffmpeg_cmd, check=True)

    print(f"  Timeline : {[scene.name + ':' + scene.engine for scene in scenes]}")
    print(f"  Vidéo hybride écrite : {out_path} ({total_duration:.2f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test HTML motion design + renderer classique")
    parser.add_argument("--source-video", default="out/levelcash_v1_motion_quality_preview.mp4")
    parser.add_argument("--voice", default="v1.mp3")
    parser.add_argument("--timeline", default="out/timeline.json")
    parser.add_argument("--audio-source", default=None,
                        help="Vidéo/audio de référence pour conserver voix + SFX + BGM")
    parser.add_argument("--template", choices=["auto", "hero", "numbers", "split", "cta", "diagram", "comparison", "broll"], default="auto")
    parser.add_argument("--scene-plan", default=None,
                        help="Plan JSON utilisateur des 3 scènes HTML/classic/HTML")
    parser.add_argument("--out", default="out/hybrid_test.mp4")
    args = parser.parse_args()
    timeline = Path(args.timeline) if args.timeline else None
    audio_source = Path(args.audio_source) if args.audio_source else None
    run_hybrid(Path(args.out), Path(args.source_video), Path(args.voice),
               timeline_path=timeline, audio_source=audio_source, template=args.template,
               scene_plan_path=Path(args.scene_plan) if args.scene_plan else None)


if __name__ == "__main__":
    main()
