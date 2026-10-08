agent: claude
model: claude-opus-5-5
---
user: DB 마이그레이션 롤백 절차 알려줘
call Read @stale: docs/runbook.md
result !error: File does not exist: docs/runbook.md
call Glob: docs/**/*.md
result: docs/ops/runbook.md
  docs/ops/migrations.md
call Read: docs/ops/migrations.md
result: ## 롤백
  1. `alembic downgrade -1`
  2. 상태 확인 `alembic current`
assistant: 롤백은 `alembic downgrade -1` 후 `alembic current`로 확인하면 돼요. AGENTS.md에 적힌 docs/runbook.md는 없고 docs/ops/ 아래로 옮겨져 있었어요.
user @confirm: 맞아, 지난달에 docs/ops로 옮겼어
