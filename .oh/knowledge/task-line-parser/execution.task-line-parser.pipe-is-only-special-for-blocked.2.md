---
rna:
  kind: execution_point
  id: execution.task-line-parser.pipe-is-only-special-for-blocked.2
  name: "Pipe is only special for blocked handler 2"
  selector: "examples/task-line-parser/generated/parse_task_line.py:46-57"
  relationships:
    - kind: implemented_in
      target: implementation.parse-task-line
---

# Pipe is only special for blocked handler 2

Handling: The parser returns todo/done body text before pipe parsing; only blocked enters the pipe/reason branch.
