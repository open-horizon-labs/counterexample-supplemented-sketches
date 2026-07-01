# Companion Note: Sketch + Counterexample + Coding Agent

`paper/main.tex` is the primary paper. This note gives readers a shorter route through the method, the clean-room parser slice, and the RosterSynth worked example evidence.

## Abstract

Coding agents fail when a broad prompt hides the constraint the human already knows. The workflow in this repo makes that constraint explicit: give the agent a sketch, adversarial counterexamples, known-code anchors, and a verification flow. The sketch names the intended implementation shape. Counterexamples name tempting wrong implementations. Known-code anchors bind the result to local conventions. Verification proves that the counterexamples defeat the wrong patches.

The contribution is a small, executable control loop for inspectable coding-agent work. Every implementation should trace back to a sketch, at least one counterexample, a known-code anchor, and a test or check. The claim boundary is finite: the evidence supports the promoted corpus E and the companion examples in this repository.

## 1. Problem

A coding agent can satisfy a prompt while missing the real constraint.

For example, a prompt says:

> Parse task lines like `todo: call Alice` and `blocked: deploy app | waiting on DNS`.

A plausible implementation might split on `:` and `|`, return a record, and pass the obvious examples. It can still be wrong:

- It may treat `done: blocked: deploy app` as two statuses.
- It may parse `|` as a reason for every status.
- It may accept `blocked: deploy app | ` with an empty reason.
- It may return dictionaries even though the project uses explicit `Ok` / `Err` results.

The failure comes from an underspecified task. The prompt exposed the happy path and hid the wrong implementation the human needed to prevent.

## 2. Method

The workflow has five parts.

```text
sketch + counterexamples + known-code anchors + coding-agent flow + verification
= inspectable known-code implementation
```

### 2.1 Sketch

A sketch is a partial solution shape. It states the implementation direction while leaving ordinary coding details to the agent.

A good sketch says:

- what kind of code should exist;
- what behavior matters;
- what implementation shape is preferred;
- what local code style or API must be preserved;
- which boundaries the counterexamples will enforce.

In the clean-room example, the sketch asks for a dependency-free task-line parser that returns explicit result objects for validation failures.

### 2.2 Counterexample

A counterexample is an adversarial example that names a plausible wrong implementation.

It has four jobs:

1. make ambiguity visible;
2. catch the tempting wrong patch;
3. become a test;
4. explain why the final code is stronger than a happy-path implementation.

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
- validation failures return data instead of exceptions.

The anchor fixes the result convention before the agent writes new code.

### 2.4 Coding-agent flow

The agent receives a repeatable flow:

1. read the sketch;
2. read known-code anchors;
3. read counterexamples;
4. implement the smallest code that satisfies them;
5. add or preserve tests for each counterexample;
6. verify that a naive implementation fails.

The flow is Markdown so a human or agent can reuse it.

### 2.5 Verification

Verification is adversarial. A useful check fails the tempting wrong patch as well as passing the intended behavior.

For the parser slice, verification requires:

- happy-path parsing;
- counterexample tests;
- result-shape assertions against `Ok` / `Err`;
- a naive-parser check showing that plausible shortcuts fail.

## 3. Companion Evidence

The repo contains two evidence layers.

### 3.1 Clean-room parser slice

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

### 3.2 RosterSynth worked example

RosterSynth is the larger worked example supporting the paper. It shows the same method on a proprietary enterprise-origin data-cleansing workflow: SME corrections become LLM-assisted input/output specs, counterexamples enter the promoted corpus E, and replay/compare gates test the result.

The generated appendix at `paper/extracted-rostersynth-kiosk-paper.md` follows one kiosk double-booking counterexample through:

- sketch Op 2;
- promoted corpus case;
- historical append failure;
- Oracle A duplicate-cancel code;
- Oracle B prompt and cassette;
- replay and semantic compare;
- wrong-cassette negative check;
- full-corpus gate evidence.

## 4. Boundaries

This note uses related work to position the method:

- Generic prompting asks the agent to build from prose. This workflow also names the wrong implementation that must fail.
- TDD writes tests before code. This workflow uses counterexamples as steering context before implementation and as verification after implementation.
- Programming by example synthesizes programs from examples, often inside a DSL or constrained search space. This workflow steers a general coding agent inside a project's local code style.
- Program sketching fills holes in partial programs and can use formal search or verification. This workflow borrows human-supplied structure while staying inside ordinary project code.
- Spec-driven development turns requirements into implementation plans and tasks. This workflow focuses on a smaller loop: sketch the implementation shape, name counterexamples, bind the agent to known code, and verify against tempting wrong patches.

## 5. Relation to Prior Work

Solar-Lezama's work on Sketch shows how a programmer can provide a partial program while a synthesizer fills low-level details under correctness criteria. The shared idea is human-supplied structure plus machine completion. This workflow applies that idea to coding agents and ordinary project code.

Microsoft PROSE shows programming by example: given a DSL and input-output examples, the system synthesizes ranked programs consistent with those examples. The shared idea is that examples constrain program generation. This workflow adds counterexamples and known-code anchors to an agent execution flow.

GitHub Spec Kit and similar spec-driven workflows treat specifications as durable inputs to agent implementation. This workflow asks a narrower question: can a sketch and counterexamples prevent the agent's likely wrong implementation?

Prompt-flow systems treat LLM prompts, tools, code, tracing, evaluation, and deployment as workflows. This work uses that operational instinct with a smaller first artifact: one sketch, one known-code anchor, counterexamples, implementation, and tests.

Tests-as-prompt and TDD-style benchmarks show that tests can serve as prompt and verification for generated code. This workflow puts special weight on counterexamples: tests chosen because they fail a plausible wrong patch.

SWE-bench-style evaluation measures coding agents against real repository issues. This repo gives a minimal method demonstration with source-linked companion evidence.

## 6. Claims

This workflow supports three local claims.

1. A sketch reduces ambiguity by giving the agent an intended implementation shape.
2. Counterexamples improve reliability when they catch plausible wrong implementations.
3. Known-code anchors reduce style drift by binding generated code to local conventions.

The clean-room slice supports these claims for the parser example. The RosterSynth appendix supports finite-corpus soundness over the promoted corpus E. Broader coding-agent reliability requires additional corpora, tasks, and independent replications.

## 7. Failure Modes

The workflow fails if:

- counterexamples are decorative and miss the plausible wrong patch;
- known-code anchors are present and ignored;
- tests only assert happy paths;
- the prompt flow changes each time;
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

The method earns a stronger claim only when the same flow transfers.

## 10. Conclusion

The clean-room method is simple: give the coding agent a sketch, show it the wrong implementation to avoid, bind it to known code, and verify that the wrong patch fails.

The outcome is inspectable coding-agent work: each implementation links to the sketch, counterexamples, known-code anchors, and checks that justify it.
