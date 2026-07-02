---
rna:
  kind: counterexample
  id: ce.task-line-parser.first-prefix-only-is-status
  name: "First prefix only is status"
  selector: "examples/task-line-parser/counterexamples.md:5-20"
  relationships:
    - kind: tests_tempting_patch
      target: split on every colon and treat a later status-looking prefix as a second status
    - kind: verified_by
      target: test.task-line-parser.first-prefix-only-is-status
    - kind: handled_by
      target: execution.task-line-parser.first-prefix-only-is-status.1
    - kind: handled_by
      target: execution.task-line-parser.first-prefix-only-is-status.2
---

# First prefix only is status

Tempting patch this counterexample fails: split on every colon and treat a later status-looking prefix as a second status
