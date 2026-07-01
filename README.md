# Sketch + Counterexample + Coding Agent

Clean-room demonstration of the workflow:

```text
sketch + counterexamples + known-code anchors + coding-agent prompt flow + verification
= reliable known code
```

This repo is not a framework. It now has two executable artifacts:

## Full RosterSynth example

`examples/rostersynth-kiosk/` is the full extracted example requested from the RosterSynth kiosk double-booking process. It starts with the real RosterSynth sketch/corpus/session snapshots and compiles them into graph nodes plus a generated paper artifact.

Artifacts:

- `tools/extract_rostersynth_example.py` — copies the RosterSynth source slice, builds the graph, writes repo-native node files, and renders the paper.
- `examples/rostersynth-kiosk/source/` — repo-local source snapshots for the sketch, kiosk scenario, cassettes, session transcript, implementation, gates, and tests.
- `build/rostersynth-kiosk-graph.json` — graph answering how the kiosk counterexample is handled.
- `paper/extracted-rostersynth-kiosk-paper.md` — generated full-example paper.
- `.oh/knowledge/rostersynth-kiosk/*.md` — RNA-shaped node files for the extracted example.

## First small slice

`examples/task-line-parser/` demonstrates a task-line parser.

Artifacts:

- `sketch.md` — incomplete human intent and solution shape.
- `counterexamples.md` — tempting wrong implementations made concrete.
- `known_code/result.py` — known-code result style the implementation must preserve.
- `generated/parse_task_line.py` — clean-room implementation.
- `tests/test_parse_task_line.py` — counterexample-driven verification.
- `verification.md` — how to run and interpret the check.

## Run

```bash
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --write --paper
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s sketch-counterexample-agent/examples/rostersynth-kiosk/tests
```
