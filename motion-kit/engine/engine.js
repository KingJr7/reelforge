/* =====================================================================
 *  MOTION ENGINE — pur, déterministe : render(t) ne dépend que de t.
 *  Aucun setTimeout / requestAnimationFrame / CSS animation => capture
 *  frame-par-frame parfaite (Puppeteer / Playwright / HyperFrames / Remotion).
 * ===================================================================== */
(() => {
"use strict";

/* ---------- 0. Utilitaires mathématiques ---------- */
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp  = (a, b, t) => a + (b - a) * t;

// cubic-bezier identique au CSS (Newton + bissection)
function bezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const X = t => ((ax * t + bx) * t + cx) * t, Y = t => ((ay * t + by) * t + cy) * t;
  const dX = t => (3 * ax * t + 2 * bx) * t + cx;
  return x => {
    if (x <= 0) return 0; if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) { const e = X(t) - x; if (Math.abs(e) < 1e-6) return Y(t); const d = dX(t); if (Math.abs(d) < 1e-6) break; t -= e / d; }
    let lo = 0, hi = 1; t = x;
    while (lo < hi) { const v = X(t); if (Math.abs(v - x) < 1e-6) break; v < x ? lo = t : hi = t; t = (lo + hi) / 2; if (hi - lo < 1e-7) break; }
    return Y(t);
  };
}
const ease = {
  outExpo : bezier(.16, 1, .3, 1),      // entrée de carte (rapide puis très doux)
  outCubic: bezier(.215, .61, .355, 1), // chute des mots
  outBack : bezier(.34, 1.56, .64, 1),  // pop du logo final
  inCubic : bezier(.32, 0, .67, 0),     // sortie de scène
  inOut   : bezier(.65, 0, .35, 1),     // dérive lente de la carte
  sine    : bezier(.37, 0, .63, 1)
};

// interpolation par images-clés : kf(t,[[t0,v0..],[t1,v1..],...]) -> tableau de valeurs
function keyframes(t, frames, easing = ease.sine) {
  if (t <= frames[0][0]) return frames[0].slice(1);
  const last = frames[frames.length - 1];
  if (t >= last[0]) return last.slice(1);
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i], b = frames[i + 1];
    if (t >= a[0] && t <= b[0]) {
      const p = easing((t - a[0]) / (b[0] - a[0]));
      return a.slice(1).map((v, k) => lerp(v, b[k + 1], p));
    }
  }
}

/* ---------- 1. Constantes d'animation (mesurées sur les vidéos de référence) ---------- */
const C = {
  CARD_ENTER : 0.45,   // s — la carte « pousse » depuis le bas (squash -> 1)
  CARD_EXIT  : 0.20,   // s — fantôme flou + fondu
  CARD_SQUASH: 0.20,   // scaleY de départ
  CARD_RISE  : 28,     // px de translation de départ (vers le bas)
  WORD_DUR   : 0.20,   // s — chute d'un mot normal
  WORD_DROP  : -14,    // px — le mot arrive d'en haut
  WORD_BLUR  : 4,      // px
  COUNT_DUR  : 1.15,   // s — compteur 0 -> valeur
  ZOOM_END   : 1.06,   // zoom lent de l'image dans la carte
  // mot d'emphase : [t(s), scale, opacité, flou(px), rotation(deg)]
  EM: [
    [0.00, 2.40, 0.00, 12, -5], [0.03, 2.30, 0.55, 8, -4], [0.07, 2.10, 0.60, 6, -3],
    [0.10, 1.30, 0.85,  2, -1], [0.13, 0.62, 1.00, 0,  0], [0.20, 0.52, 1.00, 0, 0],
    [0.27, 0.85, 1.00,  0,  0], [0.30, 1.10, 1.00, 0,  0], [0.35, 1.20, 1.00, 0, 0],
    [0.43, 1.05, 1.00,  0,  0], [0.50, 0.97, 1.00, 0,  0], [0.60, 1.00, 1.00, 0, 0]
  ]
};
const EM_LEN = C.EM[C.EM.length - 1][0];

