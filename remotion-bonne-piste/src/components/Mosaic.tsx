import * as React from "react";
import { useCurrentFrame, useVideoConfig } from "@remotion/react";
import { DESIGN, ease } from "../constants";

export interface MosaicProps {
  brandSceneStart?: number;
  time: number;
}

export const Mosaic: React.FC<MosaicProps> = ({ brandSceneStart, time }) => {
  let opacity = 0;
  if (brandSceneStart !== undefined) {
    opacity = 0.9 * (1 - clamp((time - (brandSceneStart - 0.04)) / 0.2)) * (time >= brandSceneStart - 0.04 ? 1 : 0);
  }
  return <div className="mosaic" style={{ opacity: Math.max(0, opacity) }} />;
};

function clamp(x: number, a = 0, b = 1) {
  return Math.min(b, Math.max(a, x));
}
