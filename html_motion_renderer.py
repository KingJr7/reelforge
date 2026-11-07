"""Renderer HTML frame-driven pour des scènes de motion design génératives.

La page ne dépend pas d'une horloge CSS : render_frame(frame) fixe toutes les
variables visuelles avant chaque capture. Le résultat est donc déterministe et
reproductible en vidéo.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.sync_api import sync_playwright


HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
* { box-sizing: border-box; }
html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; }
body {
  background: #101114;
  color: #f5f2ea;
  font-family: Inter, Arial, sans-serif;
}
.scene {
  position: relative; width: 100%; height: 100%; overflow: hidden;
  background:
    radial-gradient(circle at 75% 22%, rgba(255, 91, 54, .25), transparent 28%),
    linear-gradient(145deg, #17191f 0%, #0d0e12 55%, #08090b 100%);
}
.grid {
  position: absolute; inset: -20%; opacity: .14;
  background-image: linear-gradient(rgba(255,255,255,.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.16) 1px, transparent 1px);
  background-size: 64px 64px;
  transform: translate3d(calc(var(--grid-x) * 1px), calc(var(--grid-y) * 1px), 0) rotate(-8deg);
}
.orb {
  position: absolute; width: 46%; aspect-ratio: 1; border-radius: 50%;
  right: -14%; top: 9%; filter: blur(1px);
  background: linear-gradient(135deg, #ff5a36, #8c3cff 70%);
  opacity: .78;
  transform: translate3d(calc(var(--orb-x) * 1px), calc(var(--orb-y) * 1px), 0) scale(var(--orb-scale));
  box-shadow: 0 0 120px rgba(255,90,54,.30);
}
.beam {
  position: absolute; top: -20%; bottom: -20%; width: 9%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.22), transparent);
  transform: translateX(calc(var(--beam-x) * 1px)) skewX(-18deg);
  opacity: var(--beam-opacity);
}
.frame {
  position: absolute; inset: 8% 8% 8%; border: 1px solid rgba(255,255,255,.22);
  transform: translateY(calc(var(--frame-y) * 1px)); opacity: var(--frame-opacity);
}
.kicker, .title, .number, .card, .footer { position: absolute; }
.kicker {
  left: 10%; top: 14%; letter-spacing: .18em; font-size: 18px; color: #ff8c73;
  transform: translateX(calc(var(--kicker-x) * 1px)); opacity: var(--kicker-opacity);
}
.title {
  left: 9%; top: 27%; width: 84%; font-size: 11.5vw; line-height: .86;
  letter-spacing: -.07em; font-weight: 900; text-transform: uppercase;
  transform: translate3d(calc(var(--title-x) * 1px), calc(var(--title-y) * 1px), 0) scale(var(--title-scale));
  opacity: var(--title-opacity);
}
.title span { display: block; }
.title span { opacity: var(--line-opacity); }
.title .line-a { transform: translateX(calc(var(--line-a-x) * 1px)); }
.title .line-b { transform: translateX(calc(var(--line-b-x) * 1px)); }
.title .line-c { transform: translateX(calc(var(--line-c-x) * 1px)); }
.title .accent { color: #ff5a36; }
.number {
  right: 9%; top: 41%; font-size: 28vw; line-height: .8; font-weight: 900;
  color: transparent; -webkit-text-stroke: 2px rgba(255,255,255,.22);
  transform: translate3d(calc(var(--number-x) * 1px), calc(var(--number-y) * 1px), 0) rotate(var(--number-rotate));
  opacity: var(--number-opacity);
}
.card {
  left: 10%; bottom: 20%; width: 70%; height: 16%; padding: 26px;
  border: 1px solid rgba(255,255,255,.28); background: rgba(255,255,255,.07);
  backdrop-filter: blur(12px); transform: translate3d(calc(var(--card-x) * 1px), calc(var(--card-y) * 1px), 0) rotate(var(--card-rotate));
  opacity: var(--card-opacity); box-shadow: 18px 18px 0 rgba(255,90,54,.18);
}
.card strong { display: block; font-size: 30px; letter-spacing: .04em; }
.card small { display: block; margin-top: 8px; color: rgba(245,242,234,.62); letter-spacing: .12em; }
.tag {
  position: absolute; right: 10%; bottom: 42%; padding: 10px 14px;
  border: 1px solid #ff5a36; color: #ff8c73; font-size: 13px; letter-spacing: .14em;
  transform: translate3d(calc(var(--tag-x) * 1px), calc(var(--tag-y) * 1px), 0) scale(var(--tag-scale)) rotate(var(--tag-rotate));
  opacity: var(--tag-opacity);
}
.bars { position: absolute; right: 10%; bottom: 20%; width: 22%; height: 15%; display: flex; align-items: end; gap: 7%; opacity: var(--bars-opacity); }
.bars i { display: block; flex: 1; background: #ff5a36; transform: scaleY(var(--bar-scale)); transform-origin: bottom; }
.bars i:nth-child(1) { height: 35%; }
.bars i:nth-child(2) { height: 55%; background: #ff8c73; }
.bars i:nth-child(3) { height: 78%; }
.bars i:nth-child(4) { height: 100%; background: #8c3cff; }
.scan { position: absolute; left: 0; right: 0; height: 2px; background: #ff5a36; transform: translateY(calc(var(--scan-y) * 1px)); opacity: var(--scan-opacity); box-shadow: 0 0 24px #ff5a36; }
.footer {
  left: 10%; right: 10%; bottom: 9%; display: flex; justify-content: space-between;
  font-size: 14px; letter-spacing: .12em; color: rgba(245,242,234,.62);
  opacity: var(--footer-opacity); transform: translateY(calc(var(--footer-y) * 1px));
}
.wipe { position: absolute; inset: 0; background: #ff5a36; transform: scaleX(var(--wipe)); transform-origin: left; opacity: .9; }

/* Variantes éditoriales : mêmes primitives, compositions différentes. */
.scene.template-numbers .title { top: 17%; width: 76%; }
.scene.template-numbers .number { left: 9%; right: auto; top: 52%; font-size: 39vw; }
.scene.template-numbers .card { left: 10%; bottom: 12%; width: 80%; }
.scene.template-split .title { left: 54%; top: 20%; width: 39%; font-size: 8.5vw; }
.scene.template-split .number { right: 7%; top: 6%; font-size: 20vw; }
.scene.template-split .card { left: 8%; bottom: 22%; width: 43%; height: 36%; }
.scene.template-split .card strong { font-size: 24px; }
.scene.template-cta .title { top: 20%; width: 88%; }
.scene.template-cta .card { left: 8%; bottom: 18%; width: 84%; height: 21%; }
.scene.template-cta .tag { right: 8%; bottom: 45%; }
.scene.template-diagram .title { top: 16%; width: 78%; }
.scene.template-diagram .card { left: 9%; bottom: 16%; width: 82%; height: 24%; }
.scene.template-diagram .bars { right: 12%; bottom: 43%; width: 35%; height: 18%; }
.scene.template-comparison .title { top: 19%; left: 8%; width: 84%; font-size: 10vw; }
.scene.template-comparison .card { left: 8%; bottom: 18%; width: 39%; height: 23%; }
.scene.template-comparison .number { right: 7%; top: 48%; font-size: 34vw; }
.scene.template-broll .title { top: 14%; width: 86%; font-size: 10vw; }
.scene.template-broll .card { left: 6%; bottom: 16%; width: 88%; height: 29%; }
.scene.template-broll .card strong { font-size: 26px; }
.diagram, .comparison, .media-frame { display: none; position: absolute; }
.template-diagram .diagram { display: block; left: 9%; right: 9%; top: 49%; height: 25%; opacity: var(--diagram-opacity); transform: translateY(calc(var(--diagram-y) * 1px)); }
.diagram .connector { position: absolute; left: 12%; right: 12%; top: 50%; height: 3px; background: #ff5a36; transform: scaleX(var(--connector-scale)); transform-origin: left; box-shadow: 0 0 18px rgba(255,90,54,.7); }
.diagram .node { position: absolute; top: 31%; width: 26%; height: 38%; padding: 16px 10px; border: 1px solid rgba(255,255,255,.45); background: rgba(255,255,255,.08); text-align: center; font-size: 15px; letter-spacing: .08em; transform: translateY(calc(var(--node-y) * 1px)) scale(var(--node-scale)); opacity: var(--node-opacity); }
.diagram .node:nth-child(2) { left: 0; }
.diagram .node:nth-child(3) { left: 37%; }
.diagram .node:nth-child(4) { right: 0; }
.template-comparison .comparison { display: flex; left: 8%; right: 8%; top: 53%; height: 25%; gap: 10px; opacity: var(--comparison-opacity); transform: translateY(calc(var(--comparison-y) * 1px)); }
.comparison .panel { flex: 1; padding: 18px 14px; border: 1px solid rgba(255,255,255,.35); background: rgba(255,255,255,.07); transform: scale(var(--panel-scale)); }
.comparison .panel:last-child { border-color: #ff5a36; background: rgba(255,90,54,.15); }
.comparison b { display: block; font-size: 14px; letter-spacing: .15em; color: #ff8c73; margin-bottom: 14px; }
.comparison span { font-size: 23px; font-weight: 800; }
.template-broll .media-frame { display: block; left: 7%; right: 7%; top: 47%; height: 31%; border: 1px solid rgba(255,255,255,.42); background: linear-gradient(135deg, rgba(255,90,54,.35), rgba(140,60,255,.32)); opacity: var(--media-opacity); transform: translateY(calc(var(--media-y) * 1px)) scale(var(--media-scale)); overflow: hidden; }
.media-frame::before { content: "MEDIA / B-ROLL"; position: absolute; inset: 18px; border: 1px dashed rgba(255,255,255,.55); display: grid; place-items: center; font-size: 18px; letter-spacing: .18em; }
.media-frame::after { content: ""; position: absolute; width: 140%; height: 2px; left: -20%; top: 50%; background: #fff; opacity: .55; transform: translateX(calc(var(--media-scan) * 1px)); }
.media-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: .68; mix-blend-mode: screen; }
.impact-flash { position: absolute; inset: 0; background: #ff5a36; opacity: var(--impact-opacity); transform: scale(var(--impact-scale)); mix-blend-mode: screen; pointer-events: none; }
</style>
<style id="frame-style">{{FRAME_STYLE}}</style>
</head>
<body>
<main class="scene template-{{TEMPLATE}}">
  <div class="grid"></div><div class="orb"></div><div class="beam"></div><div class="frame"></div>
  <div class="kicker">{{KICKER}}</div>
  <div class="title"><span class="line-a">{{TITLE_A}}</span><span class="line-b accent">{{TITLE_B}}</span><span class="line-c">{{TITLE_C}}</span></div>
  <div class="number">{{NUMBER}}</div>
  <div class="card"><strong>{{CARD_TITLE}}</strong><small>{{CARD_SUBTITLE}}</small></div>
  <div class="tag">{{SCENE_LABEL}}</div><div class="bars"><i></i><i></i><i></i><i></i></div><div class="scan"></div>
  <div class="diagram"><div class="connector"></div><div class="node">{{DIAGRAM_A}}</div><div class="node">{{DIAGRAM_B}}</div><div class="node">{{DIAGRAM_C}}</div></div>
  <div class="comparison"><div class="panel"><b>AVANT</b><span>{{COMPARE_A}}</span></div><div class="panel"><b>APRÈS</b><span>{{COMPARE_B}}</span></div></div>
  <div class="media-frame"><img class="media-image" src="{{MEDIA_SRC}}" alt="" /></div>
  <div class="impact-flash"></div>
  <div class="footer"><span>REELFORGE 001</span><span>2026</span></div>
  <div class="wipe"></div>
</main>
<script>
const clamp = (v, a=0, b=1) => Math.max(a, Math.min(b, v));
const cubic = t => 1 - Math.pow(1 - clamp(t), 3);
const smooth = t => t * t * (3 - 2 * t);
window.renderFrame = (frame, fps, totalFrames) => {
  const t = frame / fps;
  const total = totalFrames / fps;
  const intro = cubic(t / .7);
  const outro = cubic((total - t) / .55);
  const active = intro * outro;
  const pulse = Math.sin(t * Math.PI * 2 / 3.2);
  const beat = t % 1.6;
  const beatIn = cubic(beat / .28);
  const beatOut = cubic((1.6 - beat) / .28);
  const beatActive = beatIn * beatOut;
  const sfxImpact = (window.motionSfx || []).reduce((max, event) => {
    const distance = Math.abs(t - event);
    return Math.max(max, clamp(1 - distance / .16));
  }, 0);
  const cycle = Math.floor(t / 1.6) % 3;
  const scene = document.querySelector('.scene');
  const set = (name, value) => scene.style.setProperty(name, value);
  set('--grid-x', pulse * 54); set('--grid-y', Math.cos(t / 3.2) * 42);
  set('--orb-x', Math.sin(t / 1.3) * 150); set('--orb-y', Math.cos(t / 1.7) * 100);
  set('--orb-scale', .82 + .24 * (0.5 + 0.5 * Math.sin(t * 2.1)));
  set('--beam-x', -width() + (t % 1.9) / 1.9 * width() * 2.4); set('--beam-opacity', .42 * beatActive);
  set('--frame-y', (1 - intro) * 28); set('--frame-opacity', .35 + .65 * active);
  set('--kicker-x', (1 - intro) * -80); set('--kicker-opacity', active);
  set('--title-x', (1 - intro) * -120); set('--title-y', (1 - intro) * 42);
  set('--title-scale', .92 + .08 * intro); set('--title-opacity', active);
  set('--line-opacity', beatActive); set('--line-a-x', (1 - beatIn) * -260); set('--line-b-x', (1 - beatIn) * 300); set('--line-c-x', (1 - beatIn) * -340);
  set('--number-x', (1 - intro) * 120 + pulse * 100); set('--number-y', pulse * 80);
  set('--number-rotate', `${pulse * 18}deg`); set('--number-opacity', .22 + .72 * active);
  set('--card-x', (1 - intro) * 260 + Math.sin(t * 2.4) * 48); set('--card-y', pulse * 46);
  set('--card-rotate', `${-10 + intro * 10 + pulse * 8}deg`); set('--card-opacity', active * beatActive);
  set('--tag-x', Math.sin(t * 2.2) * 80); set('--tag-y', Math.cos(t * 2.7) * 50); set('--tag-scale', .84 + .26 * beatActive); set('--tag-rotate', `${pulse * 14}deg`); set('--tag-opacity', .25 + .75 * beatActive);
  set('--bar-scale', .35 + .65 * (0.5 + 0.5 * Math.sin(t * 8.0))); set('--bars-opacity', .25 + .75 * beatActive);
  set('--scan-y', (t % 1.8) / 1.8 * 1000); set('--scan-opacity', .15 + .25 * beatActive);
  set('--footer-y', (1 - intro) * 18); set('--footer-opacity', active);
  set('--diagram-y', (1 - intro) * 36); set('--diagram-opacity', active); set('--connector-scale', beatIn); set('--node-y', (1 - beatIn) * 24); set('--node-scale', .92 + .08 * beatIn); set('--node-opacity', beatActive);
  set('--comparison-y', (1 - intro) * 28); set('--comparison-opacity', active); set('--panel-scale', .94 + .06 * beatActive);
  set('--media-y', (1 - intro) * 38); set('--media-opacity', active); set('--media-scale', .94 + .06 * beatActive); set('--media-scan', Math.sin(t * 2.4) * 180);
  set('--impact-scale', 1 + sfxImpact * .035); set('--impact-opacity', sfxImpact * .28);
  if (window.mediaFrames && window.mediaFrames.length) {
    document.querySelector('.media-image').src = window.mediaFrames[frame % window.mediaFrames.length];
  }
  set('--wipe', clamp((.16 - beat) / .12));
  document.querySelector('.tag').textContent = `SCÈNE 0${cycle + 1}`;
  document.querySelector('.card strong').textContent = ['UNE IDÉE.', 'UN SYSTÈME.', 'UN RÉSULTAT.'][cycle];
};
const width = () => window.innerWidth;
const query = new URLSearchParams(location.search);
if (query.has('frame')) {
  window.renderFrame(Number(query.get('frame')), Number(query.get('fps')), Number(query.get('total')));
}
window.motionSfx = {{SFX_EVENTS}};
window.mediaFrames = {{MEDIA_FRAMES}};
const frameArgs = null;
if (frameArgs) {
  window.renderFrame(frameArgs[0], frameArgs[1], frameArgs[2]);
}
</script>
</body>
</html>"""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _cubic(value: float) -> float:
    value = _clamp(value)
    return 1.0 - (1.0 - value) ** 3