/* ---------- 2. Construction du DOM ---------- */
let V = null, S = [];          // vidéo + scènes construites
const $ = id => document.getElementById(id);
const fmt = (n, sep = "\u202F") => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, sep);

// pose « caméra » de la carte : rotation / décalage / échelle, avec dérive pendant la scène
function autoPose(i) {
  const sgn = i % 2 ? 1 : -1;
  const r0 = sgn * (0.9 + ((i * 37) % 10) / 10 * 1.3);       // ±0.9° .. ±2.2°
  return { rot0: r0, rot1: -r0 * 0.55, dx0: sgn * (4 + (i * 13) % 7), dx1: -sgn * 3, s0: 0.985, s1: 1.015,
           panX: sgn * 10, panY: ((i * 5) % 3 - 1) * 4 };
}

async function load(video) {
  V = video;
  const st = Object.assign({}, V.style || {});
  for (const k in st) document.documentElement.style.setProperty(k.startsWith("--") ? k : "--" + k, st[k]);
  $("logo").src = V.logo || ""; 
  $("cards").innerHTML = ""; $("texts").innerHTML = ""; S = [];

  V.scenes.forEach((sc, i) => {
    const brand = sc.type === "brand";
    const card = document.createElement("div");
    card.className = "card" + (brand ? " brand" : "");
    card.innerHTML = `<div class="shadow"></div><div class="clip"><img src="${sc.image}" alt=""></div>`;
    $("cards").appendChild(card);

    const box = document.createElement("div");
    box.className = "text"; box.style.visibility = "hidden";
    const words = (sc.words || []).map((w, k) => {
      const el = document.createElement("span");
      el.className = "w" + (w.em ? " em" : "");
      el.textContent = w.count ? fmt(w.count.to) + (w.count.suffix || "") : w.w;
      box.appendChild(el);
      if (k < sc.words.length - 1) box.appendChild(document.createTextNode(" "));
      return { el, w };
    });
    $("texts").appendChild(box);
    S.push({ sc, i, card, img: card.querySelector("img"), box, words, pose: Object.assign(autoPose(i), sc.pose || {}) });
  });

  // fige la largeur finale des compteurs pour éviter tout « saut » de ligne
  S.forEach(s => s.words.forEach(o => { if (o.w.count) o.el.style.width = o.el.getBoundingClientRect().width + "px"; }));
  await document.fonts.ready;
  await Promise.all([...document.images].map(im => im.decode ? im.decode().catch(() => {}) : 0));
  window.__ready = true;
}

