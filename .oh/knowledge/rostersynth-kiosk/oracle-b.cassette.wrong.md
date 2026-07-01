---
rna:
  kind: negative_fixture
  id: oracle-b.cassette.wrong
  name: "Wrong kiosk cassette"
  selector: "examples/rostersynth-kiosk/source/cassettes/roster.kiosk_double_booking.v1.wrong.json"
  relationships:
    - kind: fails
      target: session.step5
---

# Wrong kiosk cassette

