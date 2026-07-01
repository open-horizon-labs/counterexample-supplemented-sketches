#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "rostersynth-kiosk"
SOURCE = EXAMPLE / "source"
OUT = ROOT / "build" / "rostersynth-kiosk-graph.json"
PAPER_OUT = ROOT / "paper" / "extracted-rostersynth-kiosk-paper.md"
RNA_DIR = ROOT / ".oh" / "knowledge" / "rostersynth-kiosk"

DEFAULT_SOURCE_ROOT = Path("/tmp/RosterSynth")

COPY_ITEMS = [
    "README.md",
    "paper",
    "docs",
    "scenarios",
    "cassettes",
    "rostersynth",
    "tests",
]


def ignore_generated(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith(".pyc")}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def selector(relative: str, start: int | None = None, end: int | None = None) -> str:
    base = rel(SOURCE / relative)
    if start is None:
        return base
    assert end is not None
    return f"{base}:{start}-{end}"


def copy_source(source_root: Path) -> None:
    if not source_root.exists():
        if SOURCE.exists():
            return
        raise SystemExit(f"RosterSynth source not found: {source_root}")
    if SOURCE.exists():
        shutil.rmtree(SOURCE)
    SOURCE.mkdir(parents=True, exist_ok=True)
    for item in COPY_ITEMS:
        src = source_root / item
        dst = SOURCE / item
        if not src.exists():
            raise SystemExit(f"required source item missing: {src}")
        if src.is_dir():
            shutil.copytree(src, dst, ignore=ignore_generated)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


def node(node_id: str, kind: str, name: str, selector_: str | None = None, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"id": node_id, "kind": kind, "name": name}
    if selector_:
        payload["selector"] = selector_
    payload.update(extra)
    return payload


def edge(source: str, relation: str, target: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"source": source, "relation": relation, "target": target}
    payload.update(extra)
    return payload


