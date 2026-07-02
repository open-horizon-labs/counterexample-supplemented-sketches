---
rna:
  kind: prompt_flow
  id: oracle-b.prompt
  name: "Oracle B prompt decision order"
  selector: "examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py:14-40"
  relationships:
    - kind: produces
      target: oracle-b.cassette.correct
    - kind: verified_by
      target: test.prompt.includes-order
---

# Oracle B prompt decision order

Handling: Puts Op 2 before Op 1 and states the higher-bookingId tie-break plus required modify shape.
