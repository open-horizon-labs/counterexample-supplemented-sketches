---
rna:
  kind: verification_check
  id: test.task-line-parser.empty-title-rejects
  name: "Empty title rejects"
  selector: "examples/task-line-parser/tests/test_parse_task_line.py:103-112"
  relationships:
    - kind: verifies
      target: implementation.parse-task-line
---

# Empty title rejects