def build_graph() -> dict[str, object]:
    manifest = json.loads(read(SOURCE / "scenarios" / "manifest.json"))
    scenario = json.loads(read(SOURCE / "scenarios" / "roster.kiosk_double_booking.v1.json"))
    expectation = scenario["expectations"]["resolver"]["suggestions"][0]

    nodes: list[dict[str, object]] = [
        node(
            "paper.rostersynth",
            "paper",
            "Agentic Synthesis against Counterexample-Supplemented Sketches",
            selector("paper/main.tex", 14, 24),
            claim="Sketch plus growing E, dual oracles, replay/compare gates, and counterexample promotion hold agentic coding accountable.",
        ),
        node(
            "readme.loop",
            "method_overview",
            "README method loop",
            selector("README.md", 11, 18),
            claim="Write sketch, collect examples, promote failures into E, gate over replay and compare.",
        ),
        node("session.kiosk", "agent_session", "Kiosk double-booking session", selector("docs/sessions/01-kiosk-double-booking.md")),
        node("sketch.roster", "sketch", "Roster sketch", selector("docs/sketch.md")),
        node("sketch.op2", "sketch_clause", "Op 2 cancel duplicate", selector("docs/sketch.md", 20, 27), clause="Twins on windowEnd with same shiftKind and hours cancel the higher bookingId when that alone closes delta; clusterNotes route to Oracle B."),
        node("corpus.reference-v1", "corpus", "reference-v1 scenario corpus", selector("scenarios/manifest.json"), scenario_count=len(manifest["scenarioIds"])),
        node("scenario.kiosk", "scenario", scenario["title"], selector("scenarios/roster.kiosk_double_booking.v1.json"), scenario_id=scenario["id"]),
        node(
            "ce.kiosk-double-booking",
            "counterexample",
            "Kiosk double-tap should cancel higher duplicate booking",
            selector("scenarios/roster.kiosk_double_booking.v1.json"),
            tempting_patch="append -40 hours to close coverageDelta, or cancel lower bookingId 1801 because replay still closes the hours math",
            expected_op=expectation["op"],
            expected_booking_id=expectation["bookingId"],
        ),
        node("oracle-a.deterministic", "oracle", "Oracle A deterministic resolver", selector("rostersynth/resolver/deterministic.py", 7, 9), oracle="A"),
        node("oracle-a.build-rows", "execution_point", "Oracle A build_rows dispatcher", selector("rostersynth/playbook.py", 53, 72), handling="Skips balanced employees, abstains on clusterNotes, tries duplicate cancel before append."),
        node("oracle-a.cancel-duplicate", "execution_point", "Cancel duplicate implementation", selector("rostersynth/playbook.py", 109, 137), handling="Groups active windowEnd bookings by (shiftKind, hours), picks max bookingId, and only emits modify if deactivation closes coverageDelta."),
        node("replay.effective-delta", "replay_check", "Replay effective delta", selector("rostersynth/verifier.py", 8, 18), check="Rows must close each imbalanced employee's coverageDelta."),
        node("compare.modify", "compare_check", "Semantic compare for modify rows", selector("rostersynth/eval/comparer.py", 8, 55), check="Golden compare catches wrong op, wrong bookingId, and wrong fields.status."),
        node("oracle-b.prompt", "prompt_flow", "Oracle B prompt decision order", selector("rostersynth/oracle/prompt.py", 14, 40), handling="Puts Op 2 before Op 1 and states the higher-bookingId tie-break plus required modify shape."),
        node("oracle-b.cassette.correct", "cassette", "Correct kiosk cassette", selector("cassettes/roster.kiosk_double_booking.v1.json"), expected_booking_id=1802),
        node("oracle-b.cassette.wrong", "negative_fixture", "Wrong kiosk cassette", selector("cassettes/roster.kiosk_double_booking.v1.wrong.json"), wrong_booking_id=1801),
        node("hybrid.resolver", "execution_point", "Hybrid resolver", selector("rostersynth/resolver/hybrid.py", 18, 69), handling="Runs Oracle A first; falls back to Oracle B only if deterministic row is missing or replay-invalid."),
        node("session.step0", "session_step", "Confirm counterexample in corpus E", selector("docs/sessions/01-kiosk-double-booking.md", 36, 58), observation="Golden op is modify bookingId 1802."),
        node("session.step1", "session_step", "Dump Oracle B prompts", selector("docs/sessions/01-kiosk-double-booking.md", 63, 96), observation="Prompt gives Op 2 priority over append and shows kiosk payload."),
        node("session.step2", "session_step", "Oracle A after Op 2 passes", selector("docs/sessions/01-kiosk-double-booking.md", 100, 135), observation="Deterministic gate passes; compare and replay both green."),
        node("session.step2b", "promotion_step", "Historical Op 1-only failure promotes Op 2", selector("docs/sessions/01-kiosk-double-booking.md", 140, 150), observation="Append closed delta; compare expected modify and got append."),
        node("session.step3", "session_step", "Hybrid uses Oracle A", selector("docs/sessions/01-kiosk-double-booking.md", 154, 176), observation="Hybrid passes; Oracle A handles kiosk."),
        node("session.step4", "session_step", "Oracle B correct cassette passes", selector("docs/sessions/01-kiosk-double-booking.md", 182, 205), observation="Cassette emits bookingId 1802."),
        node("session.step5", "negative_check", "Lower-booking cassette fails compare", selector("docs/sessions/01-kiosk-double-booking.md", 210, 232), observation="Lower bookingId 1801 closes replay; compare catches the wrong booking."),
        node("session.step7", "gate_result", "Full corpus gates", selector("docs/sessions/01-kiosk-double-booking.md", 281, 299), observation="Deterministic 12/12 plus 2 excluded; hybrid and llm-only cassette 14/14."),
        node("test.kiosk.cancel", "verification_check", "test_kiosk_cancel_higher_booking", selector("tests/test_rostersynth.py", 99, 105), check="Oracle A must emit modify bookingId 1802."),
        node("test.cassette.kiosk", "verification_check", "test_cassette_llm_resolves_kiosk", selector("tests/test_rostersynth.py", 129, 135), check="Oracle B cassette must emit modify bookingId 1802."),
        node("test.hybrid.kiosk", "verification_check", "test_kiosk_hybrid_uses_deterministic_without_fallback", selector("tests/test_rostersynth.py", 152, 159), check="Hybrid keeps the deterministic row and avoids fallback for kiosk."),
        node("test.row-closes-delta", "verification_check", "test_row_closes_delta_rejects_wrong_append", selector("tests/test_rostersynth.py", 138, 149), check="Replay rejects an append with the wrong magnitude."),
        node("test.prompt.includes-order", "verification_check", "test_bench_prompt_includes_decision_order_and_payload", selector("tests/test_rostersynth.py", 162, 175), check="Prompt includes DECISION ORDER, kiosk employee, and Op 2."),
        node("test.full-gates", "verification_check", "gate table tests", selector("tests/test_rostersynth.py", 24, 52), check="Deterministic excludes LLM fallbacks; hybrid and llm-only cassette pass manifest count."),
    ]

    edges: list[dict[str, object]] = [
        edge("paper.rostersynth", "described_by", "readme.loop"),
        edge("paper.rostersynth", "uses", "sketch.roster"),
        edge("paper.rostersynth", "uses", "corpus.reference-v1"),
        edge("session.kiosk", "contains", "session.step0"),
        edge("session.kiosk", "contains", "session.step1"),
        edge("session.kiosk", "contains", "session.step2"),
        edge("session.kiosk", "contains", "session.step2b"),
        edge("session.kiosk", "contains", "session.step3"),
        edge("session.kiosk", "contains", "session.step4"),
        edge("session.kiosk", "contains", "session.step5"),
        edge("session.kiosk", "contains", "session.step7"),
        edge("corpus.reference-v1", "contains", "scenario.kiosk"),
        edge("scenario.kiosk", "has_counterexample", "ce.kiosk-double-booking"),
        edge("ce.kiosk-double-booking", "specified_by", "sketch.op2"),
        edge("ce.kiosk-double-booking", "observed_in", "session.step0"),
        edge("ce.kiosk-double-booking", "promoted_by", "session.step2b"),
        edge("sketch.op2", "implemented_by", "oracle-a.cancel-duplicate"),
        edge("sketch.op2", "communicated_to", "oracle-b.prompt"),
        edge("oracle-a.deterministic", "calls", "oracle-a.build-rows"),
        edge("oracle-a.build-rows", "tries_before_append", "oracle-a.cancel-duplicate"),
        edge("oracle-a.cancel-duplicate", "replayed_by", "replay.effective-delta"),
        edge("oracle-a.cancel-duplicate", "compared_by", "compare.modify"),
        edge("oracle-a.cancel-duplicate", "verified_by", "test.kiosk.cancel"),
        edge("oracle-b.prompt", "produces", "oracle-b.cassette.correct"),
        edge("oracle-b.cassette.correct", "compared_by", "compare.modify"),
        edge("oracle-b.cassette.correct", "verified_by", "test.cassette.kiosk"),
        edge("oracle-b.cassette.wrong", "fails", "session.step5"),
        edge("compare.modify", "rejects", "oracle-b.cassette.wrong", reason="wrong bookingId 1801"),
        edge("hybrid.resolver", "prefers", "oracle-a.cancel-duplicate"),
        edge("hybrid.resolver", "fallbacks_to", "oracle-b.prompt"),
        edge("hybrid.resolver", "verified_by", "test.hybrid.kiosk"),
        edge("replay.effective-delta", "verified_by", "test.row-closes-delta"),
        edge("oracle-b.prompt", "verified_by", "test.prompt.includes-order"),
        edge("corpus.reference-v1", "gated_by", "test.full-gates"),
        edge("session.step2", "evidences", "oracle-a.cancel-duplicate"),
        edge("session.step3", "evidences", "hybrid.resolver"),
        edge("session.step4", "evidences", "oracle-b.cassette.correct"),
        edge("session.step7", "evidences", "corpus.reference-v1"),
    ]
    return {"graph": "rostersynth-kiosk-cleanroom-example", "nodes": nodes, "edges": edges}


