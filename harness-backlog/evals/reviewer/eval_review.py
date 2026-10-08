#!/usr/bin/env python3
"""검토자 eval. 정답이 정해진 세션으로 review.md + 검토 모델의 제안 품질을 잰다.

  eval_review.py                 모든 케이스, 케이스당 3번
  eval_review.py --case 'neg-*'  이름이 맞는 케이스만
  eval_review.py --runs 1        반복 횟수 바꾸기
  eval_review.py --dry-run       모델을 부르지 않고 대본 변환·라벨만 검사
  eval_review.py --no-judge      애매한 매칭을 LLM에 묻지 않음

케이스 = cases/<이름>/
  session.md   대본. 머리말(agent, model) 뒤 '---', 그 아래 한 줄에 한 턴:
                 user[ @라벨]: 글          assistant[ @라벨]: 글
                 call <도구>[ @라벨]: 입력   result[ !error][ @라벨]: 출력
               두 칸 들여쓴 줄은 앞 턴에 이어 붙는다.
  project/     검토자가 확인할 미니 하네스 (AGENTS.md 등)
  expect.json  {"must": [{"at": "라벨"|["라벨",...], "type": "...", "about": "..."}],
                "must_not": [{"at": ..., "about": "..."}],
                "max_candidates": N, "forbid_text": ["정규식", ...]}

검토는 실제 운영과 같은 조합으로 돈다 (claude 대본은 codex가, codex 대본은 claude가).
채점: 후보의 근거 턴이 정답 라벨 범위(±1턴) 안이면 맞음. 남은 것만 haiku에게 같은 문제인지 묻는다.
통과: must는 반복의 과반에서 찾고, must_not · max_candidates · forbid_text는 한 번도 어기지 않고,
     검토 뒤 project/ 파일이 그대로여야 한다.
결과는 results/<시각>.json 에 남고, 직전 결과와 비교해 보여준다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import hb  # noqa: E402
import read_sessions as rs  # noqa: E402
import review  # noqa: E402

LINE_RE = re.compile(r"^(user|assistant|call|result)(?:\s+(?!@|!)(\S+))?((?:\s+(?:@\S+|!error))*)\s*:\s?(.*)$")
TOOL_KEY = {"Bash": "command", "Read": "file_path", "Edit": "file_path", "Write": "file_path",
            "Grep": "pattern", "Glob": "pattern"}
WINDOW = 1


# ---------------------------------------------------------------- 대본 → 기록

def parse_script(text: str) -> tuple[dict, list[dict]]:
    head, sep, body = text.partition("\n---\n")
    if not sep:
        raise ValueError("머리말 뒤에 '---' 줄이 없다")
    meta = dict(line.split(":", 1) for line in head.strip().splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    if meta.get("agent") not in ("claude", "codex"):
        raise ValueError("머리말 agent 는 claude | codex")
    entries: list[dict] = []
    for raw in body.splitlines():
        if raw.startswith("  ") and entries:
            entries[-1]["text"] += "\n" + raw[2:]
            continue
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = LINE_RE.match(raw)
        if not m:
            raise ValueError(f"대본 줄 형식이 틀렸다: {raw[:60]}")
        role, tool, marks, text = m.groups()
        labels = re.findall(r"@(\S+)", marks or "")
        entries.append({"role": role, "tool": tool, "labels": labels,
                        "error": "!error" in (marks or ""), "text": text})
    return meta, entries


def _ts(i: int) -> str:
    return (dt.datetime(2026, 1, 1, 9, 0, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=10 * i)).isoformat().replace("+00:00", "Z")


def _tool_input(tool: str, text: str) -> dict:
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    return {TOOL_KEY.get(tool, "input"): text}


def to_claude(meta: dict, entries: list[dict], sid: str, cwd: str) -> list[dict]:
    rows, last_call = [], None
    model = meta.get("model", "claude-opus-5-5")
    for i, e in enumerate(entries):
        base = {"sessionId": sid, "cwd": cwd, "timestamp": _ts(i)}
        if e["role"] == "user":
            rows.append({**base, "type": "user", "message": {"role": "user", "content": e["text"]}})
        elif e["role"] == "assistant":
            rows.append({**base, "type": "assistant", "message": {"model": model, "content": [{"type": "text", "text": e["text"]}]}})
        elif e["role"] == "call":
            last_call = f"t{i}"
            rows.append({**base, "type": "assistant", "message": {"model": model, "content": [
                {"type": "tool_use", "id": last_call, "name": e["tool"] or "Bash", "input": _tool_input(e["tool"] or "Bash", e["text"])}]}})
        else:
            rows.append({**base, "type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": last_call, "is_error": e["error"], "content": e["text"]}]}})
    return rows


def to_codex(meta: dict, entries: list[dict], sid: str, cwd: str) -> list[dict]:
    rows = [{"type": "session_meta", "timestamp": _ts(0), "payload": {"id": sid, "cwd": cwd, "thread_source": "user"}},
            {"type": "turn_context", "payload": {"model": meta.get("model", "gpt-6.1-sol"), "effort": meta.get("effort", "medium")}}]
    last_call = None
    for i, e in enumerate(entries):
        ts = _ts(i)
        if e["role"] in ("user", "assistant"):
            kind = "input_text" if e["role"] == "user" else "output_text"
            rows.append({"type": "response_item", "timestamp": ts, "payload": {
                "type": "message", "role": e["role"], "content": [{"type": kind, "text": e["text"]}]}})
        elif e["role"] == "call":
            last_call = f"c{i}"
            rows.append({"type": "response_item", "timestamp": ts, "payload": {
                "type": "function_call", "name": "shell", "call_id": last_call,
                "arguments": json.dumps({"command": e["text"]}, ensure_ascii=False)}})
        else:
            out = [{"type": "input_text", "text": "Script completed\nWall time 0.1 seconds\nOutput:\n"},
                   {"type": "input_text", "text": json.dumps({"exit_code": 1 if e["error"] else 0, "output": e["text"]}, ensure_ascii=False)}]
            rows.append({"type": "response_item", "timestamp": ts, "payload": {
                "type": "function_call_output", "call_id": last_call, "output": json.dumps(out, ensure_ascii=False)}})
    return rows


def build_session(case: Path, workdir: Path) -> tuple[str, Path, dict, dict]:
    """대본을 기록 파일로 쓰고, 정규화한 세션과 라벨 → 턴 번호 표를 돌려준다."""
    meta, entries = parse_script((case / "session.md").read_text(encoding="utf-8"))
    agent, sid = meta["agent"], f"eval-{case.name}"
    rows = (to_claude if agent == "claude" else to_codex)(meta, entries, sid, str(workdir))
    path = workdir.parent / f"{sid}.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    session = rs.normalize(agent, path)
    if len(session["turns"]) != len(entries):
        raise ValueError(f"대본 {len(entries)}줄이 턴 {len(session['turns'])}개로 바뀌었다 (노이즈로 걸러진 줄이 있다)")
    labels: dict[str, int] = {}
    for i, e in enumerate(entries):
        for lab in e["labels"]:
            labels[lab] = i
    return agent, path, session, labels


def turn_range(at, labels: dict) -> tuple[int, int]:
    names = at if isinstance(at, list) else [at]
    missing = [n for n in names if n not in labels]
    if missing:
        raise ValueError(f"대본에 없는 라벨: {missing}")
    turns = [labels[n] for n in names]
    return min(turns) - WINDOW, max(turns) + WINDOW


# ---------------------------------------------------------------- 채점

def judge(expected: str, cand: dict) -> bool:
    """턴으로 못 정한 매칭만 작은 모델에게 묻는다."""
    prompt = (f"기대한 개선점: {expected}\n\n검토자가 낸 후보:\n제목: {cand.get('title')}\n내용: {cand.get('content')}\n\n"
              "두 개가 같은 문제를 가리키면 yes, 아니면 no. 한 단어로만 답한다.")
    exe = shutil.which("claude")
    if not exe:
        return False
    r = subprocess.run([exe, "-p", "--model", "haiku", "--no-session-persistence", "--restricted", "--tools", "",
                        "--strict-mcp-config"], input=prompt, capture_output=True, text=True, timeout=120)
    return r.stdout.strip().lower().startswith("yes")


def grade_run(cands: list[dict], expect: dict, labels: dict, use_judge: bool) -> dict:
    cands = [c for c in cands if isinstance(c, dict)]
    turn = lambda c: c.get("turn") if isinstance(c.get("turn"), int) else -99
    found, matched = [], set()
    type_ok = 0
    for k, m in enumerate(expect.get("must", [])):
        lo, hi = turn_range(m["at"], labels)
        hit = next((j for j, c in enumerate(cands) if j not in matched and lo <= turn(c) <= hi), None)
        if hit is None and use_judge and m.get("about"):
            hit = next((j for j, c in enumerate(cands) if j not in matched and judge(m["about"], c)), None)
        if hit is not None:
            matched.add(hit)
            found.append(k)
            type_ok += int(not m.get("type") or cands[hit].get("type") == m["type"])
    violations = []
    for m in expect.get("must_not", []):
        lo, hi = turn_range(m["at"], labels)
        lo, hi = lo + WINDOW, hi - WINDOW  # must_not 은 그 턴만
        if any(lo <= turn(c) <= hi for c in cands):
            violations.append(f"must_not: {m.get('about') or m['at']}")
    if "max_candidates" in expect and len(cands) > expect["max_candidates"]:
        violations.append(f"후보 {len(cands)}개 > 허용 {expect['max_candidates']}개")
    blob = json.dumps(cands, ensure_ascii=False)
    for pat in expect.get("forbid_text", []):
        if re.search(pat, blob):
            violations.append(f"금지 문구: {pat}")
    return {"candidates": len(cands), "found": found, "matched": len(matched), "type_ok": type_ok,
            "violations": violations, "titles": [c.get("title") for c in cands]}


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "history" not in p.parts:
            h.update(str(p.relative_to(root)).encode() + p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- 실행

def run_case(case: Path, runs: int, use_judge: bool, dry_run: bool, budget: list) -> dict:
    expect = json.loads((case / "expect.json").read_text(encoding="utf-8"))
    out = {"case": case.name, "runs": []}
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        shutil.copytree(case / "project", proj) if (case / "project").exists() else proj.mkdir()
        agent, path, session, labels = build_session(case, proj)
        for m in expect.get("must", []) + expect.get("must_not", []):
            turn_range(m["at"], labels)  # 라벨 검사
        cfg = hb.load_config(proj)
        cfg["cli_paths"] = {c: shutil.which(c) or "" for c in ("claude", "codex")}
        if not cfg["reviewers"]["claude"].get("model"):
            cfg["reviewers"]["claude"]["model"] = _codex_default_model()
        rcfg = cfg["reviewers"][agent]
        out.update(agent=agent, reviewer=f"{rcfg['cli']} {review.reviewer_label(rcfg)}", turns=len(session["turns"]))
        prompt = review.build_prompt(proj, cfg, rs.render(session, rs.signals(session, cfg)))
        if dry_run:
            out["prompt_chars"] = len(prompt)
            return out
        before = _tree_hash(proj)
        for _ in range(runs):
            if budget[0] <= 0:
                out["runs"].append({"error": "호출 상한 도달"})
                continue
            budget[0] -= 1
            try:
                res = review.parse_output(review.run_reviewer(cfg, rcfg, proj, prompt))
                g = grade_run(res.get("candidates") or [], expect, labels, use_judge)
            except Exception as e:  # noqa: BLE001
                g = {"error": f"{e.__class__.__name__}: {str(e)[:200]}"}
            out["runs"].append(g)
        if _tree_hash(proj) != before:
            out["modified_project"] = True
    ok_runs = [r for r in out["runs"] if "error" not in r]
    need = len(ok_runs) // 2 + 1 if ok_runs else 1
    musts = len(expect.get("must", []))
    out["must"] = musts
    out["must_found"] = [sum(k in r["found"] for r in ok_runs) for k in range(musts)]
    out["passed"] = bool(ok_runs) and len(ok_runs) == len(out["runs"]) \
        and all(n >= need for n in out["must_found"]) \
        and not any(r["violations"] for r in ok_runs) and not out.get("modified_project")
    return out


def _codex_default_model() -> str:
    p = Path("~/.codex/config.toml").expanduser()
    m = re.search(r'^model\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"), re.M) if p.exists() else None
    return m.group(1) if m else ""


def summarize(results: list[dict]) -> dict:
    runs = [r for c in results for r in c["runs"] if "error" not in r]
    must_total = sum(c["must"] * len([r for r in c["runs"] if "error" not in r]) for c in results)
    found = sum(len(r["found"]) for r in runs)
    cands = sum(r["candidates"] for r in runs)
    matched = sum(r["matched"] for r in runs)
    return {
        "passed": sum(c["passed"] for c in results), "cases": len(results),
        "recall": round(found / must_total, 3) if must_total else None,
        "precision": round(matched / cands, 3) if cands else None,
        "type_accuracy": round(sum(r["type_ok"] for r in runs) / found, 3) if found else None,
        "errors": sum(1 for c in results for r in c["runs"] if "error" in r),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default="*")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=60, help="검토자 호출 상한")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cases-dir", default=str(HERE / "cases"))
    ap.add_argument("--results-dir", default=str(HERE / "results"))
    a = ap.parse_args(argv)

    cases = sorted(p for p in Path(a.cases_dir).iterdir() if p.is_dir() and fnmatch.fnmatch(p.name, a.case))
    if not cases:
        print("맞는 케이스가 없다", file=sys.stderr)
        return 1
    budget, results = [a.max_calls], []
    for case in cases:
        try:
            res = run_case(case, a.runs, not a.no_judge, a.dry_run, budget)
        except (ValueError, OSError, KeyError) as e:
            print(f"✗ {case.name}: 케이스 오류 — {e}")
            return 1
        results.append(res)
        if a.dry_run:
            print(f"✓ {case.name}: {res['agent']} 대본 {res['turns']}턴 → 검토자 {res['reviewer']} · 프롬프트 {res['prompt_chars']}자")
            continue
        mark = "통과" if res["passed"] else "실패"
        found = " ".join(f"{n}/{len(res['runs'])}" for n in res["must_found"]) or "-"
        viol = sorted({v for r in res["runs"] for v in r.get("violations", [])} | {r["error"] for r in res["runs"] if "error" in r})
        print(f"{mark}  {case.name:<28} {res['reviewer']:<34} must {found:<8} {'; '.join(viol)}")
    if a.dry_run:
        return 0

    summary = summarize(results)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    rdir = Path(a.results_dir)
    prev = sorted(rdir.glob("*.json"))[-1:] if rdir.exists() else []
    rdir.mkdir(parents=True, exist_ok=True)
    n = 1
    while (rdir / f"{stamp}.json").exists():
        n += 1
        stamp = f"{stamp.split('_')[0]}_{n}"
    (rdir / f"{stamp}.json").write_text(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n통과 {summary['passed']}/{summary['cases']} · 재현율 {summary['recall']} · 정밀도 {summary['precision']}"
          f" · type 정확도 {summary['type_accuracy']} · 오류 {summary['errors']}  → results/{stamp}.json")
    if prev:
        old = json.loads(prev[0].read_text(encoding="utf-8"))
        before = {c["case"]: c["passed"] for c in old["cases"]}
        changes = [f"{c['case']} {'통과→실패' if before[c['case']] else '실패→통과'}"
                   for c in results if c["case"] in before and before[c["case"]] != c["passed"]]
        o = old["summary"]
        print(f"직전({prev[0].stem}) 대비: 재현율 {o['recall']}→{summary['recall']} · 정밀도 {o['precision']}→{summary['precision']}"
              + (f" · 바뀐 케이스: {', '.join(changes)}" if changes else ""))
    return 0 if summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
