# 역할별 디스패치 표

> **확인일: 2026-09-20** · 출처: 각 벤더 공식 문서 (아래 URL)
> 이 표가 틀려서 `agent start`가 실패하면 → SKILL.md "표가 틀렸을 때" 절차를 따른다.

## 축이 세 개다

| 축 | 무엇을 정하나 | 기본값으로 둬도 되나 |
|---|---|---|
| **모델** | 아는 것의 양 (가중치) | 난이도에 맞으면 |
| **추론** | 꼼꼼함 — 파일을 몇 개 읽고 테스트를 돌리는지 | 대부분 예 |
| **권한** | 읽기만 / 편집까지, 그리고 승인 프롬프트를 **누가 답하는지** | **아니오 — 안 정하면 pane이 멈춘다** |

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
| 구현 | `sonnet` / 기본 | `gpt-5.6-terra` / `medium` | 편집 · 자동 검토 |
| 어려운 버그·아키텍처 | `opus` / `high`~`xhigh` | `gpt-5.6-sol` / `high` | 편집 · 자동 검토 |
| 장시간 다단계 | `fable` (없으면 `best`) / 기본 | `gpt-6-astra` / 기본 | 편집 · 자동 검토 |
| 테스트·빌드·로그 | — | — | **에이전트를 띄우지 않는다** |

마지막 줄이 중요하다. 명령 하나 돌리고 출력을 읽는 일에는 에이전트가 필요 없다 → `herdr pane run`.

**"편집 · 자동 검토"가 무슨 뜻인가.** 두 CLI 모두 승인 프롬프트를 모델이 대신 받는 모드가 있다 — claude는 분류기(classifier), codex는 리뷰어 에이전트. 편집이 필요한 역할은 이걸 켠다. 안 켜면 파일 편집만 통과하고 bash 명령마다 pane이 `blocked`로 멈춘다 (아래 CLI별 표 참고).

역할이 표에 없으면 가장 가까운 줄에서 시작하고, 위의 "어느 축을 올릴지" 규칙으로 조정한다.

## CLI별 플래그

`herdr agent start`는 `--` 뒤의 인자를 그대로 넘긴다.

### claude

| | |
|---|---|
| 모델 | `--model haiku\|sonnet\|opus\|fable\|best\|opusplan` |
| 추론 | `--effort low\|medium\|high\|xhigh\|max` (기본 `high`) |
| 권한 | `--permission-mode plan` (읽기 전용) · `auto` (편집 + 분류기 검토) |

```bash
herdr agent start reviewer --kind claude --pane <pane-id> \
  -- --model sonnet --effort high --permission-mode plan
```

권한 모드는 여섯 개이고, 우리가 쓰는 건 둘이다:

| 모드 | 안 묻고 실행되는 것 |
|---|---|
| `default` (=`manual`) | 읽기만 |
| `plan` | 읽기만. 편집 차단 |
| `acceptEdits` | 편집 + `mkdir/touch/rm/mv/cp/sed`. **그 외 bash는 전부 물어본다** |
| `auto` | 전부. 분류기가 사람 대신 심사하고, 위험 판정일 때만 멈춘다 |
| `dontAsk` | 읽기 + `allow` 규칙. 물어보는 대신 **거부**한다 |
| `bypassPermissions` | 전부. 격리된 컨테이너 전용 |

`acceptEdits`를 "편집 허용"으로 쓰면 안 된다 — bash에서 멈춘다. 편집 역할은 `auto`다.

**`auto`는 모델 제약이 있다**: Opus 4.6+ / Sonnet 4.6+ / Fable만 지원한다. haiku로는 못 쓰지만, haiku를 쓰는 탐색 역할은 어차피 읽기 전용이라 `plan`으로 충분하다.

**`bypassPermissions`는 시작할 때만 켤 수 있다.** 나중에 올릴 수 없으니 `agent start` 시점에 정해야 한다.

auto 모드에서도 분류기가 기본 차단하는 것들이 있다 — force push, `git reset --hard`, `git clean -fd`, `curl | bash`, 프로덕션 배포, `terraform destroy` 류. 걸리면 pane이 `blocked`가 된다. **프롬프트를 0으로 만드는 모드는 없다.**

**모델 이름은 별칭이므로 낡지 않는다.** `sonnet`은 항상 최신 Sonnet을 가리킨다. 버전 번호를 쓰지 말 것.

### codex

| | |
|---|---|
| 모델 | `-m <이름>` — 아래 표의 실제 모델명 |
| 추론 | `-c model_reasoning_effort=low\|medium\|high\|xhigh\|max\|ultra` (기본 `medium`) |
| 권한 | `-s read-only` (읽기 전용) · `--approve-for-me` (편집 + 리뷰어 검토) |

```bash
herdr agent start reviewer --kind codex --pane <pane-id> \
  -- -m gpt-5.6-terra -c model_reasoning_effort=high -s read-only
```

**codex의 권한은 축이 두 개다** — 무엇에 닿을 수 있나(`-s`)와 언제 멈추나(`-a`).

| `-s` 샌드박스 | | `-a` 승인 정책 | |
|---|---|---|---|
| `read-only` | 수정·네트워크 불가 | `on-request` (기본) | 워크스페이스 밖 편집·네트워크는 승인 요청 |
| `workspace-write` | 워크스페이스 안 편집. 네트워크 기본 차단, `.git`·`.agents`·`.codex`는 읽기 전용 | `never` | 안 물어보고 실패로 반환 |
| `danger-full-access` | 샌드박스 없음 | `on-failure` | 실패했을 때만 |

`-s workspace-write`만 주면 `-a`가 기본 `on-request`로 남아 계속 물어본다. 편집 역할은 대신 **`--approve-for-me`** 를 쓴다 — `on-request` + `workspace-write` + 리뷰어 자동 검토를 한 번에 세팅한다.

```bash
herdr agent start impl --kind codex --pane <pane-id> \
  -- -m gpt-5.6-terra -c model_reasoning_effort=medium --approve-for-me
```

**`--approve-for-me`는 `-s`·`-a`와 함께 못 쓴다.** 같이 주면 `agent start`가 파싱 에러로 죽는다:

```
error: the argument '--approve-for-me' cannot be used with '--sandbox <SANDBOX_MODE>'
```

리뷰어는 승인이 이미 필요한 것만 본다 — 샌드박스 이탈, 차단된 네트워크, `request_permissions`, 부작용 있는 앱·MCP 툴 호출. 데이터 유출·자격증명 탐색·보안 약화·파괴적 행위를 기준으로 판정한다. 모델 호출이 추가로 들고, **리뷰어가 샌드박스 이탈도 승인할 수 있다** — 사람이 없으니 경계는 리뷰어 판단에 달린다.

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
- https://code.claude.com/docs/en/permission-modes
- https://learn.chatgpt.com/docs/agent-approvals-security
- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/learn/best-practices