def graph_maps(graph: dict[str, object]) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    return {n["id"]: n for n in graph["nodes"]}, list(graph["edges"])  # type: ignore[index]


def outgoing(edges: list[dict[str, object]], source: str, relation: str | None = None) -> list[dict[str, object]]:
    return [e for e in edges if e["source"] == source and (relation is None or e["relation"] == relation)]


def require_selectors(graph: dict[str, object]) -> None:
    missing = [n["id"] for n in graph["nodes"] if n.get("kind") not in {"corpus"} and "selector" not in n]  # type: ignore[union-attr]
    if missing:
        raise SystemExit(f"nodes without selectors: {', '.join(missing)}")
    for n in graph["nodes"]:  # type: ignore[assignment]
        selector_value = n.get("selector")
        if not selector_value:
            continue
        path_s = str(selector_value).split(":", 1)[0]
        if not (ROOT / path_s).exists():
            raise SystemExit(f"selector path missing for {n['id']}: {selector_value}")


def write_rna_nodes(graph: dict[str, object]) -> None:
    if RNA_DIR.exists():
        shutil.rmtree(RNA_DIR)
    RNA_DIR.mkdir(parents=True, exist_ok=True)
    nodes, edges = graph_maps(graph)
    for item in nodes.values():
        outgoing_edges = [e for e in edges if e["source"] == item["id"]]
        lines = ["---", "rna:", f"  kind: {item['kind']}", f"  id: {item['id']}", f"  name: {json.dumps(item['name'])}"]
        if "selector" in item:
            lines.append(f"  selector: {json.dumps(item['selector'])}")
        if outgoing_edges:
            lines.append("  relationships:")
            for relation in outgoing_edges:
                lines.append(f"    - kind: {relation['relation']}")
                lines.append(f"      target: {relation['target']}")
        lines.extend(["---", "", f"# {item['name']}", ""])
        for key in ("claim", "clause", "tempting_patch", "handling", "check", "observation"):
            if key in item:
                lines.append(f"{key.replace('_', ' ').title()}: {item[key]}")
        lines.append("")
        write(RNA_DIR / f"{item['id']}.md", "\n".join(lines))


