# Extracted Paper: Sketch + Counterexample + Coding Agent

> This paper is generated from the clean-room session graph and source selectors. Do not treat it as canonical unless `tools/extract_session_graph.py --write` and this extractor both pass.

## Abstract

This artifact demonstrates one extracted claim: a coding-agent implementation is inspectable when every counterexample links to a source span, a verification check, and the execution point that handles it. The generated graph answers `how is this counterexample handled?` from repo-local evidence instead of independent prose.

## Source Sketch

Selector: `examples/task-line-parser/sketch.md`

```md
# Sketch: Task Line Parser

Build a boring parser that converts one loose task line into a normalized task record.

Input shape:

```text
<status>: <title>
<status>: <title> | <reason>
```

Supported statuses:

- `todo`
- `done`
- `blocked`

Rules:

- The first colon selects the status; later colons belong to the title.
- `todo` and `done` do not parse `|` as a reason. Their whole body is title text.
- `blocked` requires `|` and a non-empty reason after it.
- Empty titles reject.
- Unknown statuses reject.
- Return explicit result objects from `known_code/result.py`; do not throw for validation errors.
- Keep the implementation dependency-free and pure.
```

## Known-Code Anchor

Selector: `examples/task-line-parser/known_code/result.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ParseError:
    code: str
    message: str


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True


@dataclass(frozen=True)
class Err:
    error: ParseError
    ok: bool = False


ParseResult = Ok[T] | Err


def ok(value: T) -> Ok[T]:
    return Ok(value=value)


def err(code: str, message: str) -> Err:
    return Err(error=ParseError(code=code, message=message))
```

## Generated Implementation

Selector: `examples/task-line-parser/generated/parse_task_line.py`

The implementation is not quoted in full here; each counterexample below links to the execution selectors that handle it.

## Extracted Counterexample Handling

### First prefix only is status

Counterexample selector: `examples/task-line-parser/counterexamples.md:5-20`

```md
## First prefix only is status

Input:

```text
done: blocked: deploy app
```

Tempting wrong patch: split on every colon and treat `blocked:` as a second status.

Expected:

```python
TaskRecord(status="done", title="blocked: deploy app", reason=None)
```
```

Tempting patch failed: split on every colon and treat a later status-looking prefix as a second status

Handled by execution points:
- `examples/task-line-parser/generated/parse_task_line.py:31-37` — `str.partition(':')` selects only the first colon; non-blocked bodies remain title text.
- `examples/task-line-parser/generated/parse_task_line.py:43-44` — `str.partition(':')` selects only the first colon; non-blocked bodies remain title text.

Verified by:
- `examples/task-line-parser/tests/test_parse_task_line.py:61-66`

```python
def test_only_first_colon_separates_status_from_title(self) -> None:
        self.assert_ok_record(
            "done: blocked: deploy app",
            status="done",
            title="blocked: deploy app",
        )
```

### Blocked reason cannot be empty

Counterexample selector: `examples/task-line-parser/counterexamples.md:21-32`

```md
## Blocked reason cannot be empty

Input:

```text
blocked: deploy app | 
```

Tempting wrong patch: accept an empty string as the reason.

Expected: `Err(code="empty_reason")`.
```

Tempting patch failed: accept a blank blocked reason after `|`

Handled by execution points:
- `examples/task-line-parser/generated/parse_task_line.py:46-55` — Blocked tasks partition on `|`, trim reason, and return `Err(empty_reason)` when it is blank.

Verified by:
- `examples/task-line-parser/tests/test_parse_task_line.py:82-90`

```python
def test_blocked_tasks_require_non_empty_reason_after_pipe(self) -> None:
        cases = [
            ("blocked: deploy app", "missing_reason"),
            ("blocked: deploy app | ", "empty_reason"),
        ]

        for line, expected_code in cases:
            with self.subTest(line=line):
                self.assert_err_code(line, expected_code)
```

### Empty title rejects

Counterexample selector: `examples/task-line-parser/counterexamples.md:33-44`

```md
## Empty title rejects

Input:

```text
todo:   
```

Tempting wrong patch: return an empty task.

Expected: `Err(code="empty_title")`.
```

Tempting patch failed: return an empty task title as a valid record

Handled by execution points:
- `examples/task-line-parser/generated/parse_task_line.py:39-41` — The parser rejects blank body text before status-specific handling and rejects blank blocked titles after `|` splitting.
- `examples/task-line-parser/generated/parse_task_line.py:50-53` — The parser rejects blank body text before status-specific handling and rejects blank blocked titles after `|` splitting.

Verified by:
- `examples/task-line-parser/tests/test_parse_task_line.py:103-112`

```python
def test_rejects_empty_titles_before_accepting_status_specific_syntax(self) -> None:
        cases = [
            ("todo:   ", "empty_title"),
            ("done:   ", "empty_title"),
            ("blocked: | waiting on credentials", "empty_title"),
        ]

        for line, expected_code in cases:
            with self.subTest(line=line):
                self.assert_err_code(line, expected_code)
```

### Pipe is only special for blocked

Counterexample selector: `examples/task-line-parser/counterexamples.md:45-59`

```md
## Pipe is only special for blocked

Input:

```text
done: deploy app | checked by Sam
```

Tempting wrong patch: parse `| checked by Sam` as a reason for every status.

Expected:

```python
TaskRecord(status="done", title="deploy app | checked by Sam", reason=None)
```
```

Tempting patch failed: parse `|` as a reason for todo/done statuses

Handled by execution points:
- `examples/task-line-parser/generated/parse_task_line.py:43-44` — The parser returns todo/done body text before pipe parsing; only blocked enters the pipe/reason branch.
- `examples/task-line-parser/generated/parse_task_line.py:46-57` — The parser returns todo/done body text before pipe parsing; only blocked enters the pipe/reason branch.

Verified by:
- `examples/task-line-parser/tests/test_parse_task_line.py:68-80`

```python
def test_pipe_is_title_text_for_unblocked_statuses(self) -> None:
        cases = [
            ("done: deploy app | checked by Sam", "done"),
            ("todo: deploy app | after code review", "todo"),
        ]

        for line, status in cases:
            with self.subTest(line=line):
                self.assert_ok_record(
                    line,
                    status=status,
                    title=line.split(":", 1)[1].strip(),
                )
```

## Extracted Claim

The graph supports a narrow claim: for this session, each counterexample has a source selector, a tempting patch, one or more execution selectors, and a verification selector. The paper's claims must not exceed that extracted evidence.

## Verification

Run:

```bash
python3 sketch-counterexample-agent/tools/extract_session_graph.py --write
python3 sketch-counterexample-agent/tools/extract_session_paper.py
python3 sketch-counterexample-agent/tools/extract_session_graph.py --ce first-prefix
python3 -m unittest discover -s sketch-counterexample-agent/examples/task-line-parser/tests
```
