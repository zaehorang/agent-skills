#!/usr/bin/env python3
"""Validate a blog-review raw manifest and write deterministic JSONL."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_KINDS = {"source", "understanding", "thought", "question", "request"}
REVIEW_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
REDACTION_MARKER_PATTERN = re.compile(r"\[REDACTED:\s*[^\]\r\n]+\]")
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "named credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)


class RawDataError(ValueError):
    """Raised when the manifest or its target paths violate the raw-data contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a blog-review raw manifest and atomically create JSONL."
    )
    parser.add_argument("--review", required=True, type=Path, help="Review Markdown path")
    parser.add_argument("--input", required=True, type=Path, help="Raw manifest JSON path")
    parser.add_argument("--output", required=True, type=Path, help="Destination JSONL path")
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RawDataError(f"manifest does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RawDataError(f"cannot read manifest as UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RawDataError("manifest root must be a JSON object")
    unknown = set(value) - {"review_id", "entries"}
    if unknown:
        raise RawDataError(f"unknown manifest fields: {', '.join(sorted(unknown))}")
    return value


def validate_paths(review: Path, output: Path, review_id: str) -> None:
    if not review.is_file() or review.suffix != ".md":
        raise RawDataError(f"review must be an existing Markdown file: {review}")
    if review.stem != review_id:
        raise RawDataError(
            f"review filename does not match review_id: {review.stem!r} != {review_id!r}"
        )
    if output.suffix != ".jsonl" or output.stem != review_id:
        raise RawDataError("output must be named <review_id>.jsonl")
    if output.parent.name != "raw":
        raise RawDataError("output must be inside a directory named raw")
    if output.exists():
        raise RawDataError(f"refusing to overwrite existing raw file: {output}")

    expected_raw = f"../raw/{review_id}.jsonl"
    review_text = review.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", review_text, re.DOTALL)
    if not frontmatter_match:
        raise RawDataError("review must start with YAML frontmatter")
    raw_matches = re.findall(
        r"(?m)^raw:\s*([^\s#]+)\s*(?:#.*)?$", frontmatter_match.group(1)
    )
    if raw_matches != [expected_raw]:
        raise RawDataError(
            f"review frontmatter must contain exactly: raw: {expected_raw}"
        )


def find_secret(text: str) -> str | None:
    visible_text = REDACTION_MARKER_PATTERN.sub("", text)
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(visible_text):
            return label
    return None


def validate_entries(review_id: str, entries: Any) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise RawDataError("entries must be a non-empty array")

    records: list[dict[str, Any]] = []
    allowed_fields = {"kinds", "text", "redacted", "redaction_types"}
    for sequence, entry in enumerate(entries, start=1):
        prefix = f"entries[{sequence - 1}]"
        if not isinstance(entry, dict):
            raise RawDataError(f"{prefix} must be an object")
        unknown = set(entry) - allowed_fields
        if unknown:
            raise RawDataError(f"{prefix} has unknown fields: {', '.join(sorted(unknown))}")

        kinds = entry.get("kinds")
        if not isinstance(kinds, list) or not kinds:
            raise RawDataError(f"{prefix}.kinds must be a non-empty array")
        if any(not isinstance(kind, str) for kind in kinds):
            raise RawDataError(f"{prefix}.kinds must contain only strings")
        if len(kinds) != len(set(kinds)):
            raise RawDataError(f"{prefix}.kinds must not contain duplicates")
        invalid_kinds = set(kinds) - ALLOWED_KINDS
        if invalid_kinds:
            raise RawDataError(
                f"{prefix}.kinds contains invalid values: {', '.join(sorted(invalid_kinds))}"
            )

        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RawDataError(f"{prefix}.text must be a non-empty string")

        redacted = entry.get("redacted")
        if not isinstance(redacted, bool):
            raise RawDataError(f"{prefix}.redacted must be true or false")
        redaction_types = entry.get("redaction_types")
        if redacted:
            if (
                not isinstance(redaction_types, list)
                or not redaction_types
                or any(not isinstance(item, str) or not item.strip() for item in redaction_types)
            ):
                raise RawDataError(
                    f"{prefix}.redaction_types must be a non-empty string array when redacted"
                )
            if len(redaction_types) != len(set(redaction_types)):
                raise RawDataError(f"{prefix}.redaction_types must not contain duplicates")
            if not REDACTION_MARKER_PATTERN.search(text):
                raise RawDataError(f"{prefix}.text must contain a [REDACTED: type] marker")
        elif redaction_types is not None:
            raise RawDataError(f"{prefix}.redaction_types is only allowed when redacted is true")

        secret_label = find_secret(text)
        if secret_label:
            raise RawDataError(
                f"{prefix}.text contains a possible {secret_label}; replace only the secret "
                "with [REDACTED: credential] and set redaction metadata"
            )

        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "review_id": review_id,
            "sequence": sequence,
            "kinds": kinds,
            "text": text,
            "redacted": redacted,
        }
        if redacted:
            record["redaction_types"] = redaction_types
        records.append(record)
    return records


def write_jsonl_atomically(output: Path, records: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            for record in records:
                handle.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())

        # Parse the completed temporary file before it becomes the canonical raw artifact.
        parsed = [json.loads(line) for line in temporary_path.read_text(encoding="utf-8").splitlines()]
        if parsed != records:
            raise RawDataError("generated JSONL failed its round-trip validation")
        try:
            # A hard link publishes the completed file atomically and fails if the
            # destination appeared after the earlier existence check.
            os.link(temporary_path, output)
        except FileExistsError as exc:
            raise RawDataError(f"refusing to overwrite existing raw file: {output}") from exc
        temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.input)
        review_id = manifest.get("review_id")
        if not isinstance(review_id, str) or not REVIEW_ID_PATTERN.fullmatch(review_id):
            raise RawDataError(
                "review_id must be YYYY-MM-DD followed by lowercase kebab-case words"
            )
        validate_paths(args.review, args.output, review_id)
        records = validate_entries(review_id, manifest.get("entries"))
        write_jsonl_atomically(args.output, records)
    except (OSError, UnicodeError, RawDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(records)} raw entries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
