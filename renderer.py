"""Compositeur image par image optimisé : fond numpy + sprites numpy, alpha-blending en numpy."""
from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from config import (
    CARD_ENTRY_FRAMES, CARD_EXIT_FRAMES, CARD_POS_X, CARD_POS_Y,
    CARD_RADIUS_RATIO, CARD_SMALL_WIDTH, CARD_MEDIUM_WIDTH, CARD_LARGE_WIDTH,
    CARD_FLOAT_AMPLITUDE, CARD_FLOAT_PERIOD, CARD_ZOOM_MIN, CARD_ZOOM_MAX,
    CARD_ZOOM_PERIOD, CARD_ENTRY_SLIDE, SHADOW_ALPHA_LIGHT, SHADOW_ALPHA_DARK,
    SHADOW_BLUR, SHADOW_OFFSET_Y, TEXT_POS_X, TEXT_POS_Y, TEXT_SIZE_NORMAL,
    TEXT_SIZE_EMPHASIS, TEXT_SIZE_STRONG, WORD_ENTRY_FRAMES, WORD_EXIT_FRAMES,
    WORD_ENTRY_SLIDE, WORD_FLOAT_AMPLITUDE, WORD_FLOAT_PERIOD,
    WORD_BREATH_MIN, WORD_BREATH_MAX, WORD_BREATH_PERIOD, PALETTE_LIGHT,
    PALETTE_DARK, FPS, GLITCH_FRAMES_DEFAULT, GLITCH_RGB_SHIFT,
    GLITCH_BAND_SHIFT, DEFAULT_INVERT_AT, SEED, AUDIO_SAMPLE_RATE,
    CTA_ENTRY_FRAMES, CTA_SLIDE_UP, CTA_MIN_DISPLAY, CTA_BREATH_MIN,
    CTA_BREATH_MAX, CTA_BREATH_PERIOD, TEXT_SIZE_STRONG as CTA_SIZE,
    PREVIEW_WIDTH,
)
from easing import ease_out_cubic, ease_in_cubic, ease_in_out_cubic, ease_out_back
from motion import entry_progress, exit_progress, get_motion_style
from timeline import Timeline, WordEvent, CardEvent, InvertEvent, CtaEvent


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------- #
# Police
# --------------------------------------------------------------------------- #

def load_font(size_px: int) -> ImageFont.FreeTypeFont:
    from config import find_font

    path = find_font()
    if path:
        try:
            return ImageFont.truetype(path, size_px)
        except OSError:
            pass
    return ImageFont.load_default()


_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def get_font(size_px: int) -> ImageFont.FreeTypeFont:
    if size_px not in _font_cache:
        _font_cache[size_px] = load_font(size_px)
    return _font_cache[size_px]


# --------------------------------------------------------------------------- #
# Sprites texte (cache PIL -> numpy RGBA)
# --------------------------------------------------------------------------- #

_text_sprite_cache: dict[tuple, np.ndarray] = {}


def render_text_sprite_np(text: str, size_px: int, color_rgb: tuple[int, int, int]) -> np.ndarray:
    """Pré-rend un sprite RGBA du texte en majuscules, tableau numpy (h, w, 4) uint8."""
    key = (text, size_px, color_rgb)
    if key in _text_sprite_cache:
        return _text_sprite_cache[key]

    font = get_font(size_px)
    text_upper = text.upper()
    bbox = font.getbbox(text_upper)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad = 10
    sprite_w = text_w + 2 * pad
    sprite_h = text_h + 2 * pad

    sprite = Image.new("RGBA", (sprite_w, sprite_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)
    draw.text((pad - bbox[0], pad - bbox[1]), text_upper, font=font,
              fill=color_rgb + (255,))

    arr = np.array(sprite, dtype=np.uint8)
    _text_sprite_cache[key] = arr
    return arr


# --------------------------------------------------------------------------- #
# Masque arrondi (numpy)
# --------------------------------------------------------------------------- #

_mask_cache: dict[tuple, np.ndarray] = {}


def get_rounded_mask_np(card_w: int, card_h: int, radius: int) -> np.ndarray:
    """Masque alpha arrondi, tableau numpy (h, w) uint8, anti-aliasing 4x."""
    key = (card_w, card_h, radius)
    if key in _mask_cache:
        return _mask_cache[key]

    sup = 4
    big_w = card_w * sup
    big_h = card_h * sup
    big_r = radius * sup

    mask = Image.new("L", (big_w, big_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, big_w, big_h], radius=big_r, fill=255)
    mask = mask.resize((card_w, card_h), Image.LANCZOS)
    arr = np.array(mask, dtype=np.uint8)
    _mask_cache[key] = arr
    return arr


# --------------------------------------------------------------------------- #
# Ombre floue (numpy)
# --------------------------------------------------------------------------- #

_shadow_cache: dict[tuple, np.ndarray] = {}


def get_shadow_np(card_w: int, card_h: int, radius: int, alpha: float) -> np.ndarray:
    """Sprite d'ombre (h, w, 4) uint8, décalée et floue."""
    key = (card_w, card_h, radius, int(alpha * 255))
    if key in _shadow_cache:
        return _shadow_cache[key]

    shadow = Image.new("RGBA", (card_w, card_h), (0, 0, 0, int(255 * alpha)))
    mask = get_rounded_mask_np(card_w, card_h, radius)
    shadow.putalpha(Image.fromarray(mask, mode="L"))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, int(SHADOW_BLUR))))
    arr = np.array(shadow, dtype=np.uint8)
    _shadow_cache[key] = arr
    return arr


