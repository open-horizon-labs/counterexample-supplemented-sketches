# Sketch + Counterexample + Coding Agent: A Small Control Loop for Reliable Agent-Written Code

## Abstract

Coding agents often fail because the request is underdetermined. A natural-language prompt tells the agent what to build, but not which plausible implementation would be wrong. This paper describes a small workflow: give the agent a sketch, counterexamples, known-code anchors, and a verification flow. The sketch names the intended shape. Counterexamples name the tempting wrong implementations. Known-code anchors keep the output boring and local to the project. Verification checks that the counterexamples fail the wrong patch, not merely that the happy path works.

The contribution is not a new synthesis engine and not a claim of formal correctness. It is a clean-room, executable method for making coding-agent work inspectable: every implementation should be traceable back to a sketch, at least one counterexample, a known-code anchor, and a test or check.

## 1. Problem

A coding agent can satisfy a prompt while missing the real constraint.

For example, a prompt says:

> Parse task lines like `todo: call Alice` and `blocked: deploy app | waiting on DNS`.

A plausible agent implementation might split on `:` and `|`, return a record, and pass the obvious examples. It can still be wrong:

- It may treat `done: blocked: deploy app` as two statuses.
- It may parse `|` as a reason for every status.
- It may accept `blocked: deploy app | ` with an empty reason.
- It may return dictionaries even though the project uses explicit `Ok` / `Err` results.

The failure is not that the model cannot code. The failure is that the task did not expose the wrong implementation the human already knew to fear.

## 2. Method

The workflow has five parts.

```text
sketch + counterexamples + known-code anchors + coding-agent flow + verification
= reliable known code
```

### 2.1 Sketch

A sketch is a partial solution shape. It is not a full spec and not a full implementation.

A good sketch says:

- what kind of code should exist;
- what behavior matters;
- what implementation shape is preferred;
- what is deliberately left to the agent;
- what local code style or API must be preserved.

In the clean-room example, the sketch asks for a dependency-free task-line parser that returns explicit result objects rather than throwing validation exceptions.

### 2.2 Counterexample

A counterexample is an adversarial example that names a plausible wrong implementation.

It has four jobs:

1. make ambiguity visible;
2. catch the tempting wrong patch;
3. become a test;
4. explain why the final code is more reliable than a happy-path implementation.

A counterexample is stronger than a normal example because it points at a failure mode.

Example:

```text
Input: done: blocked: deploy app
Wrong behavior: treat blocked: as a second status.
Correct behavior: status is done; title is blocked: deploy app.
```

### 2.3 Known-code anchor

A known-code anchor is code the agent must reuse or imitate. It keeps the result local and boring.

In the clean-room slice, the anchor is `known_code/result.py`:

- `Ok(value)` for success;
- `Err(ParseError(code, message))` for validation failure;
- no exceptions for expected validation errors.

The agent is not free to invent a new result convention.

### 2.4 Coding-agent flow

The agent receives a repeatable flow, not an ad-hoc request:

1. read the sketch;
2. read known-code anchors;
3. read counterexamples;
4. implement the smallest code that satisfies them;
5. add or preserve tests for each counterexample;
6. verify that a naive implementation would fail.

The flow is written as Markdown so it can be reused by a human or an agent.

### 2.5 Verification

Verification must be adversarial. A check is not enough if it would also pass the wrong patch.

For the parser slice, verification requires:

- happy-path parsing;
- counterexample tests;
- result-shape assertions against `Ok` / `Err`;
- a naive-parser check showing that plausible shortcuts fail.

## 3. Clean-Room Slice

The repo contains one minimal slice:

```text
examples/task-line-parser/
  sketch.md
  counterexamples.md
  known_code/result.py
  generated/parse_task_line.py
  tests/test_parse_task_line.py
  verification.md
```

The implementation parses:

```text
todo: call Alice
done: send invoice
blocked: deploy app | waiting on DNS
```

It rejects:

```text
todo:
blocked: deploy app |
later: deploy app
```

It preserves later colons in the title:

