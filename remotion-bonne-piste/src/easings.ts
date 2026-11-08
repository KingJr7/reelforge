/** Easing functions — identical to CSS cubic-bezier (same as motion-kit engine.js) */
const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function bezier(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;

  const X = (t: number) => ((ax * t + bx) * t + cx) * t;
  const Y = (t: number) => ((ay * t + by) * t + cy) * t;
  const dX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;

  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const e = X(t) - x;
      if (Math.abs(e) < 1e-6) return Y(t);
      const d = dX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= e / d;
    }
    let lo = 0;
    let hi = 1;
    t = x;
    while (lo < hi) {
      const v = X(t);
      if (Math.abs(v - x) < 1e-6) break;
      v < x ? (lo = t) : (hi = t);
      t = (lo + hi) / 2;
      if (hi - lo < 1e-7) break;
    }
    return Y(t);
  };
}

export const ease = {
  outExpo: bezier(0.16, 1, 0.3, 1),
  outCubic: bezier(0.215, 0.61, 0.355, 1),
  outBack: bezier(0.34, 1.56, 0.64, 1),
  inCubic: bezier(0.32, 0, 0.67, 0),
  inOut: bezier(0.65, 0, 0.35, 1),
  sine: bezier(0.37, 0, 0.63, 1),
};

/** Keyframes interpolation: kf(t, frames, easing) -> [values] */
export function keyframes(
  t: number,
  frames: number[][],
  easing: (x: number) => number = ease.sine
): number[] {
  if (t <= frames[0][0]) return frames[0].slice(1);
  const last = frames[frames.length - 1];
  if (t >= last[0]) return last.slice(1);
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i];
    const b = frames[i + 1];
    if (t >= a[0] && t <= b[0]) {
      const p = easing((t - a[0]) / (b[0] - a[0]));
      return a.slice(1).map((v, k) => lerp(v, b[k + 1], p));
    }
  }
  return last.slice(1);
}

/** Mot-clé emphasis keyframes (from motion-kit §4.6) */
export const EM_KEYFRAMES: number[][] = [
  [0.00, 2.40, 0.00, 12, -5],
  [0.03, 2.30, 0.55, 8, -4],
  [0.07, 2.10, 0.60, 6, -3],
  [0.10, 1.30, 0.85, 2, -1],
  [0.13, 0.62, 1.00, 0, 0],
  [0.20, 0.52, 1.00, 0, 0],
  [0.27, 0.85, 1.00, 0, 0],
  [0.30, 1.10, 1.00, 0, 0],
  [0.35, 1.20, 1.00, 0, 0],
  [0.43, 1.05, 1.00, 0, 0],
  [0.50, 0.97, 1.00, 0, 0],
  [0.60, 1.00, 1.00, 0, 0],
];
export const EM_LEN = EM_KEYFRAMES[EM_KEYFRAMES.length - 1][0];

export function fmt(n: number, sep = "\u202F"): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, sep);
}
