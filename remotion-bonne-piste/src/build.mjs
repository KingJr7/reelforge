#!/usr/bin/env node
/* build.mjs — script.json + words.json -> video.json (Remotion format)
 *
 * Usage: node src/build.mjs script.json words.json video.json [--wpm 165]
 *
 * script.json : { "title": "...", "logo": "...", "brandImage": "...",
 *   "scenes": [ {"image": "...", "text": "Tu aimerais *gagner* entre [[3 000]] et [[10 000]] FCFA ?"}, ... ] }
 *   - *mot* -> mot d'emphase (violet, ressort)
 *   - [[valeur|suffixe]] -> compteur 0 -> valeur (ex: [[3 000|FCFA]])
 *   - ponctuation isolée (?!.) collée au mot précédent
 * words.json : [{ "word": "...", "start": 0.30, "end": 0.62 }, ...] (Whisper output)
 *   Without words.json: timings estimated at --wpm words per minute.
 */
import { readFileSync, writeFileSync } from "node:fs";

const [scriptPath, wordsPath, outPath] = process.argv.slice(2);
const wpmIdx = process.argv.indexOf("--wpm");
const WPM = wpmIdx > -1 ? +process.argv[wpmIdx + 1] : 165;

const script = JSON.parse(readFileSync(scriptPath, "utf8"));
const asr = wordsPath && wordsPath !== "-" ? JSON.parse(readFileSync(wordsPath, "utf8")) : null;

const norm = (s) =>
  s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/g, "");

const toks = [];
script.scenes.forEach((sc, si) => {
  const re = /\[\[([^|\]]+)(?:\|([^\]]*))?\]\]|\*([^*]+)\*|(\S+)/g;
  let m;
  while ((m = re.exec(sc.text))) {
    if (m[1]) {
      const to = parseInt(m[1].replace(/\D/g, ""), 10);
      const suf = m[2] ? "\u00A0" + m[2] : "";
      toks.push({ w: m[1] + suf, em: true, count: { from: 0, to, suffix: suf }, scene: si, n: [norm(m[1])] });
    } else if (m[3]) {
      m[3].split(/\s+/).forEach((x) => toks.push({ w: x, em: true, scene: si, n: [norm(x)] }));
    } else if (/^[?!:;»…]+$/.test(m[4]) && toks.length) {
      toks[toks.length - 1].w += "\u00A0" + m[4];
    } else {
      toks.push({ w: m[4], em: false, scene: si, n: [norm(m[4])] });
    }
  }
});

// Timings: DP alignment script <-> ASR, else estimation
if (asr) {
  const A = toks.map((t) => t.n[0]);
  const B = asr.map((a) => norm(a.word));
  const n = A.length;
  const m = B.length;
  const G = -1;
  const sc = (a, b) => (a === b ? 2 : a && b && (a.startsWith(b) || b.startsWith(a)) ? 1 : -2);
  const M = Array.from({ length: n + 1 }, () => new Float32Array(m + 1));
  for (let i = 1; i <= n; i++) M[i][0] = i * G;
  for (let j = 1; j <= m; j++) M[0][j] = j * G;
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      M[i][j] = Math.max(M[i - 1][j - 1] + sc(A[i - 1], B[j - 1]), M[i - 1][j] + G, M[i][j - 1] + G);
    }
  }
  let i = n,
    j = m;
  const map = new Array(n).fill(-1);
  while (i > 0 && j > 0) {
    if (M[i][j] === M[i - 1][j - 1] + sc(A[i - 1], B[j - 1])) {
      if (sc(A[i - 1], B[j - 1]) > 0) map[i - 1] = j - 1;
      i--;
      j--;
    } else if (M[i][j] === M[i - 1][j] + G) {
      i--;
    } else {
      j--;
    }
  }
  let last = -1;
  for (let k = 0; k <= n; k++) {
    if (k === n || map[k] >= 0) {
      const t1 = k === n ? asr[asr.length - 1].end : asr[map[k]].start;
      const t0 = last < 0 ? asr[0].start : asr[map[last]].end;
      const gap = k - last - 1;
      for (let g = 1; g <= gap; g++) toks[last + g].t = lerp(t0, t1, g / (gap + 1));
      if (k < n) toks[k].t = asr[map[k]].start;
      last = k;
    }
  }
} else {
  let t = 0.3;
  const per = 60 / WPM;
  toks.forEach((k) => {
    k.t = t;
    t += per * (0.6 + Math.min(k.w.length, 10) / 10 * 0.8);
  });
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Scenes: start = first word - 0.13s ; end = start of next scene
const scenes = script.scenes.map((s, si) => {
  const ws = toks.filter((t) => t.scene === si);
  return {
    start: Math.max(0.07, ws[0].t - 0.13),
    end: 0,
    image: s.image,
    pose: s.pose,
    words: ws.map(({ t, w, em, count }) => ({
      t: +t.toFixed(3),
      w,
      ...(em ? { em: true } : {}),
      ...(count ? { count } : {}),
    })),
  });
});
const lastWord = toks[toks.length - 1].t;
scenes.forEach((s, i) => {
  s.end = i < scenes.length - 1 ? scenes[i + 1].start : s.start + 99;
});

// Brand screen
const duration = script.duration || +(lastWord + 3.5).toFixed(2);
if (script.brandImage) {
  const bs = script.brand || {};
  const bstart = bs.start ?? Math.min(duration - 3, lastWord + 0.6);
  scenes[scenes.length - 1].end = bstart;
  scenes.push({
    type: "brand",
    start: bstart,
    end: duration,
    image: script.brandImage,
    words: bs.words || [],
  });
} else {
  scenes[scenes.length - 1].end = duration;
}

const videoJson = {
  title: script.title,
  fps: 30,
  duration,
  logo: script.logo,
  audio: script.audio || null,
  scenes,
};

writeFileSync(outPath, JSON.stringify(videoJson, null, 1));
console.log(`✔ ${outPath} — ${scenes.length} scènes, ${toks.length} mots, ${duration}s`);
