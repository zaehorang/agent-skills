# 엔진 API (world.js 에서 쓰는 것)

## 좌표계

무대는 `viewBox 0 0 1600 1000`, 화면을 꽉 채운다(`slice`). 바닥은 아이소메트릭 격자다.

```
ISO.iso(gx, gy, gz)  → [X, Y]   지도에 고정된 점.  X = 800 + (gx-gy)*0.866,  Y = 120 + (gx+gy)*0.5 - gz
ISO.isoL(gx, gy, gz) → [X, Y]   원점 없는 버전 — 움직이는 물체를 자기 기준으로 그릴 때
```

gx↑ 오른쪽 아래, gy↑ 왼쪽 아래, gz↑ 위. 쓸 만한 범위는 gx·gy 0~900. 보이는 면은 윗면·왼쪽 앞면(gy+d)·오른쪽 앞면(gx+w).
**그리는 순서가 곧 앞뒤 순서다** — 뒤(gx+gy 작은 것)부터 그린다. 층(`api.L`)이 큰 순서를 잡아 준다.

## 층 `api.L`

`base`(바다·물결) → `ground`(땅·도로·구역) → `back`(뒤쪽 건물) → `mid` → `front`(앞쪽 건물) → `fx`(움직이는 물체·연결선) → `labels`(라벨·구름) → `bubbles`(말풍선). 뒤에 있는 것이 위에 그려진다.
말풍선이 라벨 위라서 라벨이 말풍선 글자를 가리지 않는다. 대신 말풍선이 그 밑의 라벨을 덮으니, 말풍선을 라벨 위에 두려면 그 라벨이 안 보여도 되는지 본다. 라벨은 물체(`front`·`fx`) 위라서 물체를 가릴 수 있다.
엔진 UI(왼쪽 아래 사건 패널, 아래 자막, 오른쪽 440px 패널)가 지도 위를 덮는 자리는 `references/world-design.md`.
`labels`·`bubbles` 와 `fx` 의 `.act` 아닌 것은 클릭을 받지 않는다.

## 그리기 도우미 `ISO.*`

| 함수 | 쓰임 |
|---|---|
| `box(parent, iso, gx,gy,gz, w,d,h, [윗면,왼쪽,오른쪽])` | 상자 — 건물·땅·기계 |
| `flat(parent, gx,gy,gz, w,d, attrs)` | 바닥 평면 — 도로·구역 |
| `faceR(parent, gx,gy,gz, d,h, fill)` / `faceL(…, w,h, fill)` | 벽면 위 창문·문 |
| `act(parent, 키, 이름)` | **클릭할 물체 묶음.** 키 = content.js `actors` 키 |
| `person(parent, x, y, {body, hard, chef, clip, hair})` | 사람 |
| `robot(parent, color)` | 로봇 |
| `bang(parent, x, y)` | 머리 위 느낌표(처음엔 숨김) |
| `paper(parent, mark)` | 날아다니는 서류. `.seal` 은 도장 |
| `label(parent, x, y, 비유, 실제, big)` | 라벨 — '실제 이름 보기'로 바뀐다. 보통 `api.label` |
| `mover(parent, attrs)` | 움직이는 물체 — 위치는 바깥(`ISO.place`), 애니메이션은 `.body` |
| `place(node, gx, gy, gz)` | 바닥 좌표에 놓기 (속성 transform) |
| `curve(path, from, to, lift)` | 두 점 잇는 곡선 |
| `C.*` | 색 묶음 — sand grass wood wall roofB roofR white glass navy stone yellow gray teal conc coral green purple gold |

## WORLD 형태

```js
window.WORLD = {
  home:{x:800, y:470, s:0.93},          // 전체 보기 카메라
  build:function(api){ … return R; },   // 한 번 그린다. 장면에서 쓸 요소·점을 R 에 담는다
  ambient:function(api, R){ … },        // 반복 배경 움직임 (선택)
  reset:function(api, R){ … },          // 기준 상태 — 장면이 바꾸는 모든 것을 되돌린다
  afterEvent:function(api, R){ … },     // 사건이 끝난 뒤 (선택)
  scenes:{ deploy:[ function(tl, api, R){ … }, … ] }   // 사건 id → 장면 함수 목록
};
```

