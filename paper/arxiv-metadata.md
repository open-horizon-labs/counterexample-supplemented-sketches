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

Coding agents can fix a failing example without preserving the domain rule that made it fail, so
later generations can repeat the same plausible mistake. We present agentic synthesis against
counterexample-supplemented sketches, a repository-native method for systems whose governing
policy is discovered during implementation. A human starts with a partial, code-shaped sketch,
and a coding agent generates the first implementation. When a concrete failure exposes missing
or mistaken policy, an operator explicitly approves the corrected behavior and rule. The agent
then revises the sketch and repairs or regenerates code and prompt surfaces for that one
counterexample. The full archive preserves provenance; a selected regression set gates each
revision before the next candidate is revealed; and periodic clean regeneration tests whether
the evolved sketch, rather than prompt history or accumulated examples, carries the learned
policy.

We demonstrate the method with CatSynth, a synthetic browser application and captured
coding-agent experiment. In one open-world run with GPT-5.4-mini, 8 of 14 frozen candidate cases
became counterexamples. The rebuild controls inherited that promotion schedule, and all three
paths passed the 8 accepted cases. Rebuilding from the evolved sketch passed 19 of 21 withheld
cases, compared with 15 of 21 when rebuilding from the initial sketch and replaying all accepted
examples. Retaining code across counterexamples required 9 Developer calls and 719 lines of
cumulative artifact churn, versus 15 calls and 2,394 lines for replay-all, and passed 18 of 21
withheld cases. These results provide inspectable evidence that the evolved sketch carried
reviewed policy and that retaining code reduced rework in this run; with one model and one reveal
order, they do not establish general superiority or correctness beyond the encoded checks.

## Comments

32 pages, 5 displayed figures (4 distinct screenshots). Includes the CatSynth artifact
supplement. Code and captured experiment artifacts:
https://github.com/open-horizon-labs/counterexample-supplemented-sketches

## Before final submission

- Confirm Eric Rubeck's consent, affiliation, and approval of the CC BY 4.0 license.
- Link the submitting author's ORCID to the arXiv account.
- Obtain `cs.SE` endorsement if arXiv requests it.
- Build `dist/agentic-synthesis-arxiv-source.zip` with `make -C paper arxiv-source`.
- Inspect arXiv's compiled PDF before selecting **Submit Article**.
