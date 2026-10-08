/* 탐험 지도 엔진 — 주제와 무관하다. 주제는 content.js(window.CONTENT)와 world.js(window.WORLD)로만 바뀐다.
   흐름: 지도 그리기 → 배경 움직임 → 사건 시작 → 장면(beat)마다 자막·움직임 → 궁금하면 말풍선 → 패널 → 실제로는? */
(function(){
"use strict";
var ISO = window.ISO, W = window.WORLD, C = window.CONTENT, el = ISO.el;
gsap.registerPlugin(MotionPathPlugin);
var RM = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function $(id){ return document.getElementById(id); }

/* ── 화면 글자 — 기본값은 한국어, content.js 의 ui 로 바꾼다 ───────
   HTML 안의 글자는 data-ui(내용)·data-ui-aria(aria-label) 키, 코드로 만드는 글자는 아래 표의 키. */
var UI_DEFAULT = {
  ready:"준비 중", again:"다시 보기", next:"다음 ▶", finish:"마치기 ✓", beatAria:"{n}번째 장면으로",
  more:"더 알아보기", talks:"누구와 무엇으로 이야기하나", steps:"안에서 일어나는 순서",
  realBtn:"🔍 실제로는? — 실제 시스템에서 보기", now:"● 지금 이 순간 일어난 일", always:"● 언제든 확인할 수 있는 것", myth:"흔한 오해",
  legendO:"파랑 공식 용어", legendC:"노랑 직접 지은 이름", legendA:"회색 자동 생성", legendHint:"색 글자에 마우스를 올리면 이유가 보여요",
  helpO:"파랑", helpC:"노랑", helpA:"회색",
  helpOdesc:"공식 용어 — 정식 이름. 그대로 외워 두세요.", helpCdesc:"직접 지은 이름 — 사용자가 정한 값이라 바꿔도 돼요.", helpAdesc:"자동 생성 — 시스템이 붙여서 매번 달라져요.",
  showReal:"실제 이름 보기", showMeta:"비유 이름 보기", actAria:"{name} 알아보기"
};
var UI = {}, uk;
for(uk in UI_DEFAULT) if(UI_DEFAULT.hasOwnProperty(uk)) UI[uk] = UI_DEFAULT[uk];
if(C.ui) for(uk in C.ui) if(C.ui.hasOwnProperty(uk)) UI[uk] = C.ui[uk];
Array.prototype.forEach.call(document.querySelectorAll("[data-ui]"), function(n){
  var k = n.getAttribute("data-ui"); if(C.ui && C.ui[k] != null) n.innerHTML = C.ui[k];
});
Array.prototype.forEach.call(document.querySelectorAll("[data-ui-aria]"), function(n){
  var k = n.getAttribute("data-ui-aria"); if(C.ui && C.ui[k] != null) n.setAttribute("aria-label", C.ui[k]);
});
if(C.lang) document.documentElement.setAttribute("lang", C.lang);
$("nameBtn").textContent = UI.showReal;
ISO.actLabel = function(name){ return UI.actAria.replace("{name}", name); };

/* ── 머리말 · 첫 안내 ─────────────────────── */
document.title = C.title;
$("brandTitle").textContent = C.title;
$("brandSub").textContent = C.subtitle || "";
if(C.logo){ $("brandLogo").textContent = C.logo; $("introLogo").textContent = C.logo; }
$("introTitle").innerHTML = C.intro.title;
$("introBody").innerHTML = C.intro.body;
$("introSub").innerHTML = C.intro.sub || "";

/* ── 층 ─────────────────────────────────── */
var world = $("world");
var L = {};
["base","ground","back","mid","front","fx","labels","bubbles"].forEach(function(n){ L[n] = el("g", {id:"L_" + n}, world); });

/* ── 카메라 ─────────────────────────────── */
var HOME = W.home || {x:800, y:470, s:0.93};
var cam = {x:HOME.x, y:HOME.y + 10, s:HOME.s * 0.92};
var EV = null;
function applyCam(){
  world.setAttribute("transform", "translate(" + (800 - cam.s*cam.x).toFixed(1) + "," + (500 - cam.s*cam.y).toFixed(1) + ") scale(" + cam.s.toFixed(4) + ")");
}
/* 사건 중에는 아래 자막에 가리지 않게 대상을 위로 올려 잡는다 */
function camTo(x, y, s, d){
  if(EV) y += 80 / s;
  return gsap.to(cam, {x:x, y:y, s:s, duration:RM ? 0 : (d == null ? 1.3 : d), ease:"power2.inOut", onUpdate:applyCam});
}
function camHome(d){ return camTo(HOME.x, HOME.y, HOME.s, d); }
applyCam();

/* ── 연결선(소통) ─────────────────────────── */
var links = {};
function link(key, variant){
  if(!links[key]) links[key] = el("path", {"class":"link" + (variant ? " " + variant : "")}, L.fx);
  return links[key];
}
function pt(p){ return typeof p === "function" ? p() : p; }

/* ── 장면 함수에 넘기는 도구 ─────────────────── */
var api = {
  ISO:ISO, el:el, iso:ISO.iso, isoL:ISO.isoL, L:L, defs:$("defs"), bg:$("bg"), RM:RM, state:{},
  camTo:camTo, camHome:camHome,
  bubble:function(x, y, w, h, tail){ return ISO.bubble(L.bubbles, x, y, w, h, tail); },
  text:ISO.text,
  label:function(x, y, ko, real, big){ return ISO.label(L.labels, x, y, ko, real, big); },
  link:link,
  /* 말풍선 튀어나오기 */
  pop:function(tl, b, at){
    tl.fromTo(b, {opacity:0, scale:.4, svgOrigin:b.ox + " " + b.oy}, {opacity:1, scale:1, duration:.45, ease:"back.out(1.6)"}, at);
  },
  /* 이전 장면 말풍선 정리 — 장면 함수가 만들어질 때의 말풍선을 기준으로 한다 */
  clearBubbles:function(tl, at){
    var olds = Array.prototype.slice.call(L.bubbles.children);
    if(!olds.length) return;
    tl.to(olds, {opacity:0, duration:.3}, at);
    tl.call(function(){ olds.forEach(function(o){ if(o.parentNode) o.parentNode.removeChild(o); }); });
  },
  /* 소통 보여주기: from → to 로 흐르는 점선. from/to 는 점 [x,y] 또는 점을 돌려주는 함수 */
  showLink:function(tl, key, from, to, at, variant){
    var p = link(key, variant);
    tl.call(function(){ ISO.curve(p, pt(from), pt(to)); }, null, at);
    tl.to(p, {opacity:1, duration:.35}, "<");
  },
  hideLinks:function(tl, keys, at){
    tl.to(keys.map(link), {opacity:0, duration:.3}, at);
  },
  /* 날아가기 — 두 점 사이를 포물선으로 */
  fly:function(tl, node, from, to, opt, at){
    opt = opt || {};
    var lift = opt.lift == null ? 140 : opt.lift;
    tl.to(node, {duration:opt.duration || 1.6, ease:opt.ease || "power1.inOut",
      motionPath:{path:[{x:from[0], y:from[1]}, {x:(from[0] + to[0]) / 2, y:Math.min(from[1], to[1]) - lift}, {x:to[0], y:to[1]}], curviness:1.2}}, at);
  }
};

/* ── 지도 그리기 ─────────────────────────── */
var R = W.build(api) || {};
api.R = R;
ISO.addHitAreas(world);

function resetWorld(){
  gsap.killTweensOf(cam);
  L.bubbles.innerHTML = "";
  Object.keys(links).forEach(function(k){ gsap.killTweensOf(links[k]); gsap.set(links[k], {opacity:0}); });
  if(W.reset) W.reset(api, R);
}

/* ── 이름 구분: 파랑 공식 · 노랑 직접 지은 이름 · 회색 자동 생성 ── */
var NC = C.names || {};
var NAME_MSG = {
  o:"<b>공식 용어</b> · 공식 문서에 나오는 정식 이름이라 그대로 써야 해요.",
  oext:"<b>공식 이름</b> · 함께 쓰는 프로젝트의 정식 이름이에요. 그대로 써요.",
  c:"<b>직접 지은 이름</b> · 사용자가 정한 이름이라 다른 이름으로 바꿔도 돼요.",
  a:"<b>자동 생성</b> · 시스템이 붙인 값이라 매번 달라져요."
};
if(NC.messages) for(var mk in NC.messages) if(NC.messages.hasOwnProperty(mk)) NAME_MSG[mk] = NC.messages[mk];
var CUSTOM = NC.custom || {}, AUTO = NC.auto || {}, PROJECT = {};
(NC.projects || []).forEach(function(p){ PROJECT[p] = 1; });
var OFFICIAL = NC.official || [];
var PATTERNS = (NC.patterns || []).map(function(p){ return {re:new RegExp("^(?:" + p.re + ")$"), src:p.re, parts:p.parts}; });
function esc(t){ return t.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&"); }
var WORDS = Object.keys(CUSTOM).concat(Object.keys(AUTO), Object.keys(PROJECT), OFFICIAL).sort(function(a, b){ return b.length - a.length; });
var ALTS = PATTERNS.map(function(p){ return "(?:" + p.src + ")"; }).concat(WORDS.map(esc));
var NAME_RE = ALTS.length ? new RegExp("(?<![\\w\\-.])(?:" + ALTS.join("|") + ")(?![\\w\\-])", "g") : null;
var CLS = {o:"n-o", c:"n-c", a:"n-a"};
function nm(kind, key, t){ return "<span class='nm " + CLS[kind] + "' data-k='" + key + "'>" + t + "</span>"; }
/* 태그 밖 글자에만 칠한다 */
function tagNames(html){
  if(!NAME_RE || !html) return html || "";
  return String(html).split(/(<[^>]+>)/).map(function(part){
    if(part.charAt(0) === "<") return part;
    return part.replace(NAME_RE, function(m){
      for(var i = 0; i < PATTERNS.length; i++){
        if(PATTERNS[i].re.test(m)) return PATTERNS[i].parts(m).map(function(q){ return nm(q[0], q[1], q[2]); }).join("");
      }
      if(AUTO[m]) return nm("a", AUTO[m], m);
      if(CUSTOM[m]) return nm("c", CUSTOM[m], m);
      return nm("o", PROJECT[m] ? "oext" : "o", m);
    });
  }).join("");
}
var ntip = $("ntip");
document.addEventListener("mouseover", function(e){
  var t = e.target.closest && e.target.closest(".nm");
  if(!t){ ntip.hidden = true; return; }
  ntip.innerHTML = NAME_MSG[t.getAttribute("data-k")] || NAME_MSG[t.classList.contains("n-o") ? "o" : t.classList.contains("n-c") ? "c" : "a"];
  ntip.hidden = false;
  var r = t.getBoundingClientRect();
  ntip.style.left = Math.min(window.innerWidth - 310, Math.max(10, r.left)) + "px";
  ntip.style.top = (r.top > 90 ? r.top - ntip.offsetHeight - 8 : r.bottom + 8) + "px";
});
(function(){
  var ex = NC.examples || {o:"official", c:"my-app", a:"-x7k2q"};
  $("helpLegend").innerHTML =
    "<div><span class='nm n-o'>" + UI.helpO + " · " + ex.o + "</span><span>" + UI.helpOdesc + "</span></div>" +
    "<div><span class='nm n-c'>" + UI.helpC + " · " + ex.c + "</span><span>" + UI.helpCdesc + "</span></div>" +
    "<div><span class='nm n-a'>" + UI.helpA + " · " + ex.a + "</span><span>" + UI.helpAdesc + "</span></div>";
})();

/* ── 사건 버튼 ─────────────────────────────── */
var EVENTS = C.events || [];
(function(){
  var h = "";
  EVENTS.forEach(function(ev, i){
    var ready = ev.ready !== false && W.scenes && W.scenes[ev.id];
    h += "<button type='button' class='ev' data-i='" + i + "'" + (ready ? "" : " disabled") + "><span class='ico'>" + (ev.icon || "•") +
      "</span><span><b>" + ev.title + "</b><small>" + (ready ? (ev.sub || "") : UI.ready) + "</small></span><span class='done' aria-hidden='true'>✓</span></button>";
  });
  $("evList").innerHTML = h;
  Array.prototype.forEach.call($("evList").querySelectorAll(".ev"), function(b){
    b.onclick = function(){ startEvent(EVENTS[+b.getAttribute("data-i")], b); };
  });
})();
function evButton(ev){ return $("evList").querySelector(".ev[data-i='" + EVENTS.indexOf(ev) + "']"); }

/* ── 사건 진행기 ─────────────────────────── */
var SC = null, beatIdx = -1, tl = null, autoCall = null, panelOpen = false;
function startEvent(ev){
  closeTip(); closePanel();
  EV = ev; SC = W.scenes[ev.id];
  $("events").classList.add("hide");
  $("caption").hidden = false;
  $("capEv").textContent = ev.title;
  var d = "";
  ev.beats.forEach(function(b, i){ d += "<button type='button' data-i='" + i + "' aria-label='" + UI.beatAria.replace("{n}", i + 1) + "'></button>"; });
  $("dots").innerHTML = d;
  Array.prototype.forEach.call($("dots").children, function(btn){ btn.onclick = function(){ goBeat(+btn.getAttribute("data-i")); }; });
  Array.prototype.forEach.call($("evList").querySelectorAll(".ev"), function(b){ b.classList.remove("pulse"); });
  goBeat(0);
}
/* 어느 장면으로든 이동 — 처음 상태로 되돌린 뒤 앞 장면들을 보이지 않게 순식간에 실행한다 */
function goBeat(k){
  if(!EV) return;
  k = Math.max(0, Math.min(EV.beats.length - 1, k));
  if(autoCall){ autoCall.kill(); autoCall = null; }
  if(tl){ tl.kill(); tl = null; }
  resetWorld();
  for(var i = 0; i < k; i++){
    var t = gsap.timeline({paused:true});
    SC[i](t, api, R);
    t.progress(1);
  }
  beatIdx = k - 1;
  nextBeat();
}
function nextBeat(){
  if(autoCall){ autoCall.kill(); autoCall = null; }
  /* 재생 중이면 빨리 감아 끝낸 뒤 넘어간다 */
  if(tl && tl.isActive()){ tl.timeScale(9); tl.eventCallback("onComplete", function(){ beatDone(); nextBeat(); }); return; }
  beatIdx++;
  if(beatIdx >= EV.beats.length){ endEvent(); return; }
  var b = EV.beats[beatIdx], a = C.actors[b.actor];
  $("capText").innerHTML = tagNames(b.text);
  $("capActor").innerHTML = a.name + "<code>" + String(a.real).split(" ")[0] + "</code>";
  Array.prototype.forEach.call($("dots").children, function(dot, i){
    dot.className = i < beatIdx ? "past" : (i === beatIdx ? "on" : "");
  });
  $("prevBtn").disabled = beatIdx === 0;
  $("nextBtn").textContent = beatIdx === EV.beats.length - 1 ? UI.finish : UI.next;
  gsap.fromTo("#capText", {opacity:0, y:6}, {opacity:1, y:0, duration:.4});
  tl = gsap.timeline({onComplete:beatDone});
  SC[beatIdx](tl, api, R);
  if(RM) tl.progress(1);
}
function prevBeat(){ if(EV && beatIdx > 0) goBeat(beatIdx - 1); }
function beatDone(){
  if(autoCall){ autoCall.kill(); autoCall = null; }
  if($("autoChk").checked && !panelOpen && EV && beatIdx < EV.beats.length - 1) autoCall = gsap.delayedCall(2.6, nextBeat);
}
function endEvent(){
  var b = evButton(EV);
  $("caption").hidden = true;
  $("events").classList.remove("hide");
  if(b){ b.classList.add("seen"); b.querySelector("small").textContent = UI.again; }
  L.bubbles.innerHTML = "";
  if(W.afterEvent) W.afterEvent(api, R);
  EV = null; tl = null;
  camHome(1.4);
}
function closeEvent(){
  if(tl) tl.kill(); if(autoCall) autoCall.kill();
  tl = null; autoCall = null;
  closePanel();
  resetWorld();
  $("caption").hidden = true; $("events").classList.remove("hide");
  EV = null;
  camHome(1.2);
}

/* ── 말풍선(겹 1) ─────────────────────────── */
var tipActor = null;
function openTip(actor, x, y){
  var a = C.actors[actor]; if(!a) return;
  tipActor = actor;
  $("tipName").textContent = a.name; $("tipReal").textContent = a.real; $("tipText").innerHTML = tagNames(a.tip);
  var t = $("tip"); t.hidden = false;
  var w = 290, h = t.offsetHeight || 150;
  t.style.left = Math.min(window.innerWidth - w - 14, Math.max(14, x + 16)) + "px";
  t.style.top = Math.min(window.innerHeight - h - 14, Math.max(80, y - h / 2)) + "px";
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
}
function closeTip(){ $("tip").hidden = true; tipActor = null; }

/* ── 패널(겹 2·3) ─────────────────────────── */
function xrBlock(x){ return "<div class='xr'><div class='xl'>" + x.l + "</div><pre>" + tagNames(x.code) + "</pre></div>"; }
function openPanel(actor){
  var a = C.actors[actor]; if(!a) return;
  closeTip();
  var beat = EV && beatIdx >= 0 ? EV.beats[beatIdx] : null;
  var now = beat && beat.actor === actor ? beat : null;
  var h = "<div class='p-kicker'>" + UI.more + "</div><div class='p-name'>" + a.name + "</div><div class='p-real'>" + a.real + "</div>" +
    "<p class='p-what'>" + tagNames(a.what) + "</p><h3>" + UI.talks + "</h3><div class='talk'>";
  (a.talks || []).forEach(function(t){ h += "<span class='who'>" + tagNames(t[0]) + "</span><span class='how'>" + t[1] + "</span><span class='what'>" + tagNames(t[2]) + "</span>"; });
  h += "</div><h3>" + UI.steps + "</h3><ol class='steps'>";
  (a.steps || []).forEach(function(s){ h += "<li>" + tagNames(s) + "</li>"; });
  h += "</ol><button type='button' class='realbtn' id='realBtn' aria-expanded='false'>" + UI.realBtn + "</button><div class='real' id='realSec'>" +
    "<div class='legend'><span class='nm n-o' data-k='o'>" + UI.legendO + "</span><span class='nm n-c' data-k='c'>" + UI.legendC + "</span>" +
    "<span class='nm n-a' data-k='a'>" + UI.legendA + "</span><small>" + UI.legendHint + "</small></div>";
  if(now){
    h += "<div class='now'>" + UI.now + "</div>";
    now.xray.forEach(function(x){ h += xrBlock(x); });
    h += "<div class='now' style='color:#64748b'>" + UI.always + "</div>";
  }
  (a.xr || []).forEach(function(x){ h += xrBlock(x); });
  if(a.myth) h += "<div class='myth'><b>" + UI.myth + "</b> · " + tagNames(a.myth) + "</div>";
  h += "</div>";
  $("panelBody").innerHTML = h;
  $("panel").scrollTop = 0;
  $("realBtn").onclick = function(){
    var open = $("realSec").classList.toggle("open");
    $("realBtn").setAttribute("aria-expanded", open ? "true" : "false");
    if(open) $("realSec").scrollIntoView({behavior:"smooth", block:"start"});
  };
  $("panel").classList.add("open"); $("panel").setAttribute("aria-hidden", "false");
  document.body.classList.add("panel-open");
  gsap.to(".steps li", {opacity:1, x:0, duration:.4, stagger:.12, delay:.35, ease:"power2.out"});
  panelOpen = true;
  if(tl && tl.isActive()) tl.pause();
  if(autoCall) autoCall.pause();
}
function closePanel(){
  if(!panelOpen) return;
  $("panel").classList.remove("open"); $("panel").setAttribute("aria-hidden", "true");
  document.body.classList.remove("panel-open");
  panelOpen = false;
  if(tl && tl.paused() && tl.progress() < 1) tl.resume();
  else if(tl && tl.progress() === 1) beatDone();
}

/* ── 보는 법 (?) ─────────────────────────── */
function openHelp(){ closeTip(); $("help").hidden = false; if(tl && tl.isActive()) tl.pause(); if(autoCall) autoCall.pause(); }
function closeHelp(){
  if($("help").hidden) return;
  $("help").hidden = true;
  if(!panelOpen){ if(tl && tl.paused() && tl.progress() < 1) tl.resume(); if(autoCall) autoCall.resume(); }
}

/* ── 연결 ─────────────────────────────────── */
world.addEventListener("click", function(e){
  var a = e.target.closest(".act");
  if(!a){ closeTip(); return; }
  e.stopPropagation();
  openTip(a.getAttribute("data-actor"), e.clientX, e.clientY);
});
world.addEventListener("keydown", function(e){
  if(e.key !== "Enter" && e.key !== " ") return;
  var a = e.target.closest(".act"); if(!a) return;
  e.preventDefault();
  var r = a.getBoundingClientRect();
  openTip(a.getAttribute("data-actor"), r.right, r.top + r.height / 2);
});
$("stage").addEventListener("click", function(e){ if(!e.target.closest(".act")) closeTip(); });
$("tipMore").onclick = function(){ openPanel(tipActor); };
$("panelClose").onclick = closePanel;
$("capActor").onclick = function(){ openPanel(EV.beats[beatIdx].actor); };
$("moreBtn").onclick = function(){ openPanel(EV.beats[beatIdx].actor); };
$("nextBtn").onclick = function(){ if(panelOpen) closePanel(); nextBeat(); };
$("prevBtn").onclick = function(){ if(panelOpen) closePanel(); prevBeat(); };
$("capClose").onclick = closeEvent;
$("autoChk").onchange = function(){ if(this.checked && tl && !tl.isActive() && !panelOpen) beatDone(); else if(!this.checked && autoCall){ autoCall.kill(); autoCall = null; } };
$("nameBtn").onclick = function(){
  var on = document.body.classList.toggle("realnames");
  this.setAttribute("aria-pressed", on ? "true" : "false");
  this.textContent = on ? UI.showMeta : UI.showReal;
};
$("overviewBtn").onclick = function(){ camHome(1); };
$("helpBtn").onclick = openHelp;
$("helpClose").onclick = closeHelp;
$("help").addEventListener("click", function(e){ if(e.target === $("help")) closeHelp(); });
document.addEventListener("keydown", function(e){
  if(e.key === "Escape"){ if(!$("help").hidden) closeHelp(); else if(panelOpen) closePanel(); else closeTip(); }
  else if(e.key === "?"){ if($("help").hidden) openHelp(); else closeHelp(); }
  else if(!$("help").hidden) return;
  else if(e.key === "ArrowRight" && EV && !$("caption").hidden){ $("nextBtn").click(); }
  else if(e.key === "ArrowLeft" && EV && !$("caption").hidden){ $("prevBtn").click(); }
});
$("introGo").onclick = function(){
  $("intro").classList.add("hide");
  setTimeout(function(){ $("intro").style.display = "none"; }, 520);
  camHome(1.8);
  var first = $("evList").querySelector(".ev:not([disabled])");
  if(first) first.classList.add("pulse");
};

resetWorld();
if(W.ambient && !RM) W.ambient(api, R);

/* 확인용 — 브라우저 자동화에서 상태를 읽을 때만 쓴다 */
window.EXPLORER = {api:api, R:R, goBeat:goBeat, next:nextBeat, prev:prevBeat, closeEvent:closeEvent,
  startEvent:function(id){ for(var i=0;i<EVENTS.length;i++) if(EVENTS[i].id === id) startEvent(EVENTS[i]); },
  /* 지금 장면을 애니메이션 없이 끝 상태로 */
  finish:function(){ if(tl && tl.progress() < 1) tl.progress(1); gsap.killTweensOf(cam); applyCam(); },
  openPanel:openPanel, closePanel:closePanel, openTip:openTip, closeTip:closeTip, tagNames:tagNames,
  events:function(){ return EVENTS.map(function(e){ return {id:e.id, beats:(e.beats || []).length, ready:e.ready !== false && !!(W.scenes && W.scenes[e.id])}; }); },
  state:function(){ return {event:EV && EV.id, beat:beatIdx, playing:!!(tl && tl.isActive()), actor:EV && beatIdx >= 0 ? EV.beats[beatIdx].actor : null}; }};
})();
