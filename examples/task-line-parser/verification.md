# Verification

Run:

```bash
python3 -m unittest discover -s sketch-counterexample-agent/examples/task-line-parser/tests
```

Regenerate `generated/parse_task_line.py` from `sketch.md` and the known-code anchors without
using `counterexamples.md` as generation context. Then run the test suite. It must establish the
finite parser example:

- happy paths parse;
- counterexamples fail tempting wrong patches;
- implementation uses the known-code `Ok` / `Err` result shape;
- validation errors return `Err`.

Adversarial check:

A naive implementation that splits on every colon, treats `|` as a reason for all statuses, or accepts empty blocked reasons must fail the tests.

This small example retains one regression for every archived CE because the four cases protect
different rules. Larger systems may keep a smaller discriminating regression subset while
preserving the complete CE archive as provenance.
