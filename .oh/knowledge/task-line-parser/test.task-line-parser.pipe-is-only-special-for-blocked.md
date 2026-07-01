---
rna:
  kind: verification_check
  id: test.task-line-parser.pipe-is-only-special-for-blocked
  name: "Pipe is only special for blocked"
  selector: "examples/task-line-parser/tests/test_parse_task_line.py:68-80"
  relationships:
    - kind: verifies
      target: implementation.parse-task-line
---

# Pipe is only special for blocked

