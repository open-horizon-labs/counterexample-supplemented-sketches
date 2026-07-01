from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from known_code.result import Err, Ok, ParseResult, err, ok


@dataclass(frozen=True)
class TaskRecord:
    status: str
    title: str
    reason: str | None = None


SUPPORTED_STATUSES = {"todo", "done", "blocked"}


def parse_task_line(line: str) -> ParseResult[TaskRecord]:
    if not isinstance(line, str):
        return err("invalid_type", "Task line must be a string.")

    raw = line.strip()
    if not raw:
        return err("empty_line", "Task line cannot be empty.")

    status, separator, remainder = raw.partition(":")
    if not separator:
        return err("missing_status", "Task line must start with '<status>:'")

    status = status.strip().lower()
    if status not in SUPPORTED_STATUSES:
        return err("unknown_status", f"Unsupported task status: {status}")

    body = remainder.strip()
    if not body:
        return err("empty_title", "Task title cannot be empty.")

    if status != "blocked":
        return ok(TaskRecord(status=status, title=body, reason=None))

    title, pipe, reason = body.partition("|")
    if not pipe:
        return err("missing_reason", "Blocked tasks require a reason after '|'.")

    title = title.strip()
    reason = reason.strip()
    if not title:
        return err("empty_title", "Task title cannot be empty.")
    if not reason:
        return err("empty_reason", "Blocked tasks require a non-empty reason after '|'.")

    return ok(TaskRecord(status=status, title=title, reason=reason))
