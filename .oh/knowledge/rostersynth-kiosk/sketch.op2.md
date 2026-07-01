---
rna:
  kind: sketch_clause
  id: sketch.op2
  name: "Op 2 cancel duplicate"
  selector: "examples/rostersynth-kiosk/source/docs/sketch.md:20-27"
  relationships:
    - kind: implemented_by
      target: oracle-a.cancel-duplicate
    - kind: communicated_to
      target: oracle-b.prompt
---

# Op 2 cancel duplicate

Clause: Twins on windowEnd with same shiftKind and hours cancel the higher bookingId when that alone closes delta; clusterNotes route to Oracle B.