```text
done: blocked: deploy app
```

It treats `|` as title text unless the status is `blocked`:

```text
done: deploy app | checked by Sam
```

## 4. What This Is Not

### Not generic prompting

Generic prompting asks the agent to build the thing. This workflow tells the agent which wrong thing must fail.

### Not just TDD

TDD writes tests before code. This workflow uses counterexamples as steering context for the coding agent and as verification after implementation.

### Not programming by example

Programming by example synthesizes programs from examples, often inside a DSL or constrained search space. This workflow uses examples and counterexamples to steer a general coding agent inside a project’s local code style.

### Not program sketching

Program sketching fills holes in partial programs and can use formal search or verification. This workflow borrows the idea that a human can provide structure, but it does not claim formal synthesis or completeness.

### Not spec-driven development

Spec-driven development turns requirements into implementation plans and tasks. This workflow focuses on a smaller loop: sketch the implementation shape, name counterexamples, bind the agent to known code, and verify against tempting wrong patches.

## 5. Relation to Prior Work

Solar-Lezama’s work on Sketch shows how a programmer can provide a partial program while a synthesizer fills low-level details under correctness criteria. The shared idea is human-supplied structure plus machine completion. The difference is that this workflow uses coding agents and ordinary project code rather than a formal sketch language or synthesizer.

Microsoft PROSE shows programming by example: given a DSL and input-output examples, the system synthesizes ranked programs consistent with those examples. The shared idea is that examples constrain program generation. The difference is that this workflow treats counterexamples and known-code anchors as part of an agent execution flow, not only as DSL synthesis input.

GitHub Spec Kit and similar spec-driven workflows treat specifications as durable inputs to agent implementation. This workflow is narrower. It asks whether a sketch and counterexamples can prevent the agent’s likely wrong implementation.

Prompt-flow systems treat LLM prompts, tools, code, tracing, evaluation, and deployment as workflows. This work uses that same operational instinct but keeps the first artifact small: one sketch, one known-code anchor, counterexamples, implementation, and tests.

Tests-as-prompt and TDD-style benchmarks show that tests can serve both as prompt and verification for generated code. This workflow uses that idea but puts special weight on counterexamples: tests chosen because they fail a plausible wrong patch.

SWE-bench-style evaluation measures coding agents against real repository issues. This clean-room slice is much smaller. It is not an agent benchmark. It is a minimal method demonstration.

## 6. Claims

This workflow supports three modest claims.

1. A sketch reduces ambiguity by giving the agent an intended implementation shape.
2. Counterexamples improve reliability when they catch plausible wrong implementations, not just edge cases.
3. Known-code anchors reduce style drift by binding generated code to local conventions.

These claims are local. The clean-room slice does not prove broad coding-agent reliability.

## 7. Failure Modes

The workflow fails if:

- counterexamples are decorative and do not catch a plausible wrong patch;
- known-code anchors are present but ignored;
- tests only assert happy paths;
- the prompt flow cannot be reused;
- the implementation passes by special-casing exact strings;
- the paper claims formal correctness without formal evidence.

## 8. First Evidence

The first slice includes seven unit tests. They cover supported statuses, first-colon behavior, pipe handling, blocked-task reasons, invalid prefixes, empty titles, and non-string input.

The adversarial naive check confirms that a plausible simple parser fails required behavior:

- it treats `|` as a reason for non-blocked statuses;
- it accepts empty blocked reasons;
- it accepts unknown statuses.

This is the minimum evidence needed for the first clean-room claim: the counterexamples are doing real work.

## 9. Next Work

The next slice should reuse the same flow on a different task shape:

- a reducer;
- a small refactor;
- a serializer/deserializer;
- a bug fix against existing known code.

The method earns a stronger claim only if the same flow transfers.

## 10. Conclusion

The clean-room method is simple: do not ask a coding agent to infer hidden constraints from a broad prompt. Give it a sketch, show it the wrong implementation to avoid, bind it to known code, and verify that the wrong patch fails.

That is the outcome: not code generation as magic, but coding-agent work made inspectable.
