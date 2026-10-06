#!/usr/bin/env python3
"""backlog 항목을 쓰는 유일한 통로.

  backlog.py add      --input item.json            새 pending 항목
  backlog.py append   --file F --input r.json      pending 항목에 재발 근거 추가
  backlog.py merge    --files A B --input item.json  원인이 같은 pending을 하나로
  backlog.py resolve  --file F --status applied|rejected --input r.json
  backlog.py list     [--json]                     pending 목록 + 운영 상태
  backlog.py ledger   --input entry.json           검토 기록 한 줄

공통: [--project <경로>] (기본: 현재 디렉터리의 git 루트)
입력은 JSON 파일이다. 여러 줄 텍스트를 셸 인자로 넘기면 깨지기 때문이다.
종료 코드: 0 성공 · 1 실패 · 3 중복이라 거부
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hb  # noqa: E402

ITEM_FIELDS = {
    "slug", "title", "type", "target", "source", "ref",
    "session_model", "reviewer_model", "content", "evidence", "existing",
}
OPTIONAL_ITEM_FIELDS = {"relates"}


class Duplicate(hb.BacklogError):
    pass


# ---------------------------------------------------------------- 검증

def _need_str(data: dict, key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise hb.BacklogError(f"'{key}'는 비어 있지 않은 문자열이어야 한다")
    return v.strip()


def _check_secrets(data: dict) -> None:
    texts = [v for v in data.values() if isinstance(v, str)]
    texts += [x for v in data.values() if isinstance(v, list) for x in v if isinstance(x, str)]
    hits = hb.scan_secrets(*texts)
    if hits:
        raise hb.BacklogError("비밀정보로 보이는 값이 있어 거부한다: " + ", ".join(hits))


def validate_item(data, extra: set[str] = frozenset()) -> dict:
    if not isinstance(data, dict):
        raise hb.BacklogError("입력 최상위는 JSON 객체여야 한다")
    for banned in ("date", "time", "status"):
        if banned in data:
            raise hb.BacklogError(f"'{banned}'는 스크립트가 정한다. 입력에서 빼라")
    unknown = set(data) - ITEM_FIELDS - OPTIONAL_ITEM_FIELDS - extra
    if unknown:
        raise hb.BacklogError("알 수 없는 필드: " + ", ".join(sorted(unknown)))
    missing = ITEM_FIELDS - set(data)
    if missing:
        raise hb.BacklogError("필수 필드 누락: " + ", ".join(sorted(missing)))
    out = {k: _need_str(data, k) for k in ITEM_FIELDS}
    if not hb.SLUG_RE.match(out["slug"]):
        raise hb.BacklogError("slug는 소문자·숫자·하이픈만 쓴다 (예: commit-staged-check)")
    if out["type"] not in hb.TYPES:
        raise hb.BacklogError("type은 " + " | ".join(hb.TYPES) + " 중 하나")
    if not hb.REF_RE.match(out["ref"]):
        raise hb.BacklogError("ref 형식: claude:<세션>#<시각> | codex:<세션>#<시각> | weekly:YYYY-Www")
    relates = data.get("relates", [])
    if not isinstance(relates, list) or not all(isinstance(r, str) and r.endswith(".md") for r in relates):
        raise hb.BacklogError("relates는 항목 파일명(.md) 목록이어야 한다")
    out["relates"] = relates
    _check_secrets(data)
    return out


def _all_items(bdir: Path):
    yield from hb.iter_items(bdir)
    yield from hb.iter_items(bdir, resolved=True)


def _find_duplicate(bdir: Path, ref: str, title: str) -> str | None:
    for p, front, _ in _all_items(bdir):
        if front.get("ref") == ref and front.get("title") == title:
            return p.name
    return None


# ---------------------------------------------------------------- 쓰기

def _front_and_sections(item: dict, status: str = "pending") -> tuple[dict, dict]:
    t = hb.now()
    front = {
        "date": t.strftime("%Y-%m-%d"), "time": t.strftime("%H:%M"),
        "title": item["title"], "type": item["type"], "target": item["target"],
        "source": item["source"], "ref": item["ref"], "relates": item["relates"],
        "session_model": item["session_model"], "reviewer_model": item["reviewer_model"],
        "status": status,
    }
    sections = {"내용": item["content"], "근거": item["evidence"], "기존 하네스": item["existing"]}
    return front, sections


def _verifier(front: dict):
    def verify(text: str) -> None:
        got, sections = hb.parse_item(text)
        for k, v in front.items():
            if v not in (None, [], "") and got.get(k) != v:
                raise hb.BacklogError(f"다시 읽은 '{k}' 값이 입력과 다르다")
        for name in hb.SECTIONS:
            if not sections.get(name):
                raise hb.BacklogError(f"다시 읽은 항목에 '## {name}'이 비어 있다")
    return verify


def _free_name(bdir: Path, date: str, slug: str) -> Path:
    base = f"{date}-{slug}"
    for n in range(1, 100):
        name = f"{base}.md" if n == 1 else f"{base}-{n}.md"
        if not (bdir / name).exists() and not (bdir / hb.RESOLVED / name).exists():
            return bdir / name
    raise hb.BacklogError("같은 날 같은 slug가 너무 많다")


def add_item(project: Path, data) -> Path:
    item = validate_item(data)
    bdir = hb.backlog_dir(project)
    dup = _find_duplicate(bdir, item["ref"], item["title"])
    if dup:
        raise Duplicate(f"같은 ref·title 항목이 이미 있다: {dup}")
    for r in item["relates"]:
        if not (bdir / r).exists() and not (bdir / hb.RESOLVED / r).exists():
            raise hb.BacklogError(f"relates가 가리키는 항목이 없다: {r}")
    front, sections = _front_and_sections(item)
    path = _free_name(bdir, front["date"], item["slug"])
    hb.publish(path, hb.render_item(front, sections), verify=_verifier(front))
    return path


def _pending_file(project: Path, name: str) -> Path:
    if "/" in name or not name.endswith(".md"):
        raise hb.BacklogError("--file 은 backlog 디렉터리 안의 항목 파일명이다")
    path = hb.backlog_dir(project) / name
    if not path.exists():
        raise hb.BacklogError(f"pending 항목이 없다: {name}")
    return path


def append_recurrence(project: Path, name: str, data) -> Path:
    if not isinstance(data, dict):
        raise hb.BacklogError("입력 최상위는 JSON 객체여야 한다")
    unknown = set(data) - {"ref", "session_model", "reviewer_model", "note"}
    if unknown:
        raise hb.BacklogError("알 수 없는 필드: " + ", ".join(sorted(unknown)))
    ref, note = _need_str(data, "ref"), _need_str(data, "note")
    smodel, rmodel = _need_str(data, "session_model"), _need_str(data, "reviewer_model")
    if not hb.REF_RE.match(ref):
        raise hb.BacklogError("ref 형식이 틀렸다")
    _check_secrets(data)
    path = _pending_file(project, name)
    front, sections = hb.read_item(path)
    if ref in sections.get("재발", "") or ref == front.get("ref"):
        raise Duplicate("이미 기록된 재발이다")
    line = f"- {hb.now():%Y-%m-%d} `{ref}` (세션 {smodel} · 검토 {rmodel}): {note}"
    sections["재발"] = (sections.get("재발", "") + "\n" + line).strip()
    hb.publish(path, hb.render_item(front, sections), overwrite=True, verify=_verifier(front))
    return path


def _resolve_to(project: Path, path: Path, status: str, resolution: str) -> Path:
    front, sections = hb.read_item(path)
    front["status"] = status
    sections.pop("해소", None)
    sections["해소"] = resolution
    dest = hb.backlog_dir(project) / hb.RESOLVED / path.name
    hb.publish(dest, hb.render_item(front, sections), verify=_verifier(front))
    path.unlink()
    return dest


def merge_items(project: Path, names: list[str], data) -> Path:
    if len(names) < 2:
        raise hb.BacklogError("병합하려면 항목이 둘 이상 필요하다")
    if not isinstance(data, dict):
        raise hb.BacklogError("입력 최상위는 JSON 객체여야 한다")
    reason = _need_str(data, "merge_reason")
    paths = [_pending_file(project, n) for n in names]
    item_in = {k: v for k, v in data.items() if k != "merge_reason"}
    item_in["relates"] = sorted(set(item_in.get("relates", [])) | set(names))
    new = add_item(project, item_in)
    done = []
    try:
        for p in paths:
            text = f"결과: 병합\n병합된 항목: {new.name}\n왜: {reason}\n날짜: {hb.now():%Y-%m-%d}"
            done.append(_resolve_to(project, p, "merged", text).name)
    except hb.BacklogError as e:
        raise hb.BacklogError(f"병합 도중 실패 ({e}). 새 항목 {new.name}, 옮겨진 원본: {done or '없음'}")
    return new


def resolve_item(project: Path, name: str, status: str, data) -> Path:
    if status not in ("applied", "rejected"):
        raise hb.BacklogError("--status 는 applied | rejected")
    if not isinstance(data, dict):
        raise hb.BacklogError("입력 최상위는 JSON 객체여야 한다")
    unknown = set(data) - {"reason", "changed"}
    if unknown:
        raise hb.BacklogError("알 수 없는 필드: " + ", ".join(sorted(unknown)))
    reason = _need_str(data, "reason")
    lines = [f"결과: {'반영' if status == 'applied' else '기각'}", f"왜: {reason}"]
    if status == "applied":
        lines.append(f"바꾼 곳: {_need_str(data, 'changed')}")
    lines.append(f"날짜: {hb.now():%Y-%m-%d}")
    _check_secrets(data)
    return _resolve_to(project, _pending_file(project, name), status, "\n".join(lines))


# ---------------------------------------------------------------- 목록

def health(project: Path) -> dict:
    entries = hb.ledger_read(project)
    week_ago = hb.now().timestamp() - 7 * 86400
    recent = [e for e in entries if e.get("at") and hb.parse_time(e["at"]).timestamp() >= week_ago]
    sessions = [e for e in recent if e.get("kind") == "session"]
    last_weekly = next((e["at"] for e in reversed(entries) if e.get("kind") == "weekly"), None)
    return {
        "reviewed_7d": sum(e.get("status") == "reviewed" for e in sessions),
        "failed_7d": sum(e.get("status") in ("failed", "unavailable") for e in sessions),
        "last_session_review": next((e["at"] for e in reversed(entries) if e.get("kind") == "session"), None),
        "last_weekly": last_weekly,
    }


def list_items(project: Path) -> dict:
    bdir = hb.backlog_dir(project)
    today = hb.now().date()
    rows = []
    for p, front, _ in hb.iter_items(bdir):
        try:
            age = (today - hb.parse_time(f"{front['date']}T00:00").date()).days
        except (KeyError, ValueError):
            age = None
        rows.append({
            "file": p.name, "age_days": age, "type": front.get("type"),
            "title": front.get("title"), "target": front.get("target"),
            "source": front.get("source"), "ref": front.get("ref"),
        })
    rows.sort(key=lambda r: (r["age_days"] is None, -(r["age_days"] or 0)))
    sources = Counter(r["source"] for r in rows)
    return {"pending": rows, "count": len(rows), "sources": dict(sources), "health": health(project)}


def print_list(data: dict) -> None:
    h = data["health"]
    print(f"pending {data['count']}건")
    for r in data["pending"]:
        age = "?" if r["age_days"] is None else f"{r['age_days']}일"
        print(f"  [{age:>4}] {r['type']:<10} {r['title']}  → {r['target']}  ({r['file']})")
    if data["sources"]:
        print("source별: " + ", ".join(f"{k} {v}" for k, v in sorted(data["sources"].items())))
    print(
        f"운영: 최근 7일 검토 {h['reviewed_7d']} · 실패/미실행 {h['failed_7d']}"
        f" · 마지막 세션 검토 {h['last_session_review'] or '없음'}"
        f" · 마지막 주간 {h['last_weekly'] or '없음'}"
    )


# ---------------------------------------------------------------- CLI

def _load_input(path: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise hb.BacklogError(f"입력 JSON을 읽지 못했다: {e.__class__.__name__}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("--input", required=True)
    s = sub.add_parser("append"); s.add_argument("--file", required=True); s.add_argument("--input", required=True)
    s = sub.add_parser("merge"); s.add_argument("--files", nargs="+", required=True); s.add_argument("--input", required=True)
    s = sub.add_parser("resolve"); s.add_argument("--file", required=True)
    s.add_argument("--status", required=True); s.add_argument("--input", required=True)
    s = sub.add_parser("list"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("ledger"); s.add_argument("--input", required=True)
    a = ap.parse_args(argv)

    try:
        project = hb.resolve_project(a.project)
        if a.cmd == "add":
            print(add_item(project, _load_input(a.input)))
        elif a.cmd == "append":
            print(append_recurrence(project, a.file, _load_input(a.input)))
        elif a.cmd == "merge":
            print(merge_items(project, a.files, _load_input(a.input)))
        elif a.cmd == "resolve":
            print(resolve_item(project, a.file, a.status, _load_input(a.input)))
        elif a.cmd == "list":
            data = list_items(project)
            print(json.dumps(data, ensure_ascii=False, indent=2)) if a.json else print_list(data)
        elif a.cmd == "ledger":
            entry = _load_input(a.input)
            if not isinstance(entry, dict) or entry.get("kind") not in ("session", "weekly", "note"):
                raise hb.BacklogError("ledger 항목은 kind가 session | weekly | note 인 객체다")
            hb.ledger_append(project, entry)
    except Duplicate as e:
        print(f"중복: {e}", file=sys.stderr)
        return 3
    except hb.BacklogError as e:
        print(f"거부: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
