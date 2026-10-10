/* explainer 브라우저 검사 (rubric B) — 페이지를 연 뒤 이 파일 내용을 그대로 실행한다.
     1) 이 파일 전체를 브라우저 자동화의 JS 실행에 붙여 넣는다 → window.MEV 가 생긴다
     2) await MEV.all()      → 전체 결과 JSON (summary + 단계별)
   개별: MEV.step(n) · MEV.labels() · MEV.clipped()
   전제: template/index.html 의 id·클래스(#rail · #count · #cam · #stage · #demobar · #demoBtn · #verdict ·
         .reg.dim · .nd .t1(역할 라벨) · .nd .t2(보조 이름) · .edge)를 쓴다. 바꿨으면 아래 SEL 만 고친다.
   주의: 자동화 탭이 백그라운드면 타이머가 1초 단위로 뭉친다 — 시연 왕복 시간은 재지 않고 "돌다가 멈춘다"만 본다.
         단계가 많으면 도구 호출 45초 제한에 걸린다 — window.__r = null; MEV.all().then(r => window.__r = r) 로 띄우고
         나중에 window.__r 을 읽는다. 진행 위치는 window.__mevProgress 에 있다.
         페이지를 연 직후의 콘솔 에러는 이 스크립트가 못 잡는다 — 자동화 도구로 콘솔도 따로 읽는다. */
