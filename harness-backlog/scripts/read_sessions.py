#!/usr/bin/env python3
"""Claude Code · Codex 세션 기록을 하나의 형태로 읽는다.

  read_sessions.py list    [--project P] [--since ISO | --all] [--unreviewed] [--json]
  read_sessions.py show    --agent claude|codex (--path F | --session ID) [--project P] [--json]
  read_sessions.py current --agent claude|codex [--project P]

show는 검토자가 읽을 텍스트를 낸다: 턴마다 역할 · 시각 · 모델, 그리고 신호
(도구 실패, 되돌림, 사용자 거절·중단, 변경 직후의 사용자 발화, 탐색 비용).
신호는 "여기를 보라"는 표시일 뿐이다. 하네스의 빈틈인지는 검토자가 판단한다.

기록 위치는 HARNESS_CLAUDE_HOME / HARNESS_CODEX_HOME 으로 바꿀 수 있다 (테스트용).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hb  # noqa: E402

CLAUDE_HOME = Path(os.environ.get("HARNESS_CLAUDE_HOME", "~/.claude")).expanduser()
CODEX_HOME = Path(os.environ.get("HARNESS_CODEX_HOME", "~/.codex")).expanduser()

REVERT_RE = re.compile(r"\bgit\s+(?:revert|reset\s+--hard|restore|checkout\s+--|stash\b)")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"}
SEARCH_RE = re.compile(r"(?:^|[;&|]\s*|\s)(?:rg|grep|find|fd|ag)\s")
READ_CMDS = {"cat", "sed", "head", "tail", "nl", "less", "bat"}
# Codex가 사용자 메시지 자리에 끼워 넣는 것. 사용자의 말이 아니다.
CODEX_NOISE = ("# AGENTS.md instructions", "<skill>", "<environment_context>", "<user_instructions>", "<INSTRUCTIONS>",
               "<turn_aborted>", "<recommended_plugins>", "<codex_internal_context", "<user_action>",
               "The following is the Codex agent history")
MY_REQUEST_RE = re.compile(r"^## My request[^\n]*:\s*\n", re.M)  # 첨부·탭 정보 머리말 뒤의 진짜 요청
IMAGE_TAG_RE = re.compile(r"<image\b[^>]*>(?:</image>)?")
SHELL_CMD_RE = re.compile(r"<user_shell_command>\s*<command>\s*(.*?)\s*</command>", re.S)
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def _lines(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 20] + f" …(+{len(s) - n + 20}자)"


def _under(cwd: str | None, project: Path) -> bool:
    """cwd 가 이 저장소의 어느 작업 트리 안에 있나."""
    if not cwd:
        return False
    for root in hb.worktrees(project):
        try:
            Path(cwd).resolve().relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _rel(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- 찾기

def _claude_meta(path: Path) -> dict | None:
    for e in _lines(path):
        if e.get("cwd") and e.get("sessionId"):
            return {"id": e["sessionId"], "cwd": e["cwd"], "start": e.get("timestamp")}
    return None


def _codex_meta(path: Path) -> dict | None:
    for e in _lines(path):
        if e.get("type") == "session_meta":
            p = e.get("payload", {})
            # subagent · guardian_review 스레드는 사용자 세션이 아니다 (SessionEnd 훅도 안 돈다)
            if p.get("thread_source") not in (None, "user"):
                return None
            return {"id": p.get("id"), "cwd": p.get("cwd"), "start": p.get("timestamp")}
        break
    return None


def discover(project: Path, since: float | None = None) -> list[dict]:
    roots = [r.resolve() for r in hb.worktrees(project)]
    under = lambda cwd: bool(cwd) and any(_rel(Path(cwd).resolve(), r) for r in roots)
    found = []
    sources = [
        ("claude", (CLAUDE_HOME / "projects").glob("*/*.jsonl"), _claude_meta),
        ("codex", (CODEX_HOME / "sessions").glob("*/*/*/rollout-*.jsonl"), _codex_meta),
    ]
    for agent, paths, meta_fn in sources:
        for p in paths:
            try:
                mtime = p.stat().st_mtime
                if since is not None and mtime < since:
                    continue
                meta = meta_fn(p)
            except OSError:
                continue  # 사라졌거나 읽을 수 없는 기록은 건너뛴다
            if not meta or not meta.get("id") or not under(meta.get("cwd")):
                continue
            found.append({"agent": agent, "key": f"{agent}:{meta['id']}", "path": str(p),
                          "end": hb.iso(hb.dt.datetime.fromtimestamp(mtime).astimezone()), **meta})
    found.sort(key=lambda s: s["end"])
    return found


def find_session(agent: str, session_id: str, project: Path | None) -> Path:
    pattern = (CLAUDE_HOME / "projects").glob(f"*/{session_id}.jsonl") if agent == "claude" \
        else (CODEX_HOME / "sessions").glob(f"*/*/*/rollout-*{session_id}.jsonl")
    for p in pattern:
        return p
    raise hb.BacklogError(f"세션 기록을 찾지 못했다: {agent}:{session_id}")


# ---------------------------------------------------------------- 정규화

def _turn(turns, role, ts, model, text, **kw):
    turns.append({"i": len(turns), "role": role, "ts": ts, "model": model, "text": text, **kw})


def _claude_user_text(text: str) -> tuple[str, str] | None:
    text = REMINDER_RE.sub("", text).strip()
    if not text or text.startswith(("<local-command-stdout>", "<local-command-caveat>", "<task-notification>")):
        return None
    if text.startswith("<command-name>"):
        name = re.search(r"<command-name>(.*?)</command-name>", text)
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        return "command", f"{name.group(1) if name else ''} {args.group(1).strip() if args else ''}".strip()
    if text.startswith("[Request interrupted"):
        return "interrupt", text
    return "message", text


def normalize_claude(path: Path) -> dict:
    turns, tool_names, model, meta = [], {}, None, None
    for e in _lines(path):
        if e.get("isSidechain") or e.get("isCompactSummary"):
            continue  # 하위 에이전트 기록, 대화 압축 요약(모델이 쓴 글)은 사용자 발화가 아니다
        meta = meta or ({"id": e["sessionId"], "cwd": e.get("cwd")} if e.get("sessionId") and e.get("cwd") else None)
        ts = e.get("timestamp")
        if e.get("type") == "attachment":
            a = e.get("attachment") or {}
            if a.get("type") == "queued_command" and (a.get("origin") or {}).get("kind") == "human":
                _turn(turns, "user", a.get("timestamp", ts), model, a.get("prompt", ""), kind="message")
            continue
        msg = e.get("message") or {}
        if e.get("type") == "assistant":
            model = msg.get("model") or model
            for c in msg.get("content") or []:
                if c.get("type") == "text" and c.get("text", "").strip():
                    _turn(turns, "assistant", ts, model, c["text"])
                elif c.get("type") == "tool_use":
                    tool_names[c.get("id")] = c.get("name")
                    _turn(turns, "tool_call", ts, model, json.dumps(c.get("input"), ensure_ascii=False),
                          tool=c.get("name"), input=c.get("input") or {})
        elif e.get("type") == "user" and not e.get("isMeta"):
            content = msg.get("content")
            parts = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
            for c in parts:
                if c.get("type") == "text":
                    got = _claude_user_text(c.get("text", ""))
                    if got:
                        _turn(turns, "user", ts, model, got[1], kind=got[0])
                elif c.get("type") == "tool_result":
                    out = c.get("content")
                    if isinstance(out, list):
                        out = "\n".join(x.get("text", "") for x in out if isinstance(x, dict))
                    out = str(out or "")
                    name = tool_names.get(c.get("tool_use_id"), "?")
                    if out.lstrip().startswith(("The user doesn't want to proceed", "[Request interrupted")):
                        _turn(turns, "user", ts, model, out, kind="reject", tool=name)
                    elif name == "AskUserQuestion":
                        _turn(turns, "user", ts, model, out, kind="answer")
                    else:
                        _turn(turns, "tool_result", ts, model, out, tool=name, error=bool(c.get("is_error")))
    return {"agent": "claude", "turns": turns, **(meta or {"id": path.stem, "cwd": None})}


EXIT_RE = re.compile(r'(?:exit_code\\?"?\s*:\s*|exited with code\s+|Exit code:?\s*)(-?\d+)')


def _codex_cmd(payload: dict) -> str:
    raw = payload.get("arguments") or payload.get("input") or payload.get("action") or ""
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    m = re.search(r'cmd\s*:\s*"((?:[^"\\]|\\.)*)"', raw) or re.search(r'"command"\s*:\s*(\[[^\]]*\]|"(?:[^"\\]|\\.)*")', raw)
    if m:
        try:
            v = json.loads(m.group(1) if m.group(1).startswith(("[", '"')) else f'"{m.group(1)}"')
            return " ".join(v) if isinstance(v, list) else v
        except json.JSONDecodeError:
            return m.group(1)
    return raw


def _codex_user_text(text: str) -> tuple[str, str] | None:
    text = text.strip()
    m = SHELL_CMD_RE.match(text)
    if m:
        return "command", f"[사용자 명령] {m.group(1)}"
    if not text or text.startswith(CODEX_NOISE):
        return None
    m = MY_REQUEST_RE.search(text)
    if m:
        text = text[m.end():].strip()
    text = IMAGE_TAG_RE.sub("[이미지]", text).strip()
    return ("message", text) if text else None


def _codex_output_text(out) -> str:
    """도구 출력은 [{"type": "input_text", "text": ...}] 목록으로 오기도 한다. 글자 부분만 잇는다."""
    if isinstance(out, str):
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            return out
        out = parsed if isinstance(parsed, list) else out
    if isinstance(out, list):
        parts = [_unwrap_exec(x.get("text", "")) for x in out if isinstance(x, dict)]
        return "\n".join(p for p in parts if p) or json.dumps(out, ensure_ascii=False)
    return out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)


EXEC_HEAD_RE = re.compile(r"^Script completed\s*\nWall time[^\n]*\n(?:Output:\s*\n?)?")


def _unwrap_exec(text: str) -> str:
    """'Script completed / Wall time' 머리말을 걷고, {"exit_code":…, "output":…} 은 코드와 출력만 남긴다."""
    text = EXEC_HEAD_RE.sub("", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return text.strip()
    if isinstance(obj, dict) and "output" in obj:
        code = obj.get("exit_code")
        return (f"exit_code: {code}\n" if code is not None else "") + str(obj["output"]).strip()
    return text.strip()


def normalize_codex(path: Path) -> dict:
    turns, model, meta, names = [], None, {}, {}
    for e in _lines(path):
        ts, p = e.get("timestamp"), e.get("payload") or {}
        t = e.get("type")
        if t == "session_meta":
            meta = {"id": p.get("id"), "cwd": p.get("cwd")}
        elif t == "turn_context":
            model = p.get("model") + (f" ({p['effort']})" if p.get("effort") else "") if p.get("model") else model
        elif t == "response_item":
            pt = p.get("type")
            if pt == "message":
                text = "\n".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
                if p.get("role") == "user":
                    got = _codex_user_text(text)
                    if got:
                        _turn(turns, "user", ts, model, got[1], kind=got[0])
                elif p.get("role") == "assistant" and text.strip():
                    _turn(turns, "assistant", ts, model, text)
            elif pt in ("function_call", "custom_tool_call", "local_shell_call"):
                names[p.get("call_id")] = p.get("name") or pt
                cmd = _codex_cmd(p)
                tool = "apply_patch" if "apply_patch" in (p.get("name") or "") or "*** Begin Patch" in cmd else (p.get("name") or "shell")
                _turn(turns, "tool_call", ts, model, cmd, tool=tool, input={"command": cmd})
            elif pt in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
                out = _codex_output_text(p.get("output"))
                codes = [int(c) for c in EXIT_RE.findall(out)]
                err = any(c != 0 for c in codes) or "aborted by user" in out or "rejected" in out.lower()[:200]
                if "rejected by user" in out.lower() or "aborted by user" in out:
                    _turn(turns, "user", ts, model, out, kind="reject", tool=names.get(p.get("call_id")))
                else:
                    _turn(turns, "tool_result", ts, model, out, tool=names.get(p.get("call_id")), error=err)
        elif t == "event_msg" and p.get("type") == "turn_aborted":
            _turn(turns, "user", ts, model, "[사용자가 턴을 중단함]", kind="interrupt")
    return {"agent": "codex", "turns": turns, **(meta or {"id": path.stem, "cwd": None})}


def normalize(agent: str, path: Path) -> dict:
    s = normalize_claude(path) if agent == "claude" else normalize_codex(path)
    s["path"] = str(path)
    s["key"] = f"{agent}:{s['id']}"
    return s


# ---------------------------------------------------------------- 신호

def _read_target(turn: dict) -> str | None:
    inp = turn.get("input") or {}
    if turn.get("tool") == "Read":
        return inp.get("file_path")
    cmd = inp.get("command")
    if not isinstance(cmd, str):
        return None
    for part in re.split(r"[;&|]+", cmd):
        words = part.split()
        if not words or words[0] not in READ_CMDS:
            continue
        files = [w for w in words[1:] if not w.startswith("-") and ("/" in w or "." in w)
                 and not re.fullmatch(r"[\d,]+p?", w)]
        if files:
            return files[-1].strip("'\"")
    return None


def signals(session: dict, cfg: dict | None = None) -> list[dict]:
    th = (cfg or hb.DEFAULT_CONFIG)["exploration"]
    turns, out = session["turns"], []
    reads: Counter = Counter()
    edited_since_user, searches = False, 0
    for t in turns:
        role = t["role"]
        if role == "user":
            kind = t.get("kind")
            if kind in ("reject", "interrupt"):
                out.append({"turn": t["i"], "kind": f"user_{kind}", "detail": _clip(t["text"], 120)})
            elif edited_since_user and kind in ("message", "answer"):
                out.append({"turn": t["i"], "kind": "user_after_change", "detail": "에이전트가 파일을 바꾼 직후의 사용자 발화"})
            edited_since_user, searches = False, 0
        elif role == "tool_call":
            cmd = (t.get("input") or {}).get("command", "")
            cmd = cmd if isinstance(cmd, str) else ""
            if t.get("tool") in EDIT_TOOLS or "*** Begin Patch" in cmd:
                edited_since_user = True
            if REVERT_RE.search(cmd):
                out.append({"turn": t["i"], "kind": "revert", "detail": _clip(cmd, 120)})
            if t.get("tool") in ("Grep", "Glob") or SEARCH_RE.search(cmd):
                searches += 1
                if searches == th["searches"]:
                    out.append({"turn": t["i"], "kind": "explore_search", "detail": f"사용자 발화 사이 검색 {searches}회"})
            target = _read_target(t)
            if target:
                reads[target] += 1
                if reads[target] == th["same_file_reads"]:
                    out.append({"turn": t["i"], "kind": "explore_reread", "detail": f"{target} {reads[target]}회 읽음"})
        elif role == "tool_result":
            if t.get("error"):
                out.append({"turn": t["i"], "kind": "tool_error", "detail": _clip(t["text"], 120)})
            elif t.get("tool") == "Read" or (t["i"] > 0 and _read_target(turns[t["i"] - 1])):
                n = t["text"].count("\n")
                if n >= th["read_lines"]:
                    out.append({"turn": t["i"], "kind": "explore_long_read", "detail": f"한 번에 {n}줄 읽음"})
    return out


# ---------------------------------------------------------------- 출력

LIMITS = {"user": 2000, "assistant": 700, "tool_call": 240, "tool_result": 240}


def unreviewed(rows: list[dict], entries: list[dict]) -> list[dict]:
    """검토한 적 없거나, 검토한 뒤로 턴이 늘어난 세션."""
    upto = hb.reviewed_upto(entries)
    out = []
    for r in rows:
        done = upto.get(r["key"])
        if done is None:
            out.append(r)
        elif done != float("inf"):
            try:
                n = len(normalize(r["agent"], Path(r["path"]))["turns"])
            except OSError:
                continue  # 읽을 수 없는 기록 하나가 전체를 멈추지 않게
            if n > done:
                out.append({**r, "reviewed_turns": int(done), "turns": n})
    return out


def render(session: dict, sigs: list[dict], max_chars: int = 120_000, start: int = 0) -> str:
    """start 가 있으면 그 앞은 이미 검토한 부분이라 맥락으로만 짧게 보이고, 신호도 start 이후만 보인다."""
    models = list(dict.fromkeys(t["model"] for t in session["turns"] if t.get("model")))
    sigs = [s for s in sigs if s["turn"] >= start]
    marked = {s["turn"] for s in sigs}
    near = {i for s in sigs for i in range(s["turn"] - 3, s["turn"] + 2)}
    head = [
        f"# 세션 {session['key']}",
        f"cwd: {session.get('cwd')}",
        f"모델: {', '.join(models) or '알 수 없음'}",
        "## 신호",
        *(f"- 턴 {s['turn']} {s['kind']}: {s['detail']}" for s in sigs),
        "" if sigs else "- 없음",
    ]

    def line(t, full: bool) -> str:
        lim = LIMITS[t["role"]] * (3 if full and t["role"] == "tool_result" and t.get("error") else 1)
        tag = t["role"] + (f":{t['kind']}" if t.get("kind") and t["kind"] != "message" else "")
        tool = f" {t['tool']}" if t.get("tool") and t["role"] != "user" else ""
        err = " !실패" if t.get("error") else ""
        mark = " ◀" if t["i"] in marked else ""
        return f"[{t['i']} {tag}{tool}{err} {t.get('ts') or ''} | {t.get('model') or '-'}]{mark} {_clip(t['text'], lim)}"

    old, new = session["turns"][:start], session["turns"][start:]
    if old:
        recent = {t["i"] for t in old[-6:]}
        ctx = [_clip(line(t, False), 400) for t in old if t["role"] == "user" or t["i"] in recent]
        head += [f"## 이미 검토한 부분 (턴 0~{start - 1}) — 맥락으로만 본다. 여기서 후보를 내지 않는다",
                 *ctx, "", f"## 새로 검토할 턴 (턴 {start}부터 — 후보의 turn은 이 범위에서만 고른다)"]
    else:
        head.append("## 턴")
    head.append("(형식: [번호 역할 시각 | 모델] 내용)")
    body = [line(t, True) for t in new]
    text = "\n".join(head + body)
    if len(text) <= max_chars:
        return text
    # 길면 사용자 발화와 신호 주변만 남긴다.
    kept, skipped = [], 0
    for t in new:
        if t["role"] == "user" or t["i"] in near:
            if skipped:
                kept.append(f"… {skipped}턴 생략")
                skipped = 0
            kept.append(line(t, True))
        else:
            skipped += 1
    if skipped:
        kept.append(f"… {skipped}턴 생략")
    return _clip("\n".join(head + kept), max_chars)


def model_at(session: dict, turn: int) -> str:
    turns = session["turns"]
    for t in reversed(turns[: turn + 1] if 0 <= turn < len(turns) else turns):
        if t.get("model") and t["role"] in ("assistant", "tool_call"):
            return t["model"]
    for t in turns[turn:] if 0 <= turn < len(turns) else []:
        if t.get("model"):
            return t["model"]
    return "unknown"


def ts_at(session: dict, turn: int) -> str:
    turns = session["turns"]
    t = turns[turn] if 0 <= turn < len(turns) else (turns[-1] if turns else {})
    return t.get("ts") or "unknown"


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    s.add_argument("--since"); s.add_argument("--all", action="store_true")
    s.add_argument("--unreviewed", action="store_true"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("--agent", choices=("claude", "codex"), required=True)
    s.add_argument("--path"); s.add_argument("--session")
    s.add_argument("--json", action="store_true"); s.add_argument("--max-chars", type=int, default=120_000)
    s = sub.add_parser("current"); s.add_argument("--agent", choices=("claude", "codex"), required=True)
    a = ap.parse_args(argv)

    try:
        if a.cmd == "show":
            path = Path(a.path) if a.path else find_session(a.agent, a.session, None)
            sess = normalize(a.agent, path)
            cfg = hb.load_config(hb.resolve_project(a.project)) if a.project else None
            sigs = signals(sess, cfg)
            if a.json:
                print(json.dumps({"session": sess, "signals": sigs}, ensure_ascii=False))
            else:
                print(render(sess, sigs, a.max_chars))
            return 0
        project = hb.resolve_project(a.project)
        if a.cmd == "current":
            cands = [s for s in discover(project) if s["agent"] == a.agent]
            if not cands:
                raise hb.BacklogError("이 프로젝트의 세션 기록을 찾지 못했다")
            sess = normalize(a.agent, Path(cands[-1]["path"]))
            print(json.dumps({"session": sess["key"], "model": model_at(sess, len(sess["turns"]) - 1)}, ensure_ascii=False))
            return 0
        entries = hb.ledger_read(project)
        if a.since:
            since = hb.parse_time(a.since).timestamp()
        elif a.all:
            since = None
        else:
            base = hb.ledger_baseline(entries)
            since = base.timestamp() if base else None
        rows = discover(project, since)
        if a.unreviewed:
            rows = unreviewed(rows, entries)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                more = f"  (턴 {r['reviewed_turns']}까지 검토함 → 지금 {r['turns']}턴)" if "turns" in r else ""
                print(f"{r['end'][:16]}  {r['key']}  {r['cwd']}{more}")
            print(f"{len(rows)}개 세션")
    except hb.BacklogError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