def _media_data_uri(media_path: Path | None) -> str:
    """Convertit un asset local en data URI pour une capture HTML reproductible."""
    if media_path is None or not media_path.exists():
        return ""
    suffix = media_path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else f"image/{suffix[1:]}"
        payload = media_path.read_bytes()
    elif suffix in {".mp4", ".mov", ".webm", ".mkv"}:
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", "0.25", "-i", str(media_path),
            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
        ], capture_output=True, check=False)
        if result.returncode != 0 or not result.stdout:
            return ""
        mime = "image/png"
        payload = result.stdout
    else:
        return ""
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


_media_frames_cache: dict[tuple[str, int, int], list[str]] = {}


def _media_frame_data_uris(media_path: Path | None, count: int = 12) -> list[str]:
    """Extrait une courte séquence déterministe pour animer les vidéos B-roll."""
    if media_path is None or not media_path.exists():
        return []
    if media_path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
        uri = _media_data_uri(media_path)
        return [uri] if uri else []
    key = (str(media_path.resolve()), media_path.stat().st_mtime_ns, count)
    if key in _media_frames_cache:
        return _media_frames_cache[key]
    with tempfile.TemporaryDirectory(prefix="reelforge_media_frames_") as temp_dir:
        pattern = str(Path(temp_dir) / "frame_%03d.png")
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(media_path), "-vf", f"fps={count}/2",
            "-frames:v", str(count), pattern,
        ], capture_output=True, check=False)
        if result.returncode != 0:
            return []
        frames = [
            f"data:image/png;base64,{base64.b64encode(frame.read_bytes()).decode('ascii')}"
            for frame in sorted(Path(temp_dir).glob("frame_*.png"))
        ]
    _media_frames_cache[key] = frames
    return frames


