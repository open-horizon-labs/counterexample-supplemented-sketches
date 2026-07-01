---
rna:
  kind: corpus
  id: corpus.reference-v1
  name: "reference-v1 scenario corpus"
  selector: "examples/rostersynth-kiosk/source/scenarios/manifest.json"
  relationships:
    - kind: contains
      target: scenario.kiosk
    - kind: gated_by
      target: test.full-gates
---

# reference-v1 scenario corpus

