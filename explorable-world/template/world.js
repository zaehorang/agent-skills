/* TODO(세계관): 지도 그리기 · 배경 움직임 · 기준 상태 · 사건별 장면 움직임
   이 파일은 '요청 하나가 창구에서 작업장으로 가는' 최소 예시다. 주제에 맞게 통째로 바꾼다.
   규칙
   - 클릭할 물체는 ISO.act(부모, 키, 이름) 로 만든다. 키는 content.js actors 의 키와 같아야 한다.
   - 장면 함수 개수·순서는 content.js 의 같은 사건 beats 와 같아야 한다.
   - 장면이 바꾼 것은 reset 에서 반드시 되돌린다 (이전·점 이동이 reset 후 앞 장면을 다시 실행해 상태를 만든다).
   - 움직일 물체는 ISO.mover 로 만들어 위치(바깥)와 애니메이션(body)을 나눈다. */
(function(){
"use strict";
var ISO = window.ISO;
var iso = ISO.iso, el = ISO.el, box = ISO.box, flat = ISO.flat, faceR = ISO.faceR, faceL = ISO.faceL, C = ISO.C, act = ISO.act;

window.WORLD = {
  home:{x:800, y:430, s:1},

  build:function(api){
    var L = api.L, R = {};
    api.bg.setAttribute("fill", "#cfe8d5");

    /* 땅 */
    box(L.ground, iso, 60, 60, -30, 560, 480, 30, C.grass);
    flat(L.ground, 200, 260, 0, 300, 40, {fill:"#e2d6b8"});

    /* 창구 (요청을 받는 곳) */
    var desk = act(L.back, "desk", "접수 창구");
    box(desk, iso, 120, 160, 0, 110, 90, 70, C.wall);
    box(desk, iso, 114, 154, 70, 122, 102, 8, C.roofB);
    faceL(desk, 150, 250, 0, 30, 40, "#2e4a6b");
    R.deskPt = iso(175, 205, 80);

    /* 작업장 (실제로 처리하는 곳) */
    var shop = act(L.mid, "worker", "작업장");
    box(shop, iso, 430, 300, 0, 130, 110, 60, C.wall);
    box(shop, iso, 424, 294, 60, 142, 122, 8, C.roofR);
    faceR(shop, 560, 330, 14, 30, 22, "#8cc0ee");
    R.shopLight = faceR(shop, 560, 330, 14, 30, 22, "#fde68a"); R.shopLight.setAttribute("opacity", 0);
    R.shopPt = iso(495, 355, 74);
    var wp = iso(590, 400, 0);
    ISO.person(shop, wp[0], wp[1], {hard:true, body:"#f97316"});

    /* 요청하는 사람 */
    var client = act(L.front, "client", "요청하는 사람");
    var cp = iso(250, 420, 0);
    ISO.person(client, cp[0], cp[1], {body:"#6366f1", clip:true});
    R.clientPt = [cp[0], cp[1] - 60];

    /* 라벨 — 비유 이름 / 실제 이름 */
    var p;
    p = iso(175, 205, 100); api.label(p[0], p[1] - 10, "접수 창구", "API Gateway");
    p = iso(495, 355, 90);  api.label(p[0], p[1] - 10, "작업장", "Worker");
    api.label(cp[0], cp[1] + 22, "요청하는 사람", "Client");

    /* 움직이는 물체 */
    R.paper = ISO.paper(L.fx, "1");
    return R;
  },

  ambient:function(api, R){
    gsap.to(document.querySelectorAll("#world .bob"), {y:-1.6, duration:.9, yoyo:true, repeat:-1, ease:"sine.inOut", stagger:.3});
  },

  reset:function(api, R){
    gsap.killTweensOf(R.paper);
    gsap.set(R.paper, {opacity:0, x:0, y:0, scale:1});
    gsap.set(R.paper.seal, {opacity:0});
    gsap.set(R.shopLight, {opacity:0});
  },

  scenes:{
    send:[
      /* 1. 요청서가 창구로 */
      function(tl, api, R){
        tl.add(api.camTo(420, 300, 1.3, 1.2));
        tl.set(R.paper, {x:R.clientPt[0], y:R.clientPt[1], opacity:0, scale:.4});
        tl.to(R.paper, {opacity:1, scale:1.2, duration:.4, ease:"back.out(2)"});
        api.fly(tl, R.paper, R.clientPt, R.deskPt, {duration:1.6});
        tl.to(R.paper.seal, {opacity:1, duration:.3});
      },
      /* 2. 창구가 작업장에 넘김 → 처리 */
      function(tl, api, R){
        tl.add(api.camTo(600, 340, 1.2, 1.2));
        api.showLink(tl, "desk-shop", R.deskPt, R.shopPt, ">");
        api.fly(tl, R.paper, R.deskPt, R.shopPt, {duration:1.4}, "<");
        tl.to(R.paper, {opacity:0, scale:.3, duration:.3});
        tl.to(R.shopLight, {opacity:1, duration:.4});
        var b = api.bubble(R.shopPt[0] + 30, R.shopPt[1] - 120, 200, 56, [R.shopPt[0] + 40, R.shopPt[1] - 64, R.shopPt[0] + 20, R.shopPt[1] - 30, R.shopPt[0] + 70, R.shopPt[1] - 64]);
        api.text(b.inner, R.shopPt[0] + 48, R.shopPt[1] - 87, "처리 완료 · 200 OK", "t", {fill:"#16a34a"});
        api.pop(tl, b, "+=.2");
      }
    ]
  }
};
})();
