# arXiv submission metadata

All metadata below is ASCII and ready to paste into arXiv. Eric Rubeck's affiliation is
intentionally omitted until he confirms it.

## Classification and license

- Primary category: `cs.SE` (Software Engineering)
- Cross-list: `cs.AI` (Artificial Intelligence)
- License: Creative Commons Attribution 4.0 International (`CC BY 4.0`)
- Report number: leave blank
- Journal reference: leave blank
- DOI: leave blank

## Title

Agentic Synthesis against Counterexample-Supplemented Sketches

## Authors

Muness Castle (Independent), Eric Rubeck

Corresponding author: Muness Castle, muness@muness.com

## Abstract

Coding agents can fix a failing example without preserving the domain rule that made it fail.
We present agentic synthesis against counterexample-supplemented sketches, a repository-native
method for systems whose policy is discovered during implementation. A human starts with a
partial sketch, and a coding agent compiles a replaceable projection. When simulation exposes
missing or mistaken policy, an operator approves the corrected behavior and the minimum general
rule the case authorizes. Every Developer call names its change authority and the rules, holes,
anchors, and approved behavior that must survive. Conflict or ambiguous permission leaves the
files unchanged and produces a clarification question. A complete archive preserves provenance;
a curated regression set gates distinct
boundaries. Before another candidate is revealed, the active case and curated regressions must
pass both deterministic approved-output comparison and a separate review against the current
sketch. Periodic clean regeneration tests whether the sketch carries the learned policy.

We demonstrate the method with CatSynth, a captured synthetic application. In one open-world run
with GPT-5.4-mini, 8 of 14 frozen candidates
became counterexamples. Under the corrected protocol, replay-all, evolved-sketch rebuild, and
retained Sketch-CE each passed all 8 accepted cases. They passed 14, 17, and 16 of 21 withheld
cases, respectively. Sketch review rejected premature empty-input and tag policies and restored
dropped anchors; adjudicated reviewer errors did not become policy. One model and one reveal
order cannot establish general correctness or superiority. On this suite, the second check
exposed drift hidden by deterministic replay, and the reviewed sketch passed three more withheld
cases than raw example replay.

## Comments

36 pages, 5 displayed figures (4 distinct screenshots). Includes the CatSynth artifact
supplement. Code and captured experiment artifacts:
https://github.com/open-horizon-labs/counterexample-supplemented-sketches

For an arXiv replacement, append this revision description to the existing comments:

`Clarifies the two-check CESS method and Developer change authority; adds the protocol-correct
CatSynth rerun and replaces the prior withheld-case headline. Results are now 14/21 for
replay-all, 17/21 for evolved-sketch rebuild, and 16/21 for retained Sketch-CE.`

## Before final submission

- Confirm Eric Rubeck's consent, affiliation, and approval of the CC BY 4.0 license.
- Link the submitting author's ORCID to the arXiv account.
- Obtain `cs.SE` endorsement if arXiv requests it.
- Build `dist/agentic-synthesis-arxiv-source.zip` with `make -C paper arxiv-source`.
- Inspect arXiv's compiled PDF before selecting **Submit Article**.
