import * as React from "react";
import { useCurrentFrame, useVideoConfig } from "@remotion/react";
import { DESIGN, ease, keyframes } from "../constants";

export interface CardProps {
  image: string;
  start: number;
  end: number;
  duration: number;
  brand?: boolean;
  pose?: { rot0?: number; rot1?: number; dx0?: number; dx1?: number; s0?: number; s1?: number; panX?: number; panY?: number };
  sceneIndex: number;
  totalScenes: number;
}

export const Card: React.FC<CardProps> = ({
  image,
  start,
  end,
  duration,
  brand = false,
  pose,
  sceneIndex,
  totalScenes,
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const time = frame / fps;

  const visible = time >= start && (time < end || sceneIndex === totalScenes - 1);
  if (!visible) return null;

  const u = clamp((time - start) / duration);
  const pIn = clamp((time - start) / DESIGN.CARD_ENTER);
  const pOut = sceneIndex === totalScenes - 1 ? 0 : clamp((time - (end - DESIGN.CARD_EXIT)) / DESIGN.CARD_EXIT);
  const drift = ease.inOut(u);

  // Auto pose (alternating rotation)
  const sgn = sceneIndex % 2 ? 1 : -1;
  const rot0 = pose?.rot0 ?? sgn * (0.9 + ((sceneIndex * 37) % 10) / 10 * 1.3);
  const rot1 = pose?.rot1 ?? -rot0 * 0.55;
  const dx0 = pose?.dx0 ?? sgn * (4 + ((sceneIndex * 13) % 7));
  const dx1 = pose?.dx1 ?? -sgn * 3;
  const s0 = pose?.s0 ?? 0.985;
  const s1 = pose?.s1 ?? 1.015;
  const panX = pose?.panX ?? sgn * 10;
  const panY = pose?.panY ?? ((sceneIndex * 5) % 3 - 1) * 4;

  let rot = lerp(rot0, rot1, drift);
  let dx = lerp(dx0, dx1, drift);
  let sx = lerp(s0, s1, drift);
  let sy = sx;
  let ty = 0;
  let opacity = 1;
  let blur = 0;

  // Entry
  if (brand) {
    const e = ease.outBack(pIn);
    sx = sy = lerp(1.18, 1, e) * sx;
    rot = lerp(-6, rot, e);
    ty = lerp(30, 0, ease.outExpo(pIn));
    opacity = clamp(pIn / 0.25);
  } else {
    const e = ease.outExpo(pIn);
    sy *= lerp(DESIGN.CARD_SQUASH, 1, e);
    ty = lerp(DESIGN.CARD_RISE, 0, e);
    rot += lerp(-3 * Math.sign(rot0 || 1), 0, e);
    opacity = clamp(pIn / 0.18);
  }

  // Exit ghost
  if (pOut > 0) {
    const q = ease.inCubic(pOut);
    opacity *= 1 - q * 0.97;
    blur = 8 * q;
    sx *= 1 + 0.03 * q;
    sy *= 1 + 0.03 * q;
    ty -= 8 * q;
  }

  // Inner image zoom + pan (Ken Burns)
  const imgZoom = lerp(1, DESIGN.ZOOM_END, u);
  const imgTx = panX * u;
  const imgTy = panY * u;

  return (
    <div
      className={`card ${brand ? "brand" : ""}`}
      style={{
        opacity,
        filter: blur ? `blur(${blur.toFixed(2)}px)` : "none",
        transform: `translate(${dx.toFixed(2)}px,${ty.toFixed(2)}px) rotate(${rot.toFixed(3)}deg) scale(${sx.toFixed(4)},${sy.toFixed(4)})`,
        visibility: "visible",
      }}
    >
      <div className="shadow" />
      <div className="clip">
        <img
          src={image}
          alt=""
          style={{
            transform: `translate(${imgTx.toFixed(2)}px,${imgTy.toFixed(2)}px) scale(${imgZoom.toFixed(4)})`,
          }}
        />
      </div>
    </div>
  );
};

function clamp(x: number, a = 0, b = 1) {
  return Math.min(b, Math.max(a, x));
}
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
