# Verification

Run:

```bash
python3 -m unittest discover -s sketch-counterexample-agent/examples/task-line-parser/tests
```

The test suite must prove the finite parser example:

- happy paths parse;
- counterexamples fail tempting wrong patches;
- implementation uses the known-code `Ok` / `Err` result shape;
- validation errors return `Err`.

Adversarial check:

A naive implementation that splits on every colon, treats `|` as a reason for all statuses, or accepts empty blocked reasons must fail the tests.
