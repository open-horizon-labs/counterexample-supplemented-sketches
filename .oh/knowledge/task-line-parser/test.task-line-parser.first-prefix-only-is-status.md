---
rna:
  kind: verification_check
  id: test.task-line-parser.first-prefix-only-is-status
  name: "First prefix only is status"
  selector: "examples/task-line-parser/tests/test_parse_task_line.py:61-66"
  relationships:
    - kind: verifies
      target: implementation.parse-task-line
---

# First prefix only is status

