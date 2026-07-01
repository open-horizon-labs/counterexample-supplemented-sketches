# Verify Known-Code Style

Check whether the implementation follows the known-code anchors.

## Verify

- Uses the shared result shape.
- Avoids validation exceptions.
- Preserves pure-function behavior.
- Covers every counterexample with a test.
- Fails a naive happy-path-only parser.

## Output

Return pass/fail, missing counterexamples, known-code style deviations, and any tempting wrong patch still possible.
