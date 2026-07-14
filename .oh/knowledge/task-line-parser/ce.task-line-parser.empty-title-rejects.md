---
rna:
  kind: counterexample
  id: ce.task-line-parser.empty-title-rejects
  name: "Empty title rejects"
  selector: "examples/task-line-parser/counterexamples.md:44-55"
  relationships:
    - kind: tests_tempting_patch
      target: return an empty task title as a valid record
    - kind: verified_by
      target: test.task-line-parser.empty-title-rejects
    - kind: handled_by
      target: execution.task-line-parser.empty-title-rejects.1
    - kind: handled_by
      target: execution.task-line-parser.empty-title-rejects.2
---

# Empty title rejects

Tempting patch this counterexample fails: return an empty task title as a valid record
