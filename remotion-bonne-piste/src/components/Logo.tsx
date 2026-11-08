import * as React from "react";
import { DESIGN } from "../constants";

export interface LogoProps {
  src: string;
  brandSceneStart?: number;
  time: number;
}

export const Logo: React.FC<LogoProps> = ({ src, brandSceneStart, time }) => {
  let opacity = 1;
  if (brandSceneStart !== undefined) {
    opacity = 1 - clamp((time - (brandSceneStart - 0.12)) / 0.15);
  }
  return (
    <img
      src={src}
      alt=""
      className="logo"
      style={{
        opacity: Math.max(0, opacity),
      }}
    />
  );
};

function clamp(x: number, a = 0, b = 1) {
  return Math.min(b, Math.max(a, x));
}
