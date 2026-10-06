#!/usr/bin/env python3
"""SessionEnd 훅. 검토를 백그라운드로 떼어내 띄우고 곧바로 끝난다.

  hook.py claude    (.claude/settings.json 의 SessionEnd)
  hook.py codex     (.codex/hooks.json 의 SessionEnd)

훅 입력(stdin JSON)의 transcript_path · session_id 를 review.py 에 넘긴다.
Codex SessionEnd 훅은 최대 3초라서 여기서는 아무것도 기다리지 않는다.
검토 프로세스가 띄운 세션이 다시 이 훅을 부르면(HARNESS_REVIEW=1) 아무것도 하지 않는다.
훅은 세션 종료를 막으면 안 되므로 어떤 경우에도 0으로 끝난다.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parents[3]  # <project>/.claude/skills/harness-backlog/scripts


def main() -> int:
    if os.environ.get("HARNESS_REVIEW") or len(sys.argv) < 2 or sys.argv[1] not in ("claude", "codex"):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    transcript = data.get("transcript_path")
    bdir = PROJECT / "history" / "harness-backlog"
    if not transcript or not (bdir / "config.json").exists():
        return 0
    log_dir = bdir / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "review.log", "a") as log:
        subprocess.Popen(
            [sys.executable, str(SCRIPTS / "review.py"), "--project", str(PROJECT),
             "--agent", sys.argv[1], "--transcript", transcript],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, cwd=PROJECT,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # 훅 실패가 세션 종료를 방해하지 않게
        sys.exit(0)
