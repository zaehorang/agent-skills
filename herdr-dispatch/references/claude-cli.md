# claude 플래그

> **확인일: 2026-10-09** · Claude Code 2.1.295 · 출처: 맨 아래 URL + `claude --help`
> 재검증 절차는 `verify.md`. 이 파일은 claude pane이 검증한다.

`herdr agent start ... --kind claude -- <여기>`에 넣는 인자.

| | |
|---|---|
| 모델 | `--model haiku\|sonnet\|opus\|fable\|best\|opusplan` |
| 추론 | `--effort low\|medium\|high\|xhigh\|max` (기본은 모델별 — 현재 `opus`·`sonnet`·`haiku`가 가리키는 5.5 세대는 `medium`, 그 이전 세대는 `high`) |
| 권한 | `--permission-mode plan` (읽기 전용) · `auto` (편집 + 분류기 검토) |

```bash
herdr agent start reviewer --kind claude --pane <pane-id> \
  -- --model sonnet --effort high --permission-mode plan
```

## 모델 별칭은 낡지 않는다

`sonnet`은 항상 최신 Sonnet을 가리킨다. 버전 번호를 쓰지 말 것. 다만 **가리키는 버전과 그 버전의 기본 effort**는 바뀌므로, 아래 표는 재검증 대상이다.

| 별칭 | 지금 가리키는 것 (Anthropic API 기준) |
|---|---|
| `haiku` | Haiku 5.5 (v2.1.293+) |
| `sonnet` | Sonnet 5.5 (v2.1.284+) |
| `opus` | Opus 5.5 (v2.1.280+) |
| `fable` | Fable 5.1 (v2.1.257+) |
| `best` | `fable`이 있으면 그것, 없으면 `opus` |
| `opusplan` | 계획은 `opus`, 실행은 `sonnet` |

## 권한 모드

여섯 개이고, 우리가 쓰는 건 둘이다:

| 모드 | 안 묻고 실행되는 것 |
|---|---|
| `manual` (설정 파일에서는 `default`) | 읽기만 |
| `plan` | 읽기만. 편집 차단 |
| `acceptEdits` | 편집 + `mkdir/touch/rm/mv/cp/sed`. **그 외 bash는 전부 물어본다** |
| `auto` | 전부. 분류기가 사람 대신 심사하고, 위험 판정일 때만 멈춘다 |
| `dontAsk` | 읽기 + `allow` 규칙. 물어보는 대신 **거부**한다 |
| `bypassPermissions` | 전부. 격리된 컨테이너 전용 |

`acceptEdits`를 "편집 허용"으로 쓰면 안 된다 — bash에서 멈춘다. 편집 역할은 `auto`다.

**`auto`는 모델 제약이 있다**: Opus 4.6+ / Sonnet 4.6+ / Haiku 5.5 / Fable만 지원한다. 현재 별칭은 전부 통과하지만, 탐색 역할은 어차피 읽기 전용이라 `plan`으로 충분하다.

**`bypassPermissions`는 시작할 때만 켤 수 있다.** 나중에 올릴 수 없으니 `agent start` 시점에 정해야 한다.

auto 모드에서도 분류기가 기본 차단하는 것들이 있다 — force push, `git reset --hard`, `git clean -fd`, `curl | bash`, 프로덕션 배포, `terraform destroy` 류. 걸리면 pane이 `blocked`가 된다. **프롬프트를 0으로 만드는 모드는 없다.**

## 출처

- https://code.claude.com/docs/en/model-config — 별칭 해석, effort 단계와 기본값, 맨 아래 "Version history" 표
- https://code.claude.com/docs/en/permission-modes — 권한 모드, auto 지원 모델, 분류기 차단 목록
- https://claude.com/blog/claude-model-and-effort-level-in-claude-code — 어느 축을 올릴지 (roles.md의 원칙)
