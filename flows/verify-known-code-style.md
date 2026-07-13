# Verify Known-Code Style

Use this flow after implementation to check the method contract: local result shape,
pure-function behavior, regression coverage, and regenerability from the evolved sketch.

## Verify

- Uses the shared result shape.
- Avoids validation exceptions.
- Preserves pure-function behavior.
- Passes the curated regression corpus.
- Fails a naive happy-path-only parser.
- Can be regenerated from the sketch and known-code anchors without reading the full CE archive.

## Output

Return pass/fail, uncovered policy boundaries, known-code style deviations, any tempting wrong
patch still possible, and any behavior present in code but absent from the sketch.
