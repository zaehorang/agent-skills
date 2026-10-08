#!/usr/bin/env node
// 탐험 지도 폴더를 브라우저 없이 검사한다.
//   node check_world.mjs <폴더>
// 실패(✗)는 고친 뒤 다시 돌린다. 권고(?)는 확인만 한다. 통과해야 브라우저를 연다.
import { readFileSync, existsSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const dir = resolve(process.argv[2] || ".");
const SKILL = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fails = [], warns = [];
const fail = m => fails.push(m), warn = m => warns.push(m);
const strip = s => String(s || "").replace(/<[^>]+>/g, "").replace(/&[a-z]+;/g, "x");

// 1. 파일
const FILES = ["index.html", "style.css", "iso.js", "engine.js", "world.js", "content.js", "world.css"];
for (const f of FILES) if (!existsSync(join(dir, f))) fail(`파일 없음: ${f}`);
if (fails.length) report();

// 2. 엔진이 스킬 최신본과 같은가
for (const f of ["index.html", "style.css", "iso.js", "engine.js"]) {
  const a = readFileSync(join(dir, f), "utf8"), bp = join(SKILL, "engine", f);
  if (existsSync(bp) && a !== readFileSync(bp, "utf8")) warn(`엔진 파일이 스킬 최신본과 다름: ${f} — 의도한 수정이 아니면 new_world.mjs --engine-only 로 갱신`);
}

// 3. 문법
for (const f of ["iso.js", "engine.js", "world.js", "content.js"]) {
  try { new vm.Script(readFileSync(join(dir, f), "utf8"), { filename: f }); }
  catch (e) { fail(`${f} 문법 오류: ${e.message}`); }
}
if (fails.length) report();

// 4. 불러오기 (DOM 없이 — 정의만 확인)
const sandbox = { window: {}, console };
sandbox.window.ISO = new Proxy({}, { get: () => () => ({}) });
vm.createContext(sandbox);
for (const f of ["content.js", "world.js"]) {
  try { vm.runInContext(readFileSync(join(dir, f), "utf8"), sandbox, { filename: f }); }
  catch (e) { fail(`${f} 실행 오류(불러올 때 DOM 을 건드리면 안 됨): ${e.message}`); }
}
const C = sandbox.window.CONTENT, W = sandbox.window.WORLD;
if (!C) fail("content.js 가 window.CONTENT 를 정의하지 않음");
if (!W) fail("world.js 가 window.WORLD 를 정의하지 않음");
if (fails.length) report();

// 5. CONTENT 형태
for (const k of ["title", "intro", "actors", "events"]) if (!C[k]) fail(`CONTENT.${k} 없음`);
if (C.intro) for (const k of ["title", "body"]) if (!C.intro[k]) fail(`CONTENT.intro.${k} 없음`);
const actors = C.actors || {};
for (const [id, a] of Object.entries(actors)) {
  // 같은 객체 안에서 키가 겹치면 뒤의 값이 앞을 조용히 덮는다 — 자료형으로 잡는다
  for (const k of ["name", "real", "tip", "what"]) if (typeof a[k] !== "string") fail(`actors.${id}.${k} 가 문자열이 아님 (키 중복으로 덮였을 수 있음)`);
  if (!Array.isArray(a.talks) || a.talks.some(t => !Array.isArray(t) || t.length !== 3)) fail(`actors.${id}.talks 는 [상대, 방식, 주고받는 것] 목록이어야 함`);
  if (!Array.isArray(a.steps) || !a.steps.length) fail(`actors.${id}.steps 가 비었거나 목록이 아님`);
  if (!Array.isArray(a.xr) || a.xr.some(x => !x.l || !x.code)) fail(`actors.${id}.xr 는 {l, code} 목록이어야 함`);
  if (!a.myth) warn(`actors.${id}.myth 없음 — 흔한 오해 한 줄을 권장`);
  if (strip(a.tip).length > 90) warn(`actors.${id}.tip ${strip(a.tip).length}자 — 말풍선은 한 문장(≈80자)`);
  if (strip(a.what).length > 260) warn(`actors.${id}.what ${strip(a.what).length}자 — 2~3문장 권장`);
  if (a.steps && a.steps.length > 8) warn(`actors.${id}.steps ${a.steps.length}개 — 7개 이하 권장`);
}

// 6. 사건 ↔ 장면
const ids = new Set();
for (const ev of C.events || []) {
  if (!ev.id) { fail("events 항목에 id 없음"); continue; }
  if (ids.has(ev.id)) fail(`events id 중복: ${ev.id}`); ids.add(ev.id);
  if (ev.ready === false) continue;
  const sc = W.scenes && W.scenes[ev.id];
  if (!sc) { fail(`사건 '${ev.id}' 의 장면이 world.js scenes 에 없음 (준비 중이면 ready:false)`); continue; }
  if (!Array.isArray(ev.beats) || !ev.beats.length) { fail(`사건 '${ev.id}' beats 비어 있음`); continue; }
  if (sc.length !== ev.beats.length) fail(`사건 '${ev.id}': beats ${ev.beats.length}개 ↔ 장면 함수 ${sc.length}개`);
  if (ev.beats.length > 9) warn(`사건 '${ev.id}' 장면 ${ev.beats.length}개 — 5~8개 권장`);
  ev.beats.forEach((b, i) => {
    const n = `${ev.id}[${i + 1}]`;
    if (!actors[b.actor]) fail(`${n}: actor '${b.actor}' 가 actors 에 없음`);
    if (!b.text) fail(`${n}: text 없음`);
    else if (strip(b.text).length > 170) warn(`${n}: 자막 ${strip(b.text).length}자 — 두 문장(≈150자) 권장`);
    if (!Array.isArray(b.xray) || !b.xray.length || b.xray.some(x => !x.l || !x.code)) fail(`${n}: xray 는 {l, code} 1개 이상`);
  });
}

// 7. 지도의 클릭 물체 ↔ actors
const wsrc = readFileSync(join(dir, "world.js"), "utf8");
const used = new Set();
for (const m of wsrc.matchAll(/act\(\s*[^,]+,\s*"([\w-]+)"/g)) used.add(m[1]);
for (const m of wsrc.matchAll(/"data-actor"\s*:\s*"([\w-]+)"/g)) used.add(m[1]);
for (const id of used) if (!actors[id]) fail(`world.js 가 쓰는 actor '${id}' 가 content.js actors 에 없음`);
for (const id of Object.keys(actors)) if (!used.has(id)) warn(`actors.${id} 는 지도에 클릭할 물체가 없음 (패널은 자막 칩으로만 열림)`);
if (!/reset\s*:/.test(wsrc)) fail("WORLD.reset 없음 — 이전·장면 이동이 상태를 되돌리지 못함");

// 8. 이름 규칙
const N = C.names || {};
for (const p of N.patterns || []) {
  try { new RegExp(p.re); } catch (e) { fail(`names.patterns 정규식 오류: ${p.re}`); }
  if (typeof p.parts !== "function") fail(`names.patterns '${p.re}' 에 parts 함수 없음`);
}
if (!N.examples) warn("names.examples 없음 — 도움말 범례에 예시가 기본값으로 나옴");
const allText = JSON.stringify(C);
if (/\bTODO\b/.test(readFileSync(join(dir, "content.js"), "utf8")) || /\bTODO\b/.test(wsrc)) warn("TODO 가 남아 있음 — 템플릿 문구를 다 바꿨는지 확인");
if (/\b(web|app|test|foo|bar)\.yaml\b/.test(allText)) warn("예시 파일·리소스 이름이 공식 용어처럼 보임 — my-shop 처럼 직접 지은 티가 나는 이름 권장");

// 9. 이름 일관성 — xr/xray 코드 안의 이름처럼 생긴 토큰이 names 규칙에 걸리는가
//    엔진(engine.js 의 NAME_RE)과 같은 방식으로 태그 밖 글자 조각마다 맞춰 본다.
{
  const esc = t => t.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&");
  const words = [...Object.keys(N.custom || {}), ...Object.keys(N.auto || {}), ...(N.projects || []), ...(N.official || [])]
    .sort((a, b) => b.length - a.length);
  const alts = (N.patterns || []).filter(p => { try { new RegExp(p.re); return true; } catch { return false; } })
    .map(p => `(?:${p.re})`).concat(words.map(esc));
  const nameRe = alts.length ? new RegExp(`(?<![\\w\\-.])(?:${alts.join("|")})(?![\\w\\-])`, "g") : null;
  // 소문자-하이픈-숫자 식별자(web-7d9f6c-4xk2p, worker-1) · 호스트명(ns1.example.com)
  const DASH_ID = /(?<![\w\-.\/])[a-z][a-z0-9]*(?:-[a-z0-9]+)+(?![\w\-]|\.[a-z])/g;
  const HOST = /(?<![\w\-.@])(?:[a-z0-9][a-z0-9-]*\.)+(?:com|net|org|io|dev|app|local|internal|svc|test|example|invalid|kr)(?![\w\-])/g;
  const found = new Map();   // 토큰 → 나온 위치들
  const scan = (code, where) => {
    for (const seg of String(code).split(/(<[^>]+>)/)) {
      if (seg.startsWith("<")) continue;
      const cover = nameRe ? [...seg.matchAll(nameRe)].map(m => [m.index, m.index + m[0].length]) : [];
      const test = (re, keep) => {
        for (const m of seg.matchAll(re)) {
          if (keep && !keep(m[0])) continue;
          const a = m.index, b = a + m[0].length;
          if (cover.some(([x, y]) => x <= a && y >= b)) continue;
          if (!found.has(m[0])) found.set(m[0], []);
          if (!found.get(m[0]).includes(where)) found.get(m[0]).push(where);
        }
      };
      test(DASH_ID, t => t.split("-").slice(1).some(x => /\d/.test(x)));
      test(HOST);
    }
  };
  for (const [id, a] of Object.entries(actors)) (a.xr || []).forEach((x, i) => scan(x.code, `${id}.xr[${i}]`));
  for (const ev of C.events || []) (ev.beats || []).forEach((b, i) => (b.xray || []).forEach((x, j) => scan(x.code, `${ev.id}[${i + 1}].xray[${j}]`)));
  const toks = [...found.entries()];
  for (const [t, where] of toks.slice(0, 8))
    warn(`xr/xray 코드의 이름 '${t}' 이 names 규칙(custom·auto·patterns·official)에 안 걸림 — 색이 안 칠해짐. 규칙에 넣거나 규칙에 걸리는 이름으로 통일 (${where.slice(0, 3).join(", ")}${where.length > 3 ? " …" : ""})`);
  if (toks.length > 8) warn(`xr/xray 코드의 규칙 밖 이름이 ${toks.length - 8}개 더 있음`);
}

// 10. 지도에 그렸지만 준비된 사건의 어느 장면에도 주인공으로 안 나오는 부품
{
  const heroes = new Set(), pending = [];
  for (const ev of C.events || []) {
    if (ev.ready === false) { if (ev.title) pending.push(strip(ev.title)); }
    else (ev.beats || []).forEach(b => heroes.add(b.actor));
  }
  const idle = [];
  if (heroes.size)
    for (const id of used) {
      if (!actors[id] || heroes.has(id)) continue;
      const tip = strip(actors[id].tip);
      if (pending.some(t => t && tip.includes(t))) continue;   // 준비 중 사건 전용이면 tip 에 그 사건 제목이 있다
      idle.push(`${id}(${strip(actors[id].name)})`);
    }
  if (idle.length)
    warn(`지도에 있지만 준비된 사건의 어느 장면에서도 주인공이 아닌 부품: ${idle.join(", ")} — 장면에서 쓰거나, 준비 중 사건 전용이면 tip 에 그 사건 제목('${pending[0] || "…"}' 처럼)을 쓰거나, 지도에서 줄인다. (배경 구역·소품이라 일부러 둔 것이면 무시)`);
}

report();
function report() {
  const name = dir.split("/").slice(-2).join("/");
  if (fails.length) {
    console.log(`FAIL  ${name}  (${fails.length}건)`);
    fails.forEach(m => console.log("  ✗ " + m));
  } else console.log(`OK    ${name}  — 정적 검사 통과. 이제 브라우저에서 장면마다 확인한다 (SKILL.md 7단계).`);
  warns.forEach(m => console.log("  ? " + m));
  process.exit(fails.length ? 1 : 0);
}
