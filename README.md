# Programming with coding agents under checkable rules

**Paper PDF:** [`paper/main.pdf`](paper/main.pdf)  
**Paper source:** [`paper/main.tex`](paper/main.tex)  
**Bibliography:** [`paper/references.bib`](paper/references.bib)  
**Worked example:** [`examples/rostersynth-kiosk/`](examples/rostersynth-kiosk/)

Hold a sketch, a growing corpus `E`, and the code/prompt surfaces accountable through gates, not chat history. When validation fails, promote the failure into `E`, edit the sketch, code, or prompts, and rerun until green. Solar-Lezama sketching and CEGIS are lineage; the contribution here is the agentic loop with dual oracles and replay/compare validation. This repository is a reference implementation only. The roster domain is a worked example.

## The idea

You want a coding agent, or yourself in Cursor, to implement policy-heavy fixes: post this adjustment, cancel that duplicate, pick the right date. Free-form chat is too weak for that job. The rule has to live somewhere the repository can check.

The method:

1. **Write a sketch.** A sketch is a partial program. It fixes the strategy, names the allowed operations, and marks holes that remain open. It lives in prose and structure, not buried in chat history.
2. **Collect examples of correct behavior.** Each example gives the input payload and the row or output the system should emit.
3. **Promote failures.** When something is wrong, add the failure as a counterexample, tighten the sketch, and have the agent change the code and prompts that implement the sketch.
4. **Run a gate over all of `E`.** The gate replays the repair and compares the semantic fields. No green gate, not done.

That loop is **agentic synthesis against counterexample-supplemented sketches**. The sketch is counterexample-supplemented because `E` grows every time the gate catches a miss. Solar-Lezama's program sketching and CEGIS are the lineage. This repo's contribution is making coding-agent work accountable to a sketch file plus an expanding corpus: not vibes, not a one-off test, not a chat transcript.

Why not just prompt the LLM? Policy splits. Part belongs in code the agent maintains; part belongs in narrative an LLM should read. The sketch says which is which.

Why not just rules? Real failures show up as corner cases. Counterexamples force the sketch, code, prompts, and gates to catch up together.

## How it works

| Piece | Role |
|---|---|
| Sketch | Partial program: the contract the agent edits against |
| Corpus `E` | Examples; grows when gates fail |
| Oracle A | Code the agent writes for encodable holes |
| Oracle B | LLM plus prompts for sketch-declared narrative holes |
| Gate | Replay plus compare over all of `E` |

```text
  Sketch + examples (E)
         │
    Agent edits sketch, code, prompts
         │
    ┌────┴────┐
    ▼         ▼
 Oracle A   Oracle B
    └────┬────┘
         ▼
   bench gate ──fail──► counterexample → refine → rerun
```

The split matters. Replay asks whether the proposed repair closes the state gap. Compare asks whether it used the policy field the sketch requires. A repair can pass replay and still violate policy.

## Worked example: RosterSynth kiosk

This clone includes a synthetic workforce-roster example: badge hours versus scheduled hours. A kiosk double-booking creates one roster-hours gap and two plausible repairs:

- append an adjustment that balances hours;
- cancel the selected duplicate booking.

The quick arithmetic repair can make replay pass. The policy repair must cancel the duplicate booking selected by the sketch. That is why the gate needs replay and compare.

Start with the stitched evidence doc:

- [`paper/extracted-rostersynth-kiosk-paper.md`](paper/extracted-rostersynth-kiosk-paper.md) traces the kiosk counterexample from sketch clause to corpus case, historical failure, Oracle A code, Oracle B prompt path, replay/compare gates, hybrid behavior, llm-only behavior, and tests.

Then inspect the source artifacts directly:

| Question | Artifact |
|---|---|
| What is the sketch? | [`examples/rostersynth-kiosk/source/docs/sketch.md`](examples/rostersynth-kiosk/source/docs/sketch.md) |
| What examples are in `E`? | [`examples/rostersynth-kiosk/source/scenarios/manifest.json`](examples/rostersynth-kiosk/source/scenarios/manifest.json) |
| What is the focal counterexample? | [`examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json`](examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json) |
| What implements Oracle A? | [`examples/rostersynth-kiosk/source/rostersynth/playbook.py`](examples/rostersynth-kiosk/source/rostersynth/playbook.py) and [`resolver/deterministic.py`](examples/rostersynth-kiosk/source/rostersynth/resolver/deterministic.py) |
| What is the hybrid path? | [`examples/rostersynth-kiosk/source/rostersynth/resolver/hybrid.py`](examples/rostersynth-kiosk/source/rostersynth/resolver/hybrid.py) |
| What is the Oracle B path? | [`examples/rostersynth-kiosk/source/rostersynth/resolver/llm.py`](examples/rostersynth-kiosk/source/rostersynth/resolver/llm.py), [`oracle/prompt.py`](examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py), and [`source/cassettes/`](examples/rostersynth-kiosk/source/cassettes/) |
| What checks the behavior? | [`examples/rostersynth-kiosk/tests/test_extracted_rostersynth.py`](examples/rostersynth-kiosk/tests/test_extracted_rostersynth.py) |

The RosterSynth name is the reference-implementation label for this worked example. It is not the technique.

## Reproduce the artifact

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

The checks cover the paper's worked-example obligations:

- Oracle A cancels higher duplicate `bookingId=1802`.
- Wrong append passes replay; compare rejects it.
- Lower-booking Oracle B fixture cancels `1801`; compare rejects it.
- Hybrid keeps deterministic Oracle A on the kiosk case and avoids fallback.
- Oracle B prompt includes decision order, Op 2, higher-bookingId rule, and payload.
- Full corpus gates match deterministic, hybrid fixture, and llm-only fixture evidence.

No live agent key is required for the checked artifact. Live Bedrock is an optional Oracle B backend; the repository ships fixture outputs so the gate is reproducible.

## Repository map

```text
paper/
  main.tex                               # paper: method, lineage, formal model, finite-corpus claim
  main.pdf                               # rendered paper
  references.bib                         # bibliography
  extracted-rostersynth-kiosk-paper.md   # generated worked-example evidence
examples/
  rostersynth-kiosk/                     # worked example supporting the paper
    source/                              # sketch, scenarios, cassettes, code, prompts
    tests/                               # self-contained checks for the worked example
  task-line-parser/                      # smallest didactic slice
flows/                                   # reusable agent-flow prompts
build/rostersynth-kiosk-graph.json       # extracted provenance graph
.oh/knowledge/rostersynth-kiosk/         # repo-native graph node files
```

## Lineage to cite

The paper carries the full argument and bibliography. The important comparison points are:

- program sketching;
- counterexample-guided inductive synthesis;
- programming by example;
- tests-as-prompts;
- promptware / natural-language programming;
- coding-agent benchmarks.

See [`paper/references.bib`](paper/references.bib) for the canonical BibTeX.
