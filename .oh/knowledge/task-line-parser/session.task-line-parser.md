---
rna:
  kind: agent_session
  id: session.task-line-parser
  name: "Task-line parser clean-room session"
  selector: "examples/task-line-parser"
  relationships:
    - kind: contains
      target: sketch.task-line-parser
    - kind: contains
      target: ce.task-line-parser.first-prefix-only-is-status
    - kind: contains
      target: ce.task-line-parser.blocked-reason-cannot-be-empty
    - kind: contains
      target: ce.task-line-parser.empty-title-rejects
    - kind: contains
      target: ce.task-line-parser.pipe-is-only-special-for-blocked
---

# Task-line parser clean-room session