def answer_ce(graph: dict[str, object], query: str) -> str:
    nodes, edges = graph_maps(graph)
    matches = [n for n in nodes.values() if n["kind"] == "counterexample" and (query in n["id"] or query.lower() in str(n["name"]).lower() or query == n.get("scenario_id"))]
    if not matches and query == "roster.kiosk_double_booking.v1":
        matches = [nodes["ce.kiosk-double-booking"]]
    if not matches:
        raise SystemExit(f"no counterexample matched: {query}")
    ce = matches[0]
    lines = [
        f"Counterexample: {ce['name']}",
        f"Source: {ce['selector']}",
        f"Tempting patch: {ce['tempting_patch']}",
        "Path:",
    ]
    ordered = [
        ("specified_by", "Sketch clause"),
        ("observed_in", "Corpus/session observation"),
        ("promoted_by", "Promotion trigger"),
    ]
    for relation, label in ordered:
        for item in outgoing(edges, ce["id"], relation):
            target = nodes[item["target"]]
            lines.append(f"- {label}: {target['selector']} — {target.get('observation') or target.get('clause') or target['name']}")
    lines.append("- Oracle A: " + nodes["oracle-a.cancel-duplicate"]["selector"] + " — " + str(nodes["oracle-a.cancel-duplicate"]["handling"]))
    lines.append("- Replay: " + nodes["replay.effective-delta"]["selector"] + " — " + str(nodes["replay.effective-delta"]["check"]))
    lines.append("- Compare: " + nodes["compare.modify"]["selector"] + " — " + str(nodes["compare.modify"]["check"]))
    lines.append("- Oracle B prompt: " + nodes["oracle-b.prompt"]["selector"] + " — " + str(nodes["oracle-b.prompt"]["handling"]))
    lines.append("- Negative check: " + nodes["session.step5"]["selector"] + " — " + str(nodes["session.step5"]["observation"]))
    lines.append("Verified by:")
    for target_id in ["test.kiosk.cancel", "test.cassette.kiosk", "test.hybrid.kiosk", "test.full-gates"]:
        target = nodes[target_id]
        lines.append(f"- {target['selector']}: {target['check']}")
    return "\n".join(lines)


