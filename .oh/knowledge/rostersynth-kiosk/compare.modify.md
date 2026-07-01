---
rna:
  kind: compare_check
  id: compare.modify
  name: "Semantic compare for modify rows"
  selector: "examples/rostersynth-kiosk/source/rostersynth/eval/comparer.py:8-55"
  relationships:
    - kind: rejects
      target: oracle-b.cassette.wrong
---

# Semantic compare for modify rows

Check: Golden compare catches wrong op, wrong bookingId, and wrong fields.status.
