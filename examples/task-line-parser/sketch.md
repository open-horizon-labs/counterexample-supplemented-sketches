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
