---
rna:
  kind: execution_point
  id: execution.task-line-parser.blocked-reason-cannot-be-empty.1
  name: "Blocked reason cannot be empty handler 1"
  selector: "examples/task-line-parser/generated/parse_task_line.py:46-55"
  relationships:
    - kind: implemented_in
      target: implementation.parse-task-line
---

# Blocked reason cannot be empty handler 1

Handling: Blocked tasks partition on `|`, trim reason, and return `Err(empty_reason)` when it is blank.