(function mevMain(){
  "use strict";
  var SEL = { rail:"#rail button", next:"#next", count:"#count", cam:"#cam", stage:"#stage",
              demobar:"#demobar", demoBtn:"#demoBtn", verdict:"#verdict",
              dimRegion:".reg.dim", onNode:".nd:not(.idle)", onEdge:".edge:not(.off)",
              label:".nd .t1", sub:".nd .t2" };          // 역할 라벨 · 보조로 작게 쓴 원래 이름
  var LABEL_MIN = 12, SUB_MIN = 10;                      // SKILL.md 2절의 하한

  var errors = [];
  window.addEventListener("error", function(e){ errors.push(String(e.message)); });
  window.addEventListener("unhandledrejection", function(e){ errors.push(String(e.reason)); });

  function $(s){ return document.querySelector(s); }
  function $$(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }
  /* 대기 — 타이머 콜백에서 바로 이어 가지 않고 MessageChannel 로 한 번 건너뛴다.
     타이머 콜백에서 이어지는 작업은 "연쇄 타이머"로 세어져 백그라운드 탭에서 점점 세게 조여지고(1초 → 1분),
     타이머 태스크 안에서 쓴 시간은 예산에서 깎여 어느 순간 안 깨운다. 건너뛰면 연쇄 수가 0 으로 돌아가고
     무거운 작업(클릭·레이아웃 측정)은 타이머 태스크 밖에서 돈다. */
  var hopQ = [], hop = new MessageChannel();
  hop.port1.onmessage = function(){ var f = hopQ.shift(); if(f) f(); };
  function wait(ms){ return new Promise(function(r){ setTimeout(function(){ hopQ.push(r); hop.port2.postMessage(0); }, ms); }); }
  function vis(el){
    for(var n = el; n && n.nodeType === 1 && n !== document.body; n = n.parentNode){
      var c = getComputedStyle(n);
      if(c.display === "none" || c.visibility === "hidden" || parseFloat(c.opacity) < 0.3) return false;
      if(n.matches && n.matches(SEL.dimRegion)) return false;
    }
    return true;
  }
  /* 백그라운드 탭에서는 CSS 전환이 진행되지 않아 카메라·칸이 시작 위치에 멈춰 있다.
     측정하는 동안만 전환을 꺼서 끝 상태로 보내고(지정된 값으로 즉시 점프), 끝나면 되돌린다. */
  function settled(fn){
    var st = document.createElement("style");
    st.textContent = SEL.cam + ", " + SEL.cam + " *{transition:none !important}";
    document.head.appendChild(st);
    void document.documentElement.offsetWidth;
    try { return fn(); } finally { st.remove(); }
  }
  function total(){ var m = /\/\s*(\d+)/.exec(($(SEL.count)||{}).textContent || ""); return m ? +m[1] : $$(SEL.rail).length; }
  function current(){ var m = /(\d+)\s*\//.exec(($(SEL.count)||{}).textContent || ""); return m ? +m[1] - 1 : -1; }
  function goTo(i){ var b = $$(SEL.rail)[i]; if(!b) throw new Error("rail 버튼 없음: " + i); b.click(); }

  /* 무대 지문 — #cam 안 id 있는 요소의 클래스·인라인 transform·opacity */
  function snap(){
    return $$(SEL.cam + " [id]").map(function(n){
      return n.id + "|" + (n.getAttribute("class")||"") + "|" + (n.style.transform||"") + "|" + (n.style.opacity||"");
    }).join("\n");
  }

  /* 라벨 실효 px — getScreenCTM().a 가 viewBox 배율 × 카메라 배율을 다 담는다 */
  function labels(){
    var out = { label:null, sub:null, labelEl:null, subEl:null };
    [["label", SEL.label], ["sub", SEL.sub]].forEach(function(pair){
      var key = pair[0];
      $$(SEL.cam + " " + pair[1]).forEach(function(t){
        if(!vis(t) || !t.getScreenCTM) return;
        var px = +(parseFloat(getComputedStyle(t).fontSize) * t.getScreenCTM().a).toFixed(1);
        if(out[key] === null || px < out[key]){ out[key] = px; out[key + "El"] = (t.textContent||"").trim().slice(0, 20); }
      });
    });
    return out;
  }

  /* 켜둔 노드·선이 무대 보이는 영역 밖으로 나갔나 — 화면 좌표로 비교 */
  function clipped(){
    var s = $(SEL.stage).getBoundingClientRect(), bad = [];
    $$(SEL.cam + " " + SEL.onNode + ", " + SEL.cam + " " + SEL.onEdge).forEach(function(el){
      if(!vis(el)) return;
      var b = el.getBoundingClientRect();
      if(b.width === 0 && b.height === 0) return;
      if(b.left < s.left - 1 || b.top < s.top - 1 || b.right > s.right + 1 || b.bottom > s.bottom + 1)
        bad.push(el.id || el.tagName);
    });
    return bad;
  }

  function hscroll(){ return document.documentElement.scrollWidth > document.documentElement.clientWidth; }

  function mark(i, phase){ window.__mevProgress = { i:i+1, phase:phase, t:Math.round(performance.now()) }; }
  async function step(i){
    var y0 = window.scrollY;
    mark(i, "go"); goTo(i);
    mark(i, "wait120"); await wait(120); mark(i, "wait800");
    var r = { i:i+1, scrollJump: Math.abs(window.scrollY - y0) > 2, hscroll: hscroll() };
    await wait(800);
    var lb = settled(labels);
    r.labelPx = lb.label; r.labelEl = lb.labelEl; r.subPx = lb.sub; r.subEl = lb.subEl;
    mark(i, "clipped"); r.clipped = settled(clipped);
    var bar = $(SEL.demobar), btn = $(SEL.demoBtn), v = $(SEL.verdict);
    r.demo = !!(bar && btn && !bar.classList.contains("empty") && vis(btn));
    if(r.demo){
      await wait(700);                       // 진입 후 1.5s — enter 의 움직임이 가라앉은 상태
      var autoOn = btn.getAttribute("aria-pressed") === "true";   // 자동 반복이면 이 사이(0.7s)에 켰다
      r.auto = autoOn;
      var base = autoOn ? null : snap();     // 되돌리기 기준: 진입 후 가라앉은 상태. auto 면 이미 켜져 있어 기준을 못 잡는다
      var vBefore = v ? v.textContent : "";
      mark(i, "click1"); btn.click(); await wait(700);
      r.pressedAfterClick = btn.getAttribute("aria-pressed");
      r.verdictChanged = v ? v.textContent !== vBefore : null;
      var vAfterClick = v ? v.textContent : "", pAfterClick = btn.getAttribute("aria-pressed");
      if(autoOn){                            // 사람이 눌렀으면 더 이상 혼자 바뀌면 안 된다
        mark(i, "autoWait"); await wait(4200);
        r.autoStoppedOnClick = (v ? v.textContent === vAfterClick : true) && btn.getAttribute("aria-pressed") === pAfterClick;
      }
      /* 되돌리기 동일성 — 끈 상태로 만들고 1.5s 가라앉힌 뒤 기준과 비교 */
      if(btn.getAttribute("aria-pressed") === "true"){ mark(i, "click2"); btn.click(); }
      await wait(1500);
      mark(i, "restore");
      if(base !== null){
        r.restoreMismatch = snap() !== base;
        /* 백그라운드 탭에서는 enter 의 연쇄 delay 가 1초씩 늘어져 기준·되돌린 상태가 서로 다른 시점에 찍힐 수 있다.
           걸렸으면 같은 간격(3s)으로 다시 재서 확정한다 */
        if(r.restoreMismatch){
          mark(i, "restoreConfirm"); goTo(i); await wait(3000); var base2 = snap();
          btn.click(); await wait(700); btn.click(); await wait(3000);
          r.restoreMismatch = snap() !== base2;
        }
      }
      else {                                 // auto: 한 번 더 켰다 끄고 두 되돌린 상태가 같은지만 본다(약한 검사)
        var off1 = snap();
        btn.click(); await wait(700); btn.click(); await wait(1500);
        r.restoreMismatch = snap() !== off1; r.restoreWeak = true;
      }
      r.hasAriaLive = !!(v && v.getAttribute("aria-live"));
    }
    /* 단계 안에서 혼자 바뀌는가 — 살아 있는 화면이면 정상이므로 경고용 */
    mark(i, "drift"); var a = snap(); await wait(1500); r.drifting = snap() !== a;
    mark(i, "done");
    return r;
  }

  async function all(){
    var n = total(), steps = [];
    errors.length = 0;
    for(var i = 0; i < n; i++) steps.push(await step(i));
    /* 테마: 강제 다크에서 body 배경이 바뀌는가 */
    var root = document.documentElement, was = root.getAttribute("data-theme");
    var bgLight = getComputedStyle(document.body).backgroundColor;
    root.setAttribute("data-theme", "dark"); await wait(50);
    var bgDark = getComputedStyle(document.body).backgroundColor;
    if(was === null) root.removeAttribute("data-theme"); else root.setAttribute("data-theme", was);
    goTo(0);
    var fails = {
      errors: errors.slice(),
      hscroll: steps.filter(function(s){ return s.hscroll; }).map(function(s){ return s.i; }),
      scrollJump: steps.filter(function(s){ return s.scrollJump; }).map(function(s){ return s.i; }),
      labelBelow: steps.filter(function(s){ return s.labelPx !== null && s.labelPx < LABEL_MIN; }).map(function(s){ return s.i + ":" + s.labelPx + "px(" + s.labelEl + ")"; }),
      subBelow: steps.filter(function(s){ return s.subPx !== null && s.subPx < SUB_MIN; }).map(function(s){ return s.i + ":" + s.subPx + "px(" + s.subEl + ")"; }),
      clipped: steps.filter(function(s){ return s.clipped.length; }).map(function(s){ return s.i + ":" + s.clipped.join(","); }),
      demoNoChange: steps.filter(function(s){ return s.demo && !s.verdictChanged; }).map(function(s){ return s.i; }),
      pressedMissing: steps.filter(function(s){ return s.demo && s.pressedAfterClick !== "true" && s.pressedAfterClick !== "false"; }).map(function(s){ return s.i; }),
      restoreMismatch: steps.filter(function(s){ return s.demo && s.restoreMismatch; }).map(function(s){ return s.i; }),
      autoKeepsRunning: steps.filter(function(s){ return s.auto && s.autoStoppedOnClick === false; }).map(function(s){ return s.i; }),
      ariaLiveMissing: steps.filter(function(s){ return s.demo && !s.hasAriaLive; }).map(function(s){ return s.i; }),
      themeUnchanged: bgLight === bgDark
    };
    var warns = {
      drifting: steps.filter(function(s){ return s.drifting && !s.demo; }).map(function(s){ return s.i; }),
      demoSteps: steps.filter(function(s){ return s.demo; }).length,
      stepsWithoutDemo: steps.filter(function(s){ return !s.demo; }).map(function(s){ return s.i; }),
      restoreWeak: steps.filter(function(s){ return s.restoreWeak; }).map(function(s){ return s.i; })
    };
    var pass = !fails.errors.length && !fails.hscroll.length && !fails.scrollJump.length && !fails.labelBelow.length &&
               !fails.subBelow.length && !fails.clipped.length && !fails.demoNoChange.length && !fails.pressedMissing.length &&
               !fails.restoreMismatch.length && !fails.autoKeepsRunning.length && !fails.ariaLiveMissing.length && !fails.themeUnchanged;
    return { summary:{ pass:pass, viewport: innerWidth + "x" + innerHeight, stageW: Math.round($(SEL.stage).getBoundingClientRect().width),
                       steps:n, hidden: document.hidden, fails:fails, warns:warns }, steps:steps };
  }

  window.MEV = { all:all, step:step, labels:labels, clipped:clipped, snap:snap, SEL:SEL };
  return "MEV 준비됨 — await MEV.all()";
})();
