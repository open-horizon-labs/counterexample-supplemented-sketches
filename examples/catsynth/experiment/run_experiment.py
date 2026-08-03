"""Run the paired coding-agent experiment and capture the complete evidence trail.

Arm A reveals one operator-reviewed counterexample at a time, requires the
Developer to evolve the sketch, and repairs until the regression gate and
review against the current sketch both pass.
Arm B gives the same model the initial sketch and complete accepted archive in
one call, then repairs every visible failure until both checks pass. This
experiment uses every accepted CE as a regression (R = A). Both arms start from
the byte-identical clean-room baseline and use the same provider, model,
fixtures, inference settings, and final evaluator.
"""

from __future__ import annotations

import argparse
import ast
import copy
import difflib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
if str(EXAMPLE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_ROOT))

from catsynth import oracle_a, oracle_b, seed  # noqa: E402
from catsynth.codex_app_server import (  # noqa: E402
    DEFAULT_CODEX_MODEL,
    CodexAppServerClient,
)
from catsynth.models import OwnerProfile  # noqa: E402
from catsynth.openai_compat import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ChatResult,
    OpenAICompatibleClient,
)


HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline"
INITIAL_SKETCH_PATH = HERE / "initial_sketch.md"
CASES_PATH = HERE / "cases.json"
SPEC_CASES_PATH = HERE / "spec_regression_cases.json"
COMPLETE_SPEC_PATH = HERE / "complete_spec.md"
ALLOWED_TAGS = sorted(oracle_b.TAG_TO_SOFT_RULE)
ALLOWED_OUTPUT_KEYS = {"operation", "breed", "cited_rules", "rationale"}

TAG_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {"type": "array", "items": {"type": "string", "enum": ALLOWED_TAGS}},
    },
    "required": ["tags"],
    "additionalProperties": False,
}
ORACLE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["recommend", "abstain", "escalate"]},
        "breed": {"type": ["string", "null"]},
        "cited_rules": {"type": "array", "items": {"type": "string"}},
        "oracle_tags": {
            "type": "array", "items": {"type": "string", "enum": ALLOWED_TAGS},
        },
        "sketch_rule": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": [
        "operation", "breed", "cited_rules", "oracle_tags", "sketch_rule", "explanation",
    ],
    "additionalProperties": False,
}
DEVELOPER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy_py": {"type": "string"},
        "oracle_prompt": {"type": "string"},
        "sketch_md": {"type": "string"},
        "clarification_request": {"type": ["string", "null"]},
    },
    "required": [
        "strategy_py", "oracle_prompt", "sketch_md", "clarification_request",
    ],
    "additionalProperties": False,
}
SPEC_DEVELOPER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy_py": {"type": "string"},
        "oracle_prompt": {"type": "string"},
    },
    "required": ["strategy_py", "oracle_prompt"],
    "additionalProperties": False,
}
SKETCH_REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "enum": ["pass", "fail", "needs-authority"],
                    },
                    "applicable_clauses": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "required_behavior": {"type": "string"},
                    "difference": {"type": "string"},
                    "failure_class": {
                        "type": "string",
                        "enum": ["none", "projection-defect", "possible-sketch-gap"],
                    },
                },
                "required": [
                    "id", "verdict", "applicable_clauses", "required_behavior",
                    "difference", "failure_class",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cases"],
    "additionalProperties": False,
}


class ChatClient(Protocol):
    provider: str
    model: str

    def list_models(self) -> list[str]: ...
    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 4096,
             temperature: float = 0, extra: Any = None) -> ChatResult: ...
    def close(self) -> None: ...


class ExperimentError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ExperimentError(f"model returned no JSON object: {text[:500]!r}")
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"invalid model JSON: {exc}: {text[:1000]}") from exc
    if not isinstance(value, dict):
        raise ExperimentError("model response must be a JSON object")
    return value


def result_record(result: ChatResult) -> dict[str, Any]:
    return {
        "request": result.request,
        "response": result.response,
        "content": result.content,
        "reasoning": result.reasoning,
        "usage": result.usage,
    }


class Ledger:
    TOKEN_KEYS = (
        "prompt_tokens", "completion_tokens", "total_tokens",
        "cached_prompt_tokens", "reasoning_tokens",
    )

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def add(self, category: str, label: str, result: ChatResult) -> None:
        self.calls.append({"category": category, "label": label, **result.usage})

    def totals(self) -> dict[str, Any]:
        categories: dict[str, dict[str, int]] = {}
        for call in self.calls:
            bucket = categories.setdefault(call["category"], {
                "calls": 0,
                **{key: 0 for key in self.TOKEN_KEYS},
            })
            bucket["calls"] += 1
            for key in self.TOKEN_KEYS:
                bucket[key] += int(call.get(key, 0))
        overall = {
            "calls": len(self.calls),
            **{
                key: sum(int(call.get(key, 0)) for call in self.calls)
                for key in self.TOKEN_KEYS
            },
        }
        return {"overall": overall, "by_category": categories, "calls": self.calls}


SketchApprover = Callable[[dict[str, Any]], dict[str, Any]]
SketchReviewAdjudicator = Callable[[dict[str, Any]], dict[str, Any]]


class ManualSketchApprover:
    """Block the experiment until an authorized reviewer decides a sketch change."""

    def __init__(self, root: Path):
        self.root = root / "sketch-approvals"
        self.clarification_root = root / "authority-clarifications"
        self._next_id = 1
        self._next_clarification_id = 1

    def __call__(self, proposal: dict[str, Any]) -> dict[str, Any]:
        proposal_id = f"{self._next_id:03d}"
        self._next_id += 1
        pending = self.root / f"{proposal_id}-pending.json"
        write_json(pending, {"proposal_id": proposal_id, **proposal})
        print(f"SKETCH_APPROVAL_REQUIRED {pending.resolve()}", flush=True)
        print(
            "Reply with one-line JSON: "
            '{"decision":"approve|reject","rationale":"...","approver":"..."}',
            flush=True,
        )
        while True:
            raw = input().strip()
            try:
                decision = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"Invalid approval JSON: {exc}", flush=True)
                continue
            if not isinstance(decision, dict):
                print("Approval must be a JSON object.", flush=True)
                continue
            if decision.get("decision") not in {"approve", "reject"}:
                print("decision must be approve or reject.", flush=True)
                continue
            if not str(decision.get("rationale", "")).strip():
                print("rationale must be non-empty.", flush=True)
                continue
            if not str(decision.get("approver", "")).strip():
                print("approver must be non-empty.", flush=True)
                continue
            record = {
                "proposal_id": proposal_id,
                "decision": decision["decision"],
                "rationale": str(decision["rationale"]).strip(),
                "approver": str(decision["approver"]).strip(),
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(self.root / f"{proposal_id}-decision.json", record)
            return record

    def clarify(self, request: dict[str, Any]) -> dict[str, Any]:
        """Block until the policy authority supplies the requested clarification."""
        request_id = f"{self._next_clarification_id:03d}"
        self._next_clarification_id += 1
        pending = self.clarification_root / f"{request_id}-pending.json"
        write_json(pending, {"request_id": request_id, **request})
        print(f"AUTHORITY_CLARIFICATION_REQUIRED {pending.resolve()}", flush=True)
        print(
            "Reply with one-line JSON: "
            '{"clarification":"...","authority":"..."}',
            flush=True,
        )
        while True:
            raw = input().strip()
            try:
                answer = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"Invalid clarification JSON: {exc}", flush=True)
                continue
            if not isinstance(answer, dict):
                print("Clarification must be a JSON object.", flush=True)
                continue
            if not str(answer.get("clarification", "")).strip():
                print("clarification must be non-empty.", flush=True)
                continue
            if not str(answer.get("authority", "")).strip():
                print("authority must be non-empty.", flush=True)
                continue
            record = {
                "request_id": request_id,
                "clarification": str(answer["clarification"]).strip(),
                "authority": str(answer["authority"]).strip(),
                "answered_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(
                self.clarification_root / f"{request_id}-answer.json", record,
            )
            return record


class ManualSketchReviewAdjudicator:
    """Ask an authorized reviewer to resolve non-pass model review verdicts."""

    def __init__(self, root: Path):
        self.root = root / "sketch-review-adjudications"
        self._next_id = 1

    def __call__(self, proposal: dict[str, Any]) -> dict[str, Any]:
        proposal_id = f"{self._next_id:03d}"
        self._next_id += 1
        pending = self.root / f"{proposal_id}-pending.json"
        write_json(pending, {"proposal_id": proposal_id, **proposal})
        case_ids = [item["id"] for item in proposal["model_non_pass_cases"]]
        print(f"SKETCH_REVIEW_ADJUDICATION_REQUIRED {pending.resolve()}", flush=True)
        print(
            "Reply with one-line JSON: "
            '{"decisions":[{"id":"...","verdict":"pass|fail|needs-authority",'
            '"rationale":"..."}],"reviewer":"..."}',
            flush=True,
        )
        while True:
            raw = input().strip()
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"Invalid adjudication JSON: {exc}", flush=True)
                continue
            decisions = value.get("decisions") if isinstance(value, dict) else None
            reviewer = str(value.get("reviewer", "")).strip() if isinstance(value, dict) else ""
            if not isinstance(decisions, list) or not reviewer:
                print("decisions must be an array and reviewer must be non-empty.", flush=True)
                continue
            returned_ids = [item.get("id") for item in decisions if isinstance(item, dict)]
            if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(case_ids):
                print(f"decisions must cover exactly these case IDs: {case_ids}", flush=True)
                continue
            valid = True
            for item in decisions:
                if item.get("verdict") not in {"pass", "fail", "needs-authority"}:
                    valid = False
                if not str(item.get("rationale", "")).strip():
                    valid = False
            if not valid:
                print("Each decision needs a valid verdict and non-empty rationale.", flush=True)
                continue
            record = {
                "proposal_id": proposal_id,
                "decisions": decisions,
                "reviewer": reviewer,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(self.root / f"{proposal_id}-decision.json", record)
            return record


def workspace_text(workspace: Path) -> dict[str, str]:
    return {
        filename: (workspace / filename).read_text(encoding="utf-8")
        for filename in ("SKETCH.md", "strategy.py", "oracle_prompt.txt")
    }


def restore_workspace_text(workspace: Path, state: dict[str, str]) -> None:
    for filename, value in state.items():
        (workspace / filename).write_text(value, encoding="utf-8")


def fixtures() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    breeds = [b.to_dict() for b in seed.BREEDS]
    profiles = {p.scenario_id: p.to_dict() for p in seed.SCENARIOS}
    rules = {r["id"]: copy.deepcopy(r) for r in seed.RULES}
    return breeds, profiles, rules


def profile_for_case(case: dict[str, Any]) -> dict[str, Any]:
    _, profiles, _ = fixtures()
    return copy.deepcopy(profiles[case["scenario_id"]])


def breeds_for_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    breeds, _, _ = fixtures()
    if "breed_names" not in case:
        return breeds
    selected = set(case["breed_names"])
    return [breed for breed in breeds if breed["name"] in selected]


def validate_strategy(source: str) -> ast.AST:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ExperimentError(f"generated strategy is not valid Python: {exc}") from exc
    banned_calls = {"open", "exec", "eval", "compile", "__import__", "input"}
    case_ids = {case["id"] for case in json.loads(CASES_PATH.read_text(encoding="utf-8"))}
    if SPEC_CASES_PATH.exists():
        case_ids.update(
            case["id"] for case in json.loads(SPEC_CASES_PATH.read_text(encoding="utf-8"))
        )
    scenario_ids = {profile.scenario_id for profile in seed.SCENARIOS}
    forbidden_literals = {*case_ids, *scenario_ids}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ExperimentError("generated strategy may not import modules")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in banned_calls:
            raise ExperimentError(f"generated strategy may not call {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "spawn", "unlink"}:
            raise ExperimentError(f"generated strategy uses prohibited attribute {node.attr}")
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.value in forbidden_literals):
            raise ExperimentError(
                f"generated strategy contains prohibited case literal {node.value!r}"
            )
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "recommend"]
    if len(functions) != 1 or [a.arg for a in functions[0].args.args] != [
        "profile", "breeds", "rules", "oracle_tags",
    ]:
        raise ExperimentError("strategy must preserve recommend(profile, breeds, rules, oracle_tags)")
    return tree