/* ---------- 3. Rendu d'un instant t (secondes) ---------- */
function render(t) {
  const D = V.duration;

  // 3.1 barre de progression (linéaire sur toute la durée)
  $("bar").firstElementChild.style.width = (clamp(t / D) * 100) + "%";

  // 3.2 logo d'en-tête : fixe, disparaît à l'arrivée de l'écran final
  const brandScene = S.find(s => s.sc.type === "brand");
  let logoOp = 1;
  if (brandScene) logoOp = 1 - clamp((t - (brandScene.sc.start - 0.12)) / 0.15);
  $("logo").style.opacity = logoOp;

  let mosaic = 0;

  S.forEach((s, idx) => {
    const { sc, card, img, box, pose } = s;
    const start = sc.start, end = sc.end, dur = end - start;
    const isLast = idx === S.length - 1, brand = sc.type === "brand";
    const visible = t >= start && (t < end || isLast);
    card.style.opacity = 0; box.style.visibility = "hidden";
    if (!visible) { card.style.visibility = "hidden"; return; }
    card.style.visibility = "visible"; box.style.visibility = "visible";

    // --- phases ---
    const u    = clamp((t - start) / dur);                                  // 0..1 sur la scène
    const pIn  = clamp((t - start) / (brand ? 0.5 : C.CARD_ENTER));
    const pOut = isLast ? 0 : clamp((t - (end - C.CARD_EXIT)) / C.CARD_EXIT);
    const drift = ease.inOut(u);

    // --- carte : pose de base (dérive lente) ---
    let rot = lerp(pose.rot0, pose.rot1, drift);
    let dx  = lerp(pose.dx0, pose.dx1, drift);
    let sx  = lerp(pose.s0, pose.s1, drift), sy = sx;
    let ty = 0, op = 1, blur = 0;

    // --- entrée ---
    if (brand) {                       // écran logo : « pop » avec dépassement + mosaïque
      const e = ease.outBack(pIn);
      sx = sy = lerp(1.18, 1, e) * sx; rot = lerp(-6, rot, e); ty = lerp(30, 0, ease.outExpo(pIn));
      op = clamp(pIn / 0.25);
      mosaic = Math.max(mosaic, 0.9 * (1 - clamp((t - (start - 0.04)) / 0.2)) * (t >= start - 0.04 ? 1 : 0));
    } else {                           // carte photo : squash vertical depuis le bas
      const e = ease.outExpo(pIn);
      sy *= lerp(C.CARD_SQUASH, 1, e);
      ty = lerp(C.CARD_RISE, 0, e);
      rot += lerp(-3 * Math.sign(pose.rot0 || 1), 0, e);
      op = clamp(pIn / 0.18);
    }
    // --- sortie : fantôme flou ---
    if (pOut > 0) {
      const q = ease.inCubic(pOut);
      op *= 1 - q * 0.97; blur = 8 * q; sx *= 1 + 0.03 * q; sy *= 1 + 0.03 * q; ty -= 8 * q;
    }
    card.style.opacity = op;
    card.style.filter = blur ? `blur(${blur.toFixed(2)}px)` : "none";
    card.style.transform = `translate(${dx.toFixed(2)}px,${ty.toFixed(2)}px) rotate(${rot.toFixed(3)}deg) scale(${sx.toFixed(4)},${sy.toFixed(4)})`;

    // --- image à l'intérieur : lent zoom + micro-pan (« Ken Burns ») ---
    if (!brand) img.style.transform = `translate(${(pose.panX * u).toFixed(2)}px,${(pose.panY * u).toFixed(2)}px) scale(${lerp(1, C.ZOOM_END, u).toFixed(4)})`;

    // --- texte : mots apparaissent à la voix ---
    const textOut = pOut > 0 ? ease.inCubic(pOut) : 0;
    box.style.opacity = 1 - textOut; box.style.filter = textOut ? `blur(${(6 * textOut).toFixed(2)}px)` : "none";
    s.words.forEach(({ el, w }) => {
      const lt = t - w.t;
      if (lt < 0) { el.style.opacity = 0; return; }
      if (w.em) {
        const [sc2, o, b, r] = keyframes(lt, C.EM);
        el.style.opacity = o; el.style.filter = b > 0.05 ? `blur(${b.toFixed(2)}px)` : "none";
        el.style.transform = `rotate(${r.toFixed(2)}deg) scale(${sc2.toFixed(3)})`;
        el.style.setProperty("--glow", clamp((lt - 0.25) / 0.3).toFixed(3));
      } else {
        const p = clamp(lt / C.WORD_DUR), e = ease.outCubic(p);
        el.style.opacity = clamp(p * 2.4);
        el.style.filter = p < 1 ? `blur(${(C.WORD_BLUR * (1 - e)).toFixed(2)}px)` : "none";
        el.style.transform = `translateY(${(C.WORD_DROP * (1 - e)).toFixed(2)}px) rotate(${(-3 * (1 - e)).toFixed(2)}deg)`;
      }
      if (w.count) {
        const v = lerp(w.count.from || 0, w.count.to, ease.outCubic(clamp(lt / C.COUNT_DUR)));
        el.textContent = fmt(v) + (w.count.suffix || "");
      }
    });
  });

  $("mosaic").style.opacity = mosaic;
}

window.loadVideo = load;
window.__render = render;
window.__EASE = ease; window.__C = C;
})();
