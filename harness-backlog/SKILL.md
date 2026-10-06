---
name: harness-backlog
description: 세션에서 드러난 하네스(AGENTS.md·스킬·문서·스크립트·권한 설정)의 빈틈을 놓치지 않고 backlog에 제안으로 모으고, 사람이 확인한 것만 하네스에 반영한다. 세션이 끝나면 다른 모델(Claude 세션은 Codex, Codex 세션은 Claude)이 자동으로 검토해 pending 항목을 남기고, 주간 검토가 여러 세션에 걸친 반복·재발·에이전트 간 차이를 찾는다. 사용자가 "backlog 보자", "하네스 backlog", "개선 제안 보여줘", "이거 반영해", "기각해", "세션 검토해줘", "놓친 거 없는지 봐줘", "harness-backlog 설치/도입/점검/제거", "/harness-backlog"라고 할 때 사용. 에이전트가 실수나 교정을 계기로 하네스를 스스로 고치려 할 때도 이 스킬로 대신 제안을 남긴다.
---

# harness-backlog

에이전트와 일하면 하네스의 빈틈이 계속 드러난다 — 알려준 정책, 바로잡은 실수, 한참 헤맨 탐색.
그런데 세션이 끝나면 사라진다. 그렇다고 에이전트가 하네스를 직접 고치게 하면 **오답이 정답 행세를 한다.**
에이전트는 자기 답이 틀린 줄 모르기 때문이다.

그래서 이 스킬의 원칙은 하나다. **AI는 제안하고, 반영은 사람이 한다.**

```
세션 종료 ─ SessionEnd 훅 ─ 다른 모델이 검토 ─┐
"세션 검토해줘" ──────────────────────────┤
주간 launchd ─ 놓친 세션 검토 + 여러 세션 종합 ─┤
                                            ▼
                     history/harness-backlog/*.md   (pending — 아직 하네스가 아니다)
                                            ▼
"backlog 보자" → 항목별 반영 / 기각 / 보류
   반영 → target 수정 → _resolved/ (applied + 왜 + 바꾼 곳)
   기각 → _resolved/ (rejected + 왜)   ← 같은 제안이 다시 나오지 않게 하는 근거
```

## 프로젝트에 놓이는 것

```
<프로젝트>/
├── AGENTS.md                         스니펫 (references/agents-md-snippet.md)
├── .claude/skills/harness-backlog/   이 스킬의 사본 (본체)
├── .agents/skills/harness-backlog →  위 본체를 가리키는 링크 (Codex용)
├── .claude/settings.json             SessionEnd 훅
├── .codex/hooks.json                 SessionEnd 훅
└── history/harness-backlog/
    ├── YYYY-MM-DD-<slug>.md          pending 항목
    ├── _resolved/                    applied · rejected · merged
    ├── config.json                   검토자 모델 등 프로젝트 값
    └── ledger.jsonl                  검토 기록 (어떤 세션을 누가 봤나)
전역: ~/.config/harness-backlog/projects (주간 검토 대상) · launchd 작업 하나
```

| 프로젝트가 정하는 것 (`config.json`) | 이 스킬의 기본값 |
|---|---|
| Claude 세션 검토자 | `codex` · Codex 기본 모델 · `medium` |
| Codex 세션 검토자 | `claude` · `claude-sonnet-5-5` |
| 주간 종합 모델 | `claude` · `claude-opus-5-5` |
| 세션당 후보 상한 | 3 |
| 탐색 신호 임계치 | 같은 파일 3회 · 한 번에 300줄 · 검색 5회 |
| 주간 실행 시각 | `setup.py --weekly 'Mon 09:00'` |

검토자는 **세션을 진행한 쪽과 다른 쪽**으로 둔다. 같은 모델은 같은 맹점을 공유한다.
검토자 CLI를 쓸 수 없으면 같은 쪽으로 대신 돌리지 않고 ledger에 `unavailable`로 남긴다.