def _frame_css(frame: int, fps: int, total_frames: int, width: int, height: int,
               sfx_events: list[float] | tuple[float, ...] = ()) -> str:
    """CSS direct pour les moteurs sans support JS/CSS moderne."""
    t = frame / fps
    total = total_frames / fps
    intro = _cubic(t / 0.7)
    outro = _cubic((total - t) / 0.55)
    active = intro * outro
    pulse = math.sin(t * math.pi * 2 / 3.2)
    beat = t % 1.6
    beat_in = _cubic(beat / 0.28)
    beat_out = _cubic((1.6 - beat) / 0.28)
    beat_active = beat_in * beat_out
    beam_x = -width + (t % 1.9) / 1.9 * width * 2.4
    wipe = _clamp((0.16 - beat) / 0.12)
    sfx_impact = max((_clamp(1.0 - abs(t - event) / 0.16) for event in sfx_events), default=0.0)
    return f"""
.grid {{ transform: translate3d({pulse * 54:.2f}px, {math.cos(t / 3.2) * 42:.2f}px, 0) rotate(-8deg); }}
.orb {{ transform: translate3d({math.sin(t / 1.3) * 150:.2f}px, {math.cos(t / 1.7) * 100:.2f}px, 0) scale({0.82 + 0.24 * (0.5 + 0.5 * math.sin(t * 2.1)):.4f}); }}
.beam {{ transform: translateX({beam_x:.2f}px) skewX(-18deg); opacity: {0.42 * beat_active:.4f}; }}
.frame {{ transform: translateY({(1 - intro) * 28:.2f}px); opacity: {0.35 + 0.65 * active:.4f}; }}
.kicker {{ transform: translateX({(1 - intro) * -80:.2f}px); opacity: {active:.4f}; }}
.title {{ transform: translate3d({(1 - intro) * -120:.2f}px, {(1 - intro) * 42:.2f}px, 0) scale({0.92 + 0.08 * intro:.4f}); opacity: {active:.4f}; }}
.title span {{ opacity: {beat_active:.4f}; }}
.title .line-a {{ transform: translateX({(1 - beat_in) * -260:.2f}px); }}
.title .line-b {{ transform: translateX({(1 - beat_in) * 300:.2f}px); }}
.title .line-c {{ transform: translateX({(1 - beat_in) * -340:.2f}px); }}
.number {{ transform: translate3d({(1 - intro) * 120 + pulse * 100:.2f}px, {pulse * 80:.2f}px, 0) rotate({pulse * 18:.2f}deg); opacity: {0.22 + 0.72 * active:.4f}; }}
.card {{ transform: translate3d({(1 - intro) * 260 + math.sin(t * 2.4) * 48:.2f}px, {pulse * 46:.2f}px, 0) rotate({-10 + intro * 10 + pulse * 8:.2f}deg); opacity: {active * beat_active:.4f}; }}
.tag {{ transform: translate3d({math.sin(t * 2.2) * 80:.2f}px, {math.cos(t * 2.7) * 50:.2f}px, 0) scale({0.84 + 0.26 * beat_active:.4f}) rotate({pulse * 14:.2f}deg); opacity: {0.25 + 0.75 * beat_active:.4f}; }}
.bars {{ opacity: {0.25 + 0.75 * beat_active:.4f}; }}
.bars i {{ transform: scaleY({0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 8.0)):.4f}); }}
.scan {{ transform: translateY({(t % 1.8) / 1.8 * height:.2f}px); opacity: {0.15 + 0.25 * beat_active:.4f}; }}
.footer {{ transform: translateY({(1 - intro) * 18:.2f}px); opacity: {active:.4f}; }}
.diagram {{ transform: translateY({(1 - intro) * 36:.2f}px); opacity: {active:.4f}; }}
.diagram .connector {{ transform: scaleX({beat_in:.4f}); }}
.diagram .node {{ transform: translateY({(1 - beat_in) * 24:.2f}px) scale({0.92 + 0.08 * beat_in:.4f}); opacity: {beat_active:.4f}; }}
.comparison {{ transform: translateY({(1 - intro) * 28:.2f}px); opacity: {active:.4f}; }}
.comparison .panel {{ transform: scale({0.94 + 0.06 * beat_active:.4f}); }}
.media-frame {{ transform: translateY({(1 - intro) * 38:.2f}px) scale({0.94 + 0.06 * beat_active:.4f}); opacity: {active:.4f}; }}
.media-frame::after {{ transform: translateX({math.sin(t * 2.4) * 180:.2f}px); }}
.impact-flash {{ transform: scale({1 + sfx_impact * .035:.4f}); opacity: {sfx_impact * .28:.4f}; }}
.wipe {{ transform: scaleX({wipe:.4f}); }}
"""


