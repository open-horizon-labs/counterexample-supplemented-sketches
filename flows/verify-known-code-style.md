# Verify Known-Code Style

Use this flow after implementation to check the method contract: local result shape, pure-function behavior, counterexample coverage, and a failing naive parser.

## Verify

- Uses the shared result shape.
- Avoids validation exceptions.
- Preserves pure-function behavior.
- Covers every counterexample with a test.
- Fails a naive happy-path-only parser.

## Output

Return pass/fail, missing counterexamples, known-code style deviations, and any tempting wrong patch still possible.
