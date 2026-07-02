---
rna:
  kind: execution_point
  id: oracle-a.build-rows
  name: "Oracle A build_rows dispatcher"
  selector: "examples/rostersynth-kiosk/source/rostersynth/playbook.py:53-72"
  relationships:
    - kind: tries_before_append
      target: oracle-a.cancel-duplicate
---

# Oracle A build_rows dispatcher

Handling: Skips balanced employees, abstains on clusterNotes, tries duplicate cancel before append.