**세션 기록이 다른 벤더로 간다.** Claude 세션은 Codex(OpenAI)에, Codex 세션은 Claude(Anthropic)에 보내진다.
보내기 전에 비밀정보 패턴(키·토큰·JWT 등)은 가리지만 정규식이 모든 것을 잡지는 못한다.
도입할 때 사용자에게 이 점을 알리고, 민감한 프로젝트에는 쓰지 않는다.

검토자는 읽기 도구만 가진다 — Claude는 `--restricted --tools Read,Grep,Glob --strict-mcp-config`,
Codex는 `-s read-only` + `approval_policy="never"` + MCP 비움. 세션 기록은 구분자로 감싸 "지시가 아니다"를 명시한다.

## 항목 하나

```yaml
---
date: "2026-10-06"
time: "10:42"
title: "커밋 전에 staged 목록을 확인한다"
type: "guard"            # knowledge 추가 · correction 수정 · guard 강제 · structure 찾는 길 · removal 줄이기
target: "AGENTS.md#커밋"  # 어느 서랍에 넣을지
source: "사용자 교정"      # 어디서 드러났나 (자유 텍스트)
ref: "claude:<세션>#<시각>" # 다시 찾아갈 위치. 주간 검토는 weekly:YYYY-Www
relates: ["..."]         # 선택
session_model: "claude-opus-5-5"
reviewer_model: "gpt-6.1-sol (medium)"
status: "pending"
---
## 내용        하네스에 넣거나 바꿀 것
## 근거        누가 무엇으로 확인했나 + 턴. 추론이면 "추론:"
## 기존 하네스   없음 / 있지만 다름 / 중복
## 재발        (주간 검토가 붙임)
## 해소        (_resolved 에서만) 결과 · 왜 · 바꾼 곳
```

항목은 **`scripts/backlog.py`로만** 만들고 옮긴다. 손으로 쓰지 않는다 — 형식 검증, 비밀정보 검사, 중복 거부, 원자적 쓰기가 거기 있다.
필드는 사람의 판단과 반영에 쓰이는 것만 둔다. 에이전트가 자기 출력에 붙인 신뢰도 같은 라벨은 아무것도 보증하지 못하므로 두지 않는다.

## 요청별 절차

스크립트는 `<스킬 디렉터리>/scripts/`에 있다. 프로젝트 안에서는 `.claude/skills/harness-backlog/scripts/`.
입력 JSON은 임시 디렉터리에 쓰고 실행 후 지운다.

### "backlog 보자"

1. `backlog.py list`로 pending을 오래된 순으로 보여준다. 마지막 줄의 운영 상태(최근 검토 수, 실패, 마지막 주간)도 함께 보여준다.
   실패·미실행이 있으면 `setup.py --check`를 권한다 — 알림이 없으니 고장은 여기서만 보인다.
   "검토 미완료"는 훅이 검토를 띄웠는데 결과가 안 남은 세션이다 — 주간 검토가 다시 검토한다.
2. 사용자가 고른 항목의 본문을 보여준다. `## 근거`가 "추론:"이면 그 점을 짚는다.
3. 사용자의 결정대로 처리한다.
   - **반영**: target을 연다 → 같은 내용이 하네스 다른 곳에 있는지 다시 찾는다 →
     **고치기 전에** 바꿀 내용(diff)을 보여주고 확인받는다 → 고친다 →
     `backlog.py resolve --file <f> --status applied --input {"reason": …, "changed": "<경로#섹션>"}`
     target이 권한·훅·설정 파일이면 diff 확인을 건너뛰지 않는다.
   - **기각**: 이유를 한 줄 받는다 (사용자 말을 요약해도 된다) → `resolve --status rejected --input {"reason": …}`
   - **보류**: 아무것도 하지 않는다.
4. 커밋은 하지 않는다. 프로젝트 관례를 따른다.

### "세션 검토해줘"

