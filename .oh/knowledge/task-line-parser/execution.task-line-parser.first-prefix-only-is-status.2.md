---
rna:
  kind: execution_point
  id: execution.task-line-parser.first-prefix-only-is-status.2
  name: "First prefix only is status handler 2"
  selector: "examples/task-line-parser/generated/parse_task_line.py:43-44"
  relationships:
    - kind: implemented_in
      target: implementation.parse-task-line
---

# First prefix only is status handler 2

Handling: `str.partition(':')` selects only the first colon; non-blocked bodies remain title text.
