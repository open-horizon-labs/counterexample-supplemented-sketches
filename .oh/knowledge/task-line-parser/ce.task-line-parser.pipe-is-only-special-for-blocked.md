---
rna:
  kind: counterexample
  id: ce.task-line-parser.pipe-is-only-special-for-blocked
  name: "Pipe is only special for blocked"
  selector: "examples/task-line-parser/counterexamples.md:45-59"
  relationships:
    - kind: tests_tempting_patch
      target: parse `|` as a reason for todo/done statuses
    - kind: verified_by
      target: test.task-line-parser.pipe-is-only-special-for-blocked
    - kind: handled_by
      target: execution.task-line-parser.pipe-is-only-special-for-blocked.1
    - kind: handled_by
      target: execution.task-line-parser.pipe-is-only-special-for-blocked.2
---

# Pipe is only special for blocked

Tempting patch this counterexample fails: parse `|` as a reason for todo/done statuses
