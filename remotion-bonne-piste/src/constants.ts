/** Design tokens — La Bonne Piste (mesurés sur 576×1024, factor 1.875 pour 1080×1920) */
export const DESIGN = {
  // Canvas (conception 576×1024, export 1080×1920 ×1.875)
  W: 576,
  H: 1024,
  SCALE: 1.875,
  EXPORT_W: 1080,
  EXPORT_H: 1920,

  // Palette
  BG_TOP: "#F6F2FF",
  BG_BOTTOM: "#FFFFFF",
  INK: "#11101C",
  ACCENT_A: "#7C3AED",
  ACCENT_B: "#A78BFA",
  SHADOW: "rgba(139,92,246,0.28)",
  TRACK: "rgba(124,58,237,0.14)",
  FILL: "#7C3AED",
  BRAND_BG: "#6400B0",

  // Positions (576×1024)
  LOGO_Y: 42,
  LOGO_W: 100,
  LOGO_H: 64,
  LOGO_RADIUS: 12,

  CARD_X: 20,
  CARD_Y: 138,
  CARD_W: 536,
  CARD_H: 380,
  CARD_RADIUS: 26,

  TEXT_TOP: 564,
  TEXT_PAD: 36,
  TEXT_W: 504,
  FS: 23.5,
  LH: 42,
  LETTER_SPACING: -0.3,

  BAR_X: 48,
  BAR_Y: 961,
  BAR_W: 480,
  BAR_H: 4,

  // Timings (secondes)
  CARD_ENTER: 0.45,
  CARD_EXIT: 0.20,
  CARD_SQUASH: 0.20,
  CARD_RISE: 28,
  WORD_DUR: 0.20,
  WORD_DROP: -14,
  WORD_BLUR: 4,
  COUNT_DUR: 1.15,
  ZOOM_END: 1.06,
  MOSAIC_DUR: 0.20,
  BRAND_POP_DUR: 0.50,
  BRAND_LOGO_FADE: 0.12,
} as const;
