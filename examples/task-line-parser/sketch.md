# Sketch: Task Line Parser

This is the evolved sketch for the clean-room parser example. Each accepted case in
`counterexamples.md` contributed a rule now stated here. A coding agent should be able to discard
the existing parser and regenerate it from this sketch plus the known-code result types. The
counterexample archive explains why the rules exist; the tests check the regenerated code.

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