def snippet(selector_value: str) -> str:
    path_part, _, span = selector_value.partition(":")
    path = ROOT / path_part
    text = read(path)
    if not span or "-" not in span:
        return text.strip()
    start_s, end_s = span.split("-", 1)
    if not start_s.isdigit() or not end_s.isdigit():
        return text.strip()
    lines = text.splitlines()
    return "\n".join(lines[int(start_s) - 1 : int(end_s)]).strip()

def append_fenced(parts: list[str], lang: str, body: str) -> None:
    parts.append(f"~~~{lang}")
    parts.append(body)
    parts.append("~~~")


def render_paper(graph: dict[str, object]) -> str:
    nodes, _edges = graph_maps(graph)
    scenario = json.loads(read(SOURCE / "scenarios" / "roster.kiosk_double_booking.v1.json"))
    manifest = json.loads(read(SOURCE / "scenarios" / "manifest.json"))
    parts: list[str] = []
    parts.append("# Agentic Synthesis against Counterexample-Supplemented Sketches")
    parts.append("")
    parts.append("> Generated from repo-local RosterSynth source snapshots and graph selectors. RosterSynth kiosk is the worked example for the process; regenerate with `tools/extract_rostersynth_example.py --write --paper`.")
    parts.append("")
    parts.append("## Abstract")
    parts.append("")
    parts.append("This example shows the full RosterSynth process on one counterexample: a kiosk double-tap creates twin 40-hour active bookings, and the tempting append repair closes the hours math while violating duplicate policy. The sketch clause, corpus case, Oracle A implementation, Oracle B prompt/cassette path, replay check, semantic compare, promotion step, negative cassette, full-gate evidence, and verification tests are all linked by graph nodes with source selectors.")
    parts.append("")
    parts.append("## Method Claim")
    parts.append("")
    for node_id in ["paper.rostersynth", "readme.loop"]:
        n = nodes[node_id]
        parts.append(f"- `{n['selector']}` — {n['claim']}")
    parts.append("")
    parts.append("## Corpus E")
    parts.append("")
    parts.append(f"- Manifest selector: `{nodes['corpus.reference-v1']['selector']}`")
    parts.append(f"- Scenario count: {len(manifest['scenarioIds'])}")
    parts.append(f"- Kiosk scenario selector: `{nodes['scenario.kiosk']['selector']}`")
    parts.append(f"- Golden expectation: `{scenario['expectations']['resolver']['suggestions'][0]['op']}` bookingId `{scenario['expectations']['resolver']['suggestions'][0]['bookingId']}`")
    parts.append("")
    append_fenced(parts, "json", json.dumps(scenario["expectations"], indent=2))
    parts.append("")
    parts.append("## Sketch Clause")
    parts.append("")
    parts.append(f"Selector: `{nodes['sketch.op2']['selector']}`")
    parts.append("")
    append_fenced(parts, "md", snippet(str(nodes["sketch.op2"]["selector"])))
    parts.append("")
    parts.append("## Counterexample")
    parts.append("")
    ce = nodes["ce.kiosk-double-booking"]
    parts.append(f"Selector: `{ce['selector']}`")
    parts.append(f"Tempting wrong patch: {ce['tempting_patch']}.")
    parts.append("")
    parts.append("The historical failure is source-backed:")
    parts.append("")
    parts.append(f"Selector: `{nodes['session.step2b']['selector']}`")
    parts.append("")
    append_fenced(parts, "md", snippet(str(nodes["session.step2b"]["selector"])))
    parts.append("")
    parts.append("## Oracle A: Encodable Policy")
    parts.append("")
    for node_id in ["oracle-a.deterministic", "oracle-a.build-rows", "oracle-a.cancel-duplicate"]:
        n = nodes[node_id]
        parts.append(f"### {n['name']}")
        parts.append("")
        parts.append(f"Selector: `{n['selector']}`")
        if "handling" in n:
            parts.append(f"Handling: {n['handling']}")
        parts.append("")
        append_fenced(parts, "python", snippet(str(n["selector"])))
        parts.append("")
    parts.append("## Replay and Compare")
    parts.append("")
    for node_id in ["replay.effective-delta", "compare.modify"]:
        n = nodes[node_id]
        parts.append(f"### {n['name']}")
        parts.append("")
        parts.append(f"Selector: `{n['selector']}`")
        parts.append(f"Check: {n['check']}")
        parts.append("")
        append_fenced(parts, "python", snippet(str(n["selector"])))
        parts.append("")
    parts.append("## Oracle B: Prompt and Cassette")
    parts.append("")
    for node_id in ["oracle-b.prompt", "oracle-b.cassette.correct", "oracle-b.cassette.wrong"]:
        n = nodes[node_id]
        parts.append(f"### {n['name']}")
        parts.append("")
        parts.append(f"Selector: `{n['selector']}`")
        if "handling" in n:
            parts.append(f"Handling: {n['handling']}")
        parts.append("")
        fence = "python" if str(n["selector"]).endswith(".py") else "json"
        append_fenced(parts, fence, snippet(str(n["selector"])))
        parts.append("")
    parts.append("## Full Session Path")
    parts.append("")
    for node_id in ["session.step0", "session.step1", "session.step2", "session.step2b", "session.step3", "session.step4", "session.step5", "session.step7"]:
        n = nodes[node_id]
        parts.append(f"- `{n['selector']}` — {n['observation']}")
    parts.append("")
    parts.append("## Query: How Is This Counterexample Handled?")
    parts.append("")
    append_fenced(parts, "text", answer_ce(graph, "roster.kiosk_double_booking.v1"))
    parts.append("")
    parts.append("## Verification Selectors")
    parts.append("")
    for node_id in ["test.kiosk.cancel", "test.cassette.kiosk", "test.hybrid.kiosk", "test.row-closes-delta", "test.prompt.includes-order", "test.full-gates"]:
        n = nodes[node_id]
        parts.append(f"- `{n['selector']}` — {n['check']}")
    parts.append("")
    parts.append("## Bounded Claim")
    parts.append("")
    parts.append("This extracted example supports the claim that the kiosk counterexample is inspectable end to end from sketch clause to corpus case, promotion trigger, Oracle A implementation, Oracle B prompt/cassette path, replay/compare checks, negative check, and tests. The evidence covers the referenced RosterSynth corpus and the public companion artifact.")
    parts.append("")
    parts.append("## Regenerate")
    parts.append("")
    append_fenced(parts, "bash", "\n".join([
        "python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --write --paper",
        "python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1",
        "python3 -m unittest discover -s sketch-counterexample-agent/examples/rostersynth-kiosk/tests",
    ]))
    return "\n".join(parts).rstrip() + "\n"


