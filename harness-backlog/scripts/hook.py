#!/usr/bin/env python3
"""SessionEnd 훅. 검토를 백그라운드로 떼어내 띄우고 곧바로 끝난다.

  hook.py claude    (.claude/settings.json 의 SessionEnd)
  hook.py codex     (.codex/hooks.json 의 SessionEnd)

훅 입력(stdin JSON)의 transcript_path · session_id 를 review.py 에 넘긴다.
Codex SessionEnd 훅은 최대 3초라서 여기서는 아무것도 기다리지 않는다.
검토 프로세스가 띄운 세션이 다시 이 훅을 부르면(HARNESS_REVIEW=1) 아무것도 하지 않는다.
훅은 세션 종료를 막으면 안 되므로 어떤 경우에도 0으로 끝난다.
"""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parents[3]  # <project>/.claude/skills/harness-backlog/scripts


def session_key(agent: str, transcript: str, data: dict) -> str:
    """review.py 가 쓰는 키와 같게, 기록 파일 안의 세션 id를 쓴다."""
    sys.path.insert(0, str(SCRIPTS))
    import read_sessions as rs
    meta = (rs._claude_meta if agent == "claude" else rs._codex_meta)(Path(transcript))
    return f"{agent}:{(meta or {}).get('id') or data.get('session_id', '?')}"


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
    # 결과가 끝내 안 남으면(검토 프로세스가 죽으면) 운영 줄에 "검토 미완료"로 보이게 먼저 적어 둔다.
    # 세션 정리 정책이 바뀌어 프로세스가 죽더라도 주간 검토가 ledger에 결과가 없는 세션을 다시 검토한다.
    entry = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "kind": "session",
             "session": session_key(sys.argv[1], transcript, data), "agent": sys.argv[1], "status": "queued"}
    with open(bdir / "ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
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
