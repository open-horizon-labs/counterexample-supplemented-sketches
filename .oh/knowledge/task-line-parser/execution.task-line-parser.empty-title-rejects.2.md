---
rna:
  kind: execution_point
  id: execution.task-line-parser.empty-title-rejects.2
  name: "Empty title rejects handler 2"
  selector: "examples/task-line-parser/generated/parse_task_line.py:50-53"
  relationships:
    - kind: implemented_in
      target: implementation.parse-task-line
---

# Empty title rejects handler 2

Handling: The parser rejects blank body text before status-specific handling and rejects blank blocked titles after `|` splitting.