# --------------------------------------------------------------------------- #
# Plaque d'icône (numpy)
# --------------------------------------------------------------------------- #

_plaque_cache: dict[tuple, np.ndarray] = {}


def get_plaque_np(card_w: int, card_h: int, radius: int,
                  color_rgb: tuple[int, int, int]) -> np.ndarray:
    key = (card_w, card_h, radius, color_rgb)
    if key in _plaque_cache:
        return _plaque_cache[key]

    plaque = Image.new("RGBA", (card_w, card_h), color_rgb + (255,))
    mask = get_rounded_mask_np(card_w, card_h, radius)
    plaque.putalpha(Image.fromarray(mask, mode="L"))
    arr = np.array(plaque, dtype=np.uint8)
    _plaque_cache[key] = arr
    return arr


# --------------------------------------------------------------------------- #
# Fond animé (numpy) optimisé : gradient de base pré-calculé + roll pour la dérive
# --------------------------------------------------------------------------- #

_bg_base_cache: dict[tuple, np.ndarray] = {}


def _get_bg_base(width: int, height: int) -> np.ndarray:
    """Pré-calcule le dégradé radial de base centré (H, W, 3) uint8."""
    key = (width, height)
    if key in _bg_base_cache:
        return _bg_base_cache[key]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    radius = max(width, height) * 0.9
    cx = width / 2
    cy = height / 2
    dx = (xx - cx) / radius
    dy = (yy - cy) / radius
    dist = np.sqrt(dx * dx + dy * dy)
    dist = np.clip(dist, 0.0, 1.0)
    t_dist = dist[:, :, np.newaxis]
    # Centre légèrement plus clair que les bords (dégradé très doux)
    inner_arr = np.array([255, 255, 255], dtype=np.float64)[np.newaxis, np.newaxis, :]
    outer_arr = np.array([245, 245, 245], dtype=np.float64)[np.newaxis, np.newaxis, :]
    grad = outer_arr * t_dist + inner_arr * (1.0 - t_dist)
    base = np.clip(grad, 0, 255).astype(np.uint8)
    _bg_base_cache[key] = base
    return base


_grain_cache: dict[tuple[int, int], np.ndarray] = {}


