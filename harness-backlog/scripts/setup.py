#!/usr/bin/env python3
"""harness-backlog 를 프로젝트에 설치 · 점검 · 제거한다.

  setup.py [--project P]                      계획만 보여준다 (기본)
  setup.py [--project P] --apply              적용한다
  setup.py [--project P] --apply --create all 없는 파일도 만든다 (단위를 골라도 된다)
  setup.py [--project P] --check              설치 상태와 운영 상태를 점검한다
  setup.py [--project P] --uninstall [--apply]  훅·등록·스킬을 뺀다. 기록(history/)은 남긴다

없는 파일은 묻고 만든다. 터미널이면 단위마다 y/N 을 묻고, 아니면 --create 로 받은 단위만 만든다.
이미 있는 설정 파일은 덮지 않고 우리 항목만 합친다. 여러 번 돌려도 결과가 같다.

생성 단위: skill · agents-link · AGENTS.md · claude-settings · codex-hooks · backlog-dir · registry · launchd
테스트용: HARNESS_CONFIG_HOME · HARNESS_LAUNCHD_DIR 로 전역 경로를 바꾸고,
HARNESS_NO_LAUNCHCTL=1 이면 launchctl 을 부르지 않는다.
"""

from __future__ import annotations

import argparse
import difflib
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hb  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_REL = Path(".claude/skills/harness-backlog")
LINK_REL = Path(".agents/skills/harness-backlog")
LINK_TARGET = "../../.claude/skills/harness-backlog"
MARK_START, MARK_END = "<!-- harness-backlog:start -->", "<!-- harness-backlog:end -->"
HOOK_TAG = "harness-backlog/scripts/hook.py"
CLAUDE_HOOK = 'python3 "$CLAUDE_PROJECT_DIR/.claude/skills/harness-backlog/scripts/hook.py" claude'
CODEX_HOOK = 'python3 "$(git rev-parse --show-toplevel)/.claude/skills/harness-backlog/scripts/hook.py" codex'
LABEL = "com.harness-backlog.weekly"
MIN_CLAUDE = (2, 1, 277)  # AGENTS.md 를 직접 읽는 최소 버전
DAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

CONFIG_HOME = Path(os.environ.get("HARNESS_CONFIG_HOME", "~/.config/harness-backlog")).expanduser()
LAUNCHD_DIR = Path(os.environ.get("HARNESS_LAUNCHD_DIR", "~/Library/LaunchAgents")).expanduser()
REGISTRY = CONFIG_HOME / "projects"
PLIST = LAUNCHD_DIR / f"{LABEL}.plist"


@dataclass
class Step:
    unit: str
    path: str
    action: str            # create | modify | remove | skip | conflict
    detail: str = ""
    apply: Callable[[], None] | None = None
    preview: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 보조

def _snippet() -> str:
    text = (SKILL_DIR / "references" / "agents-md-snippet.md").read_text(encoding="utf-8")
    start, end = text.index(MARK_START), text.index(MARK_END) + len(MARK_END)
    return text[start:end]


