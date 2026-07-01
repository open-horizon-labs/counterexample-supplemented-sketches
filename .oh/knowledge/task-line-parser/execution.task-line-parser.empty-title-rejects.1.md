---
rna:
  kind: execution_point
  id: execution.task-line-parser.empty-title-rejects.1
  name: "Empty title rejects handler 1"
  selector: "examples/task-line-parser/generated/parse_task_line.py:39-41"
  relationships:
    - kind: implemented_in
      target: implementation.parse-task-line
---

# Empty title rejects handler 1

Handling: The parser rejects blank body text before status-specific handling and rejects blank blocked titles after `|` splitting.
