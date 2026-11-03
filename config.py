"""Configuration centrale : palettes, tailles, durées, chemins, variables d'environnement."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --- Dossiers du projet -----------------------------------------------------
ROOT = Path(__file__).resolve().parent
FONTS_DIR = ROOT / "fonts"
ASSETS_DIR = ROOT / "assets"
SFX_DIR = ASSETS_DIR / "sfx"
ICONS_DIR = ASSETS_DIR / "icons"
CACHE_DIR = ROOT / "cache"
OUT_DIR = ROOT / "out"
SCRIPTS_DIR = ROOT / "scripts"

VOICE_CACHE_DIR = CACHE_DIR / "voice"
BROLL_CACHE_DIR = CACHE_DIR / "broll"

# --- Sortie par défaut ------------------------------------------------------
FPS = 30
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
PREVIEW_WIDTH = 540
PREVIEW_HEIGHT = 960
AUDIO_SAMPLE_RATE = 48000


def scale(px: int, width: int) -> float:
    """Applique le facteur d'échelle S = largeur_sortie / 1080 à une valeur en pixels."""
    return px * (width / 1080.0)


# --- Palettes ---------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    bg: str          # couleur de fond
    text: str        # couleur du texte
    shadow: str      # ombre des cartes
    icon_plate: str  # plaque derrière les icônes alpha


PALETTE_LIGHT = Palette(bg="#FDFDFD", text="#000000", shadow="#000000", icon_plate="#F4F4F4")
PALETTE_DARK = Palette(bg="#000000", text="#FFFFFF", shadow="#FFFFFF", icon_plate="#171717")


# --- Tailles de texte (en px pour 1080 de large) ---------------------------
TEXT_SIZE_NORMAL = 54
TEXT_SIZE_EMPHASIS = 76
TEXT_SIZE_STRONG = 110

# Positions (mesurées sur la référence, pour 1080x1920)
TEXT_POS_X = 540          # centre horizontal
TEXT_POS_Y = 956          # 49,8 % de la hauteur
CARD_POS_X = 540          # centre horizontal des cartes
CARD_POS_Y = 970          # 50,4 % de la hauteur

# Tailles des cartes (largeur en px pour 1080 de large)
CARD_SMALL_WIDTH = 330     # carré pour icônes
CARD_MEDIUM_WIDTH = 600    # 4:5 -> 600x750
CARD_LARGE_WIDTH = 820     # 4:5 -> 820x1025
CARD_RADIUS_RATIO = 0.15   # rayon des coins = 15 % de la largeur

# Ombres
SHADOW_OFFSET_Y = 10       # px vers le bas
SHADOW_BLUR = 28           # px de flou
SHADOW_ALPHA_LIGHT = 0.14  # 14 % noir en phase claire
SHADOW_ALPHA_DARK = 0.05   # 5 % blanc en phase sombre

# --- Durées d'animation (en frames) ----------------------------------------
CARD_ENTRY_FRAMES = 10     # 0,33 s
CARD_EXIT_FRAMES = 6       # 0,20 s
WORD_ENTRY_FRAMES = 4      # 0,13 s
WORD_EXIT_FRAMES = 3       # 0,10 s

# --- Micro-animations -------------------------------------------------------
WORD_FLOAT_AMPLITUDE = 3       # px
WORD_FLOAT_PERIOD = 2.0        # s
WORD_BREATH_MIN = 1.00
WORD_BREATH_MAX = 1.02
WORD_BREATH_PERIOD = 2.0       # s

CARD_FLOAT_AMPLITUDE = 4       # px
CARD_FLOAT_PERIOD = 2.4        # s
CARD_ZOOM_MIN = 1.00
CARD_ZOOM_MAX = 1.08
CARD_ZOOM_PERIOD = 4.0         # s (aller-retour complet)

CARD_ENTRY_SLIDE = 140         # px de glissement horizontal à l'entrée
WORD_ENTRY_SLIDE = 48          # px de glissement horizontal à l'entrée du mot

# --- Inversion --------------------------------------------------------------
DEFAULT_INVERT_AT = 0.5        # milieu de la vidéo par défaut
GLITCH_FRAMES_DEFAULT = 4      # frames de glitch après la coupe
GLITCH_RGB_SHIFT = 14          # px de séparation des canaux
GLITCH_BAND_SHIFT = 30         # px de décalage des bandes horizontales

# --- CTA --------------------------------------------------------------------
CTA_FLOAT_AMPLITUDE = None     # défini à l'exécution (scale dépendant)
CTA_SLIDE_UP = 40              # px de montée à l'apparition
CTA_ENTRY_FRAMES = 10          # 0,33 s
CTA_MIN_DISPLAY = 1.8          # s minimum d'affichage
CTA_BREATH_MIN = 1.00
CTA_BREATH_MAX = 1.03
CTA_BREATH_PERIOD = 2.0        # s

# --- Audio ------------------------------------------------------------------
SFX_IMPACT_OFFSETS = {
    "tick": 0.0015,
    "whoosh_in": 0.20,
    "land": 0.0,
    "whoosh_out": 0.05,
    "invert": 0.55,
    "cta": 0.0,
}
TICK_VARIANTS_FREQ = [1900.0, 2150.0, 2400.0, 2000.0]
DUCK_DB_DEFAULT = -22.0
DUCK_DB_SILENCE = -12.0
BGM_PEAK_DB = -10.0
VOICE_PEAK_DB = -3.0
LUFS_TARGET = -14.0
TRUE_PEAK_LIMIT = -1.5
LIMITER_LIMIT = 0.89

# --- ElevenLabs -------------------------------------------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_STABILITY = 0.4
ELEVENLABS_SIMILARITY_BOOST = 0.8
ELEVENLABS_STYLE = 0.3
ELEVENLABS_SPEED = 1.1

# --- Pexels -----------------------------------------------------------------
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_REQUEST_DELAY = 0.3  # s entre deux requêtes

# --- Déterminisme -----------------------------------------------------------
SEED = 42


def ensure_dirs() -> None:
    for d in (CACHE_DIR, OUT_DIR, VOICE_CACHE_DIR, BROLL_CACHE_DIR, FONTS_DIR, SFX_DIR, ICONS_DIR, SCRIPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def find_font() -> str:
    """Retourne le chemin de la police Poppins-Bold, ou DejaVuSans-Bold en fallback."""
    poppins = FONTS_DIR / "Poppins-Bold.ttf"
    if poppins.exists():
        return str(poppins)
    # Fallback système
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""
