#!/usr/bin/env node
/* render.mjs — Render Remotion composition to MP4
 *
 * Usage: node src/render.mjs [video.json] [output.mp4] [--scale 1.875]
 *
 * Defaults: video.json = motion-test/video.json, output = out/bonne-piste.mp4
 */
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";

const args = process.argv.slice(2);
const videoPath = args.find((a) => !a.startsWith("--")) || "motion-test/video.json";
const outPath =
  args.find((a, i) => args[i - 1] === "--output") ||
  args[args.length - 1] ||
  "out/bonne-piste.mp4";
const scaleIdx = args.indexOf("--scale");
const scale = scaleIdx > -1 ? +args[scaleIdx + 1] : 1.875;

const video = JSON.parse(readFileSync(videoPath, "utf8"));
const inputProps = JSON.stringify({ video });

console.log(`Rendering ${video.scenes.length} scenes, ${video.duration}s → ${outPath}`);

const remotionBin = resolve(dirname(new URL(import.meta.url).pathname), "..", "node_modules", ".bin", "remotion");

const cmd = [
  remotionBin,
  "render",
  "src/index.ts",
  "BonnePisteComposition",
  outPath,
  "--input-props",
  inputProps,
  "--fps",
  String(video.fps),
  "--codec",
  "h264",
  "--audio-codec",
  "aac",
  "--audio-bitrate",
  "192k",
  "--image-format",
  "jpeg",
  "--jpeg-quality",
  "95",
  "--frames",
  String(Math.round(video.duration * video.fps)),
];

const child = spawn(cmd[0], cmd.slice(1), {
  stdio: ["pipe", "inherit", "inherit"],
  cwd: resolve(dirname(new URL(import.meta.url).pathname)),
  env: { ...process.env, PUPPETEER_SKIP_CHROMIUM_DOWNLOAD: "true" },
});

child.stdout.on("data", (d) => process.stdout.write(d));
child.stderr.on("data", (d) => process.stderr.write(d));

child.on("close", (code) => {
  if (code !== 0) {
    console.error(`Remotion render failed with code ${code}`);
    process.exit(code);
  }
  console.log(`✔ ${outPath}`);
});
