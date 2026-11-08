#!/usr/bin/env node
/* Rendu déterministe : HTML -> frames (Playwright) -> MP4 (FFmpeg).
 *   node render.mjs video.json out/video.mp4 [--scale 1.875] [--fps 30] [--from 0] [--to 99999]
 *   node render.mjs video.json --stills 0.5,3,6.2           (PNG de contrôle dans out/stills/)
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { readFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf("--" + n); return i < 0 ? d : args[i + 1]; };
const [videoPath, outPath] = args.filter(a => !a.startsWith("--") && !/^[\d.,]+$/.test(a));
const scale = parseFloat(flag("scale", "1.875"));         // 576*1.875 = 1080 ; 1024*1.875 = 1920
const video = JSON.parse(readFileSync(videoPath, "utf8"));
const fps   = parseInt(flag("fps", video.fps || 30), 10);
const total = Math.round(video.duration * fps);
const from  = parseInt(flag("from", 0), 10), to = Math.min(total, parseInt(flag("to", total), 10));
const stills = flag("stills", null);

const browser = await chromium.launch({ args: ["--force-color-profile=srgb", "--font-render-hinting=none", "--disable-lcd-text"] });
const page = await browser.newPage({ viewport: { width: 576, height: 1024 }, deviceScaleFactor: scale });
await page.goto(pathToFileURL(resolve(dirname(new URL(import.meta.url).pathname), "engine/index.html")).href);
await page.evaluate(v => window.loadVideo(v), video);
await page.waitForFunction(() => window.__ready === true);

if (stills) {
  mkdirSync("out/stills", { recursive: true });
  for (const s of stills.split(",")) {
    await page.evaluate(t => window.__render(t), parseFloat(s));
    await page.screenshot({ path: `out/stills/t_${parseFloat(s).toFixed(2)}.png` });
  }
  await browser.close(); process.exit(0);
}

mkdirSync(dirname(outPath), { recursive: true });
const ff = spawn("ffmpeg", ["-y", "-loglevel", "error",
  "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
  ...(video.audio ? ["-i", resolve(dirname(videoPath), video.audio)] : []),
  "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", String(fps),
  ...(video.audio ? ["-c:a", "aac", "-b:a", "192k", "-shortest"] : []),
  "-movflags", "+faststart", outPath], { stdio: ["pipe", "inherit", "inherit"] });

for (let f = from; f < to; f++) {
  await page.evaluate(t => window.__render(t), f / fps);
  const buf = await page.screenshot({ type: "jpeg", quality: 95 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  if (f % fps === 0) process.stdout.write(`\r${f}/${total} frames`);
}
ff.stdin.end();
await new Promise(r => ff.on("close", r));
await browser.close();
console.log(`\n✔ ${outPath}`);
