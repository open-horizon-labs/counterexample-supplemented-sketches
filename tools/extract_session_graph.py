#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "task-line-parser"
OUT = ROOT / "build" / "session-graph.json"
RNA_DIR = ROOT / ".oh" / "knowledge" / "task-line-parser"


@dataclass(frozen=True)
class CeMapping:
    slug: str
    title: str
    test_selector: str
    execution_selectors: list[str]
    tempting_patch: str
    handled_by: str


MAPPINGS = [
    CeMapping(
        slug="first-prefix-only-is-status",
        title="First prefix only is status",
        test_selector="examples/task-line-parser/tests/test_parse_task_line.py:61-66",
        execution_selectors=["examples/task-line-parser/generated/parse_task_line.py:31-37", "examples/task-line-parser/generated/parse_task_line.py:43-44"],
        tempting_patch="split on every colon and treat a later status-looking prefix as a second status",
        handled_by="`str.partition(':')` selects only the first colon; non-blocked bodies remain title text.",
    ),
    CeMapping(
        slug="blocked-reason-cannot-be-empty",
        title="Blocked reason requires text",
        test_selector="examples/task-line-parser/tests/test_parse_task_line.py:82-90",
        execution_selectors=["examples/task-line-parser/generated/parse_task_line.py:46-55"],
        tempting_patch="accept a blank blocked reason after `|`",
        handled_by="Blocked tasks partition on `|`, trim reason, and return `Err(empty_reason)` when it is blank.",
    ),
    CeMapping(
        slug="empty-title-rejects",
        title="Empty title rejects",
        test_selector="examples/task-line-parser/tests/test_parse_task_line.py:103-112",
        execution_selectors=["examples/task-line-parser/generated/parse_task_line.py:39-41", "examples/task-line-parser/generated/parse_task_line.py:50-53"],
        tempting_patch="return an empty task title as a valid record",
        handled_by="The parser rejects blank body text before status-specific handling and rejects blank blocked titles after `|` splitting.",
    ),
    CeMapping(
        slug="pipe-is-only-special-for-blocked",
        title="Pipe is only special for blocked",
        test_selector="examples/task-line-parser/tests/test_parse_task_line.py:68-80",
        execution_selectors=["examples/task-line-parser/generated/parse_task_line.py:43-44", "examples/task-line-parser/generated/parse_task_line.py:46-57"],
        tempting_patch="parse `|` as a reason for todo/done statuses",
        handled_by="The parser returns todo/done body text before pipe parsing; only blocked enters the pipe/reason branch.",
    ),
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_span_for_heading(path: Path, heading: str) -> str:
    lines = read(path).splitlines()
    start = None
    for index, line in enumerate(lines, start=1):
        if line.strip() == f"## {heading}":
            start = index
            break
    if start is None:
        raise SystemExit(f"missing counterexample heading: {heading}")
    end = len(lines)
    for index in range(start + 1, len(lines) + 1):
        if lines[index - 1].startswith("## "):
            end = index - 1
            break
    return f"examples/task-line-parser/counterexamples.md:{start}-{end}"


def node(node_id: str, kind: str, name: str, selector: str | None = None, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"id": node_id, "kind": kind, "name": name}
    if selector:
        payload["selector"] = selector
    payload.update(extra)
    return payload


def edge(source: str, relation: str, target: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"source": source, "relation": relation, "target": target}
    payload.update(extra)
    return payload


def build_graph() -> dict[str, object]:
    nodes: list[dict[str, object]] = [
        node("session.task-line-parser", "agent_session", "Task-line parser clean-room session", "examples/task-line-parser"),
        node("sketch.task-line-parser", "sketch", "Task line parser sketch", "examples/task-line-parser/sketch.md"),
        node("known-code.result", "known_code_anchor", "Ok/Err result shape", "examples/task-line-parser/known_code/result.py"),
        node("implementation.parse-task-line", "generated_artifact", "parse_task_line implementation", "examples/task-line-parser/generated/parse_task_line.py"),
    ]
    edges: list[dict[str, object]] = [
        edge("session.task-line-parser", "contains", "sketch.task-line-parser"),
        edge("sketch.task-line-parser", "anchors", "implementation.parse-task-line"),
        edge("known-code.result", "constrains", "implementation.parse-task-line"),
    ]

    for mapping in MAPPINGS:
        ce_id = f"ce.task-line-parser.{mapping.slug}"
        test_id = f"test.task-line-parser.{mapping.slug}"
        ce_selector = line_span_for_heading(EXAMPLE / "counterexamples.md", mapping.title)
        nodes.append(node(ce_id, "counterexample", mapping.title, ce_selector, tempting_patch=mapping.tempting_patch))
        nodes.append(node(test_id, "verification_check", mapping.title, mapping.test_selector))
        edges.extend([
            edge("session.task-line-parser", "contains", ce_id),
            edge(ce_id, "tests_tempting_patch", mapping.tempting_patch),
            edge(ce_id, "verified_by", test_id),
            edge(test_id, "verifies", "implementation.parse-task-line"),
        ])
        for idx, selector in enumerate(mapping.execution_selectors, start=1):
            ep_id = f"execution.task-line-parser.{mapping.slug}.{idx}"
            nodes.append(node(ep_id, "execution_point", f"{mapping.title} handler {idx}", selector, handling=mapping.handled_by))
            edges.extend([
                edge(ce_id, "handled_by", ep_id),
                edge(ep_id, "implemented_in", "implementation.parse-task-line"),
            ])

    return {"graph": "sketch-counterexample-agent-session", "nodes": nodes, "edges": edges}


def write_rna_nodes(graph: dict[str, object]) -> None:
    RNA_DIR.mkdir(parents=True, exist_ok=True)
    nodes = graph["nodes"]
    edges = graph["edges"]
    for item in nodes:  # type: ignore[assignment]
        node_id = item["id"]
        outgoing = [e for e in edges if e["source"] == node_id]  # type: ignore[index]
        path = RNA_DIR / f"{node_id}.md"
        content = ["---", "rna:", f"  kind: {item['kind']}", f"  id: {node_id}", f"  name: {json.dumps(item['name'])}"]
        if "selector" in item:
            content.append(f"  selector: {json.dumps(item['selector'])}")
        if outgoing:
            content.append("  relationships:")
            for relation in outgoing:
                content.append(f"    - kind: {relation['relation']}")
                content.append(f"      target: {relation['target']}")
        content.extend(["---", "", f"# {item['name']}", ""])
        if "tempting_patch" in item:
            content.append(f"Tempting patch this counterexample fails: {item['tempting_patch']}")
        if "handling" in item:
            content.append(f"Handling: {item['handling']}")
        content.append("")
        path.write_text("\n".join(content), encoding="utf-8")


def answer_ce(graph: dict[str, object], query: str) -> str:
    nodes = {n["id"]: n for n in graph["nodes"]}  # type: ignore[index]
    edges = graph["edges"]  # type: ignore[assignment]
    matches = [n for n in graph["nodes"] if n["kind"] == "counterexample" and (query in n["id"] or query.lower() in str(n["name"]).lower())]  # type: ignore[index]
    if not matches:
        raise SystemExit(f"no counterexample matched: {query}")
    ce = matches[0]
    ce_id = ce["id"]
    lines = [f"Counterexample: {ce['name']}", f"Source: {ce['selector']}", f"Tempting patch: {ce['tempting_patch']}", "Handled by:"]
    for relation in edges:
        if relation["source"] == ce_id and relation["relation"] == "handled_by":
            target = nodes[relation["target"]]
            lines.append(f"- {target['selector']}: {target.get('handling', target['name'])}")
    lines.append("Verified by:")
    for relation in edges:
        if relation["source"] == ce_id and relation["relation"] == "verified_by":
            target = nodes[relation["target"]]
            lines.append(f"- {target['selector']}: {target['name']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--ce")
    args = parser.parse_args()
    graph = build_graph()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
        write_rna_nodes(graph)
        print(OUT)
    if args.ce:
        print(answer_ce(graph, args.ce))
    if not args.write and not args.ce:
        print(json.dumps(graph, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
