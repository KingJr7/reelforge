import * as React from "react";
import { useCurrentFrame, useVideoConfig, Styles, Audio, AbsoluteFill, IFrame } from "@remotion/react";
import { Card } from "./components/Card";
import { TextBlock } from "./components/TextBlock";
import { Logo } from "./components/Logo";
import { ProgressBar } from "./components/ProgressBar";
import { Mosaic } from "./components/Mosaic";
import { DESIGN } from "./constants";

export interface Scene {
  start: number;
  end: number;
  image: string;
  type?: string;
  pose?: any;
  words: Array<{
    t: number;
    w: string;
    em?: boolean;
    count?: { from: number; to: number; suffix: string };
  }>;
}

export interface VideoJson {
  duration: number;
  fps: number;
  logo: string;
  audio?: string;
  style?: Record<string, string>;
  scenes: Scene[];
}

interface BonnePisteCompositionProps {
  video: VideoJson;
}

export const BonnePisteComposition: React.FC<BonnePisteCompositionProps> = ({ video }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const time = frame / fps;

  const brandScene = video.scenes.find((s) => s.type === "brand");
  const brandSceneStart = brandScene?.start;

  return (
    <Styles>
      {`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { width: ${DESIGN.EXPORT_W}px; height: ${DESIGN.EXPORT_H}px; overflow: hidden; background: #fff; font-family: "Poppins", system-ui, sans-serif; color: ${DESIGN.INK}; }
        #stage {
          position: relative;
          width: ${DESIGN.EXPORT_W}px;
          height: ${DESIGN.EXPORT_H}px;
          overflow: hidden;
          background: linear-gradient(180deg, ${DESIGN.BG_TOP} 0%, #FBF9FF 45%, ${DESIGN.BG_BOTTOM} 100%);
        }
        #grid {
          position: absolute; inset: 0;
          background-image: linear-gradient(${DESIGN.ACCENT_A}22 1px, transparent 1px), linear-gradient(90deg, ${DESIGN.ACCENT_A}22 1px, transparent 1px);
          background-size: 52px 52px;
          -webkit-mask-image: linear-gradient(180deg, transparent 0%, #000 55%, #000 92%, transparent 100%);
          mask-image: linear-gradient(180deg, transparent 0%, #000 55%, #000 92%, transparent 100%);
        }
        #logo {
          position: absolute; left: 50%; top: ${DESIGN.EXPORT_H * (DESIGN.LOGO_Y / DESIGN.H)}px;
          width: ${DESIGN.EXPORT_W * (DESIGN.LOGO_W / DESIGN.W)}px; height: ${DESIGN.EXPORT_H * (DESIGN.LOGO_H / DESIGN.H)}px;
          margin-left: calc(${DESIGN.EXPORT_W * (DESIGN.LOGO_W / DESIGN.W)}px / -2);
          border-radius: ${DESIGN.EXPORT_W * (DESIGN.LOGO_RADIUS / DESIGN.W)}px;
          object-fit: cover;
          box-shadow: 0 11px 30px -11px ${DESIGN.SHADOW};
        }
        .card {
          position: absolute;
          left: ${DESIGN.EXPORT_W * (DESIGN.CARD_X / DESIGN.W)}px;
          top: ${DESIGN.EXPORT_H * (DESIGN.CARD_Y / DESIGN.H)}px;
          width: ${DESIGN.EXPORT_W * (DESIGN.CARD_W / DESIGN.W)}px;
          height: ${DESIGN.EXPORT_H * (DESIGN.CARD_H / DESIGN.H)}px;
          transform-origin: 50% 100%;
          will-change: transform, opacity, filter;
          opacity: 0;
        }
        .card .shadow {
          position: absolute; inset: 0;
          border-radius: ${DESIGN.EXPORT_W * (DESIGN.CARD_RADIUS / DESIGN.W)}px;
          box-shadow: 23px 19px 53px -11px ${DESIGN.SHADOW}, 0 34px 68px -34px ${DESIGN.SHADOW};
          background: #fff;
        }
        .card .clip {
          position: absolute; inset: 0;
          border-radius: ${DESIGN.EXPORT_W * (DESIGN.CARD_RADIUS / DESIGN.W)}px;
          overflow: hidden;
          background: #ddd;
        }
        .card img {
          position: absolute; left: 0; top: 0; width: 100%; height: 100%;
          object-fit: cover;
        }
        .card.brand .clip { background: ${DESIGN.BRAND_BG}; }
        .card.brand img { object-fit: contain; }
        .text {
          position: absolute;
          left: ${DESIGN.EXPORT_W * (DESIGN.TEXT_PAD / DESIGN.W)}px;
          right: ${DESIGN.EXPORT_W * (DESIGN.TEXT_PAD / DESIGN.W)}px;
          top: ${DESIGN.EXPORT_H * (DESIGN.TEXT_TOP / DESIGN.H)}px;
          text-align: center;
          font-weight: 600;
          font-size: ${DESIGN.EXPORT_W * (DESIGN.FS / DESIGN.W)}px;
          line-height: ${DESIGN.EXPORT_H * (DESIGN.LH / DESIGN.H)}px;
          letter-spacing: ${DESIGN.LETTER_SPACING}px;
          opacity: 1;
        }
        .w {
          display: inline-block;
          white-space: pre;
          opacity: 0;
          will-change: transform, opacity, filter;
          vertical-align: baseline;
        }
        .w.em {
          font-weight: 800;
          font-size: 1.25em;
          line-height: 1;
          position: relative;
          vertical-align: -0.12em;
          background: linear-gradient(100deg, ${DESIGN.ACCENT_A} 10%, ${DESIGN.ACCENT_B} 95%);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
          -webkit-text-fill-color: transparent;
          padding: 0 0.06em;
        }
        .w.em::after {
          content: "";
          position: absolute;
          left: 4%; right: 2%; bottom: -6px;
          height: 14px;
          border-radius: 50%;
          background: rgba(167,139,250,0.38);
          filter: blur(6px);
          z-index: -1;
          opacity: var(--glow, 0);
        }
        .sp { display: inline-block; width: 0.28em; }
        #bar {
          position: absolute;
          left: ${DESIGN.EXPORT_W * (DESIGN.BAR_X / DESIGN.W)}px;
          top: ${DESIGN.EXPORT_H * (DESIGN.BAR_Y / DESIGN.H)}px;
          width: ${DESIGN.EXPORT_W * (DESIGN.BAR_W / DESIGN.W)}px;
          height: ${DESIGN.EXPORT_H * (DESIGN.BAR_H / DESIGN.H)}px;
          border-radius: 3px;
          background: ${DESIGN.TRACK};
          overflow: hidden;
        }
        #bar i {
          display: block;
          height: 100%;
          width: 0;
          border-radius: 3px;
          background: linear-gradient(90deg, ${DESIGN.FILL}, #8B5CF6);
        }
        #mosaic {
          position: absolute; inset: 0;
          opacity: 0;
          pointer-events: none;
          mix-blend-mode: multiply;
          background-image: linear-gradient(#0000 0 0), repeating-conic-gradient(#d9d3e6 0 25%, #f3f0f9 0 50%);
          background-size: 100% 100%, 45px 45px;
        }
      `}
      <AbsoluteFill>
        <div id="stage">
          <div id="grid" />
          <img id="logo" src={video.logo} alt="" />
          <div id="cards">
            {video.scenes.map((scene, i) => (
              <Card
                key={i}
                image={scene.image}
                start={scene.start}
                end={scene.end}
                duration={scene.end - scene.start}
                brand={scene.type === "brand"}
                pose={scene.pose}
                sceneIndex={i}
                totalScenes={video.scenes.length}
              />
            ))}
          </div>
          <div id="texts">
            {video.scenes.map((scene, i) => (
              <TextBlock key={i} words={scene.words} />
            ))}
          </div>
          <div id="bar"><i /></div>
          <div id="mosaic" />
          <Logo src={video.logo} brandSceneStart={brandSceneStart} time={time} />
          <Mosaic brandSceneStart={brandSceneStart} time={time} />
        </div>
      </AbsoluteFill>
      {video.audio && <Audio src={video.audio} />}
      <ProgressBar duration={video.duration} />
    </Styles>
  );
};
