---
rna:
  kind: counterexample
  id: ce.task-line-parser.blocked-reason-cannot-be-empty
  name: "Blocked reason requires text"
  selector: "examples/task-line-parser/counterexamples.md:21-32"
  relationships:
    - kind: tests_tempting_patch
      target: accept a blank blocked reason after `|`
    - kind: verified_by
      target: test.task-line-parser.blocked-reason-cannot-be-empty
    - kind: handled_by
      target: execution.task-line-parser.blocked-reason-cannot-be-empty.1
---

# Blocked reason requires text

Tempting patch this counterexample fails: accept a blank blocked reason after `|`
