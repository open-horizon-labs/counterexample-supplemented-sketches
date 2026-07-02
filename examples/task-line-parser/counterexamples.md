# Counterexamples

These adversarial cases support the clean-room method. Each one names a plausible wrong implementation, the input that exposes it, and the expected result.

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
