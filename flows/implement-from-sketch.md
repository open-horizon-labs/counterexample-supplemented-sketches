# Implement From Sketch

Use this flow to generate a replaceable implementation from the current evolved sketch. The
sketch is the policy source. The regression corpus checks the result; it does not supply missing
policy.

## Inputs

Read:

1. the sketch;
2. known-code anchors;
3. the curated regression corpus;
4. existing tests if present.

## Rules

- Preserve known-code style.
- Prefer explicit branches over clever parsing.
- Keep the implementation dependency-free.
- Return validation errors the way known code does.
- Implement only sketched behavior.
- Do not infer unstated policy from the CE archive or regression cases.
- If a regression case requires behavior the sketch does not state, stop and request a sketch
  revision through the operator-approved CE process before implementing it.
- Keep the regression corpus small enough to run routinely and strong enough to reject known
  tempting patches.

## Output

Produce the implementation and a gate report over the regression corpus. Name any behavior that
could not be regenerated from the sketch alone.