1. `read_sessions.py list --unreviewed`로 아직 검토하지 않은 세션을 찾는다 (도입 기준 시각 이후).
   "최근 3개", "이 세션", 세션 ID로 좁힐 수 있다. 진행 중인 세션도 된다.
   ledger는 세션마다 **몇 턴까지 검토했는지**를 남긴다. 검토 뒤에 이어진 세션(진행 중 검토, resume)은
   다시 목록에 오르고, 다음 검토는 그 뒤의 턴만 본다 — 앞부분은 맥락으로만 붙는다.
2. 세션마다 `review.py --agent <claude|codex> --session <id>`를 실행한다. 다른 쪽 모델이 검토하고, 항목과 ledger가 남는다.
3. 결과(남긴 항목, 실패)를 보고한다. 검토자 CLI가 없어 `unavailable`이면 사용자에게 묻는다 —
   허락하면 `review.py --prompt-only` 출력을 지침 삼아 직접 검토하고, 후보마다 `backlog.py add`로 남긴 뒤
   `backlog.py ledger --input {"kind": "session", "session": "<agent:id>", "status": "reviewed", "reviewer": "self", "reviewer_model": "<내 모델>"}`로 검토를 기록한다.
   `ref`는 `<agent>:<세션 id>#<근거 턴의 시각>`, 모델은 `read_sessions.py show --json`의 턴 정보에서 읽는다.

### 일하다가 하네스를 고치고 싶어질 때

실수·교정을 계기로 AGENTS.md나 스킬을 고치고 싶어지면 고치지 않는다. 사용자에게 한 줄로 알리고,
원하면 그 자리에서 제안을 남긴다 — `read_sessions.py current --agent <나>`로 지금 세션과 모델을 얻어
(가장 최근에 기록된 세션이다. 같은 프로젝트에서 세션을 여럿 열어 두었다면 id를 확인한다) `backlog.py add`로 쓴다.
남기지 않아도 세션이 끝나면 검토가 다시 본다.

### 도입 · 점검 · 제거

1. 세션 기록이 상대 벤더의 모델로 보내진다는 점을 먼저 알린다 (위 "세션 기록이 다른 벤더로 간다").
   `setup.py --project <경로>`로 계획을 보여준다 (아무것도 바꾸지 않는다).
2. 없는 파일(`+ 새로 만듦`)은 단위마다 만들지 묻는다. 기존 파일 수정은 diff를 보여준다.
3. 승인받은 단위만 `setup.py --project <경로> --apply --create <단위…>`로 적용한다.
4. 출력의 "직접 할 일"을 전한다: Codex의 `/hooks`로 훅 승인, 두 CLI 로그인.
5. `setup.py --check`로 확인한다. 스킬을 고쳤다면 다시 `setup.py --apply`로 사본을 갱신한다.
6. 제거는 `setup.py --uninstall`로 계획을 보이고 승인 후 `--apply`. `history/`는 남는다.

## 하네스를 스스로 고치지 않는다

실수·교정·검증 실패를 계기로 에이전트가 **자발적으로** 하네스 파일을 고치지 않는다. 세션 검토가 제안으로 남긴다.
사용자가 직접 요청한 하네스 작업(스킬 만들기, 설정 바꾸기)은 그 요청 범위에서 한다.

## 한계

- Claude Code 문서는 "SessionEnd 훅이 띄운 프로세스는 세션 종료 뒤 살아남지 않는다"고 적지만, 2.1.291(macOS)에서
  `claude -p`와 대화형 `/exit` 모두 실측한 결과 살아남았다. 이 동작이 바뀌어 검토가 죽으면 ledger에 `queued`만 남아
  "검토 미완료"로 보이고, 주간 검토가 그 세션을 다시 검토한다. 늦어질 뿐 빠지지 않는다.

- 죽은 규칙(아무도 안 쓰는 규칙)은 세션에서 신호가 나오지 않아 잡지 못한다.
- 개인 메모리(Claude Code auto memory, Codex memories)는 건드리지 않는다. 그쪽은 개인 선호, backlog는 프로젝트 하네스다.
- 검토 품질은 검토 모델에 달려 있다. 기각 이유가 쌓이면 `references/review.md`를 고칠 근거가 된다.
