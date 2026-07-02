# Repair From Counterexample

Use this flow when an implementation failed, or would fail, a counterexample.

## Inputs

Read:

1. current implementation;
2. failing counterexample;
3. known-code anchors;
4. existing tests.

## Task

Repair the implementation so the tempting wrong patch fails and the intended behavior passes.

## Rules

- Keep the counterexample strict.
- Repair the broader rule when the sketch describes one; avoid exact-string special cases.
- Preserve known-code style.
- Add or update the smallest test that proves the rule.

## Output

Produce the code change, test change, and the tempting wrong patch now rejected.
