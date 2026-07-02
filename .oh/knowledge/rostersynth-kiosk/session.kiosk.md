---
rna:
  kind: agent_session
  id: session.kiosk
  name: "Kiosk double-booking session"
  selector: "examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md"
  relationships:
    - kind: contains
      target: session.step0
    - kind: contains
      target: session.step1
    - kind: contains
      target: session.step2
    - kind: contains
      target: session.step2b
    - kind: contains
      target: session.step3
    - kind: contains
      target: session.step4
    - kind: contains
      target: session.step5
    - kind: contains
      target: session.step7
---

# Kiosk double-booking session