def _scene_template(kicker: str, headline: tuple[str, str, str], number: str,
                    card_title: str, card_subtitle: str, scene_label: str,
                    template: str, diagram_labels: tuple[str, str, str],
                    comparison_labels: tuple[str, str], media_src: str,
                    sfx_events: list[float] | tuple[float, ...],
                    media_frames: list[str] | tuple[str, ...]) -> str:
    """Injecte les données éditoriales sans introduire de HTML arbitraire."""
    values = {
        "KICKER": kicker,
        "TITLE_A": headline[0],
        "TITLE_B": headline[1],
        "TITLE_C": headline[2],
        "NUMBER": number,
        "CARD_TITLE": card_title,
        "CARD_SUBTITLE": card_subtitle,
        "SCENE_LABEL": scene_label,
        "TEMPLATE": template,
        "DIAGRAM_A": diagram_labels[0],
        "DIAGRAM_B": diagram_labels[1],
        "DIAGRAM_C": diagram_labels[2],
        "COMPARE_A": comparison_labels[0],
        "COMPARE_B": comparison_labels[1],
        "MEDIA_SRC": media_src,
    }
    template = HTML_TEMPLATE
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", html.escape(value, quote=True))
    template = template.replace("{{SFX_EVENTS}}", json.dumps(list(sfx_events)))
    template = template.replace("{{MEDIA_FRAMES}}", json.dumps(list(media_frames)))
    return template