def write_readme() -> None:
    text = """# RosterSynth Kiosk Worked Example

This directory is the worked example supporting `paper/main.tex`.

It is generated from a local RosterSynth source checkout into repo-local snapshots under `source/`, then compiled into:

- `../../build/rostersynth-kiosk-graph.json` — graph nodes and edges for the example.
- `../../paper/extracted-rostersynth-kiosk-paper.md` — generated evidence appendix.
- `../../.oh/knowledge/rostersynth-kiosk/*.md` — repo-native node files.

The example demonstrates the full loop:

```text
sketch Op 2 + corpus counterexample
→ historical append failure
→ Oracle A duplicate-cancel implementation
→ replay check + semantic compare
→ Oracle B prompt/cassette path
→ wrong-cassette negative check
→ full-corpus gate evidence
```

Run:

```bash
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --write --paper
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s sketch-counterexample-agent/examples/rostersynth-kiosk/tests
```
"""
    write(EXAMPLE / "README.md", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--ce")
    args = parser.parse_args()

    if args.write:
        copy_source(args.source)
        write_readme()
    elif not SOURCE.exists():
        copy_source(args.source)

    graph = build_graph()
    require_selectors(graph)

    if args.write:
        write(OUT, json.dumps(graph, indent=2) + "\n")
        write_rna_nodes(graph)
        print(OUT)
    if args.paper:
        write(PAPER_OUT, render_paper(graph))
        print(PAPER_OUT)
    if args.ce:
        print(answer_ce(graph, args.ce))
    if not args.write and not args.paper and not args.ce:
        print(json.dumps(graph, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
