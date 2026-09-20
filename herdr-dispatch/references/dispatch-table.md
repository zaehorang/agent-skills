# 역할별 디스패치 표

> **확인일: 2026-09-20** · 출처: 각 벤더 공식 문서 (아래 URL)
> 이 표가 틀려서 `agent start`가 실패하면 → SKILL.md "표가 틀렸을 때" 절차를 따른다.

## 축이 세 개다

| 축 | 무엇을 정하나 | 기본값으로 둬도 되나 |
|---|---|---|
| **모델** | 아는 것의 양 (가중치) | 난이도에 맞으면 |
| **추론** | 꼼꼼함 — 파일을 몇 개 읽고 테스트를 돌리는지 | 대부분 예 |
| **권한** | 읽기만 / 편집까지, 언제 물어보는지 | **아니오 — 안 정하면 pane이 멈춘다** |

**어느 축을 올릴지 고르는 법** (Anthropic 공식 가이드):

```
맥락은 다 줬는데 틀렸다        →  모델을 올린다  (아는 게 부족)
파일을 빼먹거나 테스트를 안 돌렸다  →  추론을 올린다  (꼼꼼함이 부족)
둘 다 아니다                  →  기본값. 건드리지 않는다
```

OpenAI 쪽 원칙도 같은 방향이다 — "필요한 결과를 내는 **가장 낮은** 추론 강도를 쓰고, 계획·분석·검증이 더 필요할 때만 올려라."

**반대 방향 주의**: 어려운 작업에 작은 모델을 쓰면 오히려 비싸진다. 단계를 더 밟고 재시도하기 때문이다. 규칙은 "무조건 아껴라"가 아니라 **"난이도에 맞춰라"** 다.

## 역할표

| 역할 | claude | codex | 권한 |
|---|---|---|---|
| 탐색·검색 | `haiku` / `low` | `gpt-5.6-luna` / `medium` | 읽기 전용 |
| 리뷰 | `sonnet` / `high` | `gpt-5.6-terra` / `high` | 읽기 전용 |
| 구현 | `sonnet` / 기본 | `gpt-5.6-terra` / `medium` | 편집 허용 |
| 어려운 버그·아키텍처 | `opus` / `high`~`xhigh` | `gpt-5.6-sol` / `high` | 편집 허용 |
| 장시간 다단계 | `fable` (없으면 `best`) / 기본 | `gpt-6-astra` / 기본 | 편집 허용 |
| 테스트·빌드·로그 | — | — | **에이전트를 띄우지 않는다** |

마지막 줄이 중요하다. 명령 하나 돌리고 출력을 읽는 일에는 에이전트가 필요 없다 → `herdr pane run`.

역할이 표에 없으면 가장 가까운 줄에서 시작하고, 위의 "어느 축을 올릴지" 규칙으로 조정한다.

## CLI별 플래그

`herdr agent start`는 `--` 뒤의 인자를 그대로 넘긴다.

### claude

| | |
|---|---|
| 모델 | `--model haiku\|sonnet\|opus\|fable\|best\|opusplan` |
| 추론 | `--effort low\|medium\|high\|xhigh\|max` (기본 `high`) |
| 권한 | `--permission-mode plan` (읽기 전용) · `acceptEdits` (편집 허용) |

```bash
herdr agent start reviewer --kind claude --pane <pane-id> \
  -- --model sonnet --effort high --permission-mode plan
```

**모델 이름은 별칭이므로 낡지 않는다.** `sonnet`은 항상 최신 Sonnet을 가리킨다. 버전 번호를 쓰지 말 것.

### codex

| | |
|---|---|
| 모델 | `-m <이름>` — 아래 표의 실제 모델명 |
| 추론 | `-c model_reasoning_effort=low\|medium\|high\|xhigh\|max\|ultra` (기본 `medium`) |
| 권한 | `-s read-only` · `workspace-write` |

```bash
herdr agent start reviewer --kind codex --pane <pane-id> \
  -- -m gpt-5.6-terra -c model_reasoning_effort=high -s read-only
```

**codex는 실제 모델명이라 낡는다.** 현재 유효한 이름과 은퇴 일정:

| 모델 | 위치 | 은퇴 |
|---|---|---|
| `gpt-6-astra` | 코드·앱·리서치를 아우르는 장기 작업 | — |
| `gpt-5.6-sol` | 모호하고 어렵고 값비싼 작업 | — |
| `gpt-5.6-terra` | 일상 작업의 출발점 | — |
| `gpt-5.6-luna` | 정답 모양이 분명한 고volume 작업 | — |
| `gpt-5.5` | (구버전) | **2026-10-14** |
| `gpt-5.4`, `gpt-5.4-mini` | (구버전) | 2026-08-31 (지남) |

오늘 날짜가 은퇴일에 가깝거나 지났으면 사용자에게 알린다.

### 추론 단계가 서로 다르다

claude는 5단계(`low`~`max`), codex는 6단계(`low`~`max`, 그 위 `ultra`). **같은 이름으로 묶지 말 것.**

## 출처

- https://code.claude.com/docs/en/model-config
- https://claude.com/blog/claude-model-and-effort-level-in-claude-code
- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/learn/best-practices
