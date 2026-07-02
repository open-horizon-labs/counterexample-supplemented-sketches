---
rna:
  kind: counterexample
  id: ce.kiosk-double-booking
  name: "Kiosk double-tap should cancel higher duplicate booking"
  selector: "examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json"
  relationships:
    - kind: specified_by
      target: sketch.op2
    - kind: observed_in
      target: session.step0
    - kind: promoted_by
      target: session.step2b
---

# Kiosk double-tap should cancel higher duplicate booking

Tempting Patch: append -40 hours to close coverageDelta, or cancel lower bookingId 1801 because replay still closes the hours math