def draw_background_np(f: int, width: int, height: int, palette) -> np.ndarray:
    t = f / FPS
    base = _get_bg_base(width, height)
    arr = base.astype(np.float32)

    # Dérive du dégradé via roll (déplacement circulaire, pas de récalcul)
    drift = math.sin(2.0 * math.pi * t / 8.0)
    shift_x = int(drift * width * 0.05)
    shift_y = int(math.cos(2.0 * math.pi * t / 8.0) * height * 0.05)
    if shift_x or shift_y:
        arr = np.roll(arr, shift_x, axis=1)
        arr = np.roll(arr, shift_y, axis=0)

    # Variation de luminosité max 3 %
    var = 0.03 * math.sin(2.0 * math.pi * t / 8.0)
    arr = arr * np.float32(1.0 + var)

    # Si palette sombre, inverser le dégradé
    if palette.bg == "#000000":
        arr = 255.0 - arr

    arr = np.clip(arr, 0, 255)

    # Grain fin à 1/4 de résolution puis répété (16x plus rapide, imperceptible)
    grain_key = (width, height)
    if grain_key not in _grain_cache:
        rng = np.random.RandomState(SEED)
        _grain_cache[grain_key] = (
            rng.standard_normal((max(1, height // 4), max(1, width // 4), 1))
            * 255 * 0.015
        ).astype(np.float32)
    grain_source = _grain_cache[grain_key]
    grain_small = np.roll(grain_source, (f % grain_source.shape[0], (f * 2) % grain_source.shape[1]), axis=(0, 1))
    grain = np.repeat(np.repeat(grain_small, 4, axis=0), 4, axis=1)[:height, :width]
    grain = np.clip(grain, -32, 32)
    arr = np.clip(arr + grain, 0, 255).astype(np.uint8)
    return arr


# --------------------------------------------------------------------------- #
# Alpha-blending numpy : colle un sprite RGBA sur un canvas RGB à (x, y)
# --------------------------------------------------------------------------- #

def composite_sprite(canvas: np.ndarray, sprite: np.ndarray,
                     x: int, y: int, opacity: float = 1.0) -> None:
    """Compose sprite (h, w, 4) RGBA onto canvas (H, W, 3) RGB at (x, y).
    Modifie canvas en place."""
    h, w = sprite.shape[:2]
    H, W = canvas.shape[:2]

    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)

    if x0 >= x1 or y0 >= y1:
        return

    # Région du sprite à utiliser
    sx0 = x0 - x
    sy0 = y0 - y
    spr = sprite[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    region = canvas[y0:y1, x0:x1]

    alpha = spr[:, :, 3:4].astype(np.float32) / 255.0 * opacity
    rgb = spr[:, :, :3].astype(np.float32)
    region_f = region.astype(np.float32)

    blended = region_f * (1.0 - alpha) + rgb * alpha
    canvas[y0:y1, x0:x1] = np.clip(blended, 0, 255).astype(np.uint8)


def make_motion_accent_np(width: int, height: int, color: tuple[int, int, int],
                          progress: float) -> np.ndarray:
    """Barre d'accent animée pour les mots emphasis/strong."""
    progress = max(0.0, min(1.0, progress))
    bar_h = max(6, int(height * 0.045))
    bar_w = max(8, int(width * progress))
    sprite = Image.new("RGBA", (width, bar_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)
    radius = max(2, bar_h // 2)
    draw.rounded_rectangle([0, 0, bar_w, bar_h], radius=radius,
                           fill=color + (210,))
    return np.array(sprite, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# Affine scale + translate sur un sprite numpy (sub-pixel via sous-échantillonnage)
# --------------------------------------------------------------------------- #

def scale_translate_sprite(sprite: np.ndarray, scale: float,
                           tx: float, ty: float) -> np.ndarray:
    """Retourne une copie du sprite scalée/translatée.
    Évite la resize PIL quand scale ≈ 1.0 (seule la translation est appliquée par découpage numpy)."""
    if abs(scale - 1.0) < 0.01 and tx == 0.0 and ty == 0.0:
        return sprite

    if abs(scale - 1.0) < 0.01:
        # Seulement translation : découpage numpy (pas de resize PIL)
        h, w = sprite.shape[:2]
        # Translation par roll + bordures (approximation sub-pixel via shift entier)
        ix = int(round(tx))
        iy = int(round(ty))
        rolled = np.roll(sprite, ix, axis=1)
        rolled = np.roll(rolled, iy, axis=0)
        if ix > 0:
            rolled[:, :ix] = 0
        elif ix < 0:
            rolled[:, ix:] = 0
        if iy > 0:
            rolled[:iy, :] = 0
        elif iy < 0:
            rolled[iy:, :] = 0
        return rolled

    img = Image.fromarray(sprite, mode="RGBA")
    h, w = sprite.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    scaled = img.resize((new_w, new_h), Image.LANCZOS)
    arr = np.array(scaled, dtype=np.uint8)
    return arr


# --------------------------------------------------------------------------- #
# Micro-animations
# --------------------------------------------------------------------------- #

def word_float_y(f: int) -> float:
    return WORD_FLOAT_AMPLITUDE * math.sin(2.0 * math.pi * (f / FPS) / WORD_FLOAT_PERIOD)


def word_breath_scale(f: int) -> float:
    t = (f / FPS) / WORD_BREATH_PERIOD
    phase = (math.sin(2.0 * math.pi * t) + 1.0) / 2.0
    return WORD_BREATH_MIN + (WORD_BREATH_MAX - WORD_BREATH_MIN) * phase


def card_float_y(f: int) -> float:
    return CARD_FLOAT_AMPLITUDE * math.sin(2.0 * math.pi * (f / FPS) / CARD_FLOAT_PERIOD)


def card_zoom_scale(f: int, alternate: bool = False) -> float:
    t = (f / FPS) / CARD_ZOOM_PERIOD
    phase = (math.sin(2.0 * math.pi * t) + 1.0) / 2.0
    if alternate:
        phase = 1.0 - phase
    return CARD_ZOOM_MIN + (CARD_ZOOM_MAX - CARD_ZOOM_MIN) * phase


# --------------------------------------------------------------------------- #
# Glitch
# --------------------------------------------------------------------------- #

def apply_glitch_np(canvas: np.ndarray, f: int, invert_frame: int,
                    glitch_frames: int, width: int) -> np.ndarray:
    offset = f - invert_frame
    if offset <= 0 or offset > glitch_frames:
        return canvas

    arr = canvas.copy()

    if offset == 1:
        arr = np.clip(arr.astype(np.int16) + 128, 0, 255).astype(np.uint8)
        return arr

    shift = GLITCH_RGB_SHIFT * width // 1080
    if offset in (2, 3):
        arr[:, :, 0] = np.roll(arr[:, :, 0], shift, axis=1)
        arr[:, :, 2] = np.roll(arr[:, :, 2], -shift, axis=1)

    band_shift = GLITCH_BAND_SHIFT * width // 1080
    if offset in (2, 4):
        h = arr.shape[0]
        band1 = h // 3
        band2 = 2 * h // 3
        arr[band1:band1 + 4, :] = np.roll(arr[band1:band1 + 4, :], band_shift, axis=1)
        arr[band2:band2 + 4, :] = np.roll(arr[band2:band2 + 4, :], -band_shift, axis=1)

    return arr


def apply_flash_np(canvas: np.ndarray, offset: int) -> np.ndarray:
    """Flash court et contrôlé pour une transition premium/énergique."""
    intensity_by_frame = {0: 0.72, 1: 0.34, 2: 0.12}
    intensity = intensity_by_frame.get(offset, 0.0)
    if intensity <= 0.0:
        return canvas
    white = np.full_like(canvas, 255, dtype=np.uint8)
    return np.clip(
        canvas.astype(np.float32) * (1.0 - intensity)
        + white.astype(np.float32) * intensity,
        0, 255,
    ).astype(np.uint8)


def apply_wipe_np(canvas: np.ndarray, offset: int) -> np.ndarray:
    """Accent vertical animé pour une transition directionnelle légère."""
    progress = min(max((offset + 1) / 3.0, 0.0), 1.0)
    x = int(canvas.shape[1] * progress)
    band = max(2, canvas.shape[1] // 180)
    result = canvas.copy()
    left = max(0, x - band)
    right = min(canvas.shape[1], x + band)
    result[:, left:right] = np.clip(
        result[:, left:right].astype(np.float32) * 0.35 + 255.0 * 0.65,
        0, 255,
    ).astype(np.uint8)
    return result


def apply_zoom_cut_np(canvas: np.ndarray, offset: int) -> np.ndarray:
    """Zoom cut court, centré et borné à trois frames."""
    zoom = {0: 1.10, 1: 1.06, 2: 1.02}.get(offset, 1.0)
    if zoom == 1.0:
        return canvas
    h, w = canvas.shape[:2]
    image = Image.fromarray(canvas, mode="RGB")
    resized = image.resize((int(w * zoom), int(h * zoom)), Image.Resampling.BILINEAR)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return np.array(resized.crop((left, top, left + w, top + h)), dtype=np.uint8)


def apply_blur_reveal_np(canvas: np.ndarray, offset: int) -> np.ndarray:
    """Révélation floue courte, réservée aux transitions brèves."""
    radius = {0: 4.0, 1: 2.0, 2: 0.5}.get(offset, 0.0)
    if radius <= 0.0:
        return canvas
    image = Image.fromarray(canvas, mode="RGB").filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(image, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# Contenu carte B-roll (demo : dégradés colorés)
# --------------------------------------------------------------------------- #

_demo_card_cache: dict[int, np.ndarray] = {}


def make_demo_card_np(size_key: str, width: int) -> np.ndarray:
    import colorsys

    if size_key == "small":
        cw = int(CARD_SMALL_WIDTH * width / 1080)
        ch = cw
    elif size_key == "large":
        cw = int(CARD_LARGE_WIDTH * width / 1080)
        ch = int(cw * 1.25)
    else:
        cw = int(CARD_MEDIUM_WIDTH * width / 1080)
        ch = int(cw * 1.25)

    key = (size_key, width)
    if key not in _demo_card_cache:
        t = (time.time() % 5.0)
        hue = (t / 5.0 + 0.3) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.6, 0.9)
        color = tuple(int(c * 255) for c in rgb)

        card = np.full((ch, cw, 3), color, dtype=np.uint8)
        # Petite forme géométrique
        cy_, cx_ = ch // 2, cw // 2
        sz = min(cw, ch) // 4
        yy, xx = np.mgrid[0:ch, 0:cw]
        mask = (xx - cx_) ** 2 + (yy - cy_) ** 2 <= sz ** 2
        card[mask] = tuple(int(c * 255 * 0.7) for c in rgb)
        _demo_card_cache[key] = card
    return _demo_card_cache[key].copy()


_VIDEO_FRAME_COUNT = 12
_video_frames_cache: dict[tuple[str, int, int, int], list[np.ndarray]] = {}


def load_card_content_np(source: str, size_key: str, width: int, demo: bool,
                         frame_index: int = 0) -> np.ndarray:
    if demo:
        return make_demo_card_np(size_key, width)

    path = Path(source)
    if path.exists() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        img = Image.open(path).convert("RGB")
    elif path.exists() and path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        frames = _extract_video_frames(path, size_key, width)
        img = Image.fromarray(frames[frame_index % len(frames)], mode="RGB")
    else:
        img = Image.new("RGB", (400, 500), (200, 200, 200))

    if size_key == "small":
        cw = int(CARD_SMALL_WIDTH * width / 1080)
        ch = cw
    elif size_key == "large":
        cw = int(CARD_LARGE_WIDTH * width / 1080)
        ch = int(cw * 1.25)
    else:
        cw = int(CARD_MEDIUM_WIDTH * width / 1080)
        ch = int(cw * 1.25)

    img = ImageOps.fit(img, (cw, ch), method=Image.LANCZOS)
    return np.array(img, dtype=np.uint8)


def _card_dimensions(size_key: str, width: int) -> tuple[int, int]:
    if size_key == "small":
        cw = int(CARD_SMALL_WIDTH * width / 1080)
        ch = cw
    elif size_key == "large":
        cw = int(CARD_LARGE_WIDTH * width / 1080)
        ch = int(cw * 1.25)
    else:
        cw = int(CARD_MEDIUM_WIDTH * width / 1080)
        ch = int(cw * 1.25)
    return cw, ch


def _extract_video_frames(video_path: Path, size_key: str, width: int) -> list[np.ndarray]:
    """Pré-extrait une courte séquence de frames pour animer une carte vidéo."""
    cw, ch = _card_dimensions(size_key, width)
    key = (str(video_path), size_key, width, _VIDEO_FRAME_COUNT)
    if key in _video_frames_cache:
        return _video_frames_cache[key]

    fallback = np.full((ch, cw, 3), 200, dtype=np.uint8)
    try:
        vf = (
            f"fps=6,scale={cw}:{ch}:force_original_aspect_ratio=increase,"
            f"crop={cw}:{ch}"
        )
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video_path), "-t", "2.0",
             "-vf", vf, "-frames:v", str(_VIDEO_FRAME_COUNT),
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, timeout=30, check=False,
        )
        frame_size = cw * ch * 3
        raw = proc.stdout
        frames = [
            np.frombuffer(raw[offset:offset + frame_size], dtype=np.uint8).reshape(ch, cw, 3).copy()
            for offset in range(0, len(raw) - frame_size + 1, frame_size)
        ]
        if frames:
            while len(frames) < _VIDEO_FRAME_COUNT:
                frames.append(frames[-1].copy())
            _video_frames_cache[key] = frames[:_VIDEO_FRAME_COUNT]
            return _video_frames_cache[key]
    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    _video_frames_cache[key] = [fallback.copy() for _ in range(_VIDEO_FRAME_COUNT)]
    return _video_frames_cache[key]


# --------------------------------------------------------------------------- #
# Sprite carte complète (cache : source, size, width, palette bg)
# --------------------------------------------------------------------------- #

_card_sprite_cache: dict[tuple, np.ndarray] = {}


_card_zoom_cache: dict[tuple, np.ndarray] = {}


def render_card_sprite_np(source: str, size_key: str, width: int, palette_bg: str,
                          demo: bool, frame_index: int = 0) -> np.ndarray:
    """Sprite carte RGBA (h, w, 4) avec masque, ombre, contenu (zoom=1)."""
    key = (source, size_key, width, palette_bg, demo, frame_index)
    if key in _card_sprite_cache:
        return _card_sprite_cache[key]

    if size_key == "small":
        cw = int(CARD_SMALL_WIDTH * width / 1080)
        ch = cw
    elif size_key == "large":
        cw = int(CARD_LARGE_WIDTH * width / 1080)
        ch = int(cw * 1.25)
    else:
        cw = int(CARD_MEDIUM_WIDTH * width / 1080)
        ch = int(cw * 1.25)

    radius = int(cw * CARD_RADIUS_RATIO)
    content = load_card_content_np(source, size_key, width, demo, frame_index)

    # Canvas RGBA
    card = np.zeros((ch, cw, 4), dtype=np.uint8)

    if demo and size_key == "small":
        plaque = get_plaque_np(cw, ch, radius, hex_to_rgb("#F4F4F4" if palette_bg == "#FDFDFD" else "#171717"))
        card[:, :, :3] = plaque[:, :, :3]
        card[:, :, 3] = plaque[:, :, 3]
        card[:, :, :3] = content[:, :, :3]

    # Masque arrondi sur le contenu
    mask = get_rounded_mask_np(cw, ch, radius)
    content_rgba = np.dstack([content, mask])
    card[:, :, :3] = content_rgba[:, :, :3]
    card[:, :, 3] = mask

    # Ombre
    shadow_alpha = SHADOW_ALPHA_LIGHT if palette_bg == "#FDFDFD" else SHADOW_ALPHA_DARK
    shadow = get_shadow_np(cw, ch, radius, shadow_alpha)

    # Composite final : ombre décalée + carte
    final = np.zeros((ch, cw, 4), dtype=np.uint8)
    oy = int(SHADOW_OFFSET_Y)
    composite_sprite_np_inplace(final, shadow, 0, oy, opacity=1.0)
    composite_sprite_np_inplace(final, card, 0, 0, opacity=1.0)

    _card_sprite_cache[key] = final
    return final


def get_zoomed_card_sprite(source: str, size_key: str, width: int, palette_bg: str,
                           demo: bool, zoom: float, frame_index: int = 0) -> np.ndarray:
    """Retourne le sprite carte avec zoom appliqué (cache par zoom arrondi)."""
    key = (source, size_key, width, palette_bg, demo, round(zoom, 2), frame_index)
    if key in _card_zoom_cache:
        return _card_zoom_cache[key]

    base = render_card_sprite_np(source, size_key, width, palette_bg, demo, frame_index)
    if abs(zoom - 1.0) < 0.005:
        _card_zoom_cache[key] = base
        return base
    zoomed = scale_translate_sprite(base, zoom, 0.0, 0.0)
    _card_zoom_cache[key] = zoomed
    return zoomed


def composite_sprite_np_inplace(canvas: np.ndarray, sprite: np.ndarray,
                                x: int, y: int, opacity: float = 1.0) -> None:
    """Version inplace de composite_sprite pour canvas RGBA."""
    h, w = sprite.shape[:2]
    H, W = canvas.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    sx0 = x0 - x
    sy0 = y0 - y
    spr = sprite[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    region = canvas[y0:y1, x0:x1]
    alpha = spr[:, :, 3:4].astype(np.float32) / 255.0 * opacity
    rgb = spr[:, :, :3].astype(np.float32)
    region_f = region[:, :, :3].astype(np.float32)
    blended = region_f * (1.0 - alpha) + rgb * alpha
    region[:, :, :3] = np.clip(blended, 0, 255).astype(np.uint8)
    # Alpha du canvas : on prend le max
    region[:, :, 3] = np.maximum(region[:, :, 3], spr[:, :, 3])


# --------------------------------------------------------------------------- #
# Éléments actifs
# --------------------------------------------------------------------------- #

def find_active_word(tl: Timeline, t: float) -> WordEvent | None:
    for w in tl.words:
        if w.start <= t <= w.end:
            hidden = any(c.start <= t <= c.start + c.duration for c in tl.cards)
            if not hidden:
                return w
    return None


def find_active_card(tl: Timeline, t: float) -> CardEvent | None:
    for c in tl.cards:
        if c.start <= t <= c.start + c.duration:
            return c
    return None


# --------------------------------------------------------------------------- #
# Transform entrée/sortie
# --------------------------------------------------------------------------- #

def compute_element_transform(f: int, enter_side: str, exit_side: str,
                              start_frame: int, end_frame: int,
                              entry_frames: int, exit_frames: int,
                              slide_px: int, motion_style: str = "premium") -> tuple[float, float, float]:
    style = get_motion_style(motion_style)
    slide_px = style.card_slide if slide_px == CARD_ENTRY_SLIDE else slide_px
    rel = f - start_frame
    side = 1 if enter_side == "right" else -1
    scale_val = 1.0
    offset_x = 0.0
    opacity = 1.0

    if rel < entry_frames:
        te = rel / entry_frames
        ease = entry_progress(te, style)
        scale_val = 0.96 + 0.04 * ease if style.name == "premium" else 0.90 + 0.10 * ease
        opacity = ease_out_cubic(min(te * entry_frames / 6.0, 1.0)) if entry_frames > 6 else ease_out_cubic(te)
        offset_x = side * slide_px * (1.0 - ease_out_cubic(te))
        return (scale_val, offset_x, opacity)

    if rel < entry_frames + (end_frame - start_frame - exit_frames):
        return (1.0, 0.0, 1.0)

    exit_rel = f - end_frame + exit_frames
    if exit_rel < exit_frames:
        te = exit_rel / exit_frames
        progress = exit_progress(te, style)
        opacity = 1.0 - progress
        offset_x = side * slide_px * progress
        return (1.0, offset_x, opacity)

    return (1.0, 0.0, 0.0)


# --------------------------------------------------------------------------- #
# Rendu principal (numpy)
# --------------------------------------------------------------------------- #

def render_timeline(tl: Timeline, mix_path: Path, out_path: Path, width: int,
                    height: int, demo: bool = False, debug: bool = False,
                    invert_at: float | None = None, glitch_frames: int = GLITCH_FRAMES_DEFAULT,
                    nvenc: bool = False, target_lufs: float = -14.0,
                    motion_style: str = "premium", transition: str = "glitch") -> None:
    fps = FPS
    invert_frame = int(round(tl.invert.t * fps)) if tl.invert else -1
    transition_start = (
        invert_frame if transition in ("flash", "wipe", "zoom", "blur") else invert_frame + 1
    ) if invert_frame >= 0 else -1
    transition_end = (
        invert_frame + 2 if transition in ("flash", "wipe", "zoom", "blur") else invert_frame + glitch_frames
    ) if invert_frame >= 0 else -1

    total_frames = tl.frames
    start_time = time.time()

    font_normal = get_font(int(TEXT_SIZE_NORMAL * width / 1080))
    font_emphasis = get_font(int(TEXT_SIZE_EMPHASIS * width / 1080))
    font_strong = get_font(int(TEXT_SIZE_STRONG * width / 1080))

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-r", str(fps), "-i", "-",
        "-i", str(mix_path),
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "h264_nvenc" if nvenc else "libx264",
        "-preset", "veryfast" if width <= PREVIEW_WIDTH else "medium", "-crf", "18", "-profile:v", "high",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11,alimiter=limit=0.89",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_SAMPLE_RATE),
        "-t", str(tl.duration), "-movflags", "+faststart", str(out_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    word_start_frames = {id(w): int(round(w.start * fps)) for w in tl.words}
    card_start_frames = {id(c): int(round(c.start * fps)) for c in tl.cards}

    # Indexation une fois par rendu : évite de reparcourir tous les événements
    # à chaque frame, surtout sur les scripts longs.
    active_words: list[WordEvent | None] = [None] * total_frames
    active_cards: list[CardEvent | None] = [None] * total_frames
    for w in tl.words:
        start = max(0, int(math.floor(w.start * fps)))
        end = min(total_frames - 1, int(math.ceil(w.end * fps)))
        for frame in range(start, end + 1):
            if active_words[frame] is None:
                active_words[frame] = w
    for c in tl.cards:
        start = max(0, int(math.floor(c.start * fps)))
        end = min(total_frames - 1, int(math.ceil((c.start + c.duration) * fps)))
        for frame in range(start, end + 1):
            if active_cards[frame] is None:
                active_cards[frame] = c

    card_index_counter = 0

    for f in range(total_frames):
        t = f / fps

        if invert_frame >= 0 and f >= invert_frame:
            palette = PALETTE_DARK
        else:
            palette = PALETTE_LIGHT

        # Fond (numpy)
        canvas = draw_background_np(f, width, height, palette)

        active_card = active_cards[f]
        active_word = None if active_card is not None else active_words[f]

        cta_active = bool(tl.cta and t >= tl.cta.start)

        if active_card is not None:
            c = active_card
            start_f = card_start_frames.get(id(c), int(round(c.start * fps)))
            dur_frames = int(round(c.duration * fps))
            end_f = start_f + dur_frames

            scale_val, offset_x, opacity = compute_element_transform(
                f, c.enter_side, c.exit_side, start_f, end_f,
                CARD_ENTRY_FRAMES, CARD_EXIT_FRAMES, CARD_ENTRY_SLIDE,
                motion_style=motion_style)

            # Mouvement de caméra léger et séquence de frames pour les B-rolls vidéo.
            zoom = card_zoom_scale(f)
            frame_index = 0
            if Path(c.source).suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
                clip_progress = min(max((t - c.start) / 2.0, 0.0), 1.0)
                frame_index = int(round(clip_progress * (_VIDEO_FRAME_COUNT - 1)))
            float_y = card_float_y(f)

            card_sprite = get_zoomed_card_sprite(c.source, c.size, width, palette.bg,
                                                  demo, zoom * scale_val, frame_index)

            if opacity < 1.0:
                # Applique l'opacité sur le alpha
                card_sprite = card_sprite.copy()
                card_sprite[:, :, 3] = np.clip(card_sprite[:, :, 3].astype(np.float32) * opacity, 0, 255).astype(np.uint8)

            cx = int(CARD_POS_X * width / 1080 + offset_x)
            cy = int(CARD_POS_Y * width / 1080 + float_y)
            paste_x = cx - card_sprite.shape[1] // 2
            paste_y = cy - card_sprite.shape[0] // 2

            composite_sprite(canvas, card_sprite, paste_x, paste_y, opacity=1.0)
            card_index_counter += 1

        elif active_word is not None:
            w = active_word
            start_f = word_start_frames.get(id(w), int(round(w.start * fps)))
            rel = f - start_f

            if rel < WORD_ENTRY_FRAMES:
                te = rel / WORD_ENTRY_FRAMES
                style = get_motion_style(motion_style)
                ease = entry_progress(te, style)
                scale_val = 0.96 + 0.04 * ease if style.name == "premium" else 0.90 + 0.10 * ease
                opacity_word = ease_out_cubic(te)
                word_slide = style.word_slide * width / 1080
                offset_x = (1 if w.enter_side == "right" else -1) * word_slide * (1.0 - ease_out_cubic(te))
            else:
                scale_val = word_breath_scale(f)
                opacity_word = 1.0
                offset_x = 0.0

            float_y = word_float_y(f)

            if w.size_level == "strong":
                size_px = int(TEXT_SIZE_STRONG * width / 1080)
            elif w.size_level == "emphasis":
                size_px = int(TEXT_SIZE_EMPHASIS * width / 1080)
            else:
                size_px = int(TEXT_SIZE_NORMAL * width / 1080)

            text_color = hex_to_rgb(palette.text)
            sprite_np = render_text_sprite_np(w.text.upper(), size_px, text_color)

            if scale_val != 1.0 or offset_x != 0.0 or float_y != 0.0:
                sprite_np = scale_translate_sprite(sprite_np, scale_val, offset_x, float_y)

            if opacity_word < 1.0:
                sprite_np = sprite_np.copy()
                sprite_np[:, :, 3] = np.clip(sprite_np[:, :, 3].astype(np.float32) * opacity_word, 0, 255).astype(np.uint8)

            tx = int(TEXT_POS_X * width / 1080 + offset_x)
            ty = int(TEXT_POS_Y * width / 1080 + float_y)
            paste_x = tx - sprite_np.shape[1] // 2
            paste_y = ty - sprite_np.shape[0] // 2

            if w.size_level in ("emphasis", "strong"):
                accent_progress = 1.0 if rel >= WORD_ENTRY_FRAMES else ease_out_cubic(rel / max(1, WORD_ENTRY_FRAMES))
                accent_color = hex_to_rgb("#FF5A36" if palette.bg == "#FDFDFD" else "#35D0FF")
                accent = make_motion_accent_np(sprite_np.shape[1], sprite_np.shape[0], accent_color, accent_progress)
                accent_y = paste_y + sprite_np.shape[0] - accent.shape[0] // 2
                composite_sprite(canvas, accent, paste_x, accent_y, opacity=0.75)

            composite_sprite(canvas, sprite_np, paste_x, paste_y, opacity=1.0)

        elif cta_active:
            cta = tl.cta
            cta_start_f = int(round(cta.start * fps))
            rel = f - cta_start_f

            if rel < CTA_ENTRY_FRAMES:
                te = rel / CTA_ENTRY_FRAMES
                ease = ease_out_cubic(te)
                scale_val = 1.0
                offset_y = -CTA_SLIDE_UP * width / 1080 * (1.0 - ease)
                opacity_cta = ease
            else:
                phase = (math.sin(2.0 * math.pi * (f / FPS) / CTA_BREATH_PERIOD) + 1.0) / 2.0
                scale_val = CTA_BREATH_MIN + (CTA_BREATH_MAX - CTA_BREATH_MIN) * phase
                offset_y = 0.0
                opacity_cta = 1.0

            size_px = int(CTA_SIZE * width / 1080)
            text_color = hex_to_rgb(palette.text)
            sprite_np = render_text_sprite_np(cta.text.upper(), size_px, text_color)

            if offset_y != 0.0 or scale_val != 1.0:
                sprite_np = scale_translate_sprite(sprite_np, scale_val, 0.0, offset_y)

            if opacity_cta < 1.0:
                sprite_np = sprite_np.copy()
                sprite_np[:, :, 3] = np.clip(sprite_np[:, :, 3].astype(np.float32) * opacity_cta, 0, 255).astype(np.uint8)

            tx = int(TEXT_POS_X * width / 1080)
            ty = int(TEXT_POS_Y * width / 1080 - 60 * width / 1080 + offset_y)
            paste_x = tx - sprite_np.shape[1] // 2
            paste_y = ty - sprite_np.shape[0] // 2

            composite_sprite(canvas, sprite_np, paste_x, paste_y, opacity=1.0)

        # Transition autour de l'inversion.
        if transition_start >= 0 and transition_start <= f <= transition_end:
            offset = f - invert_frame
            if transition == "flash":
                canvas = apply_flash_np(canvas, offset)
            elif transition == "wipe":
                canvas = apply_wipe_np(canvas, offset)
            elif transition == "zoom":
                canvas = apply_zoom_cut_np(canvas, offset)
            elif transition == "blur":
                canvas = apply_blur_reveal_np(canvas, offset)
            elif transition == "glitch":
                canvas = apply_glitch_np(canvas, f, invert_frame, glitch_frames, width)

        # Écriture
        proc.stdin.write(canvas.tobytes())

        if f % 30 == 0 or f == total_frames - 1:
            elapsed = time.time() - start_time
            fps_render = (f + 1) / max(elapsed, 0.001)
            sys.stdout.write(f"\r  Rendu frame {f + 1}/{total_frames} ({fps_render:.1f} img/s)")
            sys.stdout.flush()

    sys.stdout.write("\n")

    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read().decode(errors="ignore")
        print(f"FFmpeg erreur (code {proc.returncode}): {stderr[-1000:]}", file=sys.stderr)
        sys.exit(1)

    print(f"  Vidéo écrite : {out_path} ({total_frames} frames, {tl.duration:.2f}s)")
