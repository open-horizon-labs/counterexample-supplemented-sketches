---
rna:
  kind: verification_check
  id: test.task-line-parser.blocked-reason-cannot-be-empty
  name: "Blocked reason cannot be empty"
  selector: "examples/task-line-parser/tests/test_parse_task_line.py:82-90"
  relationships:
    - kind: verifies
      target: implementation.parse-task-line
---

# Blocked reason cannot be empty

