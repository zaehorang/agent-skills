# agent-skills

내가 쓰는 **Agent Skills** 모음. 필요한 폴더만 가져다 쓰면 된다.

[Agent Skills](https://agentskills.io)는 에이전트에게 절차적 지식을 넘기는 오픈 포맷이다.
폴더 하나 = 스킬 하나이고, 안의 `SKILL.md`가 전부다. Claude Code · Codex · Cursor · Gemini CLI 등이 같은 포맷을 읽는다.

## 스킬

| 스킬 | 무엇을 하나 |
|---|---|
| [**mechanism-explainer**](./mechanism-explainer) | 시스템이 내부적으로 어떻게 돌아가는지를 **단계별로 따라가는 HTML**로 만든다. 단계마다 상태 다이어그램이 바뀌고, 실제 코드·로그의 before/after가 나란히 뜬다. 번들링·렌더링·합의 프로토콜처럼 "글로 읽으면 안 잡히는 것"에 쓴다. |
| [**behavior-spec-extraction**](./behavior-spec-extraction) | 기존 코드를 읽어 **그 기술을 모르는 사람도 검수할 수 있는 동작 명세**로 역추출한다. 클래스명·프레임워크 용어를 걷어내고 관측 가능한 동작만 남긴다. 마이그레이션·인수인계 전에 현재 동작을 글로 확정할 때. |
| [**ai-readiness-cartography**](./ai-readiness-cartography) | 레포가 **코딩 에이전트에게 얼마나 친화적인지** 100점 루브릭으로 채점하고 HTML 대시보드 + 우선순위 액션 목록을 만든다. 커버리지·존재하지 않는 경로·문서 drift·god file을 자동 탐지한다. |

각 폴더의 `SKILL.md`에 트리거 문구와 구체적인 절차가 있다.

## 설치

폴더를 통째로 스킬 디렉터리에 복사(또는 심볼릭 링크)하면 끝이다.

| 에이전트 | 개인 스킬 | 프로젝트 스킬 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Cursor · Gemini CLI 등 | 각 도구 문서 참고 | |

```bash
git clone https://github.com/zaehorang/agent-skills.git
cp -R agent-skills/mechanism-explainer ~/.claude/skills/
```

에이전트에게 시켜도 된다:

> `https://github.com/zaehorang/agent-skills` 의 `mechanism-explainer` 폴더를 내 스킬 디렉터리에 복사해줘

설치 후 에이전트를 재시작해야 목록에 뜬다.

## 스킬 하나의 구조

```
<skill-name>/
├── SKILL.md          필수 — 프론트매터(name·description) + 절차
├── references/       선택 — 길어서 본문에 못 넣은 참고 자료
├── assets/           선택 — 템플릿·골격 파일
└── scripts/          선택 — 실행 스크립트
```

`SKILL.md`는 처음에 `description`만 읽히고, 요청이 그 설명과 맞을 때 본문이 통째로 로드된다.
그래서 **`description`에 트리거 문구를 넉넉히** 적고, 긴 설명은 `references/`로 뺀다.

## 이 레포의 규칙

- **벤더 이름을 본문에 쓰지 않는다.** 특정 도구 이름(WebFetch, Artifact 등) 대신 능력으로 쓴다 — "웹 페이지를 가져온다", "파일로 저장한다". 그래야 어느 에이전트에서든 돈다.
- **스킬 폴더에 README.md를 두지 않는다.** `SKILL.md`가 그 역할이고, 둘을 두면 어긋난다.
- 스크립트는 런타임만 가정한다 (`python3`, `bash`). 패키지 설치를 요구하지 않는다.

## 라이선스

MIT
