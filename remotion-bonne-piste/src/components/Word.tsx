import * as React from "react";
import { useCurrentFrame, useVideoConfig, Styles } from "@remotion/react";
import { DESIGN, ease, keyframes, EM_KEYFRAMES, EM_LEN, fmt } from "../constants";

export interface WordProps {
  word: string;
  t: number;          // start time in seconds
  em?: boolean;       // emphasis keyword
  count?: { from: number; to: number; suffix: string };
}

export const Word: React.FC<WordProps> = ({ word, t, em = false, count }) => {
  const { duration, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const time = frame / fps;

  const lt = time - t;
  if (lt < 0) {
    return <div style={{ opacity: 0 }}>{word}</div>;
  }

  if (em) {
    const [scale, opacity, blur, rotation] = keyframes(lt, EM_KEYFRAMES, ease.sine);
    const glow = lt > 0.25 ? Math.min(1, (lt - 0.25) / 0.3) : 0;
    return (
      <div
        className="w em"
        style={{
          opacity,
          filter: blur > 0.05 ? `blur(${blur}px)` : "none",
          transform: `rotate(${rotation}deg) scale(${scale})`,
          "--glow": glow.toFixed(3),
        }}
      >
        {count ? fmt(lerp(count.from, count.to, ease.outCubic(clamp(lt / DESIGN.COUNT_DUR)))) + (count.suffix || "") : word}
      </div>
    );
  }

  const p = clamp(lt / DESIGN.WORD_DUR);
  const e = ease.outCubic(p);
  return (
    <div
      className="w"
      style={{
        opacity: clamp(p * 2.4),
        filter: p < 1 ? `blur(${(DESIGN.WORD_BLUR * (1 - e)).toFixed(2)}px)` : "none",
        transform: `translateY(${(DESIGN.WORD_DROP * (1 - e)).toFixed(2)}px) rotate(${(-3 * (1 - e)).toFixed(2)}deg)`,
      }}
    >
      {word}
    </div>
  );
};

function clamp(x: number, a = 0, b = 1) {
  return Math.min(b, Math.max(a, x));
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
