/* 쿠버네티스 항구 — 지도 그리기 · 배경 움직임 · 기준 상태 · 사건별 장면 움직임 */
(function(){
"use strict";
var ISO = window.ISO;
var iso = ISO.iso, isoL = ISO.isoL, el = ISO.el, box = ISO.box, flat = ISO.flat, faceR = ISO.faceR, faceL = ISO.faceL, C = ISO.C, act = ISO.act;

/* 컨테이너 상자 (Pod) — 바깥 그룹은 위치, 안쪽(body)은 애니메이션 */
function container(parent, id){
  var outer = ISO.mover(parent, {id:id, "class":"ctr ghost act nohit", "data-actor":"pod", tabindex:"0", role:"button", "aria-label":"컨테이너 묶음(Pod) 알아보기"});
  var g = outer.body;
  box(g, isoL, 0, 0, 0, 56, 36, 30, C.coral);
  for(var i=1;i<4;i++){
    var a = isoL(56, i*9, 4), b = isoL(56, i*9, 26);
    el("line", {"class":"door", x1:a[0], y1:a[1], x2:b[0], y2:b[1]}, g);
  }
  var tp = isoL(28, 36, 15);
  ISO.text(g, tp[0], tp[1] + 4, "my-shop", "door", {"text-anchor":"middle", "font-size":"8.5", "font-weight":"800", fill:"#fff", "font-family":"monospace"});
  return outer;
}

/* 크레인 지브 — hook(gx,gy,gz) 를 따라 다시 그린다 */
function drawCrane(R){
  var h = R.hook, T = R.craneTop;
  var tip = iso(h.gx, h.gy, 256), hk = iso(h.gx, h.gy, h.gz + 2);
  var dx = tip[0] - T[0], dy = tip[1] - T[1];
  var cx = T[0] - dx * 0.22, cy = T[1] - dy * 0.22;
  function ln(e, x1, y1, x2, y2){ e.setAttribute("x1", x1); e.setAttribute("y1", y1); e.setAttribute("x2", x2); e.setAttribute("y2", y2); }
  ln(R.jibLine, T[0], T[1], tip[0], tip[1]);
  ln(R.jibLine2, T[0], T[1] - 1, tip[0], tip[1] - 1);
  ln(R.jibCounter, T[0], T[1], cx, cy);
  R.weight.setAttribute("x", cx - 8); R.weight.setAttribute("y", cy - 4);
  R.trolley.setAttribute("x", tip[0] - 6); R.trolley.setAttribute("y", tip[1] - 2);
  ln(R.cable, tip[0], tip[1] + 4, hk[0], hk[1] - 10);
  R.hookEl.setAttribute("transform", "translate(" + hk[0] + "," + (hk[1] - 12) + ")");
  if(R.carry) ISO.place(R.carry, h.gx - 28, h.gy - 18, h.gz - 30);
}
function placeRobot(R){ ISO.place(R.robot, R.robotPos.gx, 252, 26); }
function robotPt(R){ var p = iso(R.robotPos.gx, 252, 26); return [p[0], p[1] - 50]; }

var YARD = [[350,228],[412,228],[350,276]];
var PLAN = [{pier:1, slot:0, ip:"10.244.2.4"}, {pier:0, slot:0, ip:"10.244.1.5"}, {pier:1, slot:1, ip:"10.244.2.5"}];

window.WORLD = {
  home:{x:800, y:470, s:1.04},

  /* ── 지도 그리기 (한 번) ───────────────────── */
  build:function(api){
    var L = api.L, R = {};
    var defs = api.defs;
    defs.insertAdjacentHTML("beforeend",
      "<linearGradient id='seaGrad' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#9ad8e4'/><stop offset='1' stop-color='#5eb3c9'/></linearGradient>" +
      "<linearGradient id='beamGrad' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='#fff8d6' stop-opacity='.75'/><stop offset='1' stop-color='#fff8d6' stop-opacity='0'/></linearGradient>");

    /* 바다 잔물결 */
    for(var i=0;i<46;i++){
      var x = (i*137) % 1700 - 50, y = 560 + ((i*89) % 470);
      if(i % 3 === 0) y = (i*53) % 520;
      el("path", {"class":"wave", d:"M" + x + "," + y + " q8,-6 16,0 q8,-6 16,0", fill:"none", stroke:"rgba(255,255,255,.55)", "stroke-width":2, "stroke-linecap":"round"}, L.base);
    }

    /* 땅 · 도로 · 언덕 */
    box(L.ground, iso, 0, 0, -36, 700, 650, 36, C.sand);
    flat(L.ground, 150, 350, 0, 552, 34, {fill:"#cfd5db"});
    var r1 = iso(160, 367, 0), r2 = iso(700, 367, 0);
    el("line", {x1:r1[0], y1:r1[1], x2:r2[0], y2:r2[1], stroke:"#fff", "stroke-width":2.4, "stroke-dasharray":"14 12"}, L.ground);
    flat(L.ground, 330, 205, 0, 34, 150, {fill:"#cfd5db"});
    var hill = act(L.ground, "hill", "관제 언덕");
    box(hill, iso, 30, 30, 0, 290, 240, 26, C.grass);
    [[80,220],[260,60],[300,230],[60,120],[200,240]].forEach(function(q){
      var c = iso(q[0], q[1], 26); el("circle", {cx:c[0], cy:c[1], r:5, fill:"#7fb862"}, L.ground);
      el("circle", {cx:c[0]+7, cy:c[1]+2, r:4, fill:"#93c977"}, L.ground);
    });

    /* 대기 구역 (Pending) */
    var yard = act(L.ground, "yard", "대기 구역");
    flat(yard, 340, 210, 0.5, 148, 118, {fill:"#fbf1d0", stroke:"#e0a82e", "stroke-width":2.4, "stroke-dasharray":"10 7"});
    for(var k=0;k<5;k++){
      var s1 = iso(352 + k*28, 214, 0.6), s2 = iso(340 + k*28, 226, 0.6);
      el("line", {x1:s1[0], y1:s1[1], x2:s2[0], y2:s2[1], stroke:"#f0c75e", "stroke-width":3}, yard);
    }

    /* 관제탑 (kube-apiserver) */
    var tower = act(L.back, "tower", "관제탑 접수 창구");
    box(tower, iso, 108, 98, 26, 68, 68, 112, C.white);
    faceL(tower, 128, 166, 26, 26, 38, "#2e4a6b");
    faceL(tower, 132, 166, 70, 18, 14, "#8cc0ee");
    faceR(tower, 176, 112, 82, 16, 14, "#8cc0ee"); faceR(tower, 176, 138, 82, 16, 14, "#8cc0ee");
    box(tower, iso, 98, 88, 138, 88, 88, 40, C.glass);
    box(tower, iso, 94, 84, 178, 96, 96, 8, C.navy);
    var at = iso(142, 132, 186), at2 = iso(142, 132, 222);
    el("line", {x1:at[0], y1:at[1], x2:at2[0], y2:at2[1], stroke:"#334155", "stroke-width":3}, tower);
    R.beacon = el("circle", {cx:at2[0], cy:at2[1], r:5, fill:"#ef4444"}, tower);
    R.towerPt = iso(142, 132, 158);
    R.towerDoor = iso(141, 166, 40);
    var bo = iso(142, 132, 172);
    var beam = el("g", {transform:"translate(" + bo[0] + "," + bo[1] + ")"}, L.back);
    R.beamRot = el("polygon", {points:"0,0 -330,150 -300,215", fill:"url(#beamGrad)", opacity:.55}, beam);

    /* 금고 (etcd) */
    var vault = act(L.back, "vault", "금고 장부");
    box(vault, iso, 222, 66, 26, 74, 60, 38, C.stone);
    var vd = iso(296, 96, 45);
    el("ellipse", {cx:vd[0], cy:vd[1], rx:13, ry:16, fill:"#e0b44c", stroke:"#a77d22", "stroke-width":2.5}, vault);
    el("circle", {cx:vd[0], cy:vd[1], r:4, fill:"#7a5a14"}, vault);
    R.vaultGlow = el("circle", {cx:vd[0], cy:vd[1], r:40, fill:"url(#glow)", opacity:0}, vault);
    R.vaultPt = iso(259, 96, 64);

    /* 순찰 로봇 (controller-manager) */
    R.robot = act(L.mid, "robot", "순찰 로봇");
    ISO.robot(R.robot);
    ISO.label(R.robot, 0, -84, "순찰 로봇", "controller-manager");
    R.robotPos = {gx:80};

    /* 배포 사무소 (kubectl) */
    var office = act(L.mid, "office", "배포 사무소");
    box(office, iso, 70, 440, 0, 100, 80, 52, C.wall);
    box(office, iso, 64, 434, 52, 112, 92, 7, C.roofR);
    faceR(office, 170, 452, 16, 22, 20, "#8cc0ee"); faceR(office, 170, 486, 16, 22, 20, "#8cc0ee");
    faceL(office, 92, 520, 0, 22, 34, "#7c4a35");
    var op = iso(196, 512, 0);
    ISO.person(office, op[0], op[1], {body:"#6366f1", clip:true});
    R.officePt = iso(120, 480, 66);

    /* 크레인 (kube-scheduler) */
    var crane = act(L.mid, "crane", "크레인 배치원");
    box(crane, iso, 516, 250, 0, 40, 40, 12, C.conc);
    box(crane, iso, 528, 262, 12, 16, 16, 232, C.yellow);
    for(var j=0;j<11;j++){
      var z0 = 16 + j*21, a1 = iso(544, 262, z0), a2 = iso(544, 278, z0 + 21);
      el("line", {x1:a1[0], y1:a1[1], x2:a2[0], y2:a2[1], stroke:"#b7830f", "stroke-width":1.5}, crane);
      var b1 = iso(528, 278, z0), b2 = iso(544, 278, z0 + 21);
      el("line", {x1:b1[0], y1:b1[1], x2:b2[0], y2:b2[1], stroke:"#b7830f", "stroke-width":1.5}, crane);
    }
    box(crane, iso, 522, 256, 244, 28, 28, 20, C.navy);
    faceR(crane, 550, 262, 250, 16, 9, "#8cc0ee");
    R.craneTop = iso(536, 270, 256);
    var jib = el("g", {}, L.fx);
    R.jibCounter = el("line", {stroke:"#c4911c", "stroke-width":5, "stroke-linecap":"round"}, jib);
    R.weight = el("rect", {width:16, height:12, rx:2, fill:"#475569"}, jib);
    R.jibLine = el("line", {stroke:"#dba62b", "stroke-width":6, "stroke-linecap":"round"}, jib);
    R.jibLine2 = el("line", {stroke:"#f7c948", "stroke-width":2, "stroke-linecap":"round"}, jib);
    R.cable = el("line", {stroke:"#334155", "stroke-width":1.6}, jib);
    R.trolley = el("rect", {width:12, height:7, rx:2, fill:"#334155"}, jib);
    R.hookEl = el("path", {d:"M-5,0 L5,0 L5,5 L0,10 L-5,5 Z", fill:"#475569"}, jib);
    R.hook = {gx:430, gy:250, gz:150};

    /* 안내소 (CoreDNS) · 우편함 (Service) — 다음 사건에서 쓴다 */
    var booth = act(L.mid, "booth", "안내소");
    box(booth, iso, 560, 478, 0, 46, 46, 40, C.wall);
    box(booth, iso, 554, 472, 40, 58, 58, 8, C.teal);
    faceR(booth, 606, 488, 12, 26, 18, "#8cc0ee");
    var mb = act(L.mid, "mailbox", "고정 우편함");
    var mp = iso(630, 590, 0);
    el("ellipse", {cx:mp[0], cy:mp[1], rx:12, ry:5, fill:"rgba(0,0,0,.2)"}, mb);
    el("rect", {x:mp[0]-2.5, y:mp[1]-26, width:5, height:26, fill:"#475569"}, mb);
    el("rect", {x:mp[0]-13, y:mp[1]-48, width:26, height:24, rx:8, fill:"#2563eb"}, mb);
    el("rect", {x:mp[0]-8, y:mp[1]-41, width:16, height:3, rx:1.5, fill:"#1e3a8a"}, mb);

    /* 부두 (Worker Node) */
    R.piers = [];
    [110, 390].forEach(function(g0, n){
      var P = {};
      var pg = el("g", {}, L.front);
      var deck = act(pg, "pier", "부두");
      box(deck, iso, 700, g0, -32, 190, 190, 32, C.wood);
      for(var q=1;q<8;q++){ var w1 = iso(700 + q*24, g0, 0.3), w2 = iso(700 + q*24, g0+190, 0.3);
        el("line", {x1:w1[0], y1:w1[1], x2:w2[0], y2:w2[1], stroke:"#b88654", "stroke-width":1.2}, deck); }
      var c1 = iso(772, g0+95, 1), c2 = iso(814, g0+95, 1), c3 = iso(814, g0+22, 1), c4 = iso(814, g0+178, 1);
      P.cable = el("path", {"class":"cable act nohit", "data-actor":"cni", d:"M" + c1 + " L" + c2 + " M" + c3 + " L" + c4}, pg);
      var wh = act(pg, "pier", "부두");
      box(wh, iso, 712, g0+14, 0, 60, 162, 60, C.wall);
      box(wh, iso, 708, g0+10, 60, 68, 170, 8, C.roofB);
      faceR(wh, 772, g0+40, 0, 40, 44, "#94a3b8");
      faceR(wh, 772, g0+110, 26, 30, 18, "#8cc0ee");
      P.whLight = faceR(wh, 772, g0+110, 26, 30, 18, "#fde68a"); P.whLight.setAttribute("opacity", 0);
      P.slots = [];
      for(var s=0;s<3;s++){
        var sy = g0 + 20 + s*54;
        flat(pg, 822, sy, 0.6, 58, 38, {fill:"none", stroke:"#fff", "stroke-width":2, "stroke-dasharray":"6 5", opacity:.8});
        P.slots.push([823, sy + 1]);
      }
      var mach = act(pg, "machine", "하역 기계");
      box(mach, iso, 780, g0+138, 0, 32, 32, 30, C.gray);
      var gp = iso(796, g0+154, 30);
      P.gear = el("g", {transform:"translate(" + gp[0] + "," + (gp[1]-2) + ")"}, mach);
      el("circle", {cx:0, cy:0, r:9, fill:"none", stroke:"#334155", "stroke-width":5, "stroke-dasharray":"3.5 2.6"}, P.gear);
      el("circle", {cx:0, cy:0, r:3, fill:"#334155"}, P.gear);
      P.machPt = iso(796, g0+154, 34);
      var fm = act(pg, "foreman", "부두 반장");
      var fp = iso(800, g0+58, 0);
      ISO.person(fm, fp[0], fp[1], {hard:true, clip:true, body:"#f97316"});
      P.foremanPt = [fp[0], fp[1] - 50];
      P.bang = ISO.bang(fm, fp[0] + 14, fp[1] - 70);
      api.label(fp[0] - 40, fp[1] + 14, "부두 반장", "kubelet");
      api.label(gp[0] + 4, gp[1] + 70, "하역 기계", "containerd");
      var pl = iso(895, g0+95, -14);
      api.label(pl[0] + 40, pl[1] + 12, "부두 " + (n+1), "worker-" + (n+1), true);
      R.piers.push(P);
    });

    /* 이미지 저장소 선박 (Registry) */
    var ship = act(L.front, "ship", "이미지 저장소선");
    var sh = el("g", {}, ship); R.shipBody = sh;
    box(sh, iso, 560, 700, -16, 170, 60, 24, C.navy);
    faceR(sh, 730, 700, -8, 60, 5, "#ef4444");
    [[575,708,C.green],[612,708,C.gold],[575,732,C.purple],[649,708,C.coral]].forEach(function(q){ box(sh, iso, q[0], q[1], 8, 34, 22, 18, q[2]); });
    box(sh, iso, 690, 706, 8, 26, 48, 36, C.white);
    faceR(sh, 716, 714, 30, 30, 8, "#8cc0ee");
    R.smokeAt = iso(703, 718, 52);
    R.shipPt = iso(640, 725, 34);

    /* 구름 · 갈매기 */
    var clouds = el("g", {opacity:.8}, L.labels);
    [[260,140],[1260,110],[1420,330]].forEach(function(c){
      var g = el("g", {"class":"cloud", transform:"translate(" + c[0] + "," + c[1] + ")"}, clouds);
      el("ellipse", {cx:0, cy:0, rx:46, ry:16, fill:"#fff"}, g);
      el("ellipse", {cx:-24, cy:6, rx:30, ry:12, fill:"#fff"}, g);
      el("ellipse", {cx:26, cy:5, rx:32, ry:12, fill:"#fff"}, g);
    });
    R.gulls = el("g", {}, L.labels);
    [[0,0],[30,14],[58,4]].forEach(function(q){
      el("path", {d:"M" + q[0] + "," + q[1] + " q7,-7 14,0 q7,-7 14,0", fill:"none", stroke:"#334155", "stroke-width":2.2, "stroke-linecap":"round"}, R.gulls);
    });

    /* 라벨 */
    var p;
    p = iso(30, 270, 0); api.label(p[0] - 6, p[1] + 34, "관제 언덕", "Control Plane", true);
    p = iso(142, 132, 196); api.label(p[0] + 92, p[1] + 10, "관제탑 접수 창구", "kube-apiserver");
    p = iso(259, 96, 64); api.label(p[0] - 4, p[1] - 44, "금고 장부", "etcd");
    p = R.craneTop; api.label(p[0] + 82, p[1] + 70, "크레인 배치원", "kube-scheduler");
    p = iso(414, 330, 0); api.label(p[0] - 30, p[1] + 16, "대기 구역", "Pending Pods");
    p = iso(120, 480, 60); api.label(p[0], p[1] - 22, "배포 사무소", "kubectl");
    p = iso(583, 501, 48); api.label(p[0], p[1] - 22, "안내소", "CoreDNS");
    p = iso(630, 590, 0); api.label(p[0] - 4, p[1] - 70, "고정 우편함", "Service");
    p = iso(640, 730, 60); api.label(p[0] - 40, p[1] - 30, "이미지 저장소선", "Registry");

    /* 움직이는 물체 */
    R.ctrs = [container(L.fx, "c1"), container(L.fx, "c2"), container(L.fx, "c3")];
    R.ipTags = [0,1,2].map(function(){
      var g = el("g", {"class":"iptag", opacity:0}, L.fx);
      el("rect", {x:-44, y:-11, width:88, height:22, rx:11}, g);
      el("text", {x:0, y:1}, g);
      return g;
    });
    R.doc = ISO.paper(L.fx, "×3");
    R.crates = [0,1].map(function(){
      var g = el("g", {opacity:0}, L.fx);
      box(g, isoL, -9, -7, 0, 18, 14, 14, ["#ffd8c9","#ffb59a","#f29a7a"]);
      return g;
    });
    drawCrane(R);
    return R;
  },

  /* ── 배경 움직임 — 아무것도 안 해도 살아 있게 ── */
  ambient:function(api, R){
    gsap.to(R.beamRot, {rotation:46, transformOrigin:"100% 0%", duration:5.5, yoyo:true, repeat:-1, ease:"sine.inOut"});
    gsap.to(R.beacon, {opacity:.15, duration:.7, yoyo:true, repeat:-1, ease:"power1.inOut"});
    R.patrol = gsap.to(R.robotPos, {gx:290, duration:7, yoyo:true, repeat:-1, ease:"sine.inOut", onUpdate:function(){ placeRobot(R); }});
    var w = document.getElementById("world");
    gsap.to(w.querySelectorAll(".eye"), {scaleY:.1, transformOrigin:"50% 50%", duration:.08, yoyo:true, repeat:-1, repeatDelay:3.2});
    gsap.to(w.querySelectorAll(".bulb"), {opacity:.3, duration:.5, yoyo:true, repeat:-1});
    gsap.to(R.shipBody, {y:4, duration:2.2, yoyo:true, repeat:-1, ease:"sine.inOut"});
    gsap.to(w.querySelectorAll(".wave"), {x:"+=12", opacity:.15, duration:2.6, yoyo:true, repeat:-1, ease:"sine.inOut", stagger:{each:.18, from:"random"}});
    gsap.to(w.querySelectorAll(".cloud"), {x:"+=70", duration:18, yoyo:true, repeat:-1, ease:"sine.inOut", stagger:3});
    gsap.to(w.querySelectorAll(".bob"), {y:-1.6, duration:.9, yoyo:true, repeat:-1, ease:"sine.inOut", stagger:{each:.3, from:"random"}});
    gsap.fromTo(R.gulls, {x:-260, y:330}, {x:1900, y:170, duration:30, repeat:-1, ease:"none"});
    gsap.to(R.gulls.querySelectorAll("path"), {scaleY:.4, transformOrigin:"50% 100%", duration:.35, yoyo:true, repeat:-1, stagger:.12});
    var sm = R.smokeAt;
    for(var i=0;i<3;i++){
      var c = ISO.el("circle", {cx:sm[0], cy:sm[1], r:7, fill:"#e2e8f0", opacity:0}, R.shipBody);
      gsap.fromTo(c, {attr:{cy:sm[1], r:5}, opacity:.8}, {attr:{cy:sm[1] - 60, r:15}, x:-24, opacity:0, duration:3, repeat:-1, delay:i, ease:"power1.out"});
    }
  },

  /* ── 기준 상태 — 사건 시작·장면 이동마다 여기로 돌아온다 ── */
  reset:function(api, R){
    gsap.killTweensOf([R.doc, R.hook]);
    R.carry = null;
    R.hook.gx = 430; R.hook.gy = 250; R.hook.gz = 150; drawCrane(R);
    R.ctrs.forEach(function(c, i){
      gsap.killTweensOf(c.body);
      c.classList.add("ghost");
      ISO.place(c, YARD[i][0], YARD[i][1], 0);
      gsap.set(c.body, {opacity:0, y:0, scale:1});
    });
    R.ipTags.forEach(function(t){ gsap.set(t, {opacity:0}); });
    gsap.set(R.doc, {opacity:0, x:0, y:0, scale:1});
    gsap.set(R.doc.seal, {opacity:0});
    R.piers.forEach(function(P){ P.cable.classList.remove("live"); gsap.set(P.whLight, {opacity:0}); gsap.set(P.bang, {opacity:0}); });
    R.crates.forEach(function(c){ gsap.set(c, {opacity:0}); });
    gsap.set(R.vaultGlow, {opacity:0});
    if(R.patrol) R.patrol.play();
  },
  afterEvent:function(api, R){ if(R.patrol) R.patrol.play(); },

  /* ── 사건별 장면 — content.js 의 beats 와 개수·순서가 같아야 한다 ── */
  scenes:{
    deploy:[
      /* 1. 요청서 보내기 */
      function(tl, api, R){
        tl.add(api.camTo(660, 310, 1.32, 1.3));
        var o = [R.officePt[0], R.officePt[1] - 10], d = [R.towerDoor[0], R.towerDoor[1] - 6];
        tl.set(R.doc, {x:o[0], y:o[1], opacity:0, scale:.3});
        tl.to(R.doc, {opacity:1, scale:1.25, duration:.5, ease:"back.out(2)"}, "-=.3");
        api.fly(tl, R.doc, o, d, {duration:2.2, lift:150});
        tl.to(R.doc, {scale:.9, duration:.3}, "-=.3");
      },
      /* 2. 창구 검사 — 도장 3개 */
      function(tl, api, R){
        tl.add(api.camTo(630, 175, 1.55, 1.2));
        var b = api.bubble(430, 34, 320, 214, [748, 108, 790, 150, 748, 142]), g = b.inner, el = api.el;
        api.text(g, 452, 66, "관제탑 접수 창구 안", "t");
        api.text(g, 452, 87, "도장 세 개를 모두 받아야 통과해요", "s");
        var dg = el("g", {transform:"translate(452,104)"}, g);
        el("rect", {x:0, y:0, width:30, height:38, rx:3, fill:"#fff", stroke:"#334155", "stroke-width":1.5}, dg);
        [10,17,24].forEach(function(yy){ el("line", {x1:5, y1:yy, x2:25, y2:yy, stroke:"#94a3b8", "stroke-width":1.8}, dg); });
        api.text(g, 495, 120, "my-shop.yaml", "m");
        api.text(g, 495, 138, "replicas: 3", "m", {fill:"#2563eb"});
        var inks = [["신원","인증"],["권한","인가 · RBAC"],["규칙","승인 제어"]].map(function(n, i){
          var cx = 496 + i*92, cy = 190;
          var s = el("g", {"class":"stamp"}, g);
          el("circle", {cx:cx, cy:cy, r:27}, s);
          api.text(s, cx, cy + 5, n[0], "");
          api.text(g, cx, cy + 44, n[1], "s", {"text-anchor":"middle"});
          var ink = el("g", {"class":"stamp on", opacity:0}, g);
          el("circle", {cx:cx, cy:cy, r:27}, ink);
          api.text(ink, cx, cy - 1, n[0], "");
          api.text(ink, cx, cy + 14, "✓", "", {"text-anchor":"middle", "font-size":"13", fill:"#dc2626", "font-weight":"900"});
          return ink;
        });
        api.pop(tl, b, "-=.5");
        inks.forEach(function(ink, i){
          tl.fromTo(ink, {opacity:0, scale:2.2, rotation:-25, transformOrigin:"50% 50%"}, {opacity:1, scale:1, rotation:-8, duration:.42, ease:"power3.in"}, "+=" + (i ? .5 : .7));
          tl.to(b.inner, {x:2, duration:.05, yoyo:true, repeat:3}, ">-0.02");
        });
        tl.to(R.doc.seal, {opacity:1, duration:.3}, "+=.2");
      },
      /* 3. 금고 장부에 기록 */
      function(tl, api, R){
        tl.add(api.camTo(800, 290, 1.2, 1.2));
        api.clearBubbles(tl, "<");
        var d = [R.towerDoor[0], R.towerDoor[1] - 6], v = [R.vaultPt[0] + 36, R.vaultPt[1] - 2];
        api.fly(tl, R.doc, d, v, {duration:1.4, lift:90}, "-=.6");
        tl.to(R.doc, {scale:.2, opacity:0, duration:.4});
        tl.fromTo(R.vaultGlow, {opacity:0}, {opacity:1, duration:.3, yoyo:true, repeat:1}, "<");
        var b = api.bubble(1000, 150, 250, 122, [1000, 214, 975, 236, 1000, 232]);
        api.text(b.inner, 1020, 180, "📒 금고 장부", "t");
        api.text(b.inner, 1020, 206, "deployment / my-shop", "m");
        api.text(b.inner, 1020, 230, "원하는 수   3", "m", {fill:"#2563eb"});
        api.text(b.inner, 1020, 252, "현재 수     0", "m", {fill:"#dc2626"});
        api.pop(tl, b, "-=.1");
        var o = R.officePt;
        var r = api.bubble(o[0] - 120, o[1] - 120, 290, 62, [o[0] - 10, o[1] - 58, o[0] + 2, o[1] - 36, o[0] + 14, o[1] - 58]);
        api.text(r.inner, o[0] - 104, o[1] - 94, "deployment.apps/my-shop created", "m", {fill:"#16a34a", "font-weight":"700"});
        api.text(r.inner, o[0] - 104, o[1] - 72, "접수 완료 — 사무소의 일은 여기서 끝", "s");
        api.pop(tl, r, "+=.4");
      },
      /* 4. 순찰 로봇이 차이를 발견 → 자리 미정 컨테이너 3개 */
      function(tl, api, R){
        tl.call(function(){ if(R.patrol) R.patrol.pause(); });
        tl.add(api.camTo(820, 380, 1.42, 1.2));
        api.clearBubbles(tl, "<");
        tl.to(R.robotPos, {gx:230, duration:1, ease:"power2.inOut", onUpdate:function(){ placeRobot(R); }}, "<");
        api.showLink(tl, "robot", function(){ return robotPt(R); }, R.towerPt, ">");
        var rp = iso(230, 252, 26);
        var b = api.bubble(rp[0] - 250, rp[1] - 112, 208, 68, [rp[0] - 46, rp[1] - 76, rp[0] - 20, rp[1] - 60, rp[0] - 46, rp[1] - 60]);
        api.text(b.inner, rp[0] - 232, rp[1] - 86, "원하는 3  ·  현재 0", "t");
        var bl = api.text(b.inner, rp[0] - 232, rp[1] - 62, "차이 발견! 3개 만들게요", "s");
        api.pop(tl, b, "+=.2");
        R.ctrs.forEach(function(c, i){
          tl.fromTo(c.body, {opacity:0, y:-40}, {opacity:1, y:0, duration:.55, ease:"bounce.out"}, i ? "-=.25" : "+=.5");
        });
        tl.call(function(){ bl.textContent = "만들었어요 — 아직 자리는 미정"; }, null, "+=.2");
      },
      /* 5. 크레인 배치원 — 거르기·점수·배치 */
      function(tl, api, R){
        tl.add(api.camTo(1050, 540, 1.08, 1.4));
        api.clearBubbles(tl, "<");
        api.hideLinks(tl, ["robot"], "<");
        api.showLink(tl, "crane", [R.craneTop[0], R.craneTop[1] + 20], R.towerPt, ">");
        var b = api.bubble(1250, 330, 262, 104, null);
        api.text(b.inner, 1270, 360, "어느 부두에 둘까?", "t");
        api.text(b.inner, 1270, 386, "부두 1  거르기 ✓  점수 72", "m");
        var best = api.text(b.inner, 1270, 410, "부두 2  거르기 ✓  점수 85 ★", "m", {fill:"#2563eb", "font-weight":"700"});
        api.pop(tl, b, "+=.1");
        tl.fromTo(best, {opacity:0}, {opacity:1, duration:.3, repeat:2, yoyo:true}, "+=.3");
        var hk = R.hook, draw = function(){ drawCrane(R); };
        R.ctrs.forEach(function(c, i){
          var y = YARD[i], s = R.piers[PLAN[i].pier].slots[PLAN[i].slot];
          tl.to(hk, {gx:y[0] + 28, gy:y[1] + 18, gz:130, duration:.7, ease:"power2.inOut", onUpdate:draw});
          tl.to(hk, {gz:30, duration:.35, ease:"power1.in", onUpdate:draw});
          tl.call(function(){ R.carry = c; });
          tl.to(hk, {gz:130, duration:.35, ease:"power1.out", onUpdate:draw});
          tl.to(hk, {gx:s[0] + 28, gy:s[1] + 18, duration:.9, ease:"power2.inOut", onUpdate:draw});
          tl.to(hk, {gz:30, duration:.35, ease:"power1.in", onUpdate:draw});
          tl.call(function(){ R.carry = null; ISO.place(c, s[0], s[1], 0); });
        });
        tl.to(hk, {gx:430, gy:250, gz:150, duration:.8, ease:"power2.inOut", onUpdate:draw});
      },
      /* 6. 부두 반장 → 하역 기계 → 이미지 → 실행 */
      function(tl, api, R){
        tl.add(api.camTo(1060, 640, 1.12, 1.3));
        api.clearBubbles(tl, "<");
        api.hideLinks(tl, ["crane"], "<");
        R.piers.forEach(function(P, n){
          api.showLink(tl, "f" + (n + 1), P.foremanPt, R.towerPt, n ? "<" : ">");
          tl.fromTo(P.bang, {opacity:0, y:6}, {opacity:1, y:0, duration:.35, ease:"back.out(3)"}, "<");
        });
        tl.addLabel("pull", "+=.5");
        R.piers.forEach(function(P, n){
          var cr = R.crates[n];
          tl.set(cr, {x:R.shipPt[0], y:R.shipPt[1], opacity:0}, "pull");
          tl.to(cr, {opacity:1, duration:.2}, "pull");
          api.fly(tl, cr, R.shipPt, P.machPt, {duration:1.5, lift:160}, "pull");
          tl.to(cr, {opacity:0, scale:.5, duration:.25}, "pull+=1.5");
          tl.to(P.gear, {rotation:"+=540", transformOrigin:"50% 50%", duration:1.4, ease:"power1.inOut"}, "pull+=1.4");
        });
        tl.addLabel("run", "pull+=2.6");
        R.ctrs.forEach(function(c, i){
          var s = R.piers[PLAN[i].pier].slots[PLAN[i].slot], t = R.ipTags[i], at = "run+=" + (i * .35);
          tl.call(function(){ c.classList.remove("ghost"); }, null, at);
          tl.fromTo(c.body, {scale:1.15, transformOrigin:"50% 100%"}, {scale:1, duration:.5, ease:"back.out(3)"}, at);
          var p = iso(s[0] + 28, s[1] + 18, 30);
          tl.call(function(){ t.querySelector("text").textContent = PLAN[i].ip; t.setAttribute("transform", "translate(" + p[0] + "," + (p[1] - 26) + ")"); }, null, "run+=" + (i * .35 + .3));
          tl.to(t, {opacity:1, duration:.3}, "run+=" + (i * .35 + .3));
        });
        R.piers.forEach(function(P){
          tl.call(function(){ P.cable.classList.add("live"); }, null, "run");
          tl.to(P.whLight, {opacity:1, duration:.4}, "run");
          tl.to(P.bang, {opacity:0, duration:.3}, "run+=.8");
        });
      },
      /* 7. 보고 → 장부 현재 수 3 */
      function(tl, api, R){
        tl.add(api.camTo(880, 450, 0.98, 1.4));
        api.clearBubbles(tl, "<");
        api.hideLinks(tl, ["f1", "f2"], "<");
        R.piers.forEach(function(P, n){ api.showLink(tl, "r" + (n + 1), P.foremanPt, R.vaultPt, n ? "<" : ">", "alt"); });
        var b = api.bubble(1000, 150, 250, 122, [1000, 214, 975, 236, 1000, 232]);
        api.text(b.inner, 1020, 180, "📒 금고 장부", "t");
        api.text(b.inner, 1020, 206, "deployment / my-shop", "m");
        api.text(b.inner, 1020, 230, "원하는 수   3", "m", {fill:"#2563eb"});
        var cur = api.text(b.inner, 1020, 252, "현재 수     0", "m", {fill:"#dc2626"});
        api.pop(tl, b, "+=.3");
        [1,2,3].forEach(function(n){
          tl.call(function(){ cur.textContent = "현재 수     " + n + (n === 3 ? "  ✓" : ""); if(n === 3) cur.setAttribute("fill", "#16a34a"); }, null, "+=.45");
        });
        var rp = robotPt(R);
        var rb = api.bubble(rp[0] - 230, rp[1] - 70, 196, 50, [rp[0] - 40, rp[1] - 20, rp[0] - 16, rp[1] - 6, rp[0] - 40, rp[1] - 32]);
        api.text(rb.inner, rp[0] - 214, rp[1] - 40, "3 = 3 · 다시 지켜보기", "t", {fill:"#16a34a"});
        api.pop(tl, rb, "+=.2");
        api.hideLinks(tl, ["r1", "r2"], "+=1.2");
      }
    ]
  }
};
})();
