---
rna:
  kind: execution_point
  id: hybrid.resolver
  name: "Hybrid resolver"
  selector: "examples/rostersynth-kiosk/source/rostersynth/resolver/hybrid.py:18-69"
  relationships:
    - kind: prefers
      target: oracle-a.cancel-duplicate
    - kind: fallbacks_to
      target: oracle-b.prompt
    - kind: verified_by
      target: test.hybrid.kiosk
---

# Hybrid resolver

Handling: Runs Oracle A first; falls back to Oracle B only if deterministic row is missing or replay-invalid.
