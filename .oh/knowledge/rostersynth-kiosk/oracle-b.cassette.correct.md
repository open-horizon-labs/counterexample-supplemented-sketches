---
rna:
  kind: cassette
  id: oracle-b.cassette.correct
  name: "Correct kiosk cassette"
  selector: "examples/rostersynth-kiosk/source/cassettes/roster.kiosk_double_booking.v1.json"
  relationships:
    - kind: compared_by
      target: compare.modify
    - kind: verified_by
      target: test.cassette.kiosk
---

# Correct kiosk cassette

