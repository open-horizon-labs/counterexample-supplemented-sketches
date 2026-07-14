# Repair From Counterexample

Use this flow only after an operator has explicitly approved a proposed counterexample that
exposes a missing or mistaken rule in the current sketch. If the sketch already states the
correct rule, use an ordinary regression repair instead; the failure is not a new
counterexample.

## Inputs

Read:

1. current sketch;
2. the active counterexample, operator approval, and authoritative correction;
3. current implementation, if retaining it for this cycle;
4. known-code anchors;
5. the curated regression corpus.

## Task

Revise the sketch to state the general rule exposed by the counterexample. Then repair or
regenerate the implementation under that revised sketch.

## Rules

- Keep the counterexample strict.
- Do not let Developer accept its own counterexample or authorize its own policy change.
- Change the sketch for every accepted counterexample; a CE that produces no sketch change has
  been misclassified or incompletely reviewed.
- State the broader rule; do not paste the concrete row into the sketch.
- Preserve known-code style.
- Run the active counterexample and the current regression corpus.
- Recommend whether the active case, or a smaller equivalent case, belongs in the durable
  regression subset. Preserve the complete case in the CE archive either way.

## Output

Produce the revised sketch for operator review, the repaired or regenerated implementation, the
gate result, the regression-subset recommendation, and the tempting wrong patch now rejected.
