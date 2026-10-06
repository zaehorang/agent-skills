"""harness-backlog 스크립트들이 함께 쓰는 것: 경로, 항목 형식, 비밀정보 검사, 원자적 쓰기, ledger.

표준 라이브러리만 쓴다. 다른 스크립트는 같은 디렉터리에서 `import hb`로 불러온다.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

BACKLOG_REL = Path("history/harness-backlog")
RESOLVED = "_resolved"
TYPES = ("knowledge", "correction", "guard", "structure", "removal")
RESOLVED_STATUSES = ("applied", "rejected", "merged")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REF_RE = re.compile(r"^(claude|codex):[A-Za-z0-9._-]+#\S+$|^weekly:\d{4}-W\d{2}$")

# 항목 frontmatter 순서. 값은 모두 JSON 표기로 쓴다 (YAML로도 읽힌다).
FRONT_KEYS = (
    "date", "time", "title", "type", "target", "source", "ref",
    "relates", "session_model", "reviewer_model", "status",
)
SECTIONS = ("내용", "근거", "기존 하네스")

SECRET_PATTERNS = {
    "개인키": re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----"),
    "AWS 액세스 키": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub 토큰": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "API 키(sk-)": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "Bearer 토큰": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "Slack 토큰": re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    "결제 키(sk_live)": re.compile(r"\b[rs]k_live_[A-Za-z0-9]{16,}"),
    "Google API 키": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "이름 붙은 자격증명": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"
    ),
}

DEFAULT_CONFIG = {
    # 어떤 에이전트의 세션을 누가 검토하나. 세션을 진행한 쪽과 다른 쪽을 고른다.
    "reviewers": {
        "claude": {"cli": "codex", "model": "", "effort": "medium"},
        "codex": {"cli": "claude", "model": "claude-sonnet-5-5"},
    },
    # 여러 세션을 종합하는 주간 검토는 모델 하나가 맡는다.
    "weekly": {"cli": "claude", "model": "claude-opus-5-5"},
    "cli_paths": {"claude": "", "codex": ""},
    "max_candidates": 3,
    "exploration": {"same_file_reads": 3, "read_lines": 300, "searches": 5},
}


class BacklogError(Exception):
    """사용자에게 그대로 보여줄 수 있는 실패. 비밀값은 담지 않는다."""


# ---------------------------------------------------------------- 경로

def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out) if out else None


def resolve_project(project: str | None) -> Path:
    if project:
        p = Path(project).expanduser().resolve()
        if not p.is_dir():
            raise BacklogError(f"프로젝트 디렉터리가 없다: {p}")
        return p
    root = git_root(Path.cwd())
    if root is None:
        raise BacklogError("git 저장소가 아니다. --project 로 프로젝트 경로를 지정한다.")
    return root


def backlog_dir(project: Path) -> Path:
    return project / BACKLOG_REL


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(project: Path) -> dict:
    """기본값 위에 프로젝트 값을 깊게 덮는다. 일부 키만 적어도 나머지 기본값이 남는다."""
    path = backlog_dir(project) / "config.json"
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise BacklogError(f"config.json 이 올바른 JSON이 아니다 ({e.lineno}행)")
        if isinstance(user, dict):
            _merge(cfg, user)
    return cfg


# ---------------------------------------------------------------- 시간

def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def iso(t: dt.datetime) -> str:
    return t.isoformat(timespec="seconds")


def parse_time(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.astimezone()


def iso_week(t: dt.datetime) -> str:
    y, w, _ = t.isocalendar()
    return f"{y}-W{w:02d}"


# ---------------------------------------------------------------- 비밀정보

def scan_secrets(*texts: str) -> list[str]:
    """걸린 유형 이름만 돌려준다. 값은 절대 돌려주지 않는다."""
    hits = []
    for name, pat in SECRET_PATTERNS.items():
        if any(pat.search(t or "") for t in texts):
            hits.append(name)
    return hits


def redact(text: str) -> str:
    """세션 기록을 다른 모델에 보내기 전에 비밀정보로 보이는 값을 가린다."""
    for name, pat in SECRET_PATTERNS.items():
        text = pat.sub(f"[가림: {name}]", text)
    return text


# ---------------------------------------------------------------- 항목 형식

SECTION_HEAD_RE = re.compile(r"^## ", re.M)


def safe_body(body: str) -> str:
    """본문 안의 '## ' 줄은 섹션 경계와 헷갈리므로 한 단계 내린다."""
    return SECTION_HEAD_RE.sub("### ", body.strip())


def render_item(front: dict, sections: dict) -> str:
    lines = ["---"]
    for k in FRONT_KEYS:
        if k in front and front[k] not in (None, [], ""):
            lines.append(f"{k}: {json.dumps(front[k], ensure_ascii=False)}")
    lines.append("---")
    for name, body in sections.items():
        lines += ["", f"## {name}", safe_body(body)]
    return "\n".join(lines) + "\n"


def parse_item(text: str) -> tuple[dict, dict]:
    """render_item이 만든 고정 형식만 읽는다. 범용 YAML 파서가 아니다."""
    if not text.startswith("---\n"):
        raise BacklogError("frontmatter가 없다")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise BacklogError("frontmatter가 닫히지 않았다")
    front = {}
    for line in text[4:end].splitlines():
        key, sep, raw = line.partition(": ")
        if not sep:
            raise BacklogError(f"frontmatter 줄 형식이 틀렸다: {line[:40]}")
        try:
            front[key] = json.loads(raw)
        except json.JSONDecodeError:
            front[key] = raw  # 사람이 손으로 고친 따옴표 없는 값
    sections, cur = {}, None
    for line in text[end + 5:].splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)
    return front, {k: "\n".join(v).strip() for k, v in sections.items()}


def read_item(path: Path) -> tuple[dict, dict]:
    return parse_item(path.read_text(encoding="utf-8"))


def iter_items(bdir: Path, resolved: bool = False):
    d = bdir / RESOLVED if resolved else bdir
    if not d.is_dir():
        return
    for p in sorted(d.glob("*.md")):
        if p.name.startswith("."):
            continue
        try:
            front, sections = read_item(p)
        except BacklogError:
            continue
        yield p, front, sections


# ---------------------------------------------------------------- 원자적 쓰기

def publish(path: Path, text: str, *, overwrite: bool = False, verify=None) -> None:
    """같은 디렉터리의 임시 파일에 쓰고, 다시 읽어 검증한 뒤 발행한다.

    overwrite=False면 os.link로 발행해 이미 있는 파일을 덮지 않는다.
    어느 단계에서 실패해도 반쪽짜리 최종 파일은 남지 않는다.
    """
    if overwrite and path.is_symlink():
        path = path.resolve()  # 링크(AGENTS.md → CLAUDE.md 등)를 끊지 않고 가리키는 파일에 쓴다
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=path.parent)
    try:
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, path.stat().st_mode & 0o777 if path.exists() else 0o666 & ~umask)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if verify is not None:
            verify(Path(tmp).read_text(encoding="utf-8"))
        if overwrite:
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)
            except FileExistsError:
                raise BacklogError(f"이미 있는 파일이라 덮어쓰지 않는다: {path.name}")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- ledger

def ledger_path(project: Path) -> Path:
    return backlog_dir(project) / "ledger.jsonl"


def ledger_append(project: Path, entry: dict) -> None:
    entry = {"at": iso(now()), **entry}
    path = ledger_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ledger_read(project: Path) -> list[dict]:
    path = ledger_path(project)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def ledger_baseline(entries: list[dict]) -> dt.datetime | None:
    for e in entries:
        if e.get("kind") == "setup" and e.get("baseline"):
            return parse_time(e["baseline"])
    return None


def reviewed_upto(entries: list[dict]) -> dict[str, float]:
    """세션마다 어디까지(턴 수) 검토했나. 검토 실패나 검토자 부재는 세지 않는다 — 다음에 다시 시도한다.

    세션은 끝난 뒤에도 이어질 수 있다(진행 중에 요청 검토, resume). 그래서 "검토함"이 아니라
    "몇 턴까지 검토함"을 남기고, 다음 검토는 그 뒤의 턴만 본다. turns 가 없는 옛 기록은 끝까지 본 것으로 친다.
    """
    upto: dict[str, float] = {}
    for e in entries:
        if e.get("kind") == "session" and e.get("session") and e.get("status") in ("reviewed", "skipped"):
            n = e.get("turns", float("inf"))
            upto[e["session"]] = max(upto.get(e["session"], 0), n)
    return upto


def unfinished_sessions(entries: list[dict]) -> set[str]:
    """훅이 검토를 띄웠는데(queued) 결과가 남지 않은 세션. 검토 프로세스가 죽었다는 신호다."""
    queued, finished = set(), set()
    for e in entries:
        if e.get("kind") != "session" or not e.get("session"):
            continue
        (queued if e.get("status") == "queued" else finished).add(e["session"])
    return queued - finished
