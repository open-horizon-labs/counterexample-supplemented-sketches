---
rna:
  kind: replay_check
  id: replay.effective-delta
  name: "Replay effective delta"
  selector: "examples/rostersynth-kiosk/source/rostersynth/verifier.py:8-18"
  relationships:
    - kind: verified_by
      target: test.row-closes-delta
---

# Replay effective delta

Check: Rows must close each imbalanced employee's coverageDelta.