def _diff(old: str, new: str, name: str) -> list[str]:
    return list(difflib.unified_diff(old.splitlines(), new.splitlines(), name, name, lineterm="", n=1))[:40]


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise hb.BacklogError(f"{path} 가 올바른 JSON이 아니다 ({e.lineno}행). 손으로 고친 뒤 다시 실행한다.")
    if not isinstance(data, dict):
        raise hb.BacklogError(f"{path} 최상위가 객체가 아니다")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    hb.publish(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", overwrite=True)


def _has_hook(data: dict) -> bool:
    for group in (data.get("hooks") or {}).get("SessionEnd") or []:
        for h in (group or {}).get("hooks") or []:
            if HOOK_TAG in str(h.get("command", "")):
                return True
    return False


def _add_hook(data: dict, command: str, timeout: int | None) -> dict:
    hook = {"type": "command", "command": command}
    if timeout:
        hook["timeout"] = timeout
    data.setdefault("hooks", {}).setdefault("SessionEnd", []).append({"hooks": [hook]})
    return data


def _drop_hook(data: dict) -> dict:
    groups = (data.get("hooks") or {}).get("SessionEnd") or []
    kept = []
    for g in groups:
        hooks = [h for h in (g or {}).get("hooks") or [] if HOOK_TAG not in str(h.get("command", ""))]
        if hooks:
            kept.append({**g, "hooks": hooks})
    if kept:
        data["hooks"]["SessionEnd"] = kept
    elif "hooks" in data:
        data["hooks"].pop("SessionEnd", None)
    return data


def _skill_files(root: Path) -> dict[str, Path]:
    return {str(p.relative_to(root)): p for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}


def _codex_default_model() -> str:
    path = Path("~/.codex/config.toml").expanduser()
    if not path.exists():
        return ""
    m = re.search(r'^model\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def _version(exe: str | None) -> tuple[int, ...] | None:
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def _launchctl(*args: str) -> subprocess.CompletedProcess | None:
    if os.environ.get("HARNESS_NO_LAUNCHCTL") or sys.platform != "darwin":
        return None
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def _plist(weekday: int, hour: int, minute: int) -> str:
    py = sys.executable
    loop = (f'while IFS= read -r p; do s="$p/{SKILL_REL}/scripts/weekly.py"; '
            f'[ -f "$s" ] && "{py}" "$s" --project "$p"; done < "{REGISTRY}"')
    log = Path("~/Library/Logs/harness-backlog-weekly.log").expanduser()
    esc = loop.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>-c</string><string>{esc}</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>{weekday}</integer><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:{Path('~/.local/bin').expanduser()}</string></dict>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
"""


def _registry() -> list[str]:
    return REGISTRY.read_text(encoding="utf-8").splitlines() if REGISTRY.exists() else []


# ---------------------------------------------------------------- 설치 계획

def plan_install(project: Path, weekly: tuple[int, int, int]) -> list[Step]:
    steps: list[Step] = []

    # 1. 스킬 본체
    dest = project / SKILL_REL
    if dest.resolve() == SKILL_DIR:
        steps.append(Step("skill", str(SKILL_REL), "skip", "이 스크립트가 이미 프로젝트 안의 사본이다"))
    else:
        src, have = _skill_files(SKILL_DIR), _skill_files(dest) if dest.exists() else {}
        changed = sorted(k for k in src if k not in have or not filecmp.cmp(src[k], have[k], shallow=False))
        extra = sorted(set(have) - set(src))

        def copy_skill():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(SKILL_DIR, dest, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))

        if not dest.exists():
            steps.append(Step("skill", str(SKILL_REL), "create", f"파일 {len(src)}개 복사", copy_skill))
        elif changed or extra:
            steps.append(Step("skill", str(SKILL_REL), "modify", "갱신", copy_skill,
                              [f"~ {k}" for k in changed] + [f"- {k}" for k in extra]))
        else:
            steps.append(Step("skill", str(SKILL_REL), "skip", "최신"))

    # 2. Codex가 읽는 위치에 링크
    link = project / LINK_REL
    if link.is_symlink() and os.readlink(link) == LINK_TARGET:
        steps.append(Step("agents-link", str(LINK_REL), "skip", "링크 있음"))
    elif link.exists() or link.is_symlink():
        steps.append(Step("agents-link", str(LINK_REL), "conflict", "다른 파일이 있어 건드리지 않는다"))
    else:
        def make_link():
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(LINK_TARGET, link)
        steps.append(Step("agents-link", str(LINK_REL), "create", f"→ {LINK_TARGET}", make_link))

    # 3. AGENTS.md 스니펫
    agents, block = project / "AGENTS.md", _snippet()
    if agents.exists():
        old = agents.read_text(encoding="utf-8")
        if MARK_START in old and MARK_END in old:
            cur = old[old.index(MARK_START): old.index(MARK_END) + len(MARK_END)]
            if cur == block:
                steps.append(Step("AGENTS.md", "AGENTS.md", "skip", "스니펫 최신"))
            else:
                new = old.replace(cur, block)
                steps.append(Step("AGENTS.md", "AGENTS.md", "modify", "스니펫 갱신",
                                  lambda: hb.publish(agents, new, overwrite=True), _diff(old, new, "AGENTS.md")))
        else:
            new = old.rstrip("\n") + "\n\n" + block + "\n"
            steps.append(Step("AGENTS.md", "AGENTS.md", "modify", "스니펫 추가",
                              lambda: hb.publish(agents, new, overwrite=True), _diff(old, new, "AGENTS.md")))
    else:
        new = "# AGENTS.md\n\n" + block + "\n"
        steps.append(Step("AGENTS.md", "AGENTS.md", "create", "스니펫만 담은 새 파일",
                          lambda: hb.publish(agents, new), new.splitlines()))

    # 4·5. SessionEnd 훅 (Claude Code · Codex)
    for unit, rel, cmd, timeout in (("claude-settings", ".claude/settings.json", CLAUDE_HOOK, None),
                                    ("codex-hooks", ".codex/hooks.json", CODEX_HOOK, 3)):
        path = project / rel
        data = _read_json(path) if path.exists() else {}
        if _has_hook(data):
            steps.append(Step(unit, rel, "skip", "SessionEnd 훅 있음"))
            continue
        new_data = _add_hook(json.loads(json.dumps(data)), cmd, timeout)
        steps.append(Step(unit, rel, "modify" if path.exists() else "create", "SessionEnd 훅 추가",
                          lambda p=path, d=new_data: _write_json(p, d),
                          _diff(json.dumps(data, indent=2, ensure_ascii=False),
                                json.dumps(new_data, indent=2, ensure_ascii=False), rel)))

    # 6. 기록 디렉터리: config · .gitignore · ledger 기준 시각
    bdir = hb.backlog_dir(project)
    cfg_path = bdir / "config.json"
    if cfg_path.exists():
        if hb.ledger_baseline(hb.ledger_read(project)):
            steps.append(Step("backlog-dir", str(hb.BACKLOG_REL), "skip", "config.json · 도입 기준 시각 있음"))
        else:
            steps.append(Step("backlog-dir", "history/harness-backlog/ledger.jsonl", "modify", "도입 기준 시각 기록",
                              lambda: hb.ledger_append(project, {"kind": "setup", "baseline": hb.iso(hb.now())})))
    else:
        cfg = json.loads(json.dumps(hb.DEFAULT_CONFIG))
        cfg["reviewers"]["claude"]["model"] = _codex_default_model()
        cfg["cli_paths"] = {c: shutil.which(c) or "" for c in ("claude", "codex")}

        def make_backlog():
            _write_json(cfg_path, cfg)
            gi = bdir / ".gitignore"
            if not gi.exists():
                hb.publish(gi, "logs/\n")
            if not hb.ledger_baseline(hb.ledger_read(project)):
                hb.ledger_append(project, {"kind": "setup", "baseline": hb.iso(hb.now())})

        steps.append(Step("backlog-dir", str(hb.BACKLOG_REL), "create",
                          "config.json · .gitignore(logs/) · ledger.jsonl(도입 기준 시각)", make_backlog,
                          json.dumps(cfg, ensure_ascii=False, indent=2).splitlines()))

    # 7. 주간 검토가 돌 프로젝트 목록 (전역)
    if str(project) in _registry():
        steps.append(Step("registry", str(REGISTRY), "skip", "등록됨"))
    else:
        def register():
            REGISTRY.parent.mkdir(parents=True, exist_ok=True)
            with REGISTRY.open("a", encoding="utf-8") as f:
                f.write(f"{project}\n")
        steps.append(Step("registry", str(REGISTRY), "modify" if REGISTRY.exists() else "create",
                          f"+ {project}", register))

    # 8. 주간 launchd 작업 (전역, 하나만)
    plist = _plist(*weekly)
    if PLIST.exists() and PLIST.read_text(encoding="utf-8") == plist:
        steps.append(Step("launchd", str(PLIST), "skip", "설치됨"))
    else:
        def install_plist():
            PLIST.parent.mkdir(parents=True, exist_ok=True)
            hb.publish(PLIST, plist, overwrite=True)
            uid = str(os.getuid())
            _launchctl("bootout", f"gui/{uid}", str(PLIST))
            r = _launchctl("bootstrap", f"gui/{uid}", str(PLIST))
            if r is not None and r.returncode:
                raise hb.BacklogError(f"launchctl bootstrap 실패: {r.stderr.strip()[:200]}")
        day = next(k for k, v in DAYS.items() if v == weekly[0])
        steps.append(Step("launchd", str(PLIST), "modify" if PLIST.exists() else "create",
                          f"매주 {day} {weekly[1]:02d}:{weekly[2]:02d}", install_plist))
    return steps


def plan_uninstall(project: Path) -> list[Step]:
    steps: list[Step] = []
    for unit, rel in (("claude-settings", ".claude/settings.json"), ("codex-hooks", ".codex/hooks.json")):
        path = project / rel
        if path.exists():
            data = _read_json(path)
            if _has_hook(data):
                new = _drop_hook(json.loads(json.dumps(data)))
                steps.append(Step(unit, rel, "modify", "SessionEnd 훅 제거", lambda p=path, d=new: _write_json(p, d)))
    agents = project / "AGENTS.md"
    if agents.exists():
        old = agents.read_text(encoding="utf-8")
        if MARK_START in old and MARK_END in old:
            new = old[: old.index(MARK_START)].rstrip("\n") + "\n" + old[old.index(MARK_END) + len(MARK_END):].lstrip("\n")
            steps.append(Step("AGENTS.md", "AGENTS.md", "modify", "스니펫 제거",
                              lambda: hb.publish(agents, new, overwrite=True), _diff(old, new, "AGENTS.md")))
    link = project / LINK_REL
    if link.is_symlink() and os.readlink(link) == LINK_TARGET:
        steps.append(Step("agents-link", str(LINK_REL), "remove", "링크 제거", link.unlink))
    dest = project / SKILL_REL
    if dest.exists() and dest.resolve() != SKILL_DIR:
        steps.append(Step("skill", str(SKILL_REL), "remove", "스킬 사본 제거", lambda: shutil.rmtree(dest)))
    elif dest.exists():
        steps.append(Step("skill", str(SKILL_REL), "skip",
                          "지금 실행 중인 사본이라 지우지 않는다. 다른 위치의 setup.py로 제거하거나 직접 지운다"))
    reg = _registry()
    if str(project) in reg:
        rest = [r for r in reg if r != str(project)]
        steps.append(Step("registry", str(REGISTRY), "modify", f"- {project}",
                          lambda: hb.publish(REGISTRY, "".join(f"{r}\n" for r in rest), overwrite=True)))
        if not rest and PLIST.exists():
            def drop_plist():
                _launchctl("bootout", f"gui/{os.getuid()}", str(PLIST))
                PLIST.unlink()
            steps.append(Step("launchd", str(PLIST), "remove", "등록된 프로젝트가 없어 주간 작업 제거", drop_plist))
    steps.append(Step("history", str(hb.BACKLOG_REL), "skip", "기록은 남긴다"))
    return steps


# ---------------------------------------------------------------- 실행

MARK = {"create": "+ 새로 만듦", "modify": "~ 수정", "remove": "- 제거", "skip": "  그대로", "conflict": "! 충돌"}


def show(steps: list[Step]) -> None:
    for s in steps:
        print(f"{MARK[s.action]:<8} [{s.unit}] {s.path} — {s.detail}")
        for line in s.preview:
            print(f"           {line}")


def apply(steps: list[Step], create: set[str]) -> int:
    failed = 0
    for s in steps:
        if s.action in ("skip", "conflict") or s.apply is None:
            continue
        if s.action == "create" and s.unit not in create and "all" not in create:
            if sys.stdin.isatty():
                if input(f"{s.path} 이(가) 없다. 만들까? [y/N] ").strip().lower() != "y":
                    print(f"  건너뜀: {s.unit}")
                    continue
            else:
                print(f"  승인 필요: {s.path} 를 만들려면 --create {s.unit}")
                continue
        try:
            s.apply()
            print(f"  완료: [{s.unit}] {s.detail}")
        except (OSError, hb.BacklogError) as e:
            failed += 1
            print(f"  실패: [{s.unit}] {e}")
    return failed


MANUAL = """
직접 할 일
  1. Codex에서 프로젝트를 trust하고, `/hooks`로 SessionEnd 훅을 검토·승인한다.
     훅 파일이 바뀌면 다시 승인해야 한다.
  2. 두 CLI 모두 로그인돼 있어야 교차 검토가 돈다 (claude · codex).
  3. 설치 뒤 `setup.py --check`로 상태를 확인한다."""


def check(project: Path) -> int:
    bad = 0

    def row(ok: bool | None, text: str) -> None:
        nonlocal bad
        bad += ok is False
        print(f"{'✓' if ok else ('!' if ok is None else '✗')} {text}")

    dest = project / SKILL_REL
    row(dest.exists(), f"스킬 본체 {SKILL_REL}")
    if dest.exists() and dest.resolve() != SKILL_DIR:
        src, have = _skill_files(SKILL_DIR), _skill_files(dest)
        stale = [k for k in src if k not in have or not filecmp.cmp(src[k], have[k], shallow=False)]
        row(not stale or None, "스킬이 원본과 같다" if not stale else f"원본과 다른 파일 {len(stale)}개 — setup.py --apply로 갱신")
    link = project / LINK_REL
    row(link.is_symlink() and os.readlink(link) == LINK_TARGET, f"Codex용 링크 {LINK_REL}")
    agents = project / "AGENTS.md"
    row(agents.exists() and MARK_START in agents.read_text(encoding="utf-8"), "AGENTS.md 스니펫")
    if (project / "CLAUDE.md").exists():
        row(None, "CLAUDE.md도 있다 — 기본 설정이면 Claude Code는 AGENTS.md를 읽지 않는다 "
                  "(CLAUDE.md에서 가져오거나 Project instructions를 claude-md-and-agents-md로)")
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        p = project / rel
        try:
            row(p.exists() and _has_hook(_read_json(p)), f"{rel} SessionEnd 훅")
        except hb.BacklogError as e:
            row(False, str(e))
    cfg_path = hb.backlog_dir(project) / "config.json"
    row(cfg_path.exists(), "history/harness-backlog/config.json")
    cfg = hb.load_config(project)
    for cli in ("claude", "codex"):
        exe = (cfg.get("cli_paths") or {}).get(cli) or shutil.which(cli)
        row(bool(exe and Path(exe).exists()), f"{cli} CLI {exe or '없음'}")
    cv = _version((cfg.get("cli_paths") or {}).get("claude") or shutil.which("claude"))
    if cv:
        row(cv >= MIN_CLAUDE, f"Claude Code {'.'.join(map(str, cv))} (AGENTS.md 직접 읽기는 2.1.277 이상)")
    for agent, r in cfg["reviewers"].items():
        row(bool(r.get("model")) or None, f"{agent} 세션 검토자: {r['cli']} {r.get('model') or '(모델 미지정 — 기본 모델)'}")
    row(str(project) in _registry(), f"주간 검토 등록 {REGISTRY}")
    row(PLIST.exists(), f"launchd 작업 {PLIST}")
    r = _launchctl("print", f"gui/{os.getuid()}/{LABEL}")
    if r is not None:
        row(r.returncode == 0, "launchd 작업이 로드돼 있다")
    row(None, "Codex 훅의 /hooks 승인 여부는 Codex 안에서만 확인할 수 있다")
    entries = hb.ledger_read(project)
    base = hb.ledger_baseline(entries)
    last = {k: next((e for e in reversed(entries) if e.get("kind") == k), None) for k in ("session", "weekly")}
    fails = [e for e in entries[-50:] if e.get("status") in ("failed", "unavailable")]
    print(f"\n도입 기준 {hb.iso(base) if base else '없음'} · 마지막 세션 검토 "
          f"{(last['session'] or {}).get('at', '없음')} · 마지막 주간 {(last['weekly'] or {}).get('at', '없음')}")
    for e in fails[-3:]:
        print(f"  최근 실패: {e.get('at')} {e.get('session') or e.get('week')} {e.get('status')} {e.get('note', '')}")
    return 1 if bad else 0


def parse_weekly(s: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(?i)\s*(sun|mon|tue|wed|thu|fri|sat)\s+(\d{1,2}):(\d{2})\s*", s)
    if not m:
        raise argparse.ArgumentTypeError("형식: 'Mon 09:00'")
    return DAYS[m.group(1).lower()], int(m.group(2)), int(m.group(3))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--create", nargs="*", default=[], help="만들어도 되는 단위 (all 가능)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--weekly", type=parse_weekly, default="Mon 09:00", help="주간 검토 시각 (기본 'Mon 09:00')")
    a = ap.parse_args(argv)
    weekly = a.weekly if isinstance(a.weekly, tuple) else parse_weekly(a.weekly)
    try:
        project = hb.resolve_project(a.project)
        if a.check:
            return check(project)
        steps = plan_uninstall(project) if a.uninstall else plan_install(project, weekly)
    except hb.BacklogError as e:
        print(f"중단: {e}", file=sys.stderr)
        return 1
    print(f"프로젝트: {project}\n")
    show(steps)
    if not a.apply:
        print("\n계획만 보였다. 적용하려면 --apply (없는 파일은 묻거나 --create <단위|all>).")
        return 0
    print()
    failed = apply(steps, set(a.create))
    if not a.uninstall:
        print(MANUAL)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
