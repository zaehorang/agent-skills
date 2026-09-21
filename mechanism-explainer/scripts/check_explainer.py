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


# 조작을 달아도 되는 것 — 나머지에 클릭을 달면 키보드로 닿지 않는다
INTERACTIVE = {"button", "a", "input", "select", "textarea", "summary", "label", "details"}


def is_remote(url: str) -> bool:
    return url.startswith(("http://", "https://", "//")) and not url.startswith(FONT_HOSTS)


class Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external: list[str] = []
        self.anchors: list[str] = []
        self.dead_clicks: list[str] = []
        self.aria_live = False
        self.buttons = 0
        self.in_script = False
        self.in_style = False
        self.script: list[str] = []
        self.style: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value for name, value in attrs if value is not None}
        if values.get("id"):
            self.ids.append(values["id"])
        href = values.get("href", "")
        if href.startswith("#"):
            self.anchors.append(href[1:])

        # 리소스를 "부르는" 자리만 본다 — <a href> 는 인용 링크이지 의존성이 아니다
        loaded = [values.get("src", ""), values.get("srcset", ""), values.get("poster", "")]
        if tag in ("link", "image", "use") and href:
            rel = values.get("rel", "").lower()
            if tag != "link" or rel in ("stylesheet", "preload", "icon", "shortcut icon"):
                loaded.append(href)
        for candidate in loaded:
            for part in candidate.split(","):
                url = part.strip().split(" ")[0]
                if url and is_remote(url):
                    self.external.append(url)
        self.style.append(values.get("style", ""))

        if tag == "button":
            self.buttons += 1
        if values.get("aria-live"):
            self.aria_live = True
        if values.get("onclick") and tag not in INTERACTIVE:
            self.dead_clicks.append(tag + (("#" + values["id"]) if values.get("id") else ""))

        if tag == "script" and not values.get("src"):
            self.in_script = True
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.script.append(data)
        if self.in_style:
            self.style.append(data)


def check(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    scan = Scan()
    scan.feed(text)
    bad: list[str] = []
    warn: list[str] = []

    dupes = sorted({i for i, n in collections.Counter(scan.ids).items() if n > 1})
    if dupes:
        bad.append(f"중복 id: {', '.join(dupes)}")

    seen = set(scan.ids)
    missing = sorted({a for a in scan.anchors if a and a not in seen})
    if missing:
        bad.append(f"대상 없는 내부 앵커: {', '.join(missing)}")

    css = " ".join(scan.style)
    for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", css):
        if is_remote(url.strip()):
            scan.external.append(url.strip())
    if scan.external:
        bad.append(f"외부 리소스(웹폰트 제외): {', '.join(sorted(set(scan.external))[:5])}")

    left = re.findall(r"\[\[[^\]\n]{1,60}\]\]|__PLACEHOLDER__|\bLorem ipsum\b", text)
    if left:
        bad.append(f"남은 플레이스홀더: {', '.join(sorted(set(left))[:5])}")

    if scan.dead_clicks:
        bad.append(
            "button 이 아닌 것에 클릭을 달았다 — 키보드로 닿지 않는다: "
            + ", ".join(sorted(set(scan.dead_clicks))[:5])
        )

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

    descs = re.findall(r"\bdesc\s*:\s*((?:\"(?:[^\"\\]|\\.)*\"\s*\+?\s*)+)", text)
    over = []
    for index, raw in enumerate(descs, 1):
        joined = "".join(re.findall(r"\"((?:[^\"\\]|\\.)*)\"", raw))
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", joined)).strip()
        # 목표는 280자(2절 ③). 여기서 거는 선은 레퍼런스 예제의 실제 천장이다 —
        # 더 조이면 잘 쓴 explainer 까지 걸려 경고 자체를 무시하게 된다.
        if len(plain) > 360:
            over.append(f"{index}단계 {len(plain)}자")
    if over:
        warn.append(
            "내레이션이 길다 (목표 280자) — " + ", ".join(over)
            + " · 리드 한 줄 + 불렛 2~4개로 접고, 지울 것은 조작이 이미 보여주는 문장이다."
            + " 아까운 내용은 terms 나 판정 문장으로 옮긴다 (SKILL.md 2절 ③)"
        )

    if scan.buttons and not scan.aria_live:
        warn.append("aria-live 자리가 없다 — 조작 결과를 말해 주는 판정 문장에 붙었는지 확인한다")
    if "aria-pressed" not in text and scan.buttons > 2:
        warn.append("aria-pressed 가 없다 — 되돌릴 수 있는 토글 버튼이 있으면 붙인다")

    return bad, warn


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용법: check_explainer.py <파일.html>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2

    problems, warnings = check(path)
    if problems:
        print(f"FAIL  {path}  ({len(problems)}건)")
        for item in problems:
            print(f"  - {item}")
    else:
        print(f"OK    {path}  — 정적 검사 통과. 눈으로 볼 것은 SKILL.md 6절.")
    for item in warnings:
        print(f"  ? {item}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
