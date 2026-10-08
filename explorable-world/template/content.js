/* TODO(내용): 설명 내용 — 겹 1(말풍선·자막) · 겹 2(패널) · 겹 3(실제로는?) · 이름 규칙
   actors 의 키는 world.js 의 ISO.act(..., "키") 와 같다. 장면(beats)은 world.js scenes 와 개수·순서가 같다.
   글 분량: tip 한 문장(≤80자) · beat.text 두 문장(≤150자) · what 2~3문장 · steps 3~7개 · xray 1~3블록. */
(function(){
"use strict";

var ACTORS = {
  client:{ name:"요청하는 사람", real:"Client",
    tip:"원하는 일을 요청서에 적어 창구로 보내는 쪽이에요.",
    what:"요청서에 <b>무엇을 원하는지</b> 적어 보내요. 직접 처리하지 않고 창구에 맡겨요.",
    talks:[["접수 창구","HTTPS","요청 보내기 · 응답 받기"]],
    steps:["요청서 작성","창구 주소로 전송","응답 기다리기"],
    xr:[{l:"보낸 요청", code:"<span class='k'>$ curl -X POST https://api.example.com/orders</span>"}],
    myth:"요청하는 쪽이 작업장을 직접 고른다? — 보통은 창구가 정해요." },
  desk:{ name:"접수 창구", real:"API Gateway",
    tip:"모든 요청이 처음 도착하는 곳이에요. 확인하고 알맞은 작업장으로 넘겨요.",
    what:"요청이 들어오면 <b>누가 보냈는지 확인</b>하고, 처리할 작업장으로 넘겨요.",
    talks:[["요청하는 사람","HTTPS","요청 받기"],["작업장","HTTP","요청 전달"]],
    steps:["요청 받기","신원 확인","작업장 고르기","전달"],
    xr:[{l:"전달 기록", code:"POST /orders → worker-1  <span class='g'>200</span>"}],
    myth:"창구가 직접 일을 처리한다? — 넘겨 줄 뿐이에요." },
  worker:{ name:"작업장", real:"Worker",
    tip:"넘겨받은 요청을 실제로 처리하는 곳이에요.",
    what:"창구가 넘긴 요청을 <b>실제로 처리</b>하고 결과를 돌려줘요.",
    talks:[["접수 창구","HTTP","요청 받기 · 결과 돌려주기"]],
    steps:["요청 받기","처리","결과 응답"],
    xr:[{l:"처리 로그", code:"order-7f3a2 created  <span class='g'>200 OK</span>"}],
    myth:"작업장은 하나뿐이다? — 보통 여러 개를 두고 나눠 받아요." }
};

var SEND_BEATS = [
  { actor:"client",
    text:"요청하는 사람이 요청서를 <b>접수 창구</b>로 보내요.",
    xray:[{l:"실제 요청", code:"POST /orders HTTP/1.1\nHost: api.example.com"}] },
  { actor:"worker",
    text:"창구가 요청을 <b>작업장</b>에 넘기고, 작업장이 처리해서 결과를 돌려줘요.",
    xray:[{l:"처리 결과", code:"HTTP/1.1 <span class='g'>200 OK</span>\n{ \"id\": \"order-7f3a2\" }"}] }
];

window.CONTENT = {
  title:"작은 마을",
  subtitle:"요청 하나가 처리되기까지",
  logo:"◆",
  intro:{
    title:"이 마을이 시스템이에요",
    body:"<b>창구</b>가 요청을 받고, <b>작업장</b>이 실제로 처리해요.<br>왼쪽 아래 버튼으로 사건을 일으켜 보세요.",
    sub:"궁금한 건물이나 인물은 언제든 눌러 보세요."
  },
  actors:ACTORS,
  events:[
    {id:"send", icon:"✉️", title:"요청 보내기", sub:"요청서 한 장이 처리되기까지", beats:SEND_BEATS}
  ],
  names:{
    examples:{o:"POST", c:"api.example.com", a:"order-7f3a2"},
    official:["POST","GET","HTTP/1.1","200 OK","Host"],
    projects:["curl"],
    custom:{"api.example.com":"c", "/orders":"c", "worker-1":"c"},
    auto:{},
    patterns:[ {re:"order-[0-9a-f]{5}", parts:function(m){ return [["c","c","order"], ["a","a",m.slice(5)]]; }} ],
    messages:{}
  }
};
})();