**불러올 때 DOM 을 건드리지 않는다** — 모든 그리기는 `build` 안에서. (검사 스크립트가 DOM 없이 불러온다.)

## 장면 함수에서 쓰는 `api`

```js
function(tl, api, R){
  tl.add(api.camTo(x, y, s, 초));                 // 카메라 — 자막에 가리지 않게 엔진이 위로 보정
  api.clearBubbles(tl, "<");                       // 앞 장면 말풍선 정리
  api.fly(tl, node, from, to, {duration, lift}, at);   // 포물선 비행
  api.showLink(tl, "키", from, to, at, "alt");     // 흐르는 점선 — 소통. from/to 는 점 또는 점을 돌려주는 함수. 변형: alt(초록) warn(빨강)
  api.hideLinks(tl, ["키"], at);
  var b = api.bubble(x, y, w, h, [꼬리 세 점 x,y,x,y,x,y]);   // 말풍선 (지도 좌표)
  api.text(b.inner, x, y, "글", "t|s|m", attrs);   // t 제목 · s 보조 · m 고정폭
  api.pop(tl, b, at);                              // 말풍선 튀어나오기
  tl.call(function(){ … }, null, at);              // 글자 바꾸기·클래스 토글 같은 즉시 변경
}
```

- 장면 함수는 **장면이 시작될 때** 호출되고, 이전·점 이동 때는 `reset` 후 앞 장면들이 **보이지 않게 순식간에** 다시 실행된다(`progress(1)`). 그래서 장면 함수는 같은 입력이면 같은 결과를 내야 하고, 상태 변경은 타임라인 안(`tl.to/set/call`)에서 해야 한다.
- 위치 인자 `at` 은 GSAP 타임라인 위치(`"<"`, `">"`, `"+=.3"`, 라벨).
- 확인용 전역: `EXPLORER.startEvent(id)`, `EXPLORER.goBeat(n)`, `EXPLORER.state()`, `EXPLORER.R`.

## 카메라 값 고르는 법

`camTo(x, y, s)` 의 x·y 는 **보고 싶은 것들의 중심(화면 좌표)**, s 는 배율(1 = 전체 크기). 주인공 + 말풍선이 한 화면에 들어오게 1.1~1.6. 장면마다 카메라가 움직이면 "다른 곳으로 이야기가 넘어간다"가 전달된다.

## 화면 글자 바꾸기 (`CONTENT.ui`, `CONTENT.lang`)

엔진의 버튼·패널·도움말 글자는 기본값이 한국어다. 다른 언어로 만들 때는 `content.js` 에 `lang` 과 `ui` 를 둔다. 넣지 않은 키는 기본값이 쓰인다.

```js
window.CONTENT = { …, lang:"en",
  ui:{
    /* 코드로 만드는 글자 */
    ready:"Coming soon", again:"Replay", next:"Next ▶", finish:"Done ✓", beatAria:"Go to scene {n}",
    more:"Learn more", talks:"Who it talks to, and how", steps:"What happens inside",
    realBtn:"🔍 For real? — see the actual system", now:"● What just happened", always:"● What you can always check", myth:"Common myth",
    legendO:"Blue: official term", legendC:"Yellow: name you chose", legendA:"Gray: generated", legendHint:"Hover a colored name to see why",
    helpO:"Blue", helpC:"Yellow", helpA:"Gray", helpOdesc:"…", helpCdesc:"…", helpAdesc:"…",
    showReal:"Show real names", showMeta:"Show metaphor names", actAria:"Learn about {name}",
    /* index.html 의 data-ui · data-ui-aria 키 — HTML 을 그대로 넣는다 */
    overview:"Overview", helpAria:"How to use this page", eventsTitle:"Trigger an event", capLegend:"…", auto:"Autoplay",
    capMore:"More", prev:"◀ Back", tipMore:"Learn more →", introGo:"Start exploring", introHint:"…",
    help:"<h2>…</h2> … <div class='legend-rows' id='helpLegend'></div> …"   /* 도움말 전체 — helpLegend 자리를 꼭 남긴다 */
  }
};
```

이름 색 설명(`o`·`oext`·`c`·`a` 와 직접 만든 키)은 `names.messages` 로 바꾼다.
