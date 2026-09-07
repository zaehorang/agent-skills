#!/usr/bin/env python3
"""동작 명세(Markdown)에서 구현 누출과 검증 불가능한 항목을 잡는 린터.

stdlib only, Python 3.10+.

사용법:
    python3 lint_spec.py docs/specs/*.md [--strict]

에러가 하나라도 있으면 종료 코드 1. --strict를 주면 경고도 실패로 본다.
줄 끝에 <!-- lint-ok --> 를 붙이면 그 줄의 식별자·용어 검사를 건너뛴다.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- 섹션 정의

REQUIRED_SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("Goal", ("goal", "목표")),
    ("Triggers", ("triggers", "trigger", "발동", "계기")),
    ("Inputs", ("inputs", "input", "입력")),
    ("Outputs", ("outputs", "output", "출력", "결과")),
    ("Edge cases", ("edge cases", "edge case", "edgecases", "예외", "경계")),
    ("Acceptance", ("acceptance", "인수", "검증")),
]

# ---------------------------------------------------------- 식별자 누출 패턴

ALLOWED_PROPER = {
    "JavaScript", "TypeScript", "GitHub", "GitLab", "LeetCode", "SolveSync",
    "YouTube", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "WebSocket",
    "OAuth", "OpenAI", "AppStore", "PlayStore", "WiFi", "IPhone", "IPad",
    "MacOS", "IOS", "AI",
}

FILE_EXT_OK = {
    "json", "md", "txt", "csv", "png", "jpg", "jpeg", "svg", "pdf", "zip",
    "html", "css", "yml", "yaml", "com", "org", "net", "io", "kr", "co",
}

IDENT_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "call",
        re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)"),
        "함수 호출 표기가 남아 있다. 그 호출이 밖에서 무엇으로 관측되는지로 바꾼다",
    ),
    (
        "dotted",
        re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b"),
        "점으로 이어진 식별자가 남아 있다. 사용자 관점 동작으로 바꾼다",
    ),
    (
        "camel",
        re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b"),
        "클래스/타입처럼 보이는 이름이 남아 있다. 그것이 하는 일을 사용자 말로 바꾼다",
    ),
    (
        "lower_camel",
        re.compile(r"\b[a-z]+(?:[A-Z][a-z0-9]*)+\b"),
        "변수/메서드처럼 보이는 이름이 남아 있다. 사용자 관점 동작으로 바꾼다",
    ),
    (
        "snake",
        re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
        "코드 식별자 표기가 남아 있다. 사용자 관점 동작으로 바꾼다",
    ),
    (
        "const",
        re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),
        "상수 이름이 남아 있다. 그 값이 사용자에게 무엇으로 보이는지로 바꾼다",
    ),
]

# 명확한 구현 용어 — 에러
TECH_ERROR: dict[str, str] = {
    "코루틴": "'즉시 끝나지 않는 작업'과 그동안 보이는 것으로",
    "싱글턴": "'어디까지 유지되는 상태'로",
    "리듀서": "'무엇이 어떤 조작에 어떻게 바뀌는지'로",
    "디스패치": "'어떤 조작이 일어나면'으로",
    "폴링": "'무엇이 얼마나 빨리 반영되는지'로",
    "렌더링": "'화면에 보인다'로",
    "리렌더": "'화면이 다시 그려진다'로",
    "마운트": "'화면이 열리면'으로",
    "언마운트": "'화면을 떠나면'으로",
    "메서드": "그 동작이 사용자에게 무엇을 하는지로",
    "클래스": "그것이 담당하는 사용자 관점 동작으로",
    "인터페이스": "'주고받는 값'으로",
    "생성자": "'만들어질 때'로",
    "콜백": "'끝나면 무엇이 일어나는지'로",
    "프라미스": "'즉시 끝나지 않는 작업'으로",
    "옵저버": "'값이 바뀌면 무엇이 따라 바뀌는지'로",
    "리스너": "'무엇을 기다리다가 무엇을 하는지'로",
    "델리게이트": "'누가 이어서 처리하는지'로",
    "인스턴스": "사용자가 보는 대상 이름으로",
    "프리팹": "사용자가 보는 대상 이름으로",
    "프레임": "'즉시' 또는 사용자가 체감하는 지연으로",
    "스레드": "'동시에 일어나는 일'로",
    "뮤텍스": "'동시에 하나만 처리된다'로",
    "직렬화": "'저장되는 형태'로",
    "역직렬화": "'읽어 들인다'로",
    "메모리": "사용자가 체감하는 결과로 (없으면 삭제)",
    "가비지": "사용자가 체감하는 결과로 (없으면 삭제)",
    "코드베이스": "사용자 관점 서술로",
    "coroutine": "'즉시 끝나지 않는 작업'으로",
    "singleton": "'어디까지 유지되는 상태'로",
    "reducer": "'무엇이 어떤 조작에 어떻게 바뀌는지'로",
    "dispatch": "'어떤 조작이 일어나면'으로",
    "polling": "'무엇이 얼마나 빨리 반영되는지'로",
    "render": "'화면에 보인다'로",
    "mount": "'화면이 열리면'으로",
    "unmount": "'화면을 떠나면'으로",
    "callback": "'끝나면 무엇이 일어나는지'로",
    "promise": "'즉시 끝나지 않는 작업'으로",
    "async": "'즉시 끝나지 않는 작업'으로",
    "await": "'끝날 때까지 기다린다'로",
    "thread": "'동시에 일어나는 일'로",
    "mutex": "'동시에 하나만 처리된다'로",
    "hook": "'언제부터 반응하는지'로",
    "prefab": "사용자가 보는 대상 이름으로",
}

# 애매한 용어 — 경고
TECH_WARN: dict[str, str] = {
    "캐시": "사용자가 체감하지 못하면 삭제하고, 체감되면 '기다림 없이 바로 보인다'로",
    "캐싱": "사용자가 체감하지 못하면 삭제하고, 체감되면 '기다림 없이 바로 보인다'로",
    "비동기": "'즉시 끝나지 않는다'와 그동안 보이는 것으로",
    "동기화": "무엇이 어디에서 어디로 언제 반영되는지로",
    "상태": "무엇의 상태이고 어디까지 유지되는지 함께",
    "객체": "사용자가 보는 대상 이름으로",
    "배열": "'목록'으로",
    "필드": "'항목' 또는 '입력란'으로",
    "파라미터": "'전달되는 값'으로",
    "이벤트": "사용자가 하는 행동 또는 밖에서 일어나는 사건으로",
    "API": "'서버' 또는 '외부 서비스'로",
    "엔드포인트": "'서버' 또는 '외부 서비스'로",
    "쿼리": "'조회 조건'으로",
    "트랜잭션": "'중간에 실패하면 아무것도 반영되지 않는다'로",
    "로직": "구체적인 동작 서술로",
    "핸들링": "무엇을 어떻게 하는지로",
    "초기화": "'처음 열렸을 때 무엇이 보이는지'로",
    "인스턴싱": "사용자가 보는 결과로",
}

# ---------------------------------------------------------- Acceptance 검사

# 한국어 조건절("~하면", "~멈추면", "~인 상태에서", "~한 뒤")과 영어 조건절을 폭넓게 잡는다.
CONDITION_RE = re.compile(
    r"[가-힣]면[\s,]|[가-힣]면$|상태에서|경우|때\s|때,|뒤\s|뒤,|후\s|후,|동안|\bwhen\b|\bif\b|\bgiven\b"
)

# 관측되는 결과는 한국어 서술형 어미("~된다", "~보인다", "~올라간다")로 끝난다.
RESULT_ENDING_RE = re.compile(r"[가-힣]다\.?$")

URL_RE = re.compile(r"https?://\S+")
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
QUOTED_RE = re.compile(r"[\"“”']([^\"“”']{1,80})[\"“”']")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$")
LINT_OK_RE = re.compile(r"<!--\s*lint-ok\s*-->")


@dataclass
class Finding:
    level: str  # "ERROR" | "WARN"
    line: int
    message: str


def strip_noise(text: str) -> str:
    """검사에서 제외할 관측 가능한 문자열(URL, 인용된 UI 문구, 경로/파일명)을 지운다."""
    text = URL_RE.sub(" ", text)
    text = QUOTED_RE.sub(" ", text)

    def _inline(m: re.Match[str]) -> str:
        inner = m.group(1)
        if "/" in inner:
            return " "
        if "." in inner:
            ext = inner.rsplit(".", 1)[-1].lower()
            if ext in FILE_EXT_OK:
                return " "
        return inner

    text = INLINE_CODE_RE.sub(_inline, text)
    # 남은 경로/파일명도 제외
    text = re.sub(r"\b[\w.-]+/[\w./-]+", " ", text)
    text = re.sub(
        r"\b[\w-]+\.(" + "|".join(FILE_EXT_OK) + r")\b", " ", text, flags=re.IGNORECASE
    )
    # 소수점 숫자
    text = re.sub(r"\b\d+\.\d+\b", " ", text)
    return text


def check_identifiers(text: str, line_no: int) -> list[Finding]:
    found: list[Finding] = []
    cleaned = strip_noise(text)
    seen: set[str] = set()
    for _name, pattern, advice in IDENT_RULES:
        for m in pattern.finditer(cleaned):
            token = m.group(0).strip()
            if token in ALLOWED_PROPER or token in seen:
                continue
            if len(token) < 3:
                continue
            seen.add(token)
            found.append(Finding("ERROR", line_no, f"식별자 누출 '{token}' — {advice}"))
    return found


def check_terms(text: str, line_no: int) -> list[Finding]:
    found: list[Finding] = []
    cleaned = strip_noise(text)
    # 권장 표현으로 쓰인 조건절은 모호한 용어 검사 대상에서 뺀다
    cleaned = re.sub(r"상태(에서|로|가 아니|일 때)", " ", cleaned)
    lowered = cleaned.lower()
    for term, advice in TECH_ERROR.items():
        needle = term.lower()
        if needle in lowered:
            found.append(Finding("ERROR", line_no, f"구현 용어 '{term}' — {advice} 바꾼다"))
    for term, advice in TECH_WARN.items():
        needle = term.lower()
        if needle in lowered:
            found.append(Finding("WARN", line_no, f"모호한 용어 '{term}' — {advice} 바꾸는 편이 낫다"))
    return found


def split_sections(lines: list[str]) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    """heading 텍스트(소문자) -> (heading 줄번호, [(줄번호, 본문)])"""
    sections: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    current: str | None = None
    for idx, raw in enumerate(lines, start=1):
        m = HEADING_RE.match(raw)
        if m:
            current = m.group(1).strip().lower()
            sections.setdefault(current, (idx, []))
            continue
        if current is not None:
            sections[current][1].append((idx, raw))
    return sections


def find_section(
    sections: dict[str, tuple[int, list[tuple[int, str]]]], aliases: tuple[str, ...]
) -> tuple[int, list[tuple[int, str]]] | None:
    for heading, payload in sections.items():
        for alias in aliases:
            if alias in heading:
                return payload
    return None


def check_goal(body: list[tuple[int, str]], heading_line: int) -> list[Finding]:
    text = " ".join(t.strip() for _, t in body if t.strip() and not t.strip().startswith("<!--"))
    if not text:
        return [Finding("ERROR", heading_line, "Goal이 비어 있다")]
    sentences = [s for s in re.split(r"(?<=다)\.\s*|(?<=\.)\s+", text) if s.strip()]
    findings: list[Finding] = []
    if len(sentences) > 1:
        findings.append(
            Finding("ERROR", heading_line, f"Goal은 한 문장이다 (현재 {len(sentences)}문장). 문장이 더 필요하면 기능을 잘못 잘랐다")
        )
    if len(text) > 200:
        findings.append(Finding("WARN", heading_line, f"Goal이 길다 ({len(text)}자). 한 문장으로 줄인다"))
    return findings


def check_acceptance(body: list[tuple[int, str]], heading_line: int) -> list[Finding]:
    findings: list[Finding] = []
    bullets = [(n, m.group(1).strip()) for n, t in body if (m := BULLET_RE.match(t))]
    if not bullets:
        findings.append(
            Finding("ERROR", heading_line, "Acceptance에 검증 항목이 없다. 목록으로 적는다")
        )
        return findings
    for line_no, item in bullets:
        plain = item.rstrip()
        if not CONDITION_RE.search(plain):
            findings.append(
                Finding("WARN", line_no, "검증 조건이 없다. '<조건>에서 <행동>하면 <결과>가 된다' 형태로 쓴다")
            )
        if "그리고" in plain or " and " in plain.lower():
            findings.append(
                Finding("WARN", line_no, "한 항목에 여러 결과가 뭉쳐 있다. 항목을 나눈다")
            )
        if len(re.findall(r"다\.", plain)) > 1:
            findings.append(
                Finding("WARN", line_no, "한 항목에 문장이 여럿이다. 한 항목은 한 가지만 검증한다")
            )
        if not RESULT_ENDING_RE.search(plain):
            findings.append(
                Finding("WARN", line_no, "관측되는 결과로 끝나지 않는다. '~가 보인다 / ~가 된다'로 끝맺는다")
            )
        if re.search(r"(정상|올바르게|제대로|잘)\s*(동작|작동|갱신|처리|반영)", plain):
            findings.append(
                Finding("ERROR", line_no, "'정상 동작한다'는 검증할 수 없다. 무엇이 어떻게 보이는지 적는다")
            )
    return findings


def lint_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [Finding("ERROR", 0, f"파일을 읽을 수 없다: {exc}")]

    in_fence = False
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if not in_fence:
                findings.append(
                    Finding("ERROR", idx, "코드 블록은 명세에 넣지 않는다. 밖에서 관측되는 동작으로 바꾼다")
                )
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if LINT_OK_RE.search(raw):
            continue
        if HEADING_RE.match(raw):
            continue
        if not stripped:
            continue
        findings.extend(check_identifiers(raw, idx))
        findings.extend(check_terms(raw, idx))

    if in_fence:
        findings.append(Finding("ERROR", len(lines), "닫히지 않은 코드 블록이 있다"))

    sections = split_sections(lines)
    for canonical, aliases in REQUIRED_SECTIONS:
        payload = find_section(sections, aliases)
        if payload is None:
            findings.append(Finding("ERROR", 0, f"필수 섹션 '{canonical}'이 없다"))
            continue
        heading_line, body = payload
        text = "".join(t.strip() for _, t in body)
        if not text:
            findings.append(
                Finding("ERROR", heading_line, f"섹션 '{canonical}'이 비어 있다. 없으면 '없음'이라고 적는다")
            )
            continue
        if canonical == "Goal":
            findings.extend(check_goal(body, heading_line))
        elif canonical == "Acceptance":
            findings.extend(check_acceptance(body, heading_line))

    findings.sort(key=lambda f: (f.line, 0 if f.level == "ERROR" else 1))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="동작 명세 린터")
    parser.add_argument("paths", nargs="+", help="검사할 명세 Markdown 파일")
    parser.add_argument("--strict", action="store_true", help="경고도 실패로 본다")
    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0

    for raw_path in args.paths:
        path = Path(raw_path)
        findings = lint_file(path)
        errors = [f for f in findings if f.level == "ERROR"]
        warnings = [f for f in findings if f.level == "WARN"]
        total_errors += len(errors)
        total_warnings += len(warnings)

        print(f"\n{path}")
        if not findings:
            print("  통과")
            continue
        for f in findings:
            where = f"L{f.line}" if f.line else "-"
            print(f"  {f.level:<5} {where:>6}  {f.message}")

    print(f"\n합계: 에러 {total_errors}, 경고 {total_warnings}")
    if total_errors or (args.strict and total_warnings):
        print("명세를 제출하기 전에 위 항목을 고친다. 관측 가능한 문자열이라면 그 줄 끝에 <!-- lint-ok -->를 붙인다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