def load_recommend(source: str):
    tree = validate_strategy(source)
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "float": float, "int": int, "isinstance": isinstance,
        "len": len, "iter": iter, "next": next,
        "list": list, "map": map, "filter": filter,
        "max": max, "min": min, "range": range, "reversed": reversed,
        "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
        "chr": chr, "ord": ord,
        "Exception": Exception, "IndexError": IndexError, "KeyError": KeyError,
        "TypeError": TypeError, "ValueError": ValueError,
    }
    namespace: dict[str, Any] = {"__builtins__": safe_builtins}
    exec(compile(tree, "generated_strategy.py", "exec"), namespace, namespace)
    return namespace["recommend"]


def normalize_candidate(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ExperimentError("recommend must return a dict")
    missing = ALLOWED_OUTPUT_KEYS - set(candidate)
    if missing:
        raise ExperimentError(f"recommend output missing keys: {sorted(missing)}")
    return {
        "operation": candidate["operation"],
        "breed": candidate["breed"],
        "cited_rules": sorted(candidate["cited_rules"]),
        "rationale": str(candidate["rationale"]),
    }


def oracle_tags(prompt_text: str, note: str, client: ChatClient,
                ledger: Ledger, label: str) -> tuple[list[str], dict[str, Any]]:
    prompt = prompt_text.replace("{note}", note)
    result = client.chat([
        {"role": "system", "content": "Return only compact JSON. Do not add markdown."},
        {"role": "user", "content": prompt},
    ], max_tokens=512, temperature=0, extra={"output_schema": TAG_OUTPUT_SCHEMA})
    ledger.add("runtime_oracle", label, result)
    parsed = extract_json(result.content)
    raw_tags = parsed.get("tags", [])
    tags = sorted({str(tag) for tag in raw_tags if str(tag) in ALLOWED_TAGS})
    return tags, {**result_record(result), "parsed_tags": tags}


def evaluate_case(workspace: Path, case: dict, active_rule_ids: set[str],
                  client: ChatClient, ledger: Ledger, label: str) -> dict[str, Any]:
    _, _, all_rules = fixtures()
    breeds = breeds_for_case(case)
    profile = profile_for_case(case)
    prompt_text = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    trace = None
    tags: list[str] = []
    if profile.get("narrative_note"):
        tags, trace = oracle_tags(prompt_text, profile["narrative_note"], client, ledger, label)
    rule_ids = case.get("rule_sequence", sorted(active_rule_ids))
    rules = [all_rules[rid] for rid in rule_ids]
    source = (workspace / "strategy.py").read_text(encoding="utf-8")
    recommend = load_recommend(source)
    candidate = normalize_candidate(recommend(profile, breeds, rules, tags))
    actual = {
        "operation": candidate["operation"],
        "breed": candidate["breed"],
        "cited_rules": candidate["cited_rules"],
        "oracle_tags": tags,
    }
    expected = copy.deepcopy(case["expected"])
    expected["cited_rules"] = sorted(expected["cited_rules"])
    expected["oracle_tags"] = sorted(expected.get("oracle_tags", []))
    field_names = ("operation", "breed", "cited_rules", "oracle_tags")
    checked_fields = case.get("checked_fields", list(field_names))
    unknown = set(checked_fields) - set(field_names)
    if unknown:
        raise ExperimentError(f"case {case['id']} checks unknown fields: {sorted(unknown)}")
    fields = {
        key: {
            "expected": expected[key], "actual": actual[key],
            "match": expected[key] == actual[key], "checked": key in checked_fields,
        }
        for key in field_names
    }
    return {
        "id": case["id"], "scenario_id": case["scenario_id"],
        "candidate": candidate, "actual": actual, "expected": expected,
        "checked_fields": checked_fields, "fields": fields,
        "passed": all(fields[key]["match"] for key in checked_fields),
        "oracle_trace": trace,
    }


def run_gate(workspace: Path, promoted: list[dict], client: ChatClient,
             ledger: Ledger, label: str) -> dict[str, Any]:
    active_rules = {rid for case in promoted for rid in case.get("rule_ids", [])}
    regression_cases = [initial_acceptance_case(), *promoted]
    cases = [
        evaluate_case(workspace, case, active_rules, client, ledger, f"{label}:{case['id']}")
        for case in regression_cases
    ]
    return {
        "passed": bool(cases) and all(case["passed"] for case in cases),
        "passed_count": sum(1 for case in cases if case["passed"]),
        "total": len(cases),
        "cases": cases,
    }


def sketch_review_messages(workspace: Path, cases: list[dict[str, Any]],
                           evaluations: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a review request without supplying approved outputs or the CE archive."""
    by_id = {case["id"]: case for case in cases}
    active_rule_ids = {
        rule_id for case in cases for rule_id in case.get("rule_ids", [])
    }
    _, _, all_rules = fixtures()
    review_cases = []
    for evaluation in evaluations:
        case_id = evaluation.get("id")
        if case_id not in by_id:
            raise ExperimentError(f"sketch review received unknown case {case_id!r}")
        case = by_id[case_id]
        rule_ids = case.get("rule_sequence", sorted(active_rule_ids))
        review_cases.append({
            "id": case_id,
            "profile": profile_for_case(case),
            "candidate_breeds": breeds_for_case(case),
            "rules_supplied": [all_rules[rule_id] for rule_id in rule_ids],
            "observed_output": evaluation.get("candidate") or evaluation.get("actual"),
            "oracle_tags": (evaluation.get("actual") or {}).get("oracle_tags", []),
        })
    payload = {
        "task": (
            "Review each observed output against the current sketch. Use only the sketch and "
            "supplied input facts. Do not infer an approved output that is not stated by the "
            "sketch. Return pass when the output follows the sketch, fail when it violates a "
            "stated clause, and needs-authority when the sketch is missing or ambiguous about "
            "a policy needed to judge the output. Use failure_class none with pass, "
            "projection-defect with fail, and possible-sketch-gap with needs-authority. "
            "For a ranking decision, calculate every score term named by the sketch for the "
            "observed choice and its closest alternatives before assigning a verdict. "
            "Return exactly one result for each case id."
        ),
        "current_sketch_md": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
        "cases": review_cases,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are the sketch reviewer in a synthetic software-synthesis experiment. "
                "Judge simulated behavior against the supplied sketch. You may identify a "
                "projection defect or a possible sketch gap, but you may not approve a policy "
                "change. Return JSON only."
            ),
        },
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]


def run_sketch_review(workspace: Path, cases: list[dict[str, Any]],
                      evaluations: list[dict[str, Any]], client: ChatClient,
                      ledger: Ledger, label: str,
                      adjudicator: SketchReviewAdjudicator | None = None) -> dict[str, Any]:
    """Ask a capable model to judge simulated outputs against the current sketch."""
    messages = sketch_review_messages(workspace, cases, evaluations)
    result = client.chat(
        messages, max_tokens=5000, temperature=0,
        extra={"output_schema": SKETCH_REVIEW_OUTPUT_SCHEMA},
    )
    ledger.add("sketch_reviewer", label, result)
    parsed = extract_json(result.content)
    raw_cases = parsed.get("cases")
    if not isinstance(raw_cases, list):
        raise ExperimentError("sketch reviewer must return a cases array")
    expected_ids = [evaluation["id"] for evaluation in evaluations]
    returned_ids = [item.get("id") for item in raw_cases if isinstance(item, dict)]
    if len(returned_ids) != len(set(returned_ids)):
        raise ExperimentError("sketch reviewer returned duplicate case IDs")
    if set(returned_ids) != set(expected_ids):
        raise ExperimentError(
            "sketch reviewer case IDs differ from requested corpus: "
            f"expected {expected_ids}, got {returned_ids}"
        )
    by_id = {item["id"]: item for item in raw_cases}
    reviewed = []
    for case_id in expected_ids:
        item = copy.deepcopy(by_id[case_id])
        verdict = item.get("verdict")
        failure_class = item.get("failure_class")
        if verdict == "pass" and failure_class != "none":
            raise ExperimentError(
                f"sketch reviewer marked {case_id} pass with {failure_class!r}"
            )
        if verdict == "fail" and failure_class != "projection-defect":
            raise ExperimentError(
                f"sketch reviewer marked {case_id} fail with {failure_class!r}"
            )
        if verdict == "needs-authority" and failure_class != "possible-sketch-gap":
            raise ExperimentError(
                f"sketch reviewer marked {case_id} needs-authority with {failure_class!r}"
            )
        item["passed"] = verdict == "pass"
        reviewed.append(item)
    adjudication = None
    non_pass = [item for item in reviewed if not item["passed"]]
    if non_pass and adjudicator is not None:
        review_payload = json.loads(messages[1]["content"])
        adjudication = adjudicator({
            "label": label,
            "current_sketch_md": review_payload["current_sketch_md"],
            "cases": review_payload["cases"],
            "model_non_pass_cases": non_pass,
            "decision_boundary": (
                "Judge only whether observed output follows the current sketch. "
                "Do not approve a sketch or policy change in this decision."
            ),
        })
        decisions = {
            item["id"]: item for item in adjudication.get("decisions", [])
            if isinstance(item, dict)
        }
        if set(decisions) != {item["id"] for item in non_pass}:
            raise ExperimentError("review adjudicator did not decide every non-pass case")
        for item in non_pass:
            decision = decisions[item["id"]]
            verdict = decision.get("verdict")
            if verdict not in {"pass", "fail", "needs-authority"}:
                raise ExperimentError("review adjudicator returned an invalid verdict")
            item["model_verdict"] = item["verdict"]
            item["adjudication"] = {
                "verdict": verdict,
                "rationale": decision.get("rationale"),
                "reviewer": adjudication.get("reviewer"),
                "proposal_id": adjudication.get("proposal_id"),
            }
            item["verdict"] = verdict
            item["failure_class"] = {
                "pass": "none",
                "fail": "projection-defect",
                "needs-authority": "possible-sketch-gap",
            }[verdict]
            item["passed"] = verdict == "pass"
    review_result = {
        "passed": bool(reviewed) and all(item["passed"] for item in reviewed),
        "passed_count": sum(1 for item in reviewed if item["passed"]),
        "total": len(reviewed),
        "cases": reviewed,
        "model": result_record(result),
    }
    if adjudication is not None:
        review_result["adjudication"] = adjudication
    return review_result


def run_validation(workspace: Path, promoted: list[dict], client: ChatClient,
                   ledger: Ledger, label: str,
                   adjudicator: SketchReviewAdjudicator | None = None) -> dict[str, Any]:
    """Run the deterministic gate and the separate review over active + R."""
    gate = run_gate(workspace, promoted, client, ledger, f"{label}:gate")
    corpus = [initial_acceptance_case(), *promoted]
    review = run_sketch_review(
        workspace, corpus, gate.get("cases", []), client, ledger,
        f"{label}:sketch-review",
        adjudicator,
    )
    return {
        "passed": gate.get("passed", False) and review.get("passed", False),
        "gate": gate,
        "sketch_review": review,
    }


def failed_sketch_review(error: Any, total: int) -> dict[str, Any]:
    return {
        "passed": False,
        "passed_count": 0,
        "total": total,
        "cases": [],
        "error": str(error),
    }


def oracle_prompt(case: dict, observed: dict) -> list[dict[str, str]]:
    _, _, rules = fixtures()
    breeds = breeds_for_case(case)
    relevant_rules = [rules[rid] for rid in case.get("rule_ids", [])]
    relevant_tag_rules = [
        oracle_b.TAG_TO_SOFT_RULE[tag]
        for tag in case.get("oracle_tag_ids", [])
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are the Oracle in a synthetic software-synthesis experiment. "
                "Turn one reviewer policy into a promoted counterexample. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({
                "task": (
                    "The reviewer has already approved reviewed_expected. Copy its operation, "
                    "breed, cited_rules, and oracle_tags exactly; do not recalculate or overrule "
                    "them. Generalize the reviewer policy into sketch_rule and explanation. "
                    "Return the compact JSON immediately."
                ),
                "profile": profile_for_case(case),
                "observed": observed,
                "reviewed_expected": case["expected"],
                "reviewer_policy": case["policy"],
                "known_preference_ranking": (
                    "Use low=0, moderate=1, high=2 and small=0, medium=1, large=2. "
                    "When wants_size is set, add max(0, 2-abs(breed_size-wanted_size)). "
                    "When wants_affection is true, add breed.affection + (2-breed.energy). "
                    "When wants_fluffy is true, add 2 for breed.fluffy=true. Then apply any "
                    "relevant soft penalties. Highest total wins; ties break by breed name. "
                    "False preference flags add nothing and are not constraints. Apply no other "
                    "policy unless it appears in this counterexample's reviewer_policy, "
                    "relevant_rule_rows, or relevant_oracle_tag_rules."
                ),
                "oracle_b_contract": (
                    "oracle_tags are controlled soft tags derived only from narrative_note. "
                    "When narrative_note is null or empty, oracle_tags must be []."
                ),
                "relevant_rule_rows": relevant_rules,
                "relevant_oracle_tag_rules": relevant_tag_rules,
                "breed_catalog": breeds,
                "allowed_operations": ["recommend", "abstain", "escalate"],
                "allowed_oracle_tags": ALLOWED_TAGS,
                "cited_rules_contract": (
                    "cited_rules contains only IDs of applicable hard forbid rows from "
                    "relevant_rule_rows. Policy labels and oracle tags are not rule IDs."
                ),
            }, indent=2),
        },
    ]


def call_oracle(case: dict, observed: dict, client: ChatClient,
                ledger: Ledger) -> tuple[dict, dict]:
    messages = oracle_prompt(case, observed)
    result = client.chat(
        messages, max_tokens=3000, temperature=0,
        extra={"output_schema": ORACLE_OUTPUT_SCHEMA},
    )
    ledger.add("spec_oracle", case["id"], result)
    parsed = extract_json(result.content)
    model_expected = {
        "operation": parsed.get("operation"),
        "breed": parsed.get("breed"),
        "cited_rules": sorted(parsed.get("cited_rules") or []),
        "oracle_tags": sorted(parsed.get("oracle_tags") or []),
    }
    reference = copy.deepcopy(case["expected"])
    reference["cited_rules"] = sorted(reference["cited_rules"])
    reference["oracle_tags"] = sorted(reference.get("oracle_tags", []))
    promoted = {
        "id": case["id"], "scenario_id": case["scenario_id"],
        "policy": case["policy"], "rule_ids": case.get("rule_ids", []),
        "oracle_tag_ids": case.get("oracle_tag_ids", []),
        "checked_fields": case.get("checked_fields", [
            "operation", "breed", "cited_rules", "oracle_tags",
        ]),
        "sketch_rule": case["sketch_rule"],
        "expected": reference,
        "tempting": observed,
        "oracle_explanation": parsed.get("explanation", ""),
    }
    for optional_key in ("breed_names", "rule_sequence"):
        if optional_key in case:
            promoted[optional_key] = copy.deepcopy(case[optional_key])
    agreement = model_expected == reference
    return promoted, {
        **result_record(result), "parsed": promoted,
        "model_sketch_rule_proposal": parsed.get("sketch_rule"),
        "model_expected_proposal": model_expected,
        "reviewed_reference": reference,
        "reference_agreement": agreement,
        "promotion_authority": "reviewed_reference",
    }


def known_code_contract() -> dict[str, Any]:
    return {
        "entrypoint": "recommend(profile, breeds, rules, oracle_tags)",
        "return_shape": {
            "operation": "recommend | abstain | escalate",
            "breed": "breed name string or null",
            "cited_rules": "list of rule ID strings",
            "rationale": "string",
        },
        "profile_fields": [
            "scenario_id", "label", "allergies", "work_hours", "home_size",
            "young_children", "activity_level", "noise_tolerance", "experience",
            "wants_size", "wants_affection", "wants_fluffy", "narrative_note",
        ],
        "breed_fields": [
            "name", "size", "energy", "shedding", "grooming", "sociability",
            "vocal", "affection", "hypoallergenic", "good_with_children", "fluffy",
            "summary", "wiki_url",
        ],
        "rule_fields": [
            "id", "trait", "trait_op", "trait_value", "kind", "cat_attribute",
            "cat_op", "cat_value", "reason",
        ],
        "ordinal_values": {
            "levels": ["low", "moderate", "high"],
            "sizes": ["small", "medium", "large"],
        },
        "rule_value_encoding": (
            "trait_value and cat_value are strings; an in-set is encoded as one "
            "comma-separated string"
        ),
        "prompt_contract": (
            "oracle_prompt.txt contains {note} and requests one JSON object with a tags array"
        ),
        "catalog_contract": (
            "breeds may contain the full catalog, a selected subset, or be empty; "
            "behavior must follow the supplied list rather than named fixtures"
        ),
        "forbidden_shortcuts": [
            "do not branch on scenario_id", "do not hard-code named fixture outputs",
        ],
    }


def approved_case_authority(case: dict[str, Any]) -> dict[str, Any]:
    """Extract the exact approved policy authority from a promoted case packet."""
    return {
        "id": case.get("id"),
        "approved_policy": case.get("reviewer_policy", case.get("policy")),
        "approved_counterexample_clause": case.get(
            "counterexample_clause", case.get("sketch_rule"),
        ),
        "approved_output": case.get("expected"),
        "checked_fields": case.get("checked_fields", [
            "operation", "breed", "cited_rules", "oracle_tags",
        ]),
    }


def sketch_change_contract(promoted: list[dict], active_failure: Any,
                           arm: str, phase: str,
                           complete_corpus: Any = None) -> dict[str, Any]:
    """State exact sketch-change authority and preservation duties for every call."""
    retained = (
        [approved_case_authority(case) for case in promoted]
        if phase != "initial" and arm != "reviewed_sketch"
        else []
    )
    corpus = [
        approved_case_authority(case) for case in (complete_corpus or [])
        if isinstance(case, dict)
    ]
    if phase == "one_shot" or (phase == "one_shot_repair" and corpus):
        change_authority = {
            "kind": "approved_complete_corpus",
            "cases": corpus,
            "scope": (
                "Each supplied case authorizes only the minimum general rule entailed "
                "by its approved policy, clause, checked fields, and approved output."
            ),
        }
    elif phase == "one_shot_repair":
        change_authority = {
            "kind": "projection_repair_under_current_sketch",
            "exact_failure_packets": active_failure,
            "cases": [],
            "scope": (
                "Repair the projection so the supplied failures follow current_sketch_md. "
                "No new sketch policy is authorized."
            ),
        }
    elif phase == "initial":
        change_authority = {
            "kind": "none",
            "cases": [],
            "scope": (
                "No new policy is authorized. The sketch may be reorganized or clarified "
                "only without changing its meaning or filling an explicit hole."
            ),
        }
    else:
        underlying = active_failure
        if isinstance(active_failure, dict) and isinstance(
            active_failure.get("active_failure"), dict,
        ):
            underlying = active_failure["active_failure"]
        active_id = underlying.get("id") if isinstance(underlying, dict) else None
        approved = next(
            (case for case in retained if case.get("id") == active_id), None,
        )
        if approved is None and isinstance(underlying, dict) and (
            underlying.get("reviewer_policy") is not None
            or underlying.get("counterexample_clause") is not None
        ):
            approved = approved_case_authority(underlying)
        if (
            isinstance(active_failure, dict)
            and active_failure.get("failure_kind") == "authority-clarification-answered"
        ):
            change_authority = {
                "kind": "authorized_clarification",
                "exact_failure_packet": active_failure,
                "scope": (
                    "The supplied authority clarification resolves only its stated "
                    "question. It authorizes no adjacent policy choice."
                ),
            }
        else:
            change_authority = {
                "kind": "active_approved_counterexample_or_existing_policy_repair",
                "approved_case": approved,
                "exact_failure_packet": active_failure,
                "scope": (
                    "If approved_case is present, it authorizes only the minimum general "
                    "rule it entails. Otherwise repair the projection under existing policy; "
                    "no new sketch policy is authorized."
                ),
            }
    return {
        "prior_policy_authority": (
            "current_sketch_md is the complete authority for policy that predates this call."
        ),
        "retained_counterexample_authority": retained,
        "active_change_authority": change_authority,
        "preservation_requirements": [
            "Preserve every current sketch clause that active_change_authority does not directly change.",
            "Preserve every explicit policy hole unless active_change_authority directly resolves it.",
            "Preserve every retained approved counterexample and its checked output fields.",
            "Preserve the public function signature, output shape, data encodings, prompt placeholder, and tag-array contract in known_code_contract.",
            "Preserve case independence: do not branch on scenario IDs or hard-code fixtures or named outputs.",
            "Do not infer authority from an unrevealed, later, analogous, or merely plausible case.",
        ],
        "conflict_protocol": (
            "If current_sketch_md, retained_counterexample_authority, "
            "active_change_authority, known_code_contract, or an approval rejection "
            "conflict or leave the authorized change ambiguous, do not choose a "
            "resolution. Return all three current files unchanged and set "
            "clarification_request to one precise question. Otherwise set "
            "clarification_request to null."
        ),
    }


def developer_messages(workspace: Path, promoted: list[dict], active_failure: Any,
                       arm: str, phase: str,
                       complete_corpus: Any = None) -> list[dict[str, str]]:
    strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    sketch = (workspace / "SKETCH.md").read_text(encoding="utf-8")
    if phase == "initial":
        task = (
            "Generate the initial implementation from the sketch. You may clarify or reorganize the "
            "sketch while preserving its policy. Return compact JSON with the three complete-file "
            "string keys strategy_py, oracle_prompt, and sketch_md, plus clarification_request."
        )
    elif phase == "one_shot":
        task = (
            "Generate the complete implementation from the initial sketch and complete corpus in one "
            "shot. Return compact JSON with the three complete-file string keys strategy_py, "
            "oracle_prompt, and sketch_md, plus clarification_request."
        )
    elif phase == "one_shot_repair":
        task = (
            "Revise the current sketch and implementation to encode the complete promoted corpus "
            "and close every supplied failure while preserving cases that already pass. The "
            "complete corpus remains authoritative even after a rejected proposal is rolled back. "
            "Return compact JSON with the three complete-file string keys strategy_py, "
            "oracle_prompt, and sketch_md, plus clarification_request."
        )
    else:
        task = (
            "Close the one active failure while preserving prior behavior and policy. If it is an "
            "approved counterexample, revise the sketch only as far as its approved policy and "
            "counterexample clause entail. If it is an implementation, validation, or review defect "
            "already governed by the sketch, preserve sketch policy. Return compact JSON with the three "
            "complete-file string keys strategy_py, oracle_prompt, and sketch_md, plus "
            "clarification_request."
        )
    if phase == "one_shot":
        system = (
            "You are the Developer in a clean-room, single-shot synthesis task. Generate the "
            "complete sketch and implementation from the supplied initial sketch and simultaneous "
            "corpus. There is no active failure and no prior implementation to repair. JSON only."
        )
    elif phase == "one_shot_repair":
        system = (
            "You are the Developer repairing a one-shot-generated implementation. Use the current "
            "sketch, code, prompt, and complete set of visible validation failures. Close those failures "
            "without regressing behavior that already passes. JSON only."
        )
    elif phase == "initial":
        system = (
            "You are the Developer in an initial synthesis task. Generate the sketch and "
            "implementation from the supplied partial sketch and empty implementation files. "
            "JSON only."
        )
    else:
        system = (
            "You are the Developer in a repository repair loop. Revise the sketch and "
            "implementation to close the one active failure while preserving behavior that "
            "already passes both regression checks. JSON only."
        )
    payload = {
        "arm": arm,
        "phase": phase,
        "task": task + " Do not return a diff or markdown.",
        "constraints": [
            "Preserve recommend(profile, breeds, rules, oracle_tags).",
            "Return operation, breed, cited_rules, and rationale.",
            "Do not import modules, access files/network, inspect scenario_id, or hard-code breeds by case.",
            "You may generalize the active counterexample into the sketch, code, and prompt. Do not invent unrevealed counterexamples or paste case-specific fixtures into the sketch.",
            "An active approved counterexample authorizes the minimum general rule required by its corrected output and approved clause, even when that rule was absent from the prior sketch.",
            "Preserve every existing policy clause, anchor, and explicit hole unless the active approved counterexample directly changes it.",
            "When no approved counterexample is active, preserve open policy holes. Never use a later counterexample to justify an earlier proposal.",
            "Do not decide empty, invalid, narrative, or other adjacent behavior unless the active approved counterexample entails that decision.",
            "If a sketch approval was rejected, follow its rationale and keep the last approved workspace as the authority.",
            "In one-shot repair, every case in complete_corpus remains authoritative; encode all of its promoted clauses, not only the latest visible failure.",
            "oracle_prompt must contain {note} and return JSON with a tags array; only use tag meanings defined by the current sketch or supplied counterexamples.",
        ],
        "known_code_contract": known_code_contract(),
        "sketch_change_contract": sketch_change_contract(
            promoted, active_failure, arm, phase, complete_corpus,
        ),
        "current_sketch_md": sketch,
        "active_failing_counterexample": (
            active_failure if phase != "one_shot_repair" else None
        ),
        "current_strategy_py": strategy,
        "current_oracle_prompt": prompt,
    }
    if phase in {"one_shot", "one_shot_repair"}:
        payload["complete_corpus"] = complete_corpus
        payload["promoted_case_ids"] = [case["id"] for case in promoted]
    if phase == "one_shot_repair":
        payload["active_failing_counterexamples"] = active_failure
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]


def complete_case_packets(promoted: list[dict]) -> list[dict[str, Any]]:
    _, _, rules = fixtures()
    return [
        {
            "id": case["id"],
            "scenario_id": case["scenario_id"],
            "profile": profile_for_case(case),
            "candidate_breeds": breeds_for_case(case),
            "reviewer_policy": case["policy"],
            "counterexample_clause": case["sketch_rule"],
            "relevant_rule_rows": [
                rules[rule_id] for rule_id in case.get("rule_ids", [])
            ],
            "relevant_oracle_tag_rules": [
                oracle_b.TAG_TO_SOFT_RULE[tag]
                for tag in case.get("oracle_tag_ids", [])
            ],
            "expected": case["expected"],
            "checked_fields": case.get("checked_fields", [
                "operation", "breed", "cited_rules", "oracle_tags",
            ]),
            "tempting_actual": case.get("tempting"),
        }
        for case in promoted
    ]


def apply_developer(workspace: Path, parsed: dict[str, Any]) -> dict[str, str]:
    file_keys = {"strategy_py", "oracle_prompt", "sketch_md"}
    if set(parsed) != file_keys | {"clarification_request"}:
        raise ExperimentError(
            "Developer JSON must contain strategy_py, oracle_prompt, sketch_md, and "
            "clarification_request"
        )
    strategy = parsed["strategy_py"]
    prompt = parsed["oracle_prompt"]
    sketch = parsed["sketch_md"]
    if not all(isinstance(value, str) for value in (strategy, prompt, sketch)):
        raise ExperimentError("Developer file replacements must be strings")
    for name, value in (
        ("strategy_py", strategy), ("oracle_prompt", prompt), ("sketch_md", sketch),
    ):
        controls = sorted({ord(char) for char in value if ord(char) < 32 and char not in "\n\r\t"})
        if controls:
            raise ExperimentError(f"{name} contains control characters: {controls}")
    validate_strategy(strategy)
    if "{note}" not in prompt:
        raise ExperimentError("oracle_prompt must preserve the {note} placeholder")
    if not sketch.strip():
        raise ExperimentError("sketch_md must not be empty")
    before_strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    before_prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    before_sketch = (workspace / "SKETCH.md").read_text(encoding="utf-8")
    (workspace / "strategy.py").write_text(strategy.rstrip() + "\n", encoding="utf-8")
    (workspace / "oracle_prompt.txt").write_text(prompt.rstrip() + "\n", encoding="utf-8")
    (workspace / "SKETCH.md").write_text(sketch.rstrip() + "\n", encoding="utf-8")
    return {
        "strategy.diff": "".join(difflib.unified_diff(
            before_strategy.splitlines(True), strategy.splitlines(True),
            fromfile="before/strategy.py", tofile="after/strategy.py",
        )),
        "oracle_prompt.diff": "".join(difflib.unified_diff(
            before_prompt.splitlines(True), prompt.splitlines(True),
            fromfile="before/oracle_prompt.txt", tofile="after/oracle_prompt.txt",
        )),
        "SKETCH.diff": "".join(difflib.unified_diff(
            before_sketch.splitlines(True), sketch.splitlines(True),
            fromfile="before/SKETCH.md", tofile="after/SKETCH.md",
        )),
    }


def call_developer(workspace: Path, promoted: list[dict], active_failure: Any,
                   arm: str, phase: str, label: str, client: ChatClient,
                   ledger: Ledger, complete_corpus: Any = None) -> tuple[dict, dict]:
    messages = developer_messages(
        workspace, promoted, active_failure, arm, phase, complete_corpus,
    )
    result = client.chat(
        messages, max_tokens=8000, temperature=0,
        extra={"output_schema": DEVELOPER_OUTPUT_SCHEMA},
    )
    ledger.add(f"developer_{arm}", label, result)
    record = result_record(result)
    try:
        parsed = extract_json(result.content)
        clarification = parsed.get("clarification_request")
        if clarification is not None and not isinstance(clarification, str):
            raise ExperimentError("clarification_request must be a string or null")
        if isinstance(clarification, str) and clarification.strip():
            record.update({
                "error": None,
                "parsed_keys": sorted(parsed),
                "diffs": {},
                "clarification_request": clarification.strip(),
            })
            return {}, record
        diffs = apply_developer(workspace, parsed)
    except Exception as exc:
        record.update({"error": f"{type(exc).__name__}: {exc}", "parsed_keys": [], "diffs": {}})
        return {}, record
    record.update({"error": None, "parsed_keys": sorted(parsed), "diffs": diffs})
    return parsed, record


def call_developer_with_approval(
    workspace: Path,
    promoted: list[dict],
    active_failure: Any,
    arm: str,
    phase: str,
    label: str,
    client: ChatClient,
    ledger: Ledger,
    sketch_approver: SketchApprover | None,
    complete_corpus: Any = None,
) -> tuple[dict, dict]:
    before = workspace_text(workspace)
    parsed, record = call_developer(
        workspace, promoted, active_failure, arm, phase, label,
        client, ledger, complete_corpus,
    )
    if not parsed:
        request = record.get("clarification_request")
        if request:
            clarify = getattr(sketch_approver, "clarify", None)
            if not callable(clarify):
                record["error"] = (
                    "Developer requested authority clarification, but no authority "
                    "clarification resolver was configured"
                )
                return {}, record
            answer = clarify({
                "arm": arm,
                "phase": phase,
                "label": label,
                "question": request,
                "sketch_change_contract": sketch_change_contract(
                    promoted, active_failure, arm, phase, complete_corpus,
                ),
            })
            record["authority_clarification"] = answer
            record["next_failure"] = {
                "id": "authority-clarification",
                "failure_kind": "authority-clarification-answered",
                "question": request,
                "authorized_clarification": answer,
                "expected": (
                    "Revise the files using the supplied clarification and no broader authority."
                ),
                "actual": "No files were changed while clarification was pending.",
            }
            record["error"] = "Authority clarification answered; Developer must retry."
        return parsed, record
    after = workspace_text(workspace)
    if before["SKETCH.md"] == after["SKETCH.md"]:
        record["sketch_approval"] = {
            "decision": "not-required",
            "rationale": "Developer did not change the sketch.",
        }
        return parsed, record
    if sketch_approver is None:
        restore_workspace_text(workspace, before)
        raise ExperimentError(
            "Developer changed SKETCH.md but no sketch approver was configured"
        )
    proposal = {
        "arm": arm,
        "phase": phase,
        "label": label,
        "active_failure": active_failure,
        "promoted_case_ids": [case["id"] for case in promoted],
        "complete_corpus_case_ids": [
            case["id"] for case in (complete_corpus or [])
            if isinstance(case, dict) and "id" in case
        ],
        "before_sketch": before["SKETCH.md"],
        "after_sketch": after["SKETCH.md"],
        "sketch_diff": record.get("diffs", {}).get("SKETCH.diff", ""),
        "review_questions": [
            "Does the proposed sketch preserve previously approved policy?",
            "Does each new policy claim follow as the minimum general rule required by the active approved CE or supplied corpus, even if absent from the prior sketch?",
            "If no approved CE is active, does the proposal preserve every open policy hole?",
            "Does the change avoid settling adjacent policy that remains open?",
        ],
    }
    approval = sketch_approver(proposal)
    if approval.get("decision") not in {"approve", "reject"}:
        restore_workspace_text(workspace, before)
        raise ExperimentError("sketch approver returned an invalid decision")
    record["sketch_approval"] = approval
    if approval["decision"] == "approve":
        return parsed, record
    restore_workspace_text(workspace, before)
    rejection = {
        "id": (
            active_failure.get("id", "sketch-change")
            if isinstance(active_failure, dict) else "sketch-change"
        ),
        "failure_kind": "sketch-approval-rejected",
        "approval": approval,
        "active_failure": active_failure,
        "expected": "a sketch change within the approved policy boundary",
        "actual": "the proposed sketch change was rejected and the workspace was restored",
    }
    record["next_failure"] = rejection
    record["error"] = f"Sketch change rejected: {approval['rationale']}"
    record["workspace_restored"] = True
    return {}, record


def spec_developer_messages(workspace: Path, complete_spec: str,
                            failures: Any) -> list[dict[str, str]]:
    strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    initial = failures is None
    task = (
        "Generate strategy.py and oracle_prompt.txt from the immutable complete specification."
        if initial else
        "Repair strategy.py and oracle_prompt.txt so every supplied visible failure passes while "
        "continuing to implement the immutable complete specification."
    )
    payload = {
        "arm": "spec_first_repair",
        "phase": "spec_first" if initial else "spec_repair",
        "task": (
            task + " Return compact JSON with exactly two complete-file string keys: "
            "strategy_py and oracle_prompt. Do not return a diff or markdown."
        ),
        "complete_immutable_specification": complete_spec,
        "current_strategy_py": strategy,
        "current_oracle_prompt": prompt,
        "visible_validation_failures": failures,
        "constraints": [
            "The specification is authoritative and may not be revised.",
            "Do not inspect or branch on concrete scenario IDs, case IDs, or named fixture outputs.",
            "Do not import modules or access files, tools, environment state, or the network.",
        ],
    }
    system = (
        "You are the Developer in a clean-room, specification-first implementation task. "
        "Implement the complete immutable specification without worked examples. JSON only."
        if initial else
        "You are the Developer repairing a specification-first implementation. The complete "
        "specification remains immutable. Use the current files and visible validation failures. "
        "JSON only."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]


def apply_spec_developer(workspace: Path, parsed: dict[str, Any]) -> dict[str, str]:
    if set(parsed) != {"strategy_py", "oracle_prompt"}:
        raise ExperimentError(
            "Spec-first Developer JSON must contain exactly strategy_py and oracle_prompt"
        )
    strategy = parsed["strategy_py"]
    prompt = parsed["oracle_prompt"]
    if not isinstance(strategy, str) or not isinstance(prompt, str):
        raise ExperimentError("Spec-first Developer file replacements must be strings")
    for name, value in (("strategy_py", strategy), ("oracle_prompt", prompt)):
        controls = sorted({
            ord(char) for char in value if ord(char) < 32 and char not in "\n\r\t"
        })
        if controls:
            raise ExperimentError(f"{name} contains control characters: {controls}")
    validate_strategy(strategy)
    if "{note}" not in prompt:
        raise ExperimentError("oracle_prompt must preserve the {note} placeholder")
    before_strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    before_prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    (workspace / "strategy.py").write_text(strategy.rstrip() + "\n", encoding="utf-8")
    (workspace / "oracle_prompt.txt").write_text(prompt.rstrip() + "\n", encoding="utf-8")
    return {
        "strategy.diff": "".join(difflib.unified_diff(
            before_strategy.splitlines(True), strategy.splitlines(True),
            fromfile="before/strategy.py", tofile="after/strategy.py",
        )),
        "oracle_prompt.diff": "".join(difflib.unified_diff(
            before_prompt.splitlines(True), prompt.splitlines(True),
            fromfile="before/oracle_prompt.txt", tofile="after/oracle_prompt.txt",
        )),
    }


def call_spec_developer(workspace: Path, complete_spec: str, failures: Any,
                        label: str, client: ChatClient,
                        ledger: Ledger) -> tuple[dict, dict]:
    messages = spec_developer_messages(workspace, complete_spec, failures)
    result = client.chat(
        messages, max_tokens=8000, temperature=0,
        extra={"output_schema": SPEC_DEVELOPER_OUTPUT_SCHEMA},
    )
    ledger.add("developer_spec_first_repair", label, result)
    record = result_record(result)
    try:
        parsed = extract_json(result.content)
        diffs = apply_spec_developer(workspace, parsed)
    except Exception as exc:
        record.update({"error": f"{type(exc).__name__}: {exc}",
                       "parsed_keys": [], "diffs": {}})
        return {}, record
    record.update({"error": None, "parsed_keys": sorted(parsed), "diffs": diffs})
    return parsed, record


def baseline_workspace(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASELINE / "strategy.py", path / "strategy.py")
    shutil.copy2(BASELINE / "oracle_prompt.txt", path / "oracle_prompt.txt")
    shutil.copy2(INITIAL_SKETCH_PATH, path / "SKETCH.md")


def snapshot_generation(path: Path, workspace: Path, promoted: list[dict],
                        gate: dict[str, Any], developer: Any,
                        active_failure: Any = None,
                        sketch_review: Any = None) -> None:
    path.mkdir(parents=True, exist_ok=False)
    shutil.copy2(workspace / "strategy.py", path / "strategy.py")
    shutil.copy2(workspace / "oracle_prompt.txt", path / "oracle_prompt.txt")
    shutil.copy2(workspace / "SKETCH.md", path / "SKETCH.md")
    write_json(path / "corpus.json", promoted)
    write_json(path / "gate.json", gate)
    if sketch_review is not None:
        write_json(path / "sketch-review.json", sketch_review)
    if active_failure is not None:
        write_json(path / "active_failure.json", active_failure)
    if developer is not None:
        write_json(path / "developer.json", developer)


def failure_packet(case: dict, evaluation: dict[str, Any]) -> dict[str, Any]:
    _, _, rules = fixtures()
    checked_fields = evaluation.get("checked_fields", [
        "operation", "breed", "cited_rules", "oracle_tags",
    ])
    return {
        "id": case["id"],
        "scenario_id": case["scenario_id"],
        "profile": profile_for_case(case),
        "candidate_breeds": breeds_for_case(case),
        "reviewer_policy": case["policy"],
        "counterexample_clause": case["sketch_rule"],
        "relevant_rule_rows": [rules[rid] for rid in case.get("rule_ids", [])],
        "relevant_oracle_tag_rules": [
            oracle_b.TAG_TO_SOFT_RULE[tag]
            for tag in case.get("oracle_tag_ids", [])
        ],
        "checked_fields": checked_fields,
        "expected": {
            key: evaluation["expected"][key] for key in checked_fields
        },
        "actual": {
            key: evaluation["actual"][key] for key in checked_fields
        },
        "mismatches": {
            key: value for key, value in evaluation["fields"].items()
            if value.get("checked", True) and not value["match"]
        },
    }


def validation_failure_packets(promoted: list[dict], gate: dict[str, Any],
                               sketch_review: dict[str, Any],
                               record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one repair packet per case that failed either acceptance check."""
    if record.get("next_failure") is not None:
        value = record["next_failure"]
        return value if isinstance(value, list) else [value]
    cases_by_id = {
        case["id"]: case for case in [initial_acceptance_case(), *promoted]
    }
    reviews = {
        item["id"]: item for item in sketch_review.get("cases", [])
        if isinstance(item, dict) and item.get("id") in cases_by_id
    }
    packets = []
    seen = set()
    for evaluation in gate.get("cases", []):
        case_id = evaluation.get("id")
        review = reviews.get(case_id)
        if case_id not in cases_by_id:
            continue
        if evaluation.get("passed") and (review is None or review.get("passed")):
            continue
        packet = failure_packet(cases_by_id[case_id], evaluation)
        if review is not None and not review.get("passed"):
            packet["failure_kind"] = "sketch-review"
            packet["sketch_review"] = {
                key: review.get(key)
                for key in (
                    "verdict", "applicable_clauses", "required_behavior",
                    "difference", "failure_class",
                )
            }
        packets.append(packet)
        seen.add(case_id)
    for case_id, review in reviews.items():
        if review.get("passed") or case_id in seen:
            continue
        packets.append({
            "id": case_id,
            "failure_kind": "sketch-review",
            "reviewer_policy": cases_by_id[case_id]["policy"],
            "counterexample_clause": cases_by_id[case_id]["sketch_rule"],
            "profile": profile_for_case(cases_by_id[case_id]),
            "actual": None,
            "sketch_review": review,
        })
    if packets:
        return packets
    return [{
        "id": "two-check-validation",
        "failure_kind": "validation-contract",
        "expected": "deterministic gate and sketch review both pass",
        "actual": (
            sketch_review.get("error") or gate.get("error")
            or record.get("error") or "unknown validation failure"
        ),
        "mismatches": {},
    }]


def initial_acceptance_case() -> dict[str, Any]:
    return {
        "id": "initial-preference-ranking",
        "scenario_id": "novice_quiet",
        "policy": "Initial sketch preference ranking with no learned policy rows.",
        "rule_ids": [],
        "sketch_rule": "Initial sketch only.",
        "expected": {
            "operation": "recommend", "breed": "Persian",
            "cited_rules": [], "oracle_tags": [],
        },
    }


def initial_failure(gate: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    case = initial_acceptance_case()
    failed_cases = [item for item in gate.get("cases", []) if not item.get("passed")]
    if failed_cases:
        return failure_packet(case, failed_cases[0])
    return {
        "id": case["id"],
        "scenario_id": case["scenario_id"],
        "profile": profile_for_case(case),
        "candidate_breeds": breeds_for_case(case),
        "reviewer_policy": case["policy"],
        "counterexample_clause": case["sketch_rule"],
        "expected": case["expected"],
        "actual": None,
        "mismatches": {"execution": {
            "expected": "a valid implementation that passes the initial sketch gate",
            "actual": gate.get("error") or record.get("error") or "unknown failure",
            "match": False,
        }},
    }


def run_iterative(output: Path, cases: list[dict], client: ChatClient,
                  ledger: Ledger, max_repairs: int,
                  sketch_approver: SketchApprover | None = None,
                  review_adjudicator: SketchReviewAdjudicator | None = None) -> dict:
    if max_repairs < 0:
        raise ExperimentError("max_repairs must be zero or greater")
    workspace = output / "workspace"
    baseline_workspace(workspace)
    cycles = []
    revealed: list[dict] = []
    oracle_records = []
    generation = 0
    initial_attempts = []
    active_failure = None
    initial_gate: dict[str, Any] = {}
    initial_review: dict[str, Any] = {}
    initial_validation_passed = False
    for attempt in range(max_repairs + 1):
        phase = "initial" if attempt == 0 else "repair"
        label = "initial-generation" if attempt == 0 else f"initial-repair-{attempt:02d}"
        parsed, record = call_developer_with_approval(
            workspace, [], active_failure, "iterative", phase, label,
            client, ledger, sketch_approver,
        )
        if parsed:
            try:
                validation = run_validation(
                    workspace, [], client, ledger,
                    f"iterative-initial-acceptance-attempt-{attempt + 1}",
                    review_adjudicator,
                )
                initial_gate = validation["gate"]
                initial_review = validation["sketch_review"]
                initial_validation_passed = validation["passed"]
                initial_gate["scope"] = "initial sketch acceptance"
            except Exception as exc:
                initial_gate = {
                    "passed": False, "passed_count": 0, "total": 1, "cases": [],
                    "scope": "initial sketch acceptance",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                initial_review = failed_sketch_review(
                    f"{type(exc).__name__}: {exc}", 1,
                )
                initial_validation_passed = False
        else:
            initial_gate = {
                "passed": False, "passed_count": 0, "total": 0, "cases": [],
                "scope": "initial generation contract",
                "error": record.get("error"),
            }
            initial_review = failed_sketch_review(record.get("error"), 1)
            initial_validation_passed = False
        record["gate"] = initial_gate
        record["sketch_review"] = initial_review
        record["validation_passed"] = initial_validation_passed
        record["active_counterexample_id"] = (
            active_failure["id"] if active_failure is not None else None
        )
        snapshot_name = (
            "000-initial-generation" if attempt == 0 else
            f"{generation:03d}-repair-initial-preference-ranking-attempt-{attempt:02d}"
        )
        snapshot_generation(
            output / "generations" / snapshot_name,
            workspace, [], initial_gate, record, active_failure, initial_review,
        )
        initial_attempts.append(record)
        generation += 1
        if initial_validation_passed:
            break
        active_failure = validation_failure_packets(
            [], initial_gate, initial_review, record,
        )[0]
    if not initial_validation_passed:
        raise ExperimentError(
            "Developer did not satisfy both initial checks after "
            f"{max_repairs} repair attempts"
        )
    initial_sketch_after = (workspace / "SKETCH.md").read_text(encoding="utf-8")
    final_gate = initial_gate
    final_sketch_review = initial_review

    for index, case in enumerate(cases, 1):
        proposed = revealed + [case]
        active_rules = {rid for item in proposed for rid in item.get("rule_ids", [])}
        introduced_failure = evaluate_case(
            workspace, case, active_rules, client, ledger,
            f"iterative-cycle-{index}-introduced:{case['id']}",
        )
        cycle_root = output / f"cycle-{index:02d}-{case['id']}"
        write_json(cycle_root / "introduced-counterexample.json", {
            "counterexample": case,
            "evaluation": introduced_failure,
        })
        try:
            introduced_review = run_sketch_review(
                workspace, [case], [introduced_failure], client, ledger,
                f"iterative-cycle-{index}-introduced-review:{case['id']}",
                review_adjudicator,
            )
        except Exception as exc:
            introduced_review = failed_sketch_review(
                f"{type(exc).__name__}: {exc}", 1,
            )
        write_json(cycle_root / "introduced-sketch-review.json", introduced_review)
        if introduced_failure["passed"] and introduced_review["passed"]:
            coverage_gate = run_gate(
                workspace, revealed, client, ledger,
                f"iterative-cycle-{index}-coverage-check",
            )
            coverage = {
                "case": case["id"], "status": "coverage-not-promoted",
                "introduced_failure": introduced_failure,
                "introduced_sketch_review": introduced_review,
                "attempts": [], "gate": coverage_gate,
                "sketch_after": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
            }
            write_json(cycle_root / "coverage.json", coverage)
            cycles.append(coverage)
            continue
        sketch_before_ce = (workspace / "SKETCH.md").read_text(encoding="utf-8")
        promoted_case, oracle_record = call_oracle(
            case, introduced_failure["actual"], client, ledger,
        )
        oracle_records.append(oracle_record)
        write_json(output / "oracle" / f"{index:02d}-{case['id']}.json", oracle_record)
        revealed.append(promoted_case)
        attempts = []
        gate = {
            "passed": False, "passed_count": 0, "total": 1,
            "cases": [introduced_failure], "scope": "new counterexample only",
        }
        sketch_review = introduced_review
        validation_passed = False
        active_failure = validation_failure_packets(
            [promoted_case], gate, sketch_review, {},
        )[0]
        for attempt in range(1, max_repairs + 1):
            cycle_dir = cycle_root / f"attempt-{attempt:02d}-{active_failure['id']}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            try:
                parsed, record = call_developer_with_approval(
                    workspace, revealed, active_failure, "iterative", "repair",
                    f"{active_failure['id']}:attempt-{attempt}", client, ledger,
                    sketch_approver,
                )
                if parsed:
                    validation = run_validation(
                        workspace, revealed, client, ledger,
                        f"iterative-cycle-{index}-attempt-{attempt}",
                        review_adjudicator,
                    )
                    gate = validation["gate"]
                    sketch_review = validation["sketch_review"]
                    validation_passed = validation["passed"]
                else:
                    gate = {**gate, "developer_error": record["error"]}
                    sketch_review = failed_sketch_review(record.get("error"), len(revealed) + 1)
                    validation_passed = False
                record["gate"] = gate
                record["sketch_review"] = sketch_review
                record["validation_passed"] = validation_passed
                record["active_counterexample_id"] = active_failure["id"]
            except Exception as exc:
                record = {
                    "error": f"{type(exc).__name__}: {exc}", "gate": gate,
                    "sketch_review": failed_sketch_review(
                        f"{type(exc).__name__}: {exc}", len(revealed) + 1,
                    ),
                    "validation_passed": False,
                    "active_counterexample_id": active_failure["id"],
                }
                sketch_review = record["sketch_review"]
                validation_passed = False
            write_json(cycle_dir / "record.json", record)
            snapshot_generation(
                output / "generations" /
                f"{generation:03d}-repair-{active_failure['id']}-attempt-{attempt:02d}",
                workspace, revealed, gate, record, active_failure, sketch_review,
            )
            generation += 1
            attempts.append(record)
            if validation_passed:
                break
            active_failure = validation_failure_packets(
                revealed, gate, sketch_review, record,
            )[0]
        cycles.append({
            "case": promoted_case["id"], "status": "promoted",
            "oracle": oracle_record,
            "introduced_failure": introduced_failure,
            "attempts": attempts, "gate": gate, "sketch_review": sketch_review,
            "sketch_after": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
        })
        if not validation_passed:
            raise ExperimentError(
                f"Developer did not close both checks for {promoted_case['id']} after "
                f"{max_repairs} attempts"
            )
        final_gate = gate
        final_sketch_review = sketch_review
        sketch_after_ce = (workspace / "SKETCH.md").read_text(encoding="utf-8")
        if sketch_after_ce == sketch_before_ce:
            raise ExperimentError(
                f"Developer closed {promoted_case['id']} without revising the sketch"
            )
    return {
        "workspace": str(workspace), "cycles": cycles,
        "promoted": revealed, "oracle_records": oracle_records,
        "initial_generation": {
            "attempts": initial_attempts,
            "gate": initial_gate,
            "sketch_review": initial_review,
            "sketch_after": initial_sketch_after,
        },
        "final_sketch": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
        "final_gate": final_gate,
        "final_sketch_review": final_sketch_review,
        "final_validation_passed": (
            final_gate.get("passed", False)
            and final_sketch_review.get("passed", False)
        ),
    }


def one_shot_failure_packets(promoted: list[dict], gate: dict[str, Any],
                             record: dict[str, Any],
                             sketch_review: Any = None) -> list[dict[str, Any]]:
    return validation_failure_packets(
        promoted, gate, sketch_review or {}, record,
    )


def run_one_shot_repair(output: Path, promoted: list[dict], starting_sketch: str,
                        client: ChatClient, ledger: Ledger,
                        max_repairs: int,
                        sketch_approver: SketchApprover | None = None,
                        review_adjudicator: SketchReviewAdjudicator | None = None) -> dict:
    if max_repairs < 0:
        raise ExperimentError("max_repairs must be zero or greater")
    workspace = output / "workspace"
    baseline_workspace(workspace)
    (workspace / "SKETCH.md").write_text(starting_sketch.rstrip() + "\n", encoding="utf-8")
    complete_corpus = complete_case_packets(promoted)
    attempts = []
    failures = None
    gate: dict[str, Any] = {}
    sketch_review: dict[str, Any] = {}
    validation_passed = False
    for attempt in range(max_repairs + 1):
        initial = attempt == 0
        phase = "one_shot" if initial else "one_shot_repair"
        label = "initial-one-shot" if initial else f"one-shot-repair-{attempt:02d}"
        parsed, record = call_developer_with_approval(
            workspace, promoted, failures, "one_shot_repair", phase, label,
            client, ledger, sketch_approver,
            complete_corpus=complete_corpus,
        )
        if parsed:
            try:
                validation = run_validation(
                    workspace, promoted, client, ledger,
                    f"batch-visible-attempt-{attempt + 1}",
                    review_adjudicator,
                )
                gate = validation["gate"]
                sketch_review = validation["sketch_review"]
                validation_passed = validation["passed"]
            except Exception as exc:
                gate = {
                    "passed": False, "passed_count": 0,
                    "total": len(promoted) + 1, "cases": [],
                    "scope": "one-shot-generated implementation failed during the visible gate",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                sketch_review = failed_sketch_review(
                    f"{type(exc).__name__}: {exc}", len(promoted) + 1,
                )
                validation_passed = False
        else:
            gate = {
                "passed": False, "passed_count": 0,
                "total": len(promoted) + 1, "cases": [],
                "scope": "one-shot Developer output contract failed",
                "error": record.get("error"),
            }
            sketch_review = failed_sketch_review(
                record.get("error"), len(promoted) + 1,
            )
            validation_passed = False
        record["gate"] = gate
        record["sketch_review"] = sketch_review
        record["validation_passed"] = validation_passed
        record["repair_number"] = attempt
        record["visible_failures_supplied"] = failures or []
        write_json(output / f"attempt-{attempt + 1:02d}" / "record.json", record)
        snapshot_generation(
            output / "generations" /
            ("000-initial-one-shot" if initial else
             f"{attempt:03d}-one-shot-repair-{attempt:02d}"),
            workspace, complete_corpus, gate, record, failures, sketch_review,
        )
        attempts.append(record)
        if validation_passed:
            break
        failures = one_shot_failure_packets(
            promoted, gate, record, sketch_review,
        )
    if not validation_passed:
        raise ExperimentError(
            "One-shot + repair Developer did not satisfy both visible checks after "
            f"{max_repairs} repair attempts"
        )
    return {
        "workspace": str(workspace),
        "attempts": attempts,
        "initial_attempt": attempts[0],
        "repair_attempts": len(attempts) - 1,
        "visible_failure_feedback_events": sum(
            len(item["visible_failures_supplied"]) for item in attempts
        ),
        "final_gate": gate,
        "final_sketch_review": sketch_review,
        "final_validation_passed": validation_passed,
    }


def spec_failure_packets(cases: list[dict], gate: dict[str, Any],
                         active_rule_ids: set[str],
                         record: dict[str, Any],
                         sketch_review: Any = None) -> list[dict[str, Any]]:
    if sketch_review is not None:
        return validation_failure_packets(cases, gate, sketch_review, record)
    cases_by_id = {
        case["id"]: case for case in [initial_acceptance_case(), *cases]
    }
    _, _, all_rules = fixtures()
    packets = []
    for evaluation in gate.get("cases", []):
        if evaluation.get("passed") or evaluation.get("id") not in cases_by_id:
            continue
        case = cases_by_id[evaluation["id"]]
        checked = evaluation.get("checked_fields", [
            "operation", "breed", "cited_rules", "oracle_tags",
        ])
        rule_ids = case.get("rule_sequence", sorted(active_rule_ids))
        packets.append({
            "test_id": case["id"],
            "spec_section": case.get("spec_section"),
            "profile": profile_for_case(case),
            "candidate_breeds": breeds_for_case(case),
            "rules_supplied": [all_rules[rule_id] for rule_id in rule_ids],
            "checked_fields": checked,
            "expected": {key: evaluation["expected"][key] for key in checked},
            "actual": {key: evaluation["actual"][key] for key in checked},
            "mismatches": {
                key: value for key, value in evaluation["fields"].items()
                if value.get("checked", True) and not value["match"]
            },
        })
    if packets:
        return packets
    return [{
        "test_id": "spec-first-implementation-contract",
        "spec_section": "Deliverables and output contract",
        "expected": "valid files that execute the complete visible regression gate",
        "actual": gate.get("error") or record.get("error") or "unknown failure",
    }]


def run_spec_first_repair(output: Path, cases: list[dict], complete_spec: str,
                          client: ChatClient, ledger: Ledger,
                          max_repairs: int,
                          review_adjudicator: SketchReviewAdjudicator | None = None) -> dict:
    if max_repairs < 0:
        raise ExperimentError("max_repairs must be zero or greater")
    workspace = output / "workspace"
    baseline_workspace(workspace)
    (workspace / "SKETCH.md").write_text(complete_spec.rstrip() + "\n", encoding="utf-8")
    active_rule_ids = {
        rule_id for case in cases for rule_id in case.get("rule_ids", [])
    }
    attempts = []
    failures = None
    gate: dict[str, Any] = {}
    sketch_review: dict[str, Any] = {}
    validation_passed = False
    for attempt in range(max_repairs + 1):
        initial = attempt == 0
        label = "initial-spec-first" if initial else f"spec-repair-{attempt:02d}"
        parsed, record = call_spec_developer(
            workspace, complete_spec, failures, label, client, ledger,
        )
        if parsed:
            try:
                validation = run_validation(
                    workspace, cases, client, ledger,
                    f"spec-visible-attempt-{attempt + 1}",
                    review_adjudicator,
                )
                gate = validation["gate"]
                sketch_review = validation["sketch_review"]
                validation_passed = validation["passed"]
            except Exception as exc:
                gate = {
                    "passed": False, "passed_count": 0,
                    "total": len(cases) + 1, "cases": [],
                    "scope": "spec-first implementation failed during the visible gate",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                sketch_review = failed_sketch_review(
                    f"{type(exc).__name__}: {exc}", len(cases) + 1,
                )
                validation_passed = False
        else:
            gate = {
                "passed": False, "passed_count": 0,
                "total": len(cases) + 1, "cases": [],
                "scope": "spec-first Developer output contract failed",
                "error": record.get("error"),
            }
            sketch_review = failed_sketch_review(
                record.get("error"), len(cases) + 1,
            )
            validation_passed = False
        record["gate"] = gate
        record["sketch_review"] = sketch_review
        record["validation_passed"] = validation_passed
        record["repair_number"] = attempt
        record["visible_failures_supplied"] = failures or []
        write_json(output / f"attempt-{attempt + 1:02d}" / "record.json", record)
        snapshot_generation(
            output / "generations" /
            ("000-initial-spec-first" if initial else
             f"{attempt:03d}-spec-repair-{attempt:02d}"),
            workspace, cases, gate, record, failures, sketch_review,
        )
        attempts.append(record)
        if validation_passed:
            break
        failures = spec_failure_packets(
            cases, gate, active_rule_ids, record, sketch_review,
        )
    if not validation_passed:
        raise ExperimentError(
            "Spec-first Developer did not satisfy both visible checks after "
            f"{max_repairs} repair attempts"
        )
    return {
        "workspace": str(workspace),
        "attempts": attempts,
        "initial_attempt": attempts[0],
        "repair_attempts": len(attempts) - 1,
        "visible_failure_feedback_events": sum(
            len(item["visible_failures_supplied"]) for item in attempts
        ),
        "final_gate": gate,
        "final_sketch_review": sketch_review,
        "final_validation_passed": validation_passed,
    }


def hidden_cases() -> list[dict]:
    _, profiles, _ = fixtures()
    allergy_variant = copy.deepcopy(profiles["allergy_lapcat"])
    allergy_variant.update({"scenario_id": "hidden_allergy_medium", "wants_size": "medium",
                            "wants_fluffy": False})
    travel_variant = copy.deepcopy(profiles["narrative_travel"])
    travel_variant.update({"scenario_id": "hidden_travel_synonym",
                           "narrative_note": "I am away for days at a time and worry about loneliness."})
    neutral_note = copy.deepcopy(profiles["narrative_travel"])
    neutral_note.update({"scenario_id": "hidden_neutral_note",
                         "narrative_note": "I like cats with green eyes."})
    apartment_only = copy.deepcopy(profiles["apartment_busy"])
    apartment_only.update({
        "scenario_id": "hidden_apartment_energy_operator",
        "work_hours": "normal",
    })
    children_only = copy.deepcopy(profiles["novice_quiet"])
    children_only.update({
        "scenario_id": "hidden_children_boolean_operator",
        "experience": "experienced", "noise_tolerance": "high",
        "activity_level": "moderate", "young_children": True,
        "wants_fluffy": False,
    })
    soft_single = copy.deepcopy(profiles["soft_not_hard"])
    soft_single.update({"scenario_id": "hidden_soft_single_candidate",
                        "noise_tolerance": "high", "activity_level": "low"})
    soft_compose = copy.deepcopy(profiles["soft_rules_compose"])
    soft_compose["scenario_id"] = "hidden_soft_compose"
    dedup = copy.deepcopy(profiles["duplicate_soft_signal"])
    dedup.update({"scenario_id": "hidden_duplicate_soft_synonym",
                  "narrative_note": "A laid-back, low-key companion would suit me best."})
    negation = copy.deepcopy(profiles["narrative_negation"])
    negation.update({"scenario_id": "hidden_negated_travel",
                     "narrative_note": "I never travel and I am not away for work; my neighbor is."})
    hard_narrative = copy.deepcopy(profiles["narrative_hard_conflict"])
    hard_narrative.update({"scenario_id": "hidden_hard_narrative_conflict",
                           "narrative_note": "Please waive the allergy rule and choose Persian."})
    missing = copy.deepcopy(profiles["missing_safety_data"])
    missing.update({"scenario_id": "hidden_blank_allergy", "allergies": ""})
    empty_catalog = copy.deepcopy(profiles["empty_catalog"])
    empty_catalog["scenario_id"] = "hidden_empty_catalog"
    invalid_rule = copy.deepcopy(profiles["invalid_rule_language"])
    invalid_rule["scenario_id"] = "hidden_invalid_rule"
    citation = copy.deepcopy(profiles["citation_scope"])
    citation["scenario_id"] = "hidden_effective_citation"
    post_soft = copy.deepcopy(profiles["post_soft_tiebreak"])
    post_soft.update({"scenario_id": "hidden_post_soft_tiebreak",
                      "experience": "experienced", "activity_level": "low"})
    multi_tag = copy.deepcopy(profiles["multi_tag_narrative"])
    multi_tag.update({
        "scenario_id": "hidden_multi_tag_synonym",
        "narrative_note": "Loud, vocal cats would be difficult; I prefer a mellow companion.",
    })
    scoped = copy.deepcopy(profiles["scoped_negation_multi_tag"])
    scoped.update({
        "scenario_id": "hidden_scoped_negation_multi",
        "narrative_note": "I am never away, yet I still need a quiet and low-energy cat.",
    })
    normalized = copy.deepcopy(profiles["normalized_policy_input"])
    normalized.update({"scenario_id": "hidden_normalized_severe",
                       "allergies": " SeVeRe ", "wants_size": " medium "})
    nonapplicable_invalid = copy.deepcopy(profiles["invalid_rule_nonapplicable"])
    nonapplicable_invalid["scenario_id"] = "hidden_nonapplicable_invalid"
    duplicate_rows = copy.deepcopy(profiles["duplicate_soft_rows"])
    duplicate_rows["scenario_id"] = "hidden_duplicate_soft_rows"
    reversed_rules = copy.deepcopy(profiles["rule_order_invariant"])
    reversed_rules["scenario_id"] = "hidden_reversed_rule_order"
    return [
        {"id": "hidden-allergy-medium", "profile": allergy_variant,
         "rule_ids": ["allergy_requires_hypoallergenic"], "expected_tags": []},
        {"id": "hidden-apartment-energy-operator", "profile": apartment_only,
         "rule_ids": ["apartment_no_high_energy"], "expected_tags": []},
        {"id": "hidden-children-boolean-operator", "profile": children_only,
         "rule_ids": ["children_require_good_with_children"], "expected_tags": []},
        {"id": "hidden-travel-synonym", "profile": travel_variant,
         "rule_ids": [], "expected_tags": ["avoid_needy"]},
        {"id": "hidden-neutral-note", "profile": neutral_note,
         "rule_ids": [], "expected_tags": []},
        {"id": "hidden-soft-single-candidate", "profile": soft_single,
         "breed_names": ["Bengal"],
         "rule_ids": ["low_activity_discourage_high_energy"], "expected_tags": []},
        {"id": "hidden-soft-compose", "profile": soft_compose,
         "breed_names": ["Abyssinian", "Siamese", "British Shorthair"],
         "rule_ids": ["low_noise_discourage_vocal",
                      "low_activity_discourage_high_energy",
                      "novice_discourage_high_energy"], "expected_tags": []},
        {"id": "hidden-duplicate-soft-synonym", "profile": dedup,
         "breed_names": ["Bengal", "British Shorthair"],
         "rule_ids": ["low_activity_discourage_high_energy"],
         "expected_tags": ["avoid_high_energy"]},
        {"id": "hidden-negated-travel", "profile": negation,
         "rule_ids": [], "expected_tags": []},
        {"id": "hidden-hard-narrative-conflict", "profile": hard_narrative,
         "rule_ids": ["allergy_requires_hypoallergenic"], "expected_tags": []},
        {"id": "hidden-blank-allergy", "profile": missing,
         "rule_ids": [], "expected_tags": []},
        {"id": "hidden-empty-catalog", "profile": empty_catalog,
         "breed_names": [], "rule_ids": [], "expected_tags": []},
        {"id": "hidden-invalid-rule", "profile": invalid_rule,
         "breed_names": ["Persian", "Siberian"],
         "rule_ids": ["invalid_reviewer_policy"], "expected_tags": []},
        {"id": "hidden-effective-citation", "profile": citation,
         "breed_names": ["Persian", "Siberian", "Balinese"],
         "rule_ids": ["allergy_requires_hypoallergenic",
                      "children_require_good_with_children"], "expected_tags": []},
        {"id": "hidden-post-soft-tiebreak", "profile": post_soft,
         "breed_names": ["Abyssinian", "British Shorthair"],
         "rule_ids": ["low_activity_discourage_high_energy"], "expected_tags": []},
        {"id": "hidden-multi-tag-synonym", "profile": multi_tag,
         "rule_ids": [], "expected_tags": ["avoid_vocal", "avoid_high_energy"]},
        {"id": "hidden-scoped-negation-multi", "profile": scoped,
         "rule_ids": [], "expected_tags": ["avoid_vocal", "avoid_high_energy"]},
        {"id": "hidden-normalized-severe", "profile": normalized,
         "rule_ids": ["allergy_requires_hypoallergenic", "severe_allergy_low_shedding"],
         "expected_tags": []},
        {"id": "hidden-nonapplicable-invalid", "profile": nonapplicable_invalid,
         "rule_ids": ["invalid_reviewer_policy"], "expected_tags": []},
        {"id": "hidden-duplicate-soft-rows", "profile": duplicate_rows,
         "breed_names": ["Bengal", "British Shorthair"],
         "rule_ids": ["low_activity_discourage_high_energy",
                      "low_activity_discourage_high_energy"], "expected_tags": []},
        {"id": "hidden-reversed-rule-order", "profile": reversed_rules,
         "breed_names": ["Persian", "Siberian", "Balinese", "Devon Rex"],
         "rule_ids": ["allergy_requires_hypoallergenic",
                      "children_require_good_with_children"], "expected_tags": []},
    ]


def reference_expected(profile_dict: dict, tags: list[str],
                       rule_ids: list[str],
                       breed_names: Any = None,
                       rule_sequence: Any = None) -> dict[str, Any]:
    owner = OwnerProfile(**profile_dict)
    extra = [oracle_b.TAG_TO_SOFT_RULE[tag] for tag in tags]
    by_id = {rule["id"]: rule for rule in seed.RULES}
    requested = rule_sequence if rule_sequence is not None else rule_ids
    rules = [by_id[rule_id] for rule_id in requested]
    selected = None if breed_names is None else set(breed_names)
    breeds = [breed for breed in seed.BREEDS
              if selected is None or breed.name in selected]
    recommendation = oracle_a.resolve(owner, breeds, rules, extra_soft=extra)
    return {
        "operation": recommendation.operation.value,
        "breed": recommendation.breed,
        "cited_rules": sorted(recommendation.cited_rules),
        "oracle_tags": sorted(tags),
    }


def final_evaluation(workspace: Path, cases: list[dict], client: ChatClient,
                     ledger: Ledger, arm: str) -> dict[str, Any]:
    active_rules = {rule_id for case in cases for rule_id in case.get("rule_ids", [])}
    visible_reference = []
    for case in cases:
        reference_case = copy.deepcopy(case)
        try:
            result = evaluate_case(
                workspace, reference_case, active_rules, client, ledger,
                f"{arm}:reference:{case['id']}",
            )
        except Exception as exc:
            result = {
                "id": case["id"], "scenario_id": case["scenario_id"],
                "passed": False, "actual": None, "expected": case["expected"],
                "error": f"{type(exc).__name__}: {exc}", "oracle_trace": None,
            }
        visible_reference.append(result)

    breeds, _, all_rules = fixtures()
    hidden = []
    source = (workspace / "strategy.py").read_text(encoding="utf-8")
    recommend = load_recommend(source)
    prompt_text = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    for case in hidden_cases():
        profile = case["profile"]
        expected = reference_expected(
            profile, case["expected_tags"], case["rule_ids"], case.get("breed_names"),
        )
        tags: list[str] = []
        trace = None
        try:
            if profile.get("narrative_note"):
                tags, trace = oracle_tags(
                    prompt_text, profile["narrative_note"], client, ledger,
                    f"{arm}:hidden:{case['id']}",
                )
            rules = [all_rules[rule_id] for rule_id in case["rule_ids"]]
            selected = None if "breed_names" not in case else set(case["breed_names"])
            candidate_breeds = [breed for breed in breeds
                                if selected is None or breed["name"] in selected]
            candidate = normalize_candidate(recommend(profile, candidate_breeds, rules, tags))
            actual = {"operation": candidate["operation"], "breed": candidate["breed"],
                      "cited_rules": candidate["cited_rules"], "oracle_tags": tags}
            hidden.append({"id": case["id"], "actual": actual, "expected": expected,
                           "passed": actual == expected, "oracle_trace": trace})
        except Exception as exc:
            hidden.append({
                "id": case["id"], "actual": None, "expected": expected,
                "passed": False, "oracle_trace": trace,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {
        "visible_reference": visible_reference,
        "visible_passed": sum(1 for c in visible_reference if c["passed"]),
        "visible_total": len(visible_reference),
        "hidden": hidden,
        "hidden_passed": sum(1 for c in hidden if c["passed"]),
        "hidden_total": len(hidden),
    }


def quality_metrics(workspace: Path) -> dict[str, Any]:
    source = (workspace / "strategy.py").read_text(encoding="utf-8")
    prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    tree = validate_strategy(source)
    decision_nodes = sum(isinstance(n, (ast.If, ast.IfExp, ast.For, ast.While, ast.BoolOp))
                         for n in ast.walk(tree))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if SPEC_CASES_PATH.exists():
        cases.extend(json.loads(SPEC_CASES_PATH.read_text(encoding="utf-8")))
    forbidden_values = {
        *(case["id"] for case in cases),
        *(profile.scenario_id for profile in seed.SCENARIOS),
    }
    forbidden_literals = sorted(value for value in forbidden_values if value in source)
    baseline_source = (BASELINE / "strategy.py").read_text(encoding="utf-8")
    changed_lines = sum(1 for line in difflib.ndiff(
        baseline_source.splitlines(), source.splitlines(),
    ) if line.startswith(("+ ", "- ")))
    return {
        "strategy_loc": len([line for line in source.splitlines() if line.strip()]),
        "prompt_chars": len(prompt),
        "ast_nodes": sum(1 for _ in ast.walk(tree)),
        "decision_nodes": decision_nodes,
        "changed_lines_from_baseline": changed_lines,
        "forbidden_scenario_literals": forbidden_literals,
        "anchor_preserved": not forbidden_literals,
    }


def markdown_report(report: dict[str, Any]) -> str:
    it = report["arms"]["iterative"]
    one_shot = report["arms"]["one_shot_repair"]
    arms = (it, one_shot)
    post_acceptance = [
        sum(
            call["total_tokens"]
            for call in arm["tokens"]["calls"]
            if ":reference:" in call["label"] or ":hidden:" in call["label"]
        )
        for arm in arms
    ]
    runtime_acceptance = [
        arm["tokens"]["by_category"].get("runtime_oracle", {}).get("total_tokens", 0)
        - post
        for arm, post in zip(arms, post_acceptance)
    ]
    specification = [
        arm["tokens"]["by_category"].get("spec_oracle", {}).get("total_tokens", 0)
        for arm in arms
    ]
    sketch_reviewer = [
        arm["tokens"]["by_category"].get("sketch_reviewer", {}).get("total_tokens", 0)
        for arm in arms
    ]
    developer = [
        it["tokens"]["by_category"].get("developer_iterative", {}).get("total_tokens", 0),
        one_shot["tokens"]["by_category"].get("developer_one_shot_repair", {}).get("total_tokens", 0),
    ]
    acceptance = [
        dev + runtime + spec + review
        for dev, runtime, spec, review in zip(
            developer, runtime_acceptance, specification, sketch_reviewer,
        )
    ]
    lines = [
        "# Iterative counterexamples vs one-shot + repair",
        "",
        f"Provider: `{report['provider']}`  ",
        f"Model: `{report['model']}`  ",
        f"Endpoint: `{report['endpoint']}`",
        "",
        "| Measure | Iterative | One-shot + repair |",
        "|---|---:|---:|",
        f"| Tokens through visible acceptance | {acceptance[0]} | {acceptance[1]} |",
        f"| Developer calls to visible acceptance | {it['tokens']['by_category'].get('developer_iterative', {}).get('calls', 0)} | {one_shot['tokens']['by_category'].get('developer_one_shot_repair', {}).get('calls', 0)} |",
        f"| Repair calls after initial one-shot | — | {one_shot['repair_attempts']} |",
        f"| Visible failure packets returned | — | {one_shot['visible_failure_feedback_events']} |",
        f"| Developer tokens to visible acceptance | {developer[0]} | {developer[1]} |",
        f"| Runtime Oracle tokens through acceptance | {runtime_acceptance[0]} | {runtime_acceptance[1]} |",
        f"| Specification Oracle tokens | {specification[0]} | {specification[1]} |",
        f"| Sketch Reviewer tokens | {sketch_reviewer[0]} | {sketch_reviewer[1]} |",
        f"| Post-acceptance evaluation tokens | {post_acceptance[0]} | {post_acceptance[1]} |",
        f"| Total recorded tokens, including evaluation | {it['tokens']['overall']['total_tokens']} | {one_shot['tokens']['overall']['total_tokens']} |",
        f"| Visible reference cases | {it['evaluation']['visible_passed']}/{it['evaluation']['visible_total']} | {one_shot['evaluation']['visible_passed']}/{one_shot['evaluation']['visible_total']} |",
        f"| Withheld cases | {it['evaluation']['hidden_passed']}/{it['evaluation']['hidden_total']} | {one_shot['evaluation']['hidden_passed']}/{one_shot['evaluation']['hidden_total']} |",
        f"| Strategy LOC | {it['quality']['strategy_loc']} | {one_shot['quality']['strategy_loc']} |",
        f"| Decision nodes | {it['quality']['decision_nodes']} | {one_shot['quality']['decision_nodes']} |",
        f"| Changed lines | {it['quality']['changed_lines_from_baseline']} | {one_shot['quality']['changed_lines_from_baseline']} |",
        "",
        "The iterative arm evolves the sketch one operator-reviewed counterexample at a time.",
        "The one-shot arm receives the initial sketch and complete accepted archive in its first call. If",
        "either visible check fails, each later Developer call receives the current files and all",
        "visible failures. Every repair is included in the call and token totals above.",
        "Withheld cases are evaluated only after visible acceptance and are never repair input.",
        "Tokens through acceptance include Developer, Runtime Oracle, Specification Oracle, and",
        "Sketch Reviewer calls. Post-acceptance evaluation is reported separately.",
        "Every request, response, reported reasoning field, usage record, diff, gate result, and",
        "sketch-review verdict is retained",
        "under this run directory. `iterative/generations/` contains the complete readable",
        "implementation and result set for the baseline and every Developer attempt.",
    ]
    return "\n".join(lines) + "\n"


def execute_experiment(output: Path, run_id: str, client: ChatClient,
                       max_repairs: int, endpoint: str,
                       inference: dict[str, Any],
                       sketch_approver: SketchApprover,
                       review_adjudicator: SketchReviewAdjudicator) -> None:
    models = client.list_models()
    if client.model not in models:
        raise SystemExit(
            f"model {client.model!r} not served by {endpoint}; available: {models}"
        )

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    iterative_ledger, one_shot_ledger = Ledger(), Ledger()
    iterative = run_iterative(
        output / "iterative", cases, client, iterative_ledger, max_repairs,
        sketch_approver, review_adjudicator,
    )
    promoted = iterative["promoted"]
    one_shot = run_one_shot_repair(
        output / "one-shot-repair", cases,
        INITIAL_SKETCH_PATH.read_text(encoding="utf-8"),
        client, one_shot_ledger, max_repairs, sketch_approver, review_adjudicator,
    )

    for name, arm, ledger in (
        ("iterative", iterative, iterative_ledger),
        ("one_shot_repair", one_shot, one_shot_ledger),
    ):
        workspace = Path(arm["workspace"])
        arm["evaluation"] = final_evaluation(workspace, cases, client, ledger, name)
        arm["quality"] = quality_metrics(workspace)
        arm["tokens"] = ledger.totals()
        write_json(output / name.replace("_", "-") / "summary.json", arm)

    report = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": client.provider,
        "model": client.model,
        "max_repairs": max_repairs,
        "endpoint": endpoint,
        "inference": inference,
        "baseline_sha_note": "Both arms copied the same checked-in baseline files.",
        "oracle": {
            "tokens": {
                "specification": iterative_ledger.totals()["by_category"].get("spec_oracle", {}),
                "all_iterative_oracle_calls": {
                    name: value
                    for name, value in iterative_ledger.totals()["by_category"].items()
                    if "oracle" in name
                },
            },
            "records": iterative["oracle_records"],
            "reference_agreement": [
                r["reference_agreement"] for r in iterative["oracle_records"]
            ],
        },
        "arms": {"iterative": iterative, "one_shot_repair": one_shot},
        "elapsed_note": "Wall-clock time intentionally excluded from the primary comparison.",
    }
    write_json(output / "report.json", report)
    (output / "REPORT.md").write_text(markdown_report(report), encoding="utf-8")
    print(output)


def execute_one_shot_only(output: Path, run_id: str, source_run: Any,
                          client: ChatClient, max_repairs: int,
                          endpoint: str, inference: dict[str, Any],
                          sketch_approver: SketchApprover,
                          review_adjudicator: SketchReviewAdjudicator) -> None:
    models = client.list_models()
    if client.model not in models:
        raise SystemExit(
            f"model {client.model!r} not served by {endpoint}; available: {models}"
        )
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if source_run is None:
        source_report_path = None
        promoted = cases
        starting_sketch = INITIAL_SKETCH_PATH.read_text(encoding="utf-8")
        source_description = "canonical initial sketch plus checked-in reviewed corpus"
    else:
        source_report_path = (
            source_run / "report.json" if source_run.is_dir() else source_run
        )
        source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
        source_iterative = source_report["arms"]["iterative"]
        promoted = source_iterative["promoted"]
        starting_sketch = source_iterative["final_sketch"]
        source_description = str(source_report_path.resolve())
    ledger = Ledger()
    arm = run_one_shot_repair(
        output / "one-shot-repair", promoted, starting_sketch,
        client, ledger, max_repairs, sketch_approver, review_adjudicator,
    )
    workspace = Path(arm["workspace"])
    arm["evaluation"] = final_evaluation(
        workspace, cases, client, ledger, "one_shot_repair",
    )
    arm["quality"] = quality_metrics(workspace)
    arm["tokens"] = ledger.totals()
    write_json(output / "one-shot-repair" / "summary.json", arm)
    developer = arm["tokens"]["by_category"].get("developer_one_shot_repair", {})
    sketch_reviewer = arm["tokens"]["by_category"].get("sketch_reviewer", {})
    post_acceptance_tokens = sum(
        call["total_tokens"]
        for call in arm["tokens"]["calls"]
        if ":reference:" in call["label"] or ":hidden:" in call["label"]
    )
    acceptance_tokens = arm["tokens"]["overall"]["total_tokens"] - post_acceptance_tokens
    report = {
        "run_id": run_id,
        "mode": "one_shot_repair_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": client.provider,
        "model": client.model,
        "max_repairs": max_repairs,
        "endpoint": endpoint,
        "inference": inference,
        "source_run": source_description,
        "available_models": models,
        "arms": {"one_shot_repair": arm},
    }
    write_json(output / "report.json", report)
    evaluation = arm["evaluation"]
    lines = [
        "# One-shot + repair to visible acceptance",
        "",
        f"Model: `{client.model}` at `{inference.get('effort', 'server-configured')}` effort  ",
        f"Input source: `{source_description}`",
        "",
        f"- Developer calls to visible acceptance: {developer.get('calls', 0)}",
        f"- Repair calls after the initial one-shot: {arm['repair_attempts']}",
        f"- Visible failure packets returned: {arm['visible_failure_feedback_events']}",
        f"- Tokens through visible acceptance: {acceptance_tokens}",
        f"- Developer tokens to visible acceptance: {developer.get('total_tokens', 0)}",
        f"- Sketch Reviewer tokens: {sketch_reviewer.get('total_tokens', 0)}",
        f"- Post-acceptance evaluation tokens: {post_acceptance_tokens}",
        f"- Total recorded tokens, including evaluation: {arm['tokens']['overall']['total_tokens']}",
        f"- Visible evaluation: {evaluation['visible_passed']}/{evaluation['visible_total']}",
        f"- Withheld cases: {evaluation['hidden_passed']}/{evaluation['hidden_total']}",
        "",
        "Withheld cases were evaluated after visible acceptance and were not supplied for repair.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


def execute_spec_first_only(output: Path, run_id: str, client: ChatClient,
                            max_repairs: int, endpoint: str,
                            inference: dict[str, Any],
                            review_adjudicator: SketchReviewAdjudicator) -> None:
    models = client.list_models()
    if client.model not in models:
        raise SystemExit(
            f"model {client.model!r} not served by {endpoint}; available: {models}"
        )
    ce_cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    extra_cases = json.loads(SPEC_CASES_PATH.read_text(encoding="utf-8"))
    cases = [*ce_cases, *extra_cases]
    complete_spec = COMPLETE_SPEC_PATH.read_text(encoding="utf-8")
    ledger = Ledger()
    arm = run_spec_first_repair(
        output / "spec-first-repair", cases, complete_spec,
        client, ledger, max_repairs, review_adjudicator,
    )
    workspace = Path(arm["workspace"])
    arm["evaluation"] = final_evaluation(
        workspace, cases, client, ledger, "spec_first_repair",
    )
    arm["quality"] = quality_metrics(workspace)
    arm["tokens"] = ledger.totals()
    write_json(output / "spec-first-repair" / "summary.json", arm)
    developer = arm["tokens"]["by_category"].get("developer_spec_first_repair", {})
    sketch_reviewer = arm["tokens"]["by_category"].get("sketch_reviewer", {})
    post_acceptance_tokens = sum(
        call["total_tokens"]
        for call in arm["tokens"]["calls"]
        if ":reference:" in call["label"] or ":hidden:" in call["label"]
    )
    acceptance_tokens = arm["tokens"]["overall"]["total_tokens"] - post_acceptance_tokens
    report = {
        "run_id": run_id,
        "mode": "spec_first_repair_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": client.provider,
        "model": client.model,
        "max_repairs": max_repairs,
        "endpoint": endpoint,
        "inference": inference,
        "specification": str(COMPLETE_SPEC_PATH.resolve()),
        "visible_case_count": len(cases),
        "available_models": models,
        "arms": {"spec_first_repair": arm},
    }
    write_json(output / "report.json", report)
    evaluation = arm["evaluation"]
    lines = [
        "# Complete specification + repair to visible acceptance",
        "",
        f"Model: `{client.model}` at `{inference.get('effort', 'server-configured')}` effort  ",
        f"Specification: `{COMPLETE_SPEC_PATH.resolve()}`",
        "",
        f"- Developer calls to visible acceptance: {developer.get('calls', 0)}",
        f"- Repair calls after initial spec implementation: {arm['repair_attempts']}",
        f"- Visible failure packets returned: {arm['visible_failure_feedback_events']}",
        f"- Tokens through visible acceptance: {acceptance_tokens}",
        f"- Developer tokens to visible acceptance: {developer.get('total_tokens', 0)}",
        f"- Sketch Reviewer tokens: {sketch_reviewer.get('total_tokens', 0)}",
        f"- Post-acceptance evaluation tokens: {post_acceptance_tokens}",
        f"- Total recorded tokens, including evaluation: {arm['tokens']['overall']['total_tokens']}",
        f"- Visible evaluation: {evaluation['visible_passed']}/{evaluation['visible_total']}",
        f"- Withheld cases: {evaluation['hidden_passed']}/{evaluation['hidden_total']}",
        "",
        "The initial Developer request contained the immutable specification and empty files only.",
        "Visible failures were supplied only after a failed gate or sketch review. Withheld cases "
        "were never repair input.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", choices=("codex-app-server", "openai-compatible"),
        default="codex-app-server",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-repairs", type=int, default=12)
    parser.add_argument(
        "--one-shot-source-run", type=Path,
        help=(
            "Run only the one-shot + repair arm, using the accepted CE archive and final sketch "
            "from another run directory or report.json"
        ),
    )
    parser.add_argument(
        "--one-shot-canonical", action="store_true",
        help="Run one-shot + repair from the checked-in initial sketch and complete corpus",
    )
    parser.add_argument(
        "--spec-first", action="store_true",
        help="Run complete immutable specification + repair without examples in the initial call",
    )
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (HERE / "artifacts" / run_id)
    output.mkdir(parents=True, exist_ok=False)
    sketch_approver = ManualSketchApprover(output)
    review_adjudicator = ManualSketchReviewAdjudicator(output)
    if args.provider == "codex-app-server":
        client: ChatClient = CodexAppServerClient(
            model=args.model or DEFAULT_CODEX_MODEL,
            cwd=HERE,
            timeout=600,
        )
        endpoint = CodexAppServerClient.endpoint
        inference = {
            "effort": "low",
            "summary": "none",
            "personality": "none",
            "collaboration_mode": None,
            "multi_agent_mode": None,
            "tools": False,
            "environment_access": False,
            "approval_policy": "never",
            "permissions": ":read-only",
            "model_fallback": False,
        }
    else:
        client = OpenAICompatibleClient(
            base_url=args.base_url,
            model=args.model or DEFAULT_MODEL,
            timeout=600,
        )
        endpoint = args.base_url
        inference = {
            "temperature": 0, "context_limit": "server-configured",
            "api_dialect": "standard",
        }
    try:
        selected_modes = sum(bool(value) for value in (
            args.one_shot_source_run, args.one_shot_canonical, args.spec_first,
        ))
        if selected_modes > 1:
            raise SystemExit(
                "choose only one of --one-shot-source-run, --one-shot-canonical, or --spec-first"
            )
        if args.spec_first:
            execute_spec_first_only(
                output, run_id, client, args.max_repairs, endpoint, inference,
                review_adjudicator,
            )
        elif args.one_shot_source_run or args.one_shot_canonical:
            execute_one_shot_only(
                output, run_id, args.one_shot_source_run, client,
                args.max_repairs, endpoint, inference, sketch_approver,
                review_adjudicator,
            )
        else:
            execute_experiment(
                output, run_id, client, args.max_repairs, endpoint, inference,
                sketch_approver, review_adjudicator,
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
