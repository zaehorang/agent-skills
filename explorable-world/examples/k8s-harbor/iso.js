/* 아이소메트릭 그리기 도우미 — 주제와 무관하게 재사용한다.
   좌표: 바닥 평면 (gx, gy) + 높이 gz → 화면 (X, Y).
   gx 가 커지면 오른쪽 아래, gy 가 커지면 왼쪽 아래, gz 가 커지면 위로 간다.
   보이는 면은 윗면 · 왼쪽 앞면(gy+d) · 오른쪽 앞면(gx+w) 세 개다. */
(function(){
"use strict";
var NS = "http://www.w3.org/2000/svg";
var ISO = window.ISO = {};
var O = {x:800, y:120};

ISO.setOrigin = function(x, y){ O.x = x; O.y = y; };
ISO.iso  = function(gx, gy, gz){ return [O.x + (gx-gy)*0.866, O.y + (gx+gy)*0.5 - (gz||0)]; };
ISO.isoL = function(gx, gy, gz){ return [(gx-gy)*0.866, (gx+gy)*0.5 - (gz||0)]; };
var iso = ISO.iso;

function el(tag, attrs, parent){
  var e = document.createElementNS(NS, tag);
  if(attrs) for(var k in attrs) if(attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
  if(parent) parent.appendChild(e);
  return e;
}
ISO.el = el;
function pts(a){ return a.map(function(p){ return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" "); }
ISO.pts = pts;

/* 상자 — c = [윗면, 왼쪽 앞면, 오른쪽 앞면] 색. P 는 iso(지도 고정) 또는 isoL(움직이는 물체 기준) */
ISO.box = function(parent, P, gx, gy, gz, w, d, h, c, cls){
  var g = el("g", {"class": cls || ""}, parent);
  el("polygon", {points: pts([P(gx,gy+d,gz), P(gx+w,gy+d,gz), P(gx+w,gy+d,gz+h), P(gx,gy+d,gz+h)]), fill:c[1]}, g);
  el("polygon", {points: pts([P(gx+w,gy,gz), P(gx+w,gy+d,gz), P(gx+w,gy+d,gz+h), P(gx+w,gy,gz+h)]), fill:c[2]}, g);
  el("polygon", {points: pts([P(gx,gy,gz+h), P(gx+w,gy,gz+h), P(gx+w,gy+d,gz+h), P(gx,gy+d,gz+h)]), fill:c[0]}, g);
  return g;
};
/* 바닥에 붙은 평면 (도로·구역 표시) */
ISO.flat = function(parent, gx, gy, gz, w, d, attrs){
  var a = attrs || {};
  a.points = pts([iso(gx,gy,gz), iso(gx+w,gy,gz), iso(gx+w,gy+d,gz), iso(gx,gy+d,gz)]);
  return el("polygon", a, parent);
};
/* 오른쪽 앞면(gx 고정)·왼쪽 앞면(gy 고정) 위의 사각형 — 창문·문 */
ISO.faceR = function(parent, gx, gy, gz, d, h, fill){
  return el("polygon", {points: pts([iso(gx,gy,gz), iso(gx,gy+d,gz), iso(gx,gy+d,gz+h), iso(gx,gy,gz+h)]), fill:fill}, parent);
};
ISO.faceL = function(parent, gx, gy, gz, w, h, fill){
  return el("polygon", {points: pts([iso(gx,gy,gz), iso(gx+w,gy,gz), iso(gx+w,gy,gz+h), iso(gx,gy,gz+h)]), fill:fill}, parent);
};

/* 자주 쓰는 색 묶음 [윗면, 왼쪽, 오른쪽] */
ISO.C = {
  sand:["#f3e4c2","#dcc69b","#c9b083"], grass:["#b4dd93","#8dbd6f","#7aa95e"],
  wood:["#cfa06b","#a97b4a","#94683d"], wall:["#eef2f6","#cdd7e1","#b7c3cf"],
  roofB:["#4f7aa6","#3b6590","#33587e"], white:["#ffffff","#dfe7ef","#c9d4e0"],
  glass:["#8cc0ee","#5e95cc","#4f83b8"], navy:["#2e4a6b","#22395a","#1b3049"],
  stone:["#7b8591","#5b636e","#4b525c"], yellow:["#f7c948","#dba62b","#c4911c"],
  gray:["#9aa6b2","#7a8794","#69757f"], roofR:["#e07a5f","#c4614a","#b0553f"],
  teal:["#5ec4b6","#3ea597","#348d81"], conc:["#d5dbe1","#b8c1ca","#a6b0ba"],
  coral:["#ff8a66","#e8603f","#cf5133"], green:["#22c55e","#16a34a","#15803d"],
  purple:["#a855f7","#9333ea","#7e22ce"], gold:["#eab308","#ca8a04","#a16207"]
};

ISO.actLabel = function(name){ return name + " 알아보기"; };   /* 엔진이 화면 글자 설정(ui.actAria)으로 바꾼다 */
/* 클릭할 수 있는 등장인물·건물 묶음. actorId 는 content.js 의 actors 키와 같아야 한다 */
ISO.act = function(parent, actorId, name, cls){
  return el("g", {"class":"act" + (cls ? " " + cls : ""), "data-actor":actorId, tabindex:"0", role:"button",
    "aria-label":ISO.actLabel(name)}, parent);
};

/* ── 인물 · 로봇 ─────────────────────────────── */
ISO.person = function(parent, x, y, o){
  o = o || {};
  var g = el("g", {transform:"translate(" + x + "," + y + ")"}, parent);
  el("ellipse", {cx:0, cy:0, rx:13, ry:5, fill:"rgba(0,0,0,.18)"}, g);
  var b = el("g", {"class":"bob"}, g);
  el("rect", {x:-7, y:-15, width:5.5, height:15, rx:2, fill:"#334155"}, b);
  el("rect", {x:1.5, y:-15, width:5.5, height:15, rx:2, fill:"#334155"}, b);
  el("rect", {x:-10, y:-37, width:20, height:24, rx:7, fill:o.body || "#3b82f6"}, b);
  el("circle", {cx:0, cy:-45, r:8.5, fill:"#f5cfa8"}, b);
  if(o.hard){
    el("path", {d:"M-10,-47 A10,9 0 0 1 10,-47 Z", fill:"#facc15", stroke:"#ca8a04", "stroke-width":1}, b);
    el("rect", {x:-12, y:-48, width:24, height:3, rx:1.5, fill:"#eab308"}, b);
  } else if(o.chef){
    el("rect", {x:-8, y:-60, width:16, height:12, rx:5, fill:"#fff", stroke:"#cbd5e1"}, b);
  } else {
    el("path", {d:"M-9,-47 A9,8 0 0 1 9,-47 Z", fill:o.hair || "#3f2e22"}, b);
  }
  if(o.clip){
    el("rect", {x:7, y:-33, width:11, height:14, rx:2, fill:"#fff", stroke:"#64748b", "stroke-width":1.2}, b);
    el("line", {x1:9.5, y1:-28, x2:15.5, y2:-28, stroke:"#94a3b8", "stroke-width":1.2}, b);
    el("line", {x1:9.5, y1:-24, x2:15.5, y2:-24, stroke:"#94a3b8", "stroke-width":1.2}, b);
  }
  return g;
};
ISO.robot = function(parent, color){
  var g = el("g", {}, parent);
  el("ellipse", {cx:0, cy:0, rx:17, ry:6, fill:"rgba(0,0,0,.2)"}, g);
  var b = el("g", {"class":"bob"}, g);
  el("circle", {cx:-10, cy:-5, r:5.5, fill:"#1e293b"}, b);
  el("circle", {cx:10, cy:-5, r:5.5, fill:"#1e293b"}, b);
  el("rect", {x:-16, y:-36, width:32, height:30, rx:9, fill:color || "#8b9cff"}, b);
  el("rect", {x:-9, y:-27, width:18, height:10, rx:3, fill:"#c7d2fe"}, b);
  el("rect", {x:-12, y:-55, width:24, height:17, rx:7, fill:"#c7d2fe"}, b);
  el("rect", {x:-9, y:-51, width:18, height:8, rx:4, fill:"#1e293b"}, b);
  el("circle", {"class":"eye", cx:-3.5, cy:-47, r:2.4, fill:"#22d3ee"}, b);
  el("circle", {"class":"eye", cx:3.5, cy:-47, r:2.4, fill:"#22d3ee"}, b);
  el("line", {x1:0, y1:-55, x2:0, y2:-64, stroke:"#475569", "stroke-width":2}, b);
  el("circle", {"class":"bulb", cx:0, cy:-66, r:3.4, fill:"#f43f5e"}, b);
  return g;
};
/* 머리 위 느낌표 — 무언가를 알아챘다는 신호 */
ISO.bang = function(parent, x, y){
  var g = el("g", {opacity:0}, parent);
  el("circle", {cx:x, cy:y, r:10, fill:"#facc15", stroke:"#ca8a04", "stroke-width":1.5}, g);
  var t = el("text", {x:x, y:y + 4.5, "text-anchor":"middle", "font-size":"14", "font-weight":"900", fill:"#78350f"}, g);
  t.textContent = "!";
  return g;
};
/* 서류 한 장 — 요청서·메시지가 날아갈 때 */
ISO.paper = function(parent, mark){
  var g = el("g", {opacity:0}, parent);
  var dg = el("g", {transform:"translate(-15,-19)"}, g);
  el("path", {d:"M0,0 H22 L30,8 V38 H0 Z", fill:"#fff", stroke:"#334155", "stroke-width":1.6}, dg);
  el("path", {d:"M22,0 V8 H30", fill:"#e2e8f0", stroke:"#334155", "stroke-width":1.4}, dg);
  [12,18,24].forEach(function(yy){ el("line", {x1:5, y1:yy, x2:25, y2:yy, stroke:"#94a3b8", "stroke-width":1.8}, dg); });
  if(mark){ var t = el("text", {x:15, y:34, "text-anchor":"middle", "font-size":"7.5", "font-weight":"800", fill:"#2563eb", "font-family":"monospace"}, dg); t.textContent = mark; }
  g.seal = el("circle", {cx:24, cy:31, r:6, fill:"#dc2626", opacity:0}, dg);
  return g;
};

/* ── 라벨 — 비유 이름(ko)과 실제 이름(real)을 둘 다 갖고, '실제 이름 보기'로 바뀐다 ── */
ISO.label = function(parent, x, y, ko, real, big){
  var g = el("g", {"class":"lbl" + (big ? " big" : ""), transform:"translate(" + x + "," + y + ")"}, parent);
  var fs = big ? 17 : 15;
  var w = Math.max(ko.length * fs * 0.98, real.length * fs * 0.62) + 22;
  el("rect", {x:-w/2, y:-15, width:w, height:30, rx:15}, g);
  var t1 = el("text", {"class":"ko", x:0, y:1}, g); t1.textContent = ko;
  var t2 = el("text", {"class":"real", x:0, y:1}, g); t2.textContent = real;
  return g;
};

/* ── 말풍선 — 지도 좌표에 붙는다 (카메라와 같이 확대) ── */
ISO.bubble = function(layer, x, y, w, h, tail){
  var g = el("g", {"class":"bub", opacity:0}, layer);
  var inner = el("g", {}, g);
  el("rect", {"class":"bg", x:x, y:y, width:w, height:h, rx:14}, inner);
  if(tail) el("path", {d:"M" + tail[0] + "," + tail[1] + " L" + tail[2] + "," + tail[3] + " L" + tail[4] + "," + tail[5] + " Z", fill:"#fff"}, inner);
  g.inner = inner;
  g.ox = tail ? tail[2] : x + w/2; g.oy = tail ? tail[3] : y + h;
  return g;
};
ISO.text = function(parent, x, y, s, cls, attrs){
  var a = attrs || {}; a.x = x; a.y = y; a["class"] = cls || "";
  var t = el("text", a, parent); t.textContent = s; return t;
};
/* 두 점을 잇는 곡선 */
ISO.curve = function(path, from, to, lift){
  var mx = (from[0] + to[0]) / 2, my = Math.min(from[1], to[1]) - (lift == null ? 60 : lift);
  path.setAttribute("d", "M" + from[0].toFixed(1) + "," + from[1].toFixed(1) + " Q" + mx.toFixed(1) + "," + my.toFixed(1) + " " + to[0].toFixed(1) + "," + to[1].toFixed(1));
  return path;
};
/* 바닥 좌표에 물체 놓기 — 바깥 그룹은 위치(속성), 안쪽 그룹은 GSAP 애니메이션으로 나눈다 */
ISO.place = function(node, gx, gy, gz){
  var a = iso(gx, gy, gz || 0);
  node.setAttribute("transform", "translate(" + a[0].toFixed(1) + "," + a[1].toFixed(1) + ")");
};
ISO.mover = function(parent, attrs){
  var outer = el("g", attrs || {}, parent);
  outer.body = el("g", {}, outer);
  return outer;
};

/* 클릭 영역 — 빌드가 끝난 뒤 한 번 */
ISO.addHitAreas = function(root){
  Array.prototype.forEach.call(root.querySelectorAll(".act"), function(a){
    if(a.classList.contains("nohit")) return;
    var b = a.getBBox();
    var r = el("rect", {"class":"hit", x:b.x - 6, y:b.y - 6, width:b.width + 12, height:b.height + 12, rx:12});
    a.insertBefore(r, a.firstChild);
  });
};
})();
