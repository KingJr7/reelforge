import * as React from "react";
import { useCurrentFrame, useVideoConfig } from "@remotion/react";
import { DESIGN } from "../constants";

export interface ProgressBarProps {
  duration: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ duration }) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const time = frame / fps;
  const width = Math.min(100, (time / duration) * 100);

  return (
    <div className="bar">
      <i style={{ width: `${width}%` }} />
    </div>
  );
};
