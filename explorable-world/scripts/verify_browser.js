/* 탐험 지도 브라우저 검사 (rubric B) — 페이지를 연 뒤 이 파일 내용을 그대로 실행한다.
   애니메이션을 기다리지 않고 장면마다 끝 상태로 바로 넘겨 재므로 한 번에 몇 초면 끝난다.
     1) 이 파일 전체를 브라우저 자동화의 JS 실행에 붙여 넣는다 → window.EWV 가 생긴다
     2) await EWV.all()            → 전체 결과 JSON (요약 + 장면별 + 부품별)
   개별: EWV.scan(사건id) · EWV.replay(사건id) · EWV.panels() · EWV.labels()
   다른 화면 크기: await EWV.at(1280, 640) — 같은 페이지를 그 크기의 iframe 에 열어 같은 검사를 돌린다(창을 못 바꿀 때)
   주의: 페이지를 연 직후 콘솔 에러는 이 스크립트가 못 잡는다 — 자동화 도구로 콘솔 에러도 따로 읽는다. */
(function ewvMain(){
  "use strict";
  var X = window.EXPLORER;
  if(!X){ throw new Error("EXPLORER 없음 — 엔진이 최신인지(new_world.mjs --engine-only) 확인"); }
  var errors = [];
  window.addEventListener("error", function(e){ errors.push(String(e.message)); });
  window.addEventListener("unhandledrejection", function(e){ errors.push(String(e.reason)); });

  function $(s){ return document.querySelector(s); }
  function vis(el){
    var cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if(r.width < 1 || r.height < 1) return false;
    for(var n = el; n && n.nodeType === 1; n = n.parentNode){
      var c = getComputedStyle(n);
      if(c.display === "none" || c.visibility === "hidden" || parseFloat(c.opacity) < 0.3) return false;
    }
    return cs.display !== "none";
  }
  function inter(a, b){
    var w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    return w > 0 && h > 0 ? w * h : 0;
  }
  function round(s){ return String(s).replace(/-?\d+\.\d+/g, function(n){ return Math.round(parseFloat(n)); }); }
  function intro(){ var b = $("#introGo"); if(b && $("#intro").style.display !== "none") b.click(); }

  /* 장면 끝 상태의 지문 — 움직이는 층(fx·말풍선)과 클릭 물체의 클래스만 본다 (배경 움직임 제외) */
  function snap(){
    var parts = [];
    ["#L_fx", "#L_bubbles"].forEach(function(sel){
      var root = $(sel); if(!root) return;
      Array.prototype.forEach.call(root.querySelectorAll("*"), function(n){
        var op = n.style && n.style.opacity !== "" ? n.style.opacity : (n.getAttribute("opacity") || "");
        parts.push(n.tagName + "|" + (n.getAttribute("class") || "") + "|" + round(n.getAttribute("transform") || "") + "|" +
          round(n.style ? n.style.transform : "") + "|" + round(op) + "|" + (n.childElementCount ? "" : (n.textContent || "")));
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll("#world .act"), function(n){ parts.push("act|" + n.getAttribute("class")); });
    return parts.join("\n");
  }

  /* 말풍선 꼬리 끝(화면 좌표) — ISO.bubble 이 첫 path 로 그리는 삼각형의 둘째 점. 꼬리가 없으면 null */
  function tailTip(b){
    var p = b.querySelector("path"), svg = $("#stage");
    if(!p || !svg || !p.getScreenCTM) return null;
    var n = (p.getAttribute("d") || "").match(/-?\d+(?:\.\d+)?/g);
    if(!n || n.length < 6) return null;
    var pt = svg.createSVGPoint(); pt.x = +n[2]; pt.y = +n[3];
    var q = pt.matrixTransform(p.getScreenCTM());
    return {x:q.x, y:q.y};
  }
  function union(rs){
    return rs.reduce(function(u, r){
      return u ? {left:Math.min(u.left, r.left), top:Math.min(u.top, r.top), right:Math.max(u.right, r.right), bottom:Math.max(u.bottom, r.bottom)}
               : {left:r.left, top:r.top, right:r.right, bottom:r.bottom};
    }, null);
  }
  function near(pt, r, pad){ return pt.x >= r.left - pad && pt.x <= r.right + pad && pt.y >= r.top - pad && pt.y <= r.bottom + pad; }

  /* 장면마다: 주인공이 자막에 가리는가 · 말풍선이 화면 밖인가 · 말풍선이 자막과 겹치는가
     B8 라벨이 말풍선 글자를 가리는가(라벨이 말풍선보다 위에 그려질 때만) · B9 꼬리 끝이 주인공 근처를 가리키는가 */
  function scan(evId){
    intro();
    var ev = X.events().filter(function(e){ return e.id === evId; })[0];
    if(!ev || !ev.ready) return {event:evId, error:"준비된 사건이 아님"};
    X.startEvent(evId);
    var out = [];
    for(var k = 0; k < ev.beats; k++){
      X.goBeat(k); X.finish();
      var st = X.state(), cap = $("#caption").getBoundingClientRect();
      var vw = window.innerWidth, vh = window.innerHeight;
      var hero = Array.prototype.filter.call(document.querySelectorAll('#world [data-actor="' + st.actor + '"]'), vis);
      var best = null;
      hero.forEach(function(el){
        var r = el.getBoundingClientRect(), area = r.width * r.height;
        var onScreen = inter(r, {left:0, top:0, right:vw, bottom:vh}) / area;
        var covered = inter(r, cap) / area;
        var score = onScreen * (1 - covered);
        if(!best || score > best.score) best = {score:score, onScreen:+onScreen.toFixed(2), covered:+covered.toFixed(2)};
      });
      var bubEls = Array.prototype.filter.call(document.querySelectorAll("#L_bubbles .bub"), vis);
      var bubs = bubEls.map(function(b){
        var r = b.getBoundingClientRect();
        return {out:r.left < -4 || r.top < -4 || r.right > vw + 4 || r.bottom > vh + 4, underCaption:inter(r, cap) / (r.width * r.height) > 0.25};
      });
      /* B8 — 말풍선보다 위에 그려지는 라벨이 말풍선 글자를 10% 넘게 덮으면 */
      var labOver = [];
      var labEls = Array.prototype.filter.call(document.querySelectorAll("#L_labels .lbl"), vis);
      bubEls.forEach(function(b){
        var texts = Array.prototype.filter.call(b.querySelectorAll("text"), function(t){ return t.textContent.trim() && vis(t); });
        labEls.forEach(function(l){
          if(!(l.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_PRECEDING)) return;   /* 라벨이 말풍선 뒤(아래)에 그려지면 가리지 못한다 */
          var lr = l.getBoundingClientRect();
          texts.forEach(function(t){
            var tr = t.getBoundingClientRect(), a = tr.width * tr.height;
            if(a > 0 && inter(lr, tr) / a > 0.1)
              labOver.push({label:(l.querySelector("text") || l).textContent.trim(), bubble:t.textContent.trim().slice(0, 24)});
          });
        });
      });
      /* B9 — 꼬리 끝이 주인공(확장 bbox) 근처인가. 아니면 어느 부품을 가리키는지 같이 적는다 */
      var heroBox = union(hero.map(function(h){ return h.getBoundingClientRect(); }));
      var away = [];
      if(heroBox){
        var pad = Math.max(14, Math.min(50, 0.3 * Math.max(heroBox.right - heroBox.left, heroBox.bottom - heroBox.top)));
        bubEls.forEach(function(b, i){
          var tip = tailTip(b);
          if(!tip || near(tip, heroBox, pad)) return;
          var at = null, area = 1e12;
          Array.prototype.forEach.call(document.querySelectorAll("#world [data-actor]"), function(el){
            if(!vis(el)) return;
            var r = el.getBoundingClientRect(), a = r.width * r.height;
            if(a > 0 && a < area && near(tip, r, 6)){ area = a; at = el.getAttribute("data-actor"); }
          });
          away.push({bubble:i + 1, text:((b.querySelector("text") || {}).textContent || "").trim().slice(0, 24), pointsAt:at});
        });
      }
      out.push({beat:k + 1, actor:st.actor,
        heroVisible:best ? best.score >= 0.5 : false, hero:best,
        bubbles:bubs.length, bubbleOut:bubs.filter(function(b){ return b.out; }).length,
        bubbleUnderCaption:bubs.filter(function(b){ return b.underCaption; }).length,
        labelOverBubble:labOver, tailAwayFromHero:away,
        links:Array.prototype.filter.call(document.querySelectorAll("#L_fx .link"), vis).length});
    }
    X.closeEvent();
    return {event:evId, beats:out};
  }

  /* 차례로 넘긴 상태 == 점으로 바로 간 상태 (이전·점 이동이 상태를 정확히 만드는가) */
  function replay(evId){
    intro();
    var ev = X.events().filter(function(e){ return e.id === evId; })[0];
    if(!ev || !ev.ready) return {event:evId, error:"준비된 사건이 아님"};
    X.startEvent(evId);
    var seq = [];
    X.goBeat(0); X.finish(); seq.push(snap());
    for(var k = 1; k < ev.beats; k++){ X.next(); X.finish(); seq.push(snap()); }
    var bad = [];
    for(var j = ev.beats - 1; j >= 0; j--){
      X.goBeat(j); X.finish();
      if(snap() !== seq[j]) bad.push(j + 1);
    }
    X.closeEvent();
    return {event:evId, mismatchBeats:bad.reverse()};
  }

  /* 부품마다 패널: 3겹이 다 있는가 */
  function panels(){
    intro();
    var ids = Array.prototype.map.call(document.querySelectorAll("#world [data-actor]"), function(n){ return n.getAttribute("data-actor"); });
    ids = ids.filter(function(v, i){ return ids.indexOf(v) === i; });
    var res = ids.map(function(id){
      X.openPanel(id);
      var body = $("#panelBody");
      var r = {actor:id, what:!!(body.querySelector(".p-what") && body.querySelector(".p-what").textContent.trim()),
        talks:body.querySelectorAll(".talk .who").length, steps:body.querySelectorAll(".steps li").length,
        real:body.querySelectorAll("#realSec .xr").length, myth:!!body.querySelector(".myth"),
        colored:body.querySelectorAll(".nm").length};
      r.complete = r.what && r.talks > 0 && r.steps > 0 && r.real > 0;
      X.closePanel();
      return r;
    });
    return res;
  }

  /* 전체 보기에서 라벨 글자 크기 · 라벨이 클릭 물체를 가리는 정도 */
  function labels(){
    intro();
    X.finish(); var ct = X.api.camHome(0.01); ct.progress(1);   /* 전체 보기 배율로 확실히 옮긴 뒤 잰다 */
    var acts = Array.prototype.filter.call(document.querySelectorAll("#world .act"), vis).map(function(a){ return {id:a.getAttribute("data-actor"), r:a.getBoundingClientRect()}; });
    var sizes = [], covers = [];
    Array.prototype.forEach.call(document.querySelectorAll("#L_labels .lbl"), function(l){
      var t = Array.prototype.filter.call(l.querySelectorAll("text"), function(x){ return getComputedStyle(x).display !== "none"; })[0];
      if(!t || !vis(l)) return;
      var tr = t.getBoundingClientRect();
      sizes.push(+(tr.height / 1.2).toFixed(1));
      var lr = l.getBoundingClientRect();
      acts.forEach(function(a){
        var ar = a.r, area = ar.width * ar.height;
        if(area < 400) return;
        var c = inter(lr, ar) / area;
        if(c > 0.35) covers.push({label:t.textContent, actor:a.id, covered:+c.toFixed(2)});
      });
    });
    return {count:sizes.length, minPx:sizes.length ? Math.min.apply(null, sizes) : null, under12:sizes.filter(function(s){ return s < 12; }).length, heavyCover:covers};
  }

  /* 다른 화면 크기에서 재기 — 창을 못 바꿀 때. 같은 출처의 이 페이지를 w×h iframe 에 열고 이 스크립트를 그 안에서 실행한다 */
  async function at(w, h){
    var f = document.createElement("iframe");
    f.style.cssText = "position:fixed;left:0;top:0;width:" + w + "px;height:" + h + "px;border:0;z-index:99999;background:#fff";
    f.src = location.href.split("#")[0];
    document.body.appendChild(f);
    try{
      await new Promise(function(ok, no){ f.addEventListener("load", ok); setTimeout(function(){ no(new Error("iframe 로드 시간 초과")); }, 20000); });
      await new Promise(function(ok){ setTimeout(ok, 500); });
      f.contentWindow.eval("(" + ewvMain.toString() + ")()");
      return await f.contentWindow.EWV.all();
    } finally { f.remove(); }
  }

  window.EWV = {
    at:at, scan:scan, replay:replay, panels:panels, labels:labels, errors:function(){ return errors.slice(); },
    all:async function(){
      var evs = X.events().filter(function(e){ return e.ready; }).map(function(e){ return e.id; });
      var lab = labels();
      var scans = evs.map(scan), reps = evs.map(replay), pans = panels();
      var beats = [].concat.apply([], scans.map(function(s){ return (s.beats || []).map(function(b){ b.event = s.event; return b; }); }));
      var summary = {
        B1_errors:errors.length,
        B2_heroHidden:beats.filter(function(b){ return !b.heroVisible; }).map(function(b){ return b.event + "#" + b.beat; }),
        B3_bubbleOut:beats.filter(function(b){ return b.bubbleOut; }).map(function(b){ return b.event + "#" + b.beat; }),
        B3_bubbleUnderCaption:beats.filter(function(b){ return b.bubbleUnderCaption; }).map(function(b){ return b.event + "#" + b.beat; }),
        B4_replayMismatch:reps.filter(function(r){ return r.mismatchBeats && r.mismatchBeats.length; }),
        B5_panelIncomplete:pans.filter(function(p){ return !p.complete; }).map(function(p){ return p.actor; }),
        B6_labelMinPx:lab.minPx, B6_labelsUnder12:lab.under12,
        B7_labelCovers:lab.heavyCover.length,
        B8_labelOverBubble:beats.filter(function(b){ return b.labelOverBubble.length; }).map(function(b){ return b.event + "#" + b.beat; }),
        B9_tailAwayFromHero:beats.filter(function(b){ return b.tailAwayFromHero.length; }).map(function(b){
          return b.event + "#" + b.beat + "→" + b.tailAwayFromHero.map(function(t){ return t.pointsAt || "?"; }).join("/"); }),
        viewport:window.innerWidth + "x" + window.innerHeight,
        /* 한 크기만 재면 그 사실이 남도록 — 넓은 창(≥1000)과 세로가 짧은 창(<760)을 함께 재는 것이 rubric 절차 */
        sizeKind:(window.innerWidth >= 1000 ? "wide" : "narrow") + "/" + (window.innerHeight < 760 ? "short" : "tall"),
        screen:screen.width + "x" + screen.height, dpr:window.devicePixelRatio,
        inFrame:window !== window.top
      };
      summary.pass = summary.B1_errors === 0 && !summary.B2_heroHidden.length && !summary.B3_bubbleOut.length &&
        !summary.B4_replayMismatch.length && !summary.B5_panelIncomplete.length && (summary.B6_labelMinPx || 0) >= 11 &&
        !summary.B8_labelOverBubble.length;   /* B7·B9 는 경고만 */
      return JSON.stringify({summary:summary, beats:beats, panels:pans, labels:lab, errors:errors}, null, 1);
    }
  };
  return "EWV 준비됨 — await EWV.all()";
})();
