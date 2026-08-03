---
name: cess
description: Apply Counterexample-Supplemented Sketches (CESS) to open-world agent and software synthesis. Use when a user mentions CESS, Sketch-CE, counterexample-supplemented sketches, evolved sketches, compiled projections, simulation-driven correction, or asks to make an agent-generated system improve from reviewed failures without losing earlier behavior.
---

# Counterexample-Supplemented Sketches

Treat CESS as a two-level synthesis and evaluation method. Evolve the user-governed sketch; compile it into a replaceable projection; discover failures in simulation; promote approved failures into counterexamples; and require the active case plus curated regressions to pass both deterministic checks and review against the current sketch.

## Preserve the Core Contract

Keep these artifacts and roles distinct:

| Symbol | Artifact or role | Responsibility |
|---|---|---|
| `S` | Sketch | State the user-governed behavior, policy order, interfaces, known rules, and explicit holes. |
| `K` | Anchors | Preserve fixed repository interfaces, types, protocols, and environmental constraints. |
| `P` | Compiled projection | Implement `S + K` as replaceable code, prompts, configuration, or other executable surfaces. Some CESS material calls this `H`. |
| `A` | Accepted-CE archive | Preserve every approved failure, correction, policy change, and provenance record. |
| `R ⊆ A` | Regression set | Retain curated cases that reject distinct known wrong implementations. |
| `G` | Deterministic gate | Run replay and approved-output compare over the active case and `R`. |

Apply this acceptance rule to the active case and curated regression set `R`:

```text
accepted(case, P, S) = gate_passes(case, P)
                       AND sketch_review_passes(case, P, S)
```

Treat a missing deterministic encoding as an explicit gap, not as a pass. Do not let either check substitute for the other.

Call deterministic comparison with approved fields **approved-output compare**. Reserve **sketch review** for a capable model and/or user comparing simulated output with `S`.

## Use CE Authority Precisely

An approved, active CE authorizes the smallest general sketch rule required by its corrected output and approved clause. The rule is not an invention merely because it was absent from the prior sketch. That is how an open-world sketch learns.

Do not stretch that authority:

- preserve earlier approved rules and anchors;
- add consequences required by the active CE;
- keep neighboring outcomes open when the CE does not settle them;
- when no approved CE is active, preserve existing holes rather than filling them;
- do not use a later CE to justify an earlier proposal retroactively;
- treat a reviewer calculation or classification error as an adjudication issue, not as authority to change policy.

Sketch review asks whether an output follows the current sketch. Sketch-change approval asks whether proposed policy wording is authorized. An adjudication of the first decision cannot silently grant the second.

Give the Developer an explicit change contract on every call, including initial compilation. Name the exact authority for any sketch change, every current rule and hole it must preserve, the approved behavior that must not regress, and the stable projection contracts. If these sources conflict or leave the permitted change ambiguous, require the Developer to return the files unchanged and ask the policy authority one precise question. Never let the Developer resolve an authority conflict by inference.

## Run One CESS Cycle

1. **Locate the authority.** Identify `S`, `K`, `P`, `A`, `R`, `G`, the simulator, and whoever may approve policy changes. Create an artifact register when the repository does not make them obvious. Read [references/working-forms.md](references/working-forms.md) for reusable forms.
2. **Compile the projection.** Generate or regenerate `P` from `S + K`. Give the Developer the explicit change contract above. Treat the projection as disposable; do not infer the governing policy from the current code when it conflicts with the sketch.
3. **Simulate one concrete case.** Run `P`, preserve its input, output, and relevant trace, and have a capable model and/or user compare that behavior with `S`.
4. **Classify the failure before editing.** If `S` already states the right rule, record an implementation defect and repair or regenerate `P` without changing policy. If the case exposes a missing, mistaken, or ambiguous rule in `S`, propose a counterexample.
5. **Review the proposed CE.** Record the concrete input, actual output, corrected output or behavior, violated or missing sketch rule, generalized policy change, and tempting wrong repair. First decide whether the output follows `S`; only then decide whether to repair `P` or approve a change to `S`. The same reviewer may make both decisions when authorized.
6. **Evolve the sketch.** For an approved CE, revise `S` so the correction follows as a general rule rather than as a case-specific fixture. Add the minimum general rule entailed by the corrected output and approved clause, even when it was absent from the prior sketch. Keep adjacent policy choices as explicit holes or return them to the authority. Review the sketch change against the approved correction.
7. **Make the learning executable.** Add a deterministic check that fails the tempting wrong repair, or link the CE to an existing regression that already protects the same boundary. The active case always runs during its cycle; it enters `R` only when it adds distinct protection.
8. **Recompile and validate twice.** Repair or regenerate `P` from the revised `S + K`. Run the active case and `R` through `G`. Run those same cases in simulation and compare each output with the current `S`.
9. **Keep one failure active.** If either check fails, make that case the next active failure and repeat. Do not introduce another candidate case until both checks pass for the active case and `R`.
10. **Curate regressions.** After both checks pass, add the active CE to `R` only when existing regressions do not protect its boundary. Keep every approved CE in `A`.
11. **Test sketch sufficiency.** Periodically discard `P`, regenerate it from `S + K` without supplying `A` as bulk prompt context, and run `R` through both checks. If regeneration needs the archive to recover policy, strengthen the sketch.

## Reject Common Compressions

Do not reduce CESS to any of these patterns:

- an example archive plus unit tests;
- reflection or memory plumbing around a fixed implementation;
- a model that may suggest failures but cannot review simulated output against the sketch;
- an exact-output gate mislabeled as the only semantic evaluation;
- patching `P` while leaving a deficient `S` unchanged;
- editing `S` for an implementation bug when `S` already states the correct rule;
- smuggling an unapproved adjacent policy choice into `S` while generalizing a CE;
- passing only the newest CE while skipping `R` in either check;
- running every archived CE forever instead of curating `R`;
- replaying the full CE archive as generation context instead of making `S` carry the learned policy;
- treating a green finite corpus as proof for unseen cases.

## Report the Cycle

Return or update a cycle report containing:

- the active case and its classification;
- the sketch clause before and after the change;
- the projection surfaces rebuilt or repaired;
- the deterministic regression added, or the explicit reason it cannot be encoded;
- deterministic results for the active case and `R`;
- sketch-review results for the active case and `R`;
- the tempting wrong repair and evidence that it still fails;
- the approval authority and decision;
- the CE evidence that entails each new sketch rule, and any adjacent choices left open;
- the next active failure, or the bounded acceptance claim.

Do not announce completion from deterministic tests alone. State only what the exercised corpus and current reviewers establish.

## Self-Check Before Handoff

Verify that the work has one unambiguous answer to each question:

1. Which artifact is the user-governed sketch?
2. Which artifacts are compiled, replaceable projections?
3. Who or what judges simulated output against the sketch?
4. Was the failure an implementation defect or an approved sketch-changing CE?
5. What generalized sketch change and deterministic regression preserve the correction?
6. Did the active case and `R` pass both checks?
7. Can a fresh projection be generated from `S + K` without the CE archive as prompt context?

If any answer is missing or conflates artifacts, keep the cycle open.
