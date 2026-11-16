"""Commit message and Git Trailers parser."""

from __future__ import annotations

import re
from typing import Any

TRAILER_KEYS = {
    "issue": "issue",
    "task": "task",
    "why": "why",
    "what": "what",
    "executed-command": "executed_command",
    "verification": "verification",
}

_TRAILER_LINE_RE = re.compile(
    r"^(Issue|Task|Why|What|Executed-Command|Verification):\s*(.*)$",
    re.IGNORECASE,
)
_OPENSPEC_ID_RE = re.compile(r"\bS\d{2}-\d{2}(?:-\d{2})?\b")
_TEST_SUBJECT_RE = re.compile(r"^test(?:\([^)]+\))?!?:", re.IGNORECASE)


def extract_trailers(body: str) -> dict[str, str | None]:
    """Extract structured Git Trailers and metadata fields from commit body."""
    result: dict[str, str | None] = {field: None for field in TRAILER_KEYS.values()}
    if not body:
        return result

    for raw_line in body.splitlines():
        match = _TRAILER_LINE_RE.match(raw_line.strip())
        if not match:
            continue
        raw_key = match.group(1).lower()
        value = match.group(2).strip()
        field_name = TRAILER_KEYS.get(raw_key)
        if field_name is not None:
            result[field_name] = value if value else None

    return result


def extract_task_ids(subject: str, body: str, trailers: dict[str, str | None]) -> list[str]:
    """Extract unique OpenSpec specification IDs (e.g. S01-03-02) preserving order."""
    sources = [trailers.get("task") or "", subject or "", body or ""]
    seen: set[str] = set()
    ids: list[str] = []
    for text in sources:
        for match in _OPENSPEC_ID_RE.findall(text):
            if match not in seen:
                seen.add(match)
                ids.append(match)
    return ids


def _is_test_file(path: str) -> bool:
    """Return True when the path appears to be a test file."""
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    return (
        lower.startswith("tests/")
        or "/tests/" in lower
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def classify_change_type(
    subject: str,
    body: str,
    trailers: dict[str, str | None],
    files: list[str] | None = None,
) -> str:
    """Classify commit change type into 'command', 'test', or 'manual'."""
    executed_command = trailers.get("executed_command")
    if executed_command:
        normalized = executed_command.strip().strip('"\'').lower()
        if normalized and normalized != "manual":
            return "command"

    if _TEST_SUBJECT_RE.match((subject or "").strip()):
        return "test"

    if files:
        non_empty_files = [path for path in files if path]
        if non_empty_files and all(_is_test_file(path) for path in non_empty_files):
            return "test"

    return "manual"


def parse_commit_metadata(
    subject: str,
    body: str,
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Parse trailers, OpenSpec task IDs, and change classification from a commit."""
    trailers = extract_trailers(body)
    task_ids = extract_task_ids(subject, body, trailers)
    change_type = classify_change_type(subject, body, trailers, files=files)
    return {
        "trailers": trailers,
        "task_ids": task_ids,
        "change_type": change_type,
    }
