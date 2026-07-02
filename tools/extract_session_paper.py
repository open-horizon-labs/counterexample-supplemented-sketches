#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "build" / "session-graph.json"
OUT = ROOT / "paper" / "extracted-session-paper.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def repo_path(selector: str) -> tuple[Path, str | None]:
    if ":" not in selector:
        return ROOT / selector, None
    path, lines = selector.rsplit(":", 1)
    if "-" in lines and all(part.isdigit() for part in lines.split("-", 1)):
        return ROOT / path, lines
    return ROOT / selector, None


def snippet(selector: str) -> str:
    path, span = repo_path(selector)
    text = read(path)
    if not span:
        return text.strip()
    start_s, end_s = span.split("-", 1)
    start = int(start_s)
    end = int(end_s)
    lines = text.splitlines()
    return "\n".join(lines[start - 1 : end]).strip()


def load_graph() -> dict:
    if not GRAPH_PATH.exists():
        subprocess.run(["python3", str(ROOT / "tools" / "extract_session_graph.py"), "--write"], check=True)
    return json.loads(read(GRAPH_PATH))


def by_id(graph: dict) -> dict[str, dict]:
    return {node["id"]: node for node in graph["nodes"]}


def outgoing(graph: dict, source: str, relation: str | None = None) -> list[dict]:
    return [edge for edge in graph["edges"] if edge["source"] == source and (relation is None or edge["relation"] == relation)]


def counterexamples(graph: dict) -> list[dict]:
    return [node for node in graph["nodes"] if node["kind"] == "counterexample"]


def render() -> str:
    graph = load_graph()
    nodes = by_id(graph)
    sketch = nodes["sketch.task-line-parser"]
    known = nodes["known-code.result"]
    implementation = nodes["implementation.parse-task-line"]

    parts: list[str] = []
    parts.append("# Extracted Session Evidence: Sketch + Counterexample + Coding Agent")
    parts.append("")
    parts.append("> Generated from the clean-room session graph and source selectors. This appendix is companion evidence for `paper/main.tex`; regenerate after `tools/extract_session_graph.py --write` and this extractor pass.")
    parts.append("")
    parts.append("## Claim Boundary")
    parts.append("")
    parts.append("This artifact supports one finite-session claim: a coding-agent implementation is inspectable when every counterexample links to a source span, a verification check, and the execution point that handles it. The generated graph answers `how is this counterexample handled?` from repo-local evidence.")
    parts.append("")
    parts.append("## Source Sketch")
    parts.append("")
    parts.append(f"Selector: `{sketch['selector']}`")
    parts.append("")
    parts.append("```md")
    parts.append(snippet(sketch["selector"]))
    parts.append("```")
    parts.append("")
    parts.append("## Known-Code Anchor")
    parts.append("")
    parts.append(f"Selector: `{known['selector']}`")
    parts.append("")
    parts.append("```python")
    parts.append(snippet(known["selector"]))
    parts.append("```")
    parts.append("")
    parts.append("## Generated Implementation")
    parts.append("")
    parts.append(f"Selector: `{implementation['selector']}`")
    parts.append("")
    parts.append("The implementation is referenced by selector; each counterexample below links to the execution selectors that handle it.")
    parts.append("")
    parts.append("## Extracted Counterexample Handling")
    parts.append("")

    for ce in counterexamples(graph):
        parts.append(f"### {ce['name']}")
        parts.append("")
        parts.append(f"Counterexample selector: `{ce['selector']}`")
        parts.append("")
        parts.append("```md")
        parts.append(snippet(ce["selector"]))
        parts.append("```")
        parts.append("")
        parts.append(f"Tempting patch failed: {ce['tempting_patch']}")
        parts.append("")
        parts.append("Handled by execution points:")
        for edge in outgoing(graph, ce["id"], "handled_by"):
            ep = nodes[edge["target"]]
            parts.append(f"- `{ep['selector']}` — {ep.get('handling', ep['name'])}")
        parts.append("")
        parts.append("Verified by:")
        for edge in outgoing(graph, ce["id"], "verified_by"):
            test = nodes[edge["target"]]
            parts.append(f"- `{test['selector']}`")
            parts.append("")
            parts.append("```python")
            parts.append(snippet(test["selector"]))
            parts.append("```")
        parts.append("")

    parts.append("## Extracted Claim")
    parts.append("")
    parts.append("The graph supports a narrow claim: for this session, each counterexample has a source selector, a tempting patch, one or more execution selectors, and a verification selector. The paper's claims should stay within that extracted evidence.")
    parts.append("")
    parts.append("## Verification")
    parts.append("")
    parts.append("Run:")
    parts.append("")
    parts.append("```bash")
    parts.append("python3 sketch-counterexample-agent/tools/extract_session_graph.py --write")
    parts.append("python3 sketch-counterexample-agent/tools/extract_session_paper.py")
    parts.append("python3 sketch-counterexample-agent/tools/extract_session_graph.py --ce first-prefix")
    parts.append("python3 -m unittest discover -s sketch-counterexample-agent/examples/task-line-parser/tests")
    parts.append("```")
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
