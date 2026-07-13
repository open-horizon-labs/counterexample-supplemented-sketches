# Counterexamples

This is the accepted-counterexample archive for the compact parser example. Each case records a
plausible wrong implementation, the input that exposes it, and the expected result that forced a
revision of `sketch.md`.

Archive membership means the example operator explicitly approved the case and corrected result
as a counterexample to the prior sketch. This compact directory shows the durable end state, not
the live approval event log.

A fresh implementation should not need this archive as prompt context. The evolved sketch carries
the policy learned from these cases. The tests use the cases as executable regression checks. This
example keeps all four because each protects a distinct boundary; here the regression subset
happens to equal the archive.

## First prefix only is status

Input:

```text
done: blocked: deploy app
```

Tempting wrong patch: split on every colon and treat `blocked:` as a second status.

Expected:

```python
TaskRecord(status="done", title="blocked: deploy app", reason=None)
```

## Blocked reason requires text

Input:

```text
blocked: deploy app | 
```

Tempting wrong patch: accept an empty string as the reason.

Expected: `Err(code="empty_reason")`.

## Empty title rejects

Input:

```text
todo:   
```

Tempting wrong patch: return an empty task.

Expected: `Err(code="empty_title")`.

## Pipe is only special for blocked

Input:

```text
done: deploy app | checked by Sam
```

Tempting wrong patch: parse `| checked by Sam` as a reason for every status.

Expected:

```python
TaskRecord(status="done", title="deploy app | checked by Sam", reason=None)
```
