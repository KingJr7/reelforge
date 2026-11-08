import * as React from "react";
import { Word } from "./Word";

export interface TextBlockProps {
  words: Array<{
    t: number;
    w: string;
    em?: boolean;
    count?: { from: number; to: number; suffix: string };
  }>;
}

export const TextBlock: React.FC<TextBlockProps> = ({ words }) => {
  return (
    <div className="text">
      {words.map((w, i) => (
        <React.Fragment key={i}>
          <Word word={w.w} t={w.t} em={w.em} count={w.count} />
          {i < words.length - 1 && <span className="sp"> </span>}
        </React.Fragment>
      ))}
    </div>
  );
};
