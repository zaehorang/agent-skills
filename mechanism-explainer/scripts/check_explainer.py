#!/usr/bin/env python3
"""Static checks for a single-file explainer. Fails loudly, says only what is wrong.

    python3 scripts/check_explainer.py out.html

Covers everything that can be decided without a browser. What it cannot see —
label size on screen, clipped elements, whether a demo actually changes anything —
stays in the SKILL.md eye-check list.
"""

from __future__ import annotations

import collections
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

FONT_HOSTS = ("https://fonts.googleapis.com", "https://fonts.gstatic.com")


class Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external: list[str] = []
        self.anchors: list[str] = []
        self.in_script = False
        self.script: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value for name, value in attrs if value is not None}
        if values.get("id"):
            self.ids.append(values["id"])
        href = values.get("href", "")
        if href.startswith("#"):
            self.anchors.append(href[1:])
        for candidate in (values.get("src", ""), href):
            if candidate.startswith(("http://", "https://", "//")):
                if not candidate.startswith(FONT_HOSTS):
                    self.external.append(candidate)
        if tag == "script" and not values.get("src"):
            self.in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.script.append(data)


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    scan = Scan()
    scan.feed(text)
    bad: list[str] = []

    dupes = sorted({i for i, n in collections.Counter(scan.ids).items() if n > 1})
    if dupes:
        bad.append(f"중복 id: {', '.join(dupes)}")

    seen = set(scan.ids)
    missing = sorted({a for a in scan.anchors if a and a not in seen})
    if missing:
        bad.append(f"대상 없는 내부 앵커: {', '.join(missing)}")

    if scan.external:
        bad.append(f"외부 의존성(웹폰트 제외): {', '.join(sorted(set(scan.external))[:5])}")

    left = re.findall(r"\[\[[^\]\n]{1,60}\]\]|TODO|FIXME|__PLACEHOLDER__", text)
    if left:
        bad.append(f"남은 플레이스홀더: {', '.join(sorted(set(left))[:5])}")

    body = "".join(scan.script)
    if "setInterval" in body and "clearInterval" not in body:
        bad.append("setInterval 은 있는데 clearInterval 이 없다 — 단계를 옮겨도 계속 돈다")
    if "setTimeout" in body and "clearTimeout" not in body:
        bad.append("setTimeout 은 있는데 clearTimeout 이 없다 — 단계를 옮긴 뒤 혼자 튀어나온다")

    if "prefers-reduced-motion" not in text:
        bad.append("prefers-reduced-motion 처리가 없다")

    theme = [
        ("라이트 기본값", bool(re.search(r":root\s*\{", text))),
        ("prefers-color-scheme 다크", "prefers-color-scheme" in text and "dark" in text),
        ("data-theme 다크", 'data-theme="dark"' in text or "data-theme='dark'" in text),
    ]
    absent = [name for name, ok in theme if not ok]
    if absent:
        bad.append(f"테마 토큰이 세 군데에 다 없다 — 빠진 곳: {', '.join(absent)}")

    if not re.search(r"(body|html)\s*\{[^}]*background", text):
        bad.append("body 배경을 토큰으로 명시하지 않았다 — 뷰어 배경이 비친다")

    if body.strip():
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        try:
            done = subprocess.run(
                ["node", "--check", tmp_path], capture_output=True, text=True
            )
            if done.returncode != 0:
                first = (done.stderr.strip().splitlines() or ["?"])[0]
                bad.append(f"스크립트 구문 오류: {first}")
        except FileNotFoundError:
            print("  (node 가 없어 구문 검사는 건너뜀)", file=sys.stderr)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return bad


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용법: check_explainer.py <파일.html>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2

    problems = check(path)
    if problems:
        print(f"FAIL  {path}  ({len(problems)}건)")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"OK    {path}  — 정적 검사 통과. 눈으로 볼 것은 SKILL.md 6절.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
