# Implement From Sketch

Use this flow to implement the method from a sketch: preserve local code style, satisfy the counterexamples, and verify that tempting wrong patches fail.

## Inputs

Read:

1. the sketch;
2. known-code anchors;
3. counterexamples;
4. existing tests if present.

## Rules

- Preserve known-code style.
- Prefer explicit branches over clever parsing.
- Keep the implementation dependency-free.
- Return validation errors the way known code does.
- Implement only sketched behavior.
- Add tests for every counterexample.
- If the sketch is ambiguous, choose the behavior required by the counterexamples.

## Output

Produce implementation, tests, and a note naming which counterexample defeats which tempting wrong patch.
