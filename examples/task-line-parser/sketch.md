# Sketch: Task Line Parser

This sketch is the method input for the clean-room parser example. It gives the coding agent the intended shape while the companion counterexamples name plausible wrong implementations.

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
- For `todo` and `done`, `|` stays in title text; only `blocked` uses it as a reason separator.
- `blocked` requires `|` and a non-empty reason after it.
- Empty titles reject.
- Unknown statuses reject.
- Return explicit result objects from `known_code/result.py`; validation errors return `Err`.
- Keep the implementation dependency-free and pure.
