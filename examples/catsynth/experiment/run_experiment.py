"""Run the paired coding-agent experiment and capture the complete evidence trail.

Arm A reveals one counterexample at a time and lets the Developer repair until
the promoted gate passes. Arm B gives the same model the initial sketch and full
reviewed corpus once, then repairs every visible failure until the same gate
passes. Both start from the byte-identical clean-room baseline and use the same
provider, model, fixtures, inference settings, and final evaluator.
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
from typing import Any, Protocol

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
    },
    "required": ["strategy_py", "oracle_prompt", "sketch_md"],
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


def developer_messages(workspace: Path, promoted: list[dict], active_failure: Any,
                       arm: str, phase: str,
                       complete_corpus: Any = None) -> list[dict[str, str]]:
    del promoted
    strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    sketch = (workspace / "SKETCH.md").read_text(encoding="utf-8")
    if phase == "initial":
        task = (
            "Generate the initial implementation from the sketch. You may clarify or reorganize the "
            "sketch while preserving its policy. Return compact JSON with exactly three string keys: "
            "strategy_py, oracle_prompt, and sketch_md. Each value is a complete file."
        )
    elif phase == "one_shot":
        task = (
            "Generate the complete implementation from the initial sketch and complete corpus in one "
            "shot. Return compact JSON with exactly three string keys: strategy_py, oracle_prompt, "
            "and sketch_md."
        )
    elif phase == "one_shot_repair":
        task = (
            "Revise the current sketch and implementation to close every supplied failing "
            "counterexample while preserving cases that already pass. Return compact JSON with "
            "exactly three string keys: strategy_py, oracle_prompt, and sketch_md. Each value must "
            "be the complete replacement file."
        )
    else:
        task = (
            "Revise the sketch and implementation as you see fit to close the one active failing "
            "counterexample while preserving prior behavior. Return compact JSON with exactly three "
            "string keys: strategy_py, oracle_prompt, and sketch_md. Each value must be the complete "
            "replacement file."
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
            "sketch, code, prompt, and complete set of visible gate failures. Close those failures "
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
            "already passes the regression gate. JSON only."
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
            "oracle_prompt must contain {note} and return JSON with a tags array; only use tag meanings defined by the current sketch or supplied counterexamples.",
        ],
        "known_code_contract": known_code_contract(),
        "current_sketch_md": sketch,
        "active_failing_counterexample": (
            active_failure if phase != "one_shot_repair" else None
        ),
        "current_strategy_py": strategy,
        "current_oracle_prompt": prompt,
    }
    if phase == "one_shot":
        payload["complete_corpus"] = complete_corpus
    elif phase == "one_shot_repair":
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
    if set(parsed) != {"strategy_py", "oracle_prompt", "sketch_md"}:
        raise ExperimentError(
            "Developer JSON must contain exactly strategy_py, oracle_prompt, and sketch_md"
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
        diffs = apply_developer(workspace, parsed)
    except Exception as exc:
        record.update({"error": f"{type(exc).__name__}: {exc}", "parsed_keys": [], "diffs": {}})
        return {}, record
    record.update({"error": None, "parsed_keys": sorted(parsed), "diffs": diffs})
    return parsed, record


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
        "visible_gate_failures": failures,
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
        "specification remains immutable. Use the current files and visible gate failures. JSON only."
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
                        active_failure: Any = None) -> None:
    path.mkdir(parents=True, exist_ok=False)
    shutil.copy2(workspace / "strategy.py", path / "strategy.py")
    shutil.copy2(workspace / "oracle_prompt.txt", path / "oracle_prompt.txt")
    shutil.copy2(workspace / "SKETCH.md", path / "SKETCH.md")
    write_json(path / "corpus.json", promoted)
    write_json(path / "gate.json", gate)
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
                  ledger: Ledger, max_repairs: int) -> dict:
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
    for attempt in range(max_repairs + 1):
        phase = "initial" if attempt == 0 else "repair"
        label = "initial-generation" if attempt == 0 else f"initial-repair-{attempt:02d}"
        parsed, record = call_developer(
            workspace, [], active_failure, "iterative", phase, label,
            client, ledger,
        )
        if parsed:
            try:
                initial_gate = run_gate(
                    workspace, [], client, ledger,
                    f"iterative-initial-acceptance-attempt-{attempt + 1}",
                )
                initial_gate["scope"] = "initial sketch acceptance"
            except Exception as exc:
                initial_gate = {
                    "passed": False, "passed_count": 0, "total": 1, "cases": [],
                    "scope": "initial sketch acceptance",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        else:
            initial_gate = {
                "passed": False, "passed_count": 0, "total": 0, "cases": [],
                "scope": "initial generation contract",
                "error": record.get("error"),
            }
        record["gate"] = initial_gate
        record["active_counterexample_id"] = (
            active_failure["id"] if active_failure is not None else None
        )
        snapshot_name = (
            "000-initial-generation" if attempt == 0 else
            f"{generation:03d}-repair-initial-preference-ranking-attempt-{attempt:02d}"
        )
        snapshot_generation(
            output / "generations" / snapshot_name,
            workspace, [], initial_gate, record, active_failure,
        )
        initial_attempts.append(record)
        generation += 1
        if initial_gate["passed"]:
            break
        active_failure = initial_failure(initial_gate, record)
    if not initial_gate["passed"]:
        raise ExperimentError(
            "Developer did not satisfy the initial sketch after "
            f"{max_repairs} repair attempts"
        )
    initial_sketch_after = (workspace / "SKETCH.md").read_text(encoding="utf-8")

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
        if introduced_failure["passed"]:
            coverage_gate = run_gate(
                workspace, revealed, client, ledger,
                f"iterative-cycle-{index}-coverage-check",
            )
            coverage = {
                "case": case["id"], "status": "coverage-not-promoted",
                "introduced_failure": introduced_failure,
                "attempts": [], "gate": coverage_gate,
                "sketch_after": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
            }
            write_json(cycle_root / "coverage.json", coverage)
            cycles.append(coverage)
            continue
        promoted_case, oracle_record = call_oracle(
            case, introduced_failure["actual"], client, ledger,
        )
        oracle_records.append(oracle_record)
        write_json(output / "oracle" / f"{index:02d}-{case['id']}.json", oracle_record)
        revealed.append(promoted_case)
        attempts = []
        target_case = promoted_case
        target_evaluation = introduced_failure
        gate = {
            "passed": False, "passed_count": 0, "total": 1,
            "cases": [introduced_failure], "scope": "new counterexample only",
        }
        for attempt in range(1, max_repairs + 1):
            active_failure = failure_packet(target_case, target_evaluation)
            cycle_dir = cycle_root / f"attempt-{attempt:02d}-{target_case['id']}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            try:
                parsed, record = call_developer(
                    workspace, revealed, active_failure, "iterative", "repair",
                    f"{target_case['id']}:attempt-{attempt}", client, ledger,
                )
                if parsed:
                    gate = run_gate(
                        workspace, revealed, client, ledger,
                        f"iterative-cycle-{index}-attempt-{attempt}",
                    )
                else:
                    gate = {**gate, "developer_error": record["error"]}
                record["gate"] = gate
                record["active_counterexample_id"] = target_case["id"]
            except Exception as exc:
                record = {
                    "error": f"{type(exc).__name__}: {exc}", "gate": gate,
                    "active_counterexample_id": target_case["id"],
                }
            write_json(cycle_dir / "record.json", record)
            snapshot_generation(
                output / "generations" /
                f"{generation:03d}-repair-{target_case['id']}-attempt-{attempt:02d}",
                workspace, revealed, gate, record, active_failure,
            )
            generation += 1
            attempts.append(record)
            if gate["passed"]:
                break
            failed = next(item for item in gate["cases"] if not item["passed"])
            target_case = next(
                item for item in [initial_acceptance_case(), *revealed]
                if item["id"] == failed["id"]
            )
            target_evaluation = failed
        cycles.append({
            "case": promoted_case["id"], "status": "promoted",
            "oracle": oracle_record,
            "introduced_failure": introduced_failure,
            "attempts": attempts, "gate": gate,
            "sketch_after": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
        })
        if not gate["passed"]:
            raise ExperimentError(
                f"Developer did not close {promoted_case['id']} after {max_repairs} attempts"
            )
    return {
        "workspace": str(workspace), "cycles": cycles,
        "promoted": revealed, "oracle_records": oracle_records,
        "initial_generation": {
            "attempts": initial_attempts,
            "gate": initial_gate,
            "sketch_after": initial_sketch_after,
        },
        "final_sketch": (workspace / "SKETCH.md").read_text(encoding="utf-8"),
        "final_gate": run_gate(workspace, revealed, client, ledger, "iterative-final"),
    }


def one_shot_failure_packets(promoted: list[dict], gate: dict[str, Any],
                             record: dict[str, Any]) -> list[dict[str, Any]]:
    cases_by_id = {
        case["id"]: case for case in [initial_acceptance_case(), *promoted]
    }
    packets = [
        failure_packet(cases_by_id[item["id"]], item)
        for item in gate.get("cases", [])
        if not item.get("passed") and item.get("id") in cases_by_id
    ]
    if packets:
        return packets
    return [{
        "id": "one-shot-generated-implementation",
        "failure_kind": "developer-output-or-runtime-contract",
        "expected": "valid files that pass the complete visible regression gate",
        "actual": gate.get("error") or record.get("error") or "unknown failure",
        "mismatches": {"execution": {
            "expected": "a valid implementation that passes the visible gate",
            "actual": gate.get("error") or record.get("error") or "unknown failure",
            "match": False,
        }},
    }]


def run_one_shot_repair(output: Path, promoted: list[dict], starting_sketch: str,
                        client: ChatClient, ledger: Ledger,
                        max_repairs: int) -> dict:
    if max_repairs < 0:
        raise ExperimentError("max_repairs must be zero or greater")
    workspace = output / "workspace"
    baseline_workspace(workspace)
    (workspace / "SKETCH.md").write_text(starting_sketch.rstrip() + "\n", encoding="utf-8")
    complete_corpus = complete_case_packets(promoted)
    attempts = []
    failures = None
    gate: dict[str, Any] = {}
    for attempt in range(max_repairs + 1):
        initial = attempt == 0
        phase = "one_shot" if initial else "one_shot_repair"
        label = "initial-one-shot" if initial else f"one-shot-repair-{attempt:02d}"
        parsed, record = call_developer(
            workspace, promoted, failures, "one_shot_repair", phase, label,
            client, ledger, complete_corpus=complete_corpus if initial else None,
        )
        if parsed:
            try:
                gate = run_gate(
                    workspace, promoted, client, ledger,
                    f"batch-visible-gate-attempt-{attempt + 1}",
                )
            except Exception as exc:
                gate = {
                    "passed": False, "passed_count": 0,
                    "total": len(promoted) + 1, "cases": [],
                    "scope": "one-shot-generated implementation failed during the visible gate",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        else:
            gate = {
                "passed": False, "passed_count": 0,
                "total": len(promoted) + 1, "cases": [],
                "scope": "one-shot Developer output contract failed",
                "error": record.get("error"),
            }
        record["gate"] = gate
        record["repair_number"] = attempt
        record["visible_failures_supplied"] = failures or []
        write_json(output / f"attempt-{attempt + 1:02d}" / "record.json", record)
        snapshot_generation(
            output / "generations" /
            ("000-initial-one-shot" if initial else
             f"{attempt:03d}-one-shot-repair-{attempt:02d}"),
            workspace, complete_corpus, gate, record, failures,
        )
        attempts.append(record)
        if gate["passed"]:
            break
        failures = one_shot_failure_packets(promoted, gate, record)
    if not gate["passed"]:
        raise ExperimentError(
            "One-shot + repair Developer did not satisfy the visible regression gate after "
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
    }


def spec_failure_packets(cases: list[dict], gate: dict[str, Any],
                         active_rule_ids: set[str],
                         record: dict[str, Any]) -> list[dict[str, Any]]:
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
                          max_repairs: int) -> dict:
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
    for attempt in range(max_repairs + 1):
        initial = attempt == 0
        label = "initial-spec-first" if initial else f"spec-repair-{attempt:02d}"
        parsed, record = call_spec_developer(
            workspace, complete_spec, failures, label, client, ledger,
        )
        if parsed:
            try:
                gate = run_gate(
                    workspace, cases, client, ledger,
                    f"spec-visible-gate-attempt-{attempt + 1}",
                )
            except Exception as exc:
                gate = {
                    "passed": False, "passed_count": 0,
                    "total": len(cases) + 1, "cases": [],
                    "scope": "spec-first implementation failed during the visible gate",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        else:
            gate = {
                "passed": False, "passed_count": 0,
                "total": len(cases) + 1, "cases": [],
                "scope": "spec-first Developer output contract failed",
                "error": record.get("error"),
            }
        record["gate"] = gate
        record["repair_number"] = attempt
        record["visible_failures_supplied"] = failures or []
        write_json(output / f"attempt-{attempt + 1:02d}" / "record.json", record)
        snapshot_generation(
            output / "generations" /
            ("000-initial-spec-first" if initial else
             f"{attempt:03d}-spec-repair-{attempt:02d}"),
            workspace, cases, gate, record, failures,
        )
        attempts.append(record)
        if gate["passed"]:
            break
        failures = spec_failure_packets(cases, gate, active_rule_ids, record)
    if not gate["passed"]:
        raise ExperimentError(
            "Spec-first Developer did not satisfy the visible regression gate after "
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
    developer = [
        it["tokens"]["by_category"].get("developer_iterative", {}).get("total_tokens", 0),
        one_shot["tokens"]["by_category"].get("developer_one_shot_repair", {}).get("total_tokens", 0),
    ]
    acceptance = [
        dev + runtime + spec
        for dev, runtime, spec in zip(developer, runtime_acceptance, specification)
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
        f"| Post-acceptance evaluation tokens | {post_acceptance[0]} | {post_acceptance[1]} |",
        f"| Total recorded tokens, including evaluation | {it['tokens']['overall']['total_tokens']} | {one_shot['tokens']['overall']['total_tokens']} |",
        f"| Visible reference cases | {it['evaluation']['visible_passed']}/{it['evaluation']['visible_total']} | {one_shot['evaluation']['visible_passed']}/{one_shot['evaluation']['visible_total']} |",
        f"| Hidden-suite pass rate | {it['evaluation']['hidden_passed']}/{it['evaluation']['hidden_total']} | {one_shot['evaluation']['hidden_passed']}/{one_shot['evaluation']['hidden_total']} |",
        f"| Strategy LOC | {it['quality']['strategy_loc']} | {one_shot['quality']['strategy_loc']} |",
        f"| Decision nodes | {it['quality']['decision_nodes']} | {one_shot['quality']['decision_nodes']} |",
        f"| Changed lines | {it['quality']['changed_lines_from_baseline']} | {one_shot['quality']['changed_lines_from_baseline']} |",
        "",
        "The iterative arm discovers the specification one counterexample at a time. The",
        "one-shot arm receives the initial sketch and complete reviewed corpus in its first call. If",
        "the visible gate fails, each later Developer call receives the current files and all",
        "visible failures. Every repair is included in the call and token totals above.",
        "Hidden cases are evaluated only after visible acceptance and are never repair input.",
        "Tokens through acceptance include Developer, Runtime Oracle, and Specification Oracle",
        "calls. Post-acceptance visible and hidden evaluation is reported separately.",
        "Every request, response, reported reasoning field, usage record, diff, and gate result is retained",
        "under this run directory. `iterative/generations/` contains the complete readable",
        "implementation and result set for the baseline and every Developer attempt.",
    ]
    return "\n".join(lines) + "\n"


def execute_experiment(output: Path, run_id: str, client: ChatClient,
                       max_repairs: int, endpoint: str,
                       inference: dict[str, Any]) -> None:
    models = client.list_models()
    if client.model not in models:
        raise SystemExit(
            f"model {client.model!r} not served by {endpoint}; available: {models}"
        )

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    iterative_ledger, one_shot_ledger = Ledger(), Ledger()
    iterative = run_iterative(
        output / "iterative", cases, client, iterative_ledger, max_repairs,
    )
    promoted = iterative["promoted"]
    one_shot = run_one_shot_repair(
        output / "one-shot-repair", cases,
        INITIAL_SKETCH_PATH.read_text(encoding="utf-8"),
        client, one_shot_ledger, max_repairs,
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
                          endpoint: str, inference: dict[str, Any]) -> None:
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
        client, ledger, max_repairs,
    )
    workspace = Path(arm["workspace"])
    arm["evaluation"] = final_evaluation(
        workspace, cases, client, ledger, "one_shot_repair",
    )
    arm["quality"] = quality_metrics(workspace)
    arm["tokens"] = ledger.totals()
    write_json(output / "one-shot-repair" / "summary.json", arm)
    developer = arm["tokens"]["by_category"].get("developer_one_shot_repair", {})
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
        f"- Post-acceptance evaluation tokens: {post_acceptance_tokens}",
        f"- Total recorded tokens, including evaluation: {arm['tokens']['overall']['total_tokens']}",
        f"- Visible evaluation: {evaluation['visible_passed']}/{evaluation['visible_total']}",
        f"- Hidden-suite pass rate: {evaluation['hidden_passed']}/{evaluation['hidden_total']}",
        "",
        "Hidden cases were evaluated after visible acceptance and were not supplied for repair.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


def execute_spec_first_only(output: Path, run_id: str, client: ChatClient,
                            max_repairs: int, endpoint: str,
                            inference: dict[str, Any]) -> None:
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
        client, ledger, max_repairs,
    )
    workspace = Path(arm["workspace"])
    arm["evaluation"] = final_evaluation(
        workspace, cases, client, ledger, "spec_first_repair",
    )
    arm["quality"] = quality_metrics(workspace)
    arm["tokens"] = ledger.totals()
    write_json(output / "spec-first-repair" / "summary.json", arm)
    developer = arm["tokens"]["by_category"].get("developer_spec_first_repair", {})
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
        f"- Post-acceptance evaluation tokens: {post_acceptance_tokens}",
        f"- Total recorded tokens, including evaluation: {arm['tokens']['overall']['total_tokens']}",
        f"- Visible evaluation: {evaluation['visible_passed']}/{evaluation['visible_total']}",
        f"- Hidden-suite pass rate: {evaluation['hidden_passed']}/{evaluation['hidden_total']}",
        "",
        "The initial Developer request contained the immutable specification and empty files only.",
        "Visible failures were supplied only after a failed gate. Hidden cases were never repair input.",
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
            "Run only the one-shot + repair arm, using the promoted corpus and final sketch "
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
            )
        elif args.one_shot_source_run or args.one_shot_canonical:
            execute_one_shot_only(
                output, run_id, args.one_shot_source_run, client,
                args.max_repairs, endpoint, inference,
            )
        else:
            execute_experiment(
                output, run_id, client, args.max_repairs, endpoint, inference,
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
