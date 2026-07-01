# Agentic Synthesis against Counterexample-Supplemented Sketches

**Paper:** [`paper/main.tex`](paper/main.tex)  
**Bibliography:** [`paper/references.bib`](paper/references.bib)  
**Companion artifact:** runnable examples, fixtures, and provenance for the paper's claims.

This repository is a supporting document to the paper. The code is here so readers can inspect and run the examples behind the argument; it is not the headline and it is not a framework.

The paper argues for **agentic synthesis against counterexample-supplemented sketches**: a process for programming with coding agents under checkable rules. A human writes a partial program-like sketch, failures are promoted into a counterexample corpus, an agent edits code and prompts, and a replay/compare gate establishes finite-corpus correctness for the current promoted cases.

## Read first

Start with the paper:

- [`paper/main.tex`](paper/main.tex) — process paper with references, formal model, synthesis loop, and finite-corpus correctness theorem.
- [`paper/references.bib`](paper/references.bib) — references for sketching, CEGIS, program synthesis, programming-by-example, SWE-bench, and tests-as-prompts.

The RosterSynth kiosk material is a worked example inside the paper. It is not the name of the process and not the center of the repo.

## What this companion artifact supports

The paper's central executable claim is bounded:

> If the replay/compare gate passes every case in the promoted counterexample corpus `E`, then the current agent-produced artifact is correct for `E` under the repository's executable replay and compare semantics.

The repository supports that claim with:

| Artifact | Paper role |
|---|---|
| `examples/rostersynth-kiosk/source/docs/sketch.md` | Concrete sketch clauses for the worked example |
| `examples/rostersynth-kiosk/source/scenarios/*.json` | Corpus `E` and promoted counterexamples |
| `examples/rostersynth-kiosk/source/rostersynth/playbook.py` | Oracle A deterministic implementation |
| `examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py` | Oracle B prompt path |
| `examples/rostersynth-kiosk/source/cassettes/*.json` | Reproducible Oracle B cassette fixtures |
| `examples/rostersynth-kiosk/tests/test_extracted_rostersynth.py` | Executable checks for the paper's worked-example claims |
| `build/rostersynth-kiosk-graph.json` | Source/provenance graph for appendix-style inspection |
| `.oh/knowledge/rostersynth-kiosk/` | Repo-native node files for the same graph |

## Worked example: RosterSynth kiosk

The paper uses one concrete case to show why replay alone is not enough.

A roster has twin active 40-hour bookings on the pay-window end date. Badge hours are 40 and scheduled hours are 80, so a naive append of `-40h` closes the coverage math. That repair is replay-valid but semantically wrong. The correct repair cancels the duplicate booking with the higher `bookingId`.

The counterexample path is:

```text
roster.kiosk_double_booking.v1
→ sketch Op 2: cancel duplicate higher bookingId when it alone closes delta
→ historical failure: append -40h passes replay but fails compare
→ Oracle A: _try_cancel_duplicate emits modify bookingId=1802 status=4
→ Oracle B prompt/cassette path states the same rule
→ wrong cassette bookingId=1801 passes replay but fails compare
→ gate passes after sketch/code/prompt alignment
```

That path is evidence for the paper's method, not the method itself.

## Reproduce the paper artifact

From the repo root:

```bash
python3 tools/extract_rostersynth_example.py --write --paper
python3 tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s examples/rostersynth-kiosk/tests
```

Expected test result:

```text
Ran 6 tests
OK
```

The checks exercise the paper's worked-example obligations:

- Oracle A cancels higher duplicate `bookingId=1802`.
- Wrong append passes replay but fails compare.
- Wrong cassette cancels `1801`, passes replay, and fails compare.
- Hybrid uses deterministic Oracle A for kiosk instead of fallback.
- Oracle B prompt includes decision order, Op 2, higher-bookingId rule, and payload.
- Full corpus gates match deterministic, hybrid cassette, and llm-only cassette evidence.

## For programmers

Use the companion artifact as an implementation appendix. The adaptable pattern is:

1. Put the intended strategy in a sketch file.
2. Add counterexamples for plausible wrong implementations.
3. Point the agent at known-code anchors before it writes new code.
4. Require a replay check for state repair.
5. Require a compare check for semantic fields replay under-specifies.
6. Promote every failure into the corpus and sketch before rerunning the agent.

A tiny didactic parser slice remains under [`examples/task-line-parser/`](examples/task-line-parser/) for readers who want the smallest possible version of the loop.

## For academics

Treat the repository as supplementary material for evaluating the paper's claims:

- the method is named and argued in [`paper/main.tex`](paper/main.tex);
- the correctness result is finite-corpus soundness, not universal correctness;
- the RosterSynth kiosk case is the concrete witness;
- the tests and graph show how source artifacts back the paper's claims.

The relevant comparison points are program sketching, CEGIS, programming by example, tests-as-prompts, and coding-agent benchmarks.

## Repository map

```text
paper/
  main.tex                               # paper: process, references, formal model, correctness theorem
  references.bib                         # bibliography
  extracted-rostersynth-kiosk-paper.md   # generated evidence appendix; not the paper spine
examples/
  rostersynth-kiosk/                     # worked example supporting the paper
    source/                              # copied RosterSynth source slice: sketch, scenarios, cassettes, code, tests
    tests/                               # self-contained checks for the paper's worked-example claims
  task-line-parser/                      # smallest didactic slice
flows/                                   # reusable agent flow prompts
.oh/knowledge/rostersynth-kiosk/         # repo-native graph node files
build/rostersynth-kiosk-graph.json       # extracted provenance graph
```

## Citation

> Castle, M. and Rubeck, E. *Agentic Synthesis against Counterexample-Supplemented Sketches.* 2026.

Private companion repo for now: `open-horizon-labs/sketch-counterexample-agent`.