HTML_TEMPLATES = ("hero", "numbers", "split", "cta", "diagram", "comparison", "broll")


def resolve_template(template: str, headline: tuple[str, str, str],
                     card_title: str = "", has_cta: bool = False) -> str:
    """Choisit une composition depuis le contenu quand le mode auto est actif."""
    if template != "auto":
        if template not in HTML_TEMPLATES:
            raise ValueError(f"template inconnu: {template} (choix: {list(HTML_TEMPLATES)})")
        return template
    text = " ".join((*headline, card_title)).lower()
    if has_cta:
        return "cta"
    if any(char.isdigit() for char in text) or any(token in text for token in ("€", "fcfa", "%")):
        return "numbers"
    if any(token in text for token in ("compar", "avant", "après", "versus", "vs")):
        return "comparison"
    if any(token in text for token in ("étape", "process", "méthode", "système", "comment")):
        return "diagram"
    if card_title or "b-roll" in text or "image" in text:
        return "broll"
    return "hero"


def render_html_motion(out_path: Path, duration: float = 8.0, fps: int = 30,
                       width: int = 540, height: int = 960,
                       audio_path: Path | None = None,
                       kicker: str = "LEVELCASH / MOTION SYSTEM",
                       headline: tuple[str, str, str] = ("GAGNE", "AVEC", "TON MOBILE"),
                       number: str = "03", card_title: str = "UNE IDÉE.",
                       card_subtitle: str = "UN MOUVEMENT. UN RÉSULTAT.",
                       scene_label: str = "SCÈNE 01", template: str = "hero",
                       has_cta: bool = False,
                       diagram_labels: tuple[str, str, str] = ("INPUT", "PROCESS", "OUTPUT"),
                       comparison_labels: tuple[str, str] = ("FRICTION", "FLOW"),
                       media_path: Path | None = None,
                       sfx_events: list[float] | tuple[float, ...] = (),
                       media_frames: list[str] | tuple[str, ...] = ()) -> None:
    """Capture une scène HTML frame par frame puis l'encode en MP4."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, round(duration * fps))
    executable = next(
        (candidate for candidate in (
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ) if Path(candidate).exists()),
        None,
    )

    with tempfile.TemporaryDirectory(prefix="reelforge_html_frames_") as frame_dir, \
         tempfile.TemporaryDirectory(prefix="reelforge_chromium_runtime_") as runtime_dir:
        frame_path = Path(frame_dir)
        html_path = frame_path / "scene.html"
        template = resolve_template(template, headline, card_title, has_cta=has_cta)
        scene_template = _scene_template(
            kicker, headline, number, card_title, card_subtitle, scene_label, template,
            diagram_labels, comparison_labels, _media_data_uri(media_path), sfx_events,
            media_frames or _media_frame_data_uris(media_path),
        )
        html_path.write_text(scene_template, encoding="utf-8")
        browser_env = os.environ.copy()
        browser_env["XDG_RUNTIME_DIR"] = runtime_dir
        captured = False
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=executable,
                    env=browser_env,
                    args=["--no-sandbox", "--disable-gpu", "--disable-crash-reporter"],
                )
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                page.set_content(scene_template.replace("{{FRAME_STYLE}}", ""), wait_until="load")
                page.evaluate("document.fonts.ready")
                for frame in range(total_frames):
                    page.evaluate("([frame, fps, total]) => window.renderFrame(frame, fps, total)",
                                  [frame, fps, total_frames])
                    page.screenshot(path=str(frame_path / f"frame_{frame:05d}.png"), type="png")
                browser.close()
                captured = True
        except Exception as exc:
            print(f"  Playwright indisponible ({type(exc).__name__}), fallback wkhtmltoimage")

        if not captured:
            wkhtml = shutil.which("wkhtmltoimage")
            if wkhtml is None:
                raise RuntimeError("Ni Chromium/Playwright ni wkhtmltoimage ne sont disponibles")
            requested_workers = int(os.getenv("REELFORGE_HTML_WORKERS", "4"))
            workers = max(1, min(requested_workers, total_frames, os.cpu_count() or 1))

            def capture_fallback(frame: int) -> None:
                frame_html = frame_path / f"scene_{frame:05d}.html"
                frame_html.write_text(
                    scene_template
                    .replace("{{FRAME_STYLE}}", _frame_css(frame, fps, total_frames, width, height, sfx_events))
                    .replace(
                        "const frameArgs = null;",
                        f"const frameArgs = [{frame}, {fps}, {total_frames}];",
                    ),
                    encoding="utf-8",
                )
                subprocess.run([
                    wkhtml, "--enable-javascript", "--javascript-delay", "30",
                    "--width", str(width), "--height", str(height),
                    frame_html.as_uri(), str(frame_path / f"frame_{frame:05d}.png"),
                ], check=True, capture_output=True)

            print(f"  Capture HTML parallèle : {workers} workers")
            with ThreadPoolExecutor(max_workers=workers) as executor:
                list(executor.map(capture_fallback, range(total_frames)))

        cmd = [
            "ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
            "-i", str(frame_path / "frame_%05d.png"),
        ]
        if audio_path is not None:
            cmd += ["-i", str(audio_path)]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-t", str(duration)]
        if audio_path is not None:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += [str(out_path)]
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prototype motion design HTML frame-driven")
    parser.add_argument("--out", default="out/html_motion_demo.mp4")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=540)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--audio", default=None)
    parser.add_argument("--template", choices=["auto", *HTML_TEMPLATES], default="auto")
    args = parser.parse_args()
    render_html_motion(Path(args.out), args.duration, args.fps, args.width, args.height,
                       Path(args.audio) if args.audio else None, template=args.template)


if __name__ == "__main__":
    main()
