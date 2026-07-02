---
rna:
  kind: execution_point
  id: oracle-a.cancel-duplicate
  name: "Cancel duplicate implementation"
  selector: "examples/rostersynth-kiosk/source/rostersynth/playbook.py:109-137"
  relationships:
    - kind: replayed_by
      target: replay.effective-delta
    - kind: compared_by
      target: compare.modify
    - kind: verified_by
      target: test.kiosk.cancel
---

# Cancel duplicate implementation

Handling: Groups active windowEnd bookings by (shiftKind, hours), picks max bookingId, and only emits modify if deactivation closes coverageDelta.
