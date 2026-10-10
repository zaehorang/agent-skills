#!/usr/bin/env node
// 새 탐험 지도 폴더를 만든다.
//   node new_world.mjs <대상 폴더> [--from template|examples/<이름>] [--engine-only]
// - 엔진 파일(index.html · style.css · iso.js · engine.js · gsap.min.js · MotionPathPlugin.min.js)은 항상 스킬의 최신본으로 덮어쓴다.
// - 주제 파일(world.js · content.js · world.css)은 대상에 없을 때만 복사한다. 이미 있으면 건드리지 않는다.
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const dest = args.find(a => !a.startsWith("--") && args[args.indexOf(a) - 1] !== "--from");
if (!dest) { console.error("사용법: node new_world.mjs <대상 폴더> [--from template|examples/<이름>] [--engine-only]"); process.exit(2); }
const fromIdx = args.indexOf("--from");
const from = fromIdx >= 0 ? args[fromIdx + 1] : "template";
const engineOnly = args.includes("--engine-only");

const out = resolve(dest);
mkdirSync(out, { recursive: true });
for (const f of readdirSync(join(SKILL, "engine"))) {
  cpSync(join(SKILL, "engine", f), join(out, f));
  console.log("엔진   ", f);
}
if (!engineOnly) {
  const src = join(SKILL, from);
  if (!existsSync(src)) { console.error("없는 출발점:", from); process.exit(2); }
  for (const f of ["world.js", "content.js", "world.css"]) {
    if (existsSync(join(out, f))) { console.log("유지   ", f, "(이미 있음)"); continue; }
    cpSync(join(src, f), join(out, f));
    console.log("복사   ", f, "←", from);
  }
}
console.log("\n완료:", out);
