# RosterSynth Kiosk Worked Example

This directory is the worked example supporting `paper/main.tex`.

It is generated from a local RosterSynth source checkout into repo-local snapshots under `source/`, then compiled into:

- `../../build/rostersynth-kiosk-graph.json` — graph nodes and edges for the example.
- `../../paper/extracted-rostersynth-kiosk-paper.md` — generated evidence appendix.
- `../../.oh/knowledge/rostersynth-kiosk/*.md` — repo-native node files.

The example demonstrates the full loop:

```text
sketch Op 2 + corpus counterexample
→ historical append failure
→ Oracle A duplicate-cancel implementation
→ replay check + semantic compare
→ Oracle B prompt/cassette path
→ wrong-cassette negative check
→ full-corpus gate evidence
```

Run:

```bash
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --write --paper
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s sketch-counterexample-agent/examples/rostersynth-kiosk/tests
```
