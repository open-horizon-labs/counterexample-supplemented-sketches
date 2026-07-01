# Repair From Counterexample

A generated implementation failed or would fail a counterexample.

## Inputs

Read:

1. current implementation;
2. failing counterexample;
3. known-code anchors;
4. existing tests.

## Task

Repair the implementation so the counterexample fails the tempting wrong patch and passes the intended behavior.

## Rules

- Do not weaken the counterexample.
- Do not special-case only the exact string when the sketch describes a broader rule.
- Preserve known-code style.
- Add or update the smallest test that proves the rule.

## Output

Produce the code change, test change, and the tempting wrong patch now rejected.
