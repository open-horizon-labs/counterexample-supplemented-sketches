# Agentic Synthesis against Counterexample-Supplemented Sketches

**Paper PDF:** [`paper/main.pdf`](paper/main.pdf)  
**Paper source:** [`paper/main.tex`](paper/main.tex)  
**Bibliography source:** [`paper/references.bib`](paper/references.bib)  
**Companion artifact:** runnable examples, fixtures, and provenance for the paper's claims.

**Agentic synthesis against counterexample-supplemented sketches** makes coding-agent work checkable against a finite promoted corpus. A human writes a partial program-like sketch; failures become counterexamples; an agent edits code and prompts; replay/compare gates check the current artifact against the promoted cases.

The paper is the primary artifact. It names the method, gives the formal model, places the work against sketching, CEGIS, programming by example, tests-as-prompts, and coding-agent benchmarks, and states the finite-corpus correctness claim. This repository is companion evidence: runnable examples, fixtures, provenance, and tests for the paper's worked claims.

## Method at a glance

```mermaid
flowchart LR
    Sketch["Sketch: permitted strategy"] --> Agent["Agent edits code/prompts"]
    Anchors["Known-code anchors"] --> Agent
    Corpus["Promoted corpus E"] --> Replay["Replay: did state repair?"]
    Agent --> Replay
    Replay --> Compare["Semantic compare: did policy field match?"]
    Corpus --> Compare
    Compare -->|pass| Done["Current artifact satisfies E"]
    Compare -->|fail| Counterexample["Promote counterexample"]
    Counterexample --> Sketch
```

## Read by path

- **Academics:** start with [`paper/main.tex`](paper/main.tex), then inspect [`paper/references.bib`](paper/references.bib) and the executable evidence below. The claim boundary is finite-corpus soundness over the promoted corpus `E`.
- **Developers:** read the RosterSynth kiosk path, then run the commands in [Reproduce the paper artifact](#reproduce-the-paper-artifact). The examples show how to turn sketch clauses, failures, replay checks, and compare checks into an agent loop.

The RosterSynth kiosk material is the paper's worked example. It supports the method; the paper carries the claim.

## Originating setting

The method originated in a proprietary enterprise deployment for a heterogeneous data-cleansing pipeline operated by non-developers. That deployment used a custom Cursor extension, `cursor://`-style commands, an embedded SME web app, SME corrections converted with LLM assistance into input/output specs, a counterexample loop, and a promoted golden corpus for multiple downstream clients.

This public companion contains the publishable slice: the paper, clean fixtures, runnable examples, tests, and provenance. Production data, client-specific rules, proprietary extension code, and private SME workflows stay outside the repo.

## What this companion artifact supports

The paper's executable claim is bounded:

> If the replay/compare gate passes every case in the promoted counterexample corpus `E`, then the current agent-produced artifact is correct for `E` under the repository's executable replay and compare semantics.

The repository supports that claim with:

| Artifact | Paper role |
|---|---|
| `examples/rostersynth-kiosk/source/docs/sketch.md` | Concrete sketch clauses for the worked example |
| `examples/rostersynth-kiosk/source/scenarios/*.json` | Corpus `E` and promoted counterexamples |
| `examples/rostersynth-kiosk/source/rostersynth/playbook.py` | Oracle A deterministic implementation |
| `examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py` | Oracle B prompt path |
| `examples/rostersynth-kiosk/source/cassettes/*.json` | Reproducible Oracle B cassette fixtures |
| `examples/rostersynth-kiosk/tests/test_extracted_rostersynth.py` | Executable checks for the paper's worked-example claims |
| `build/rostersynth-kiosk-graph.json` | Source/provenance graph for appendix-style inspection |
| `.oh/knowledge/rostersynth-kiosk/` | Repo-native node files for the same graph |

## Worked example: RosterSynth kiosk

The paper uses one concrete case to show why replay and semantic compare are separate checks.

A roster has twin active 40-hour bookings on the pay-window end date. Badge hours are 40 and scheduled hours are 80, so a naive append of `-40h` closes the coverage math while violating duplicate policy. The correct repair cancels the duplicate booking with the higher `bookingId`.

The counterexample path is:

```text
roster.kiosk_double_booking.v1
→ sketch Op 2: cancel duplicate higher bookingId when it alone closes delta
→ historical failure: append -40h passes replay; compare rejects expected append vs modify
→ Oracle A: _try_cancel_duplicate emits modify bookingId=1802 status=4
→ Oracle B prompt/cassette path states the same rule
→ lower-booking cassette bookingId=1801 passes replay; compare catches wrong booking
→ gate passes after sketch/code/prompt alignment
```

That path is evidence for the paper's method.

## Reproduce the paper artifact

From the repo root:

```bash
python3 tools/extract_rostersynth_example.py --write --paper
python3 tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s examples/rostersynth-kiosk/tests
```

Expected test result:

```text
Ran 6 tests
OK
```

The checks exercise the paper's worked-example obligations:

- Oracle A cancels higher duplicate `bookingId=1802`.
- Wrong append passes replay; compare rejects it.
- Lower-booking cassette cancels `1801`; compare rejects it.
- Hybrid keeps deterministic Oracle A on the kiosk case and avoids fallback.
- Oracle B prompt includes decision order, Op 2, higher-bookingId rule, and payload.
- Full corpus gates match deterministic, hybrid cassette, and llm-only cassette evidence.

## For developers

Use the companion artifact as an implementation appendix. The adaptable pattern is:

1. Put the intended strategy in a sketch file.
2. Add counterexamples for plausible wrong implementations.
3. Point the agent at known-code anchors before it writes new code.
4. Require a replay check for state repair.
5. Require a compare check for semantic fields replay under-specifies.
6. Promote every failure into the corpus and sketch before rerunning the agent.

A tiny didactic parser slice remains under [`examples/task-line-parser/`](examples/task-line-parser/) for readers who want the smallest version of the loop.

## For academics

Treat the repository as supplementary material for evaluating the paper's claims:

- [`paper/main.tex`](paper/main.tex) names and argues the method;
- the correctness result is finite-corpus soundness over the promoted corpus `E`;
- the RosterSynth kiosk case is the concrete witness;
- the tests and graph show how source artifacts back the paper's claims.

The relevant comparison points are program sketching, CEGIS, programming by example, tests-as-prompts, and coding-agent benchmarks.

## Repository map

```text
paper/
  main.tex                               # paper: process, references, formal model, correctness theorem
  references.bib                         # bibliography
  extracted-rostersynth-kiosk-paper.md   # generated evidence appendix
examples/
  rostersynth-kiosk/                     # worked example supporting the paper
    source/                              # copied RosterSynth source slice: sketch, scenarios, cassettes, code, tests
    tests/                               # self-contained checks for the paper's worked-example claims
  task-line-parser/                      # smallest didactic slice
flows/                                   # reusable agent flow prompts
.oh/knowledge/rostersynth-kiosk/         # repo-native graph node files
build/rostersynth-kiosk-graph.json       # extracted provenance graph
```

## References

The paper's canonical BibTeX is [`paper/references.bib`](paper/references.bib). The current reference set is:

- Solar-Lezama, Armando. 2008. *Program Synthesis by Sketching.* EECS Department, University of California, Berkeley, technical report UCB/EECS-2008-177. <http://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-177.html>
- Solar-Lezama, Armando. 2013. *Program Sketching.* *International Journal on Software Tools for Technology Transfer* 15(5-6), 475-495. <https://doi.org/10.1007/s10009-012-0249-7>
- Solar-Lezama, Armando, Liviu Tancau, Rastislav Bodik, Sanjit A. Seshia, and Vijay A. Saraswat. 2006. *Combinatorial Sketching for Finite Programs.* ASPLOS 2006, 404-415. <https://doi.org/10.1145/1168857.1168907>
- Jha, Susmit, Sumit Gulwani, Sanjit A. Seshia, and Ashish Tiwari. 2010. *Oracle-Guided Component-Based Program Synthesis.* ICSE 2010, 215-224. <https://doi.org/10.1145/1806799.1806833>
- Gulwani, Sumit, Oleksandr Polozov, and Rishabh Singh. 2017. *Program Synthesis.* *Foundations and Trends in Programming Languages* 4(1-2), 1-119. <https://doi.org/10.1561/2500000010>
- Polozov, Oleksandr, and Sumit Gulwani. 2015. *FlashMeta: A Framework for Inductive Program Synthesis.* OOPSLA 2015, 107-126. <https://doi.org/10.1145/2814270.2814310>
- Jimenez, Carlos E., John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, and Karthik R. Narasimhan. 2024. *SWE-bench: Can Language Models Resolve Real-world GitHub Issues?* ICLR 2024. <https://openreview.net/forum?id=VTF8yNQM66>
- Cui, Yi. 2025. *Tests as Prompt: A Test-Driven-Development Benchmark for LLM Code Generation.* arXiv:2505.09027. <https://arxiv.org/abs/2505.09027>
- Reynolds, Laria, and Kyle McDonell. 2021. *Prompt Programming for Large Language Models: Beyond the Few-Shot Paradigm.* arXiv:2102.07350. <https://arxiv.org/abs/2102.07350>
- Liu, Pengfei, Weizhe Yuan, Jinlan Fu, Zhengbao Jiang, Hiroaki Hayashi, and Graham Neubig. 2023. *Pre-train, Prompt, and Predict: A Systematic Survey of Prompting Methods in Natural Language Processing.* *ACM Computing Surveys* 55(9), article 195, 1-35. <https://doi.org/10.1145/3560815>
- Beheshti, Amin. 2024. *Natural Language-Oriented Programming (NLOP): Towards Democratizing Software Creation.* IEEE SSE 2024, 258-267. <https://doi.org/10.1109/SSE62657.2024.00047>
- Ko, Andrew J., Robin Abraham, Laura Beckwith, Alan Blackwell, Margaret Burnett, Martin Erwig, Chris Scaffidi, Joseph Lawrance, Henry Lieberman, Brad Myers, Mary Beth Rosson, Gregg Rothermel, Mary Shaw, and Susan Wiedenbeck. 2011. *The State of the Art in End-User Software Engineering.* *ACM Computing Surveys* 43(3), article 21. <https://doi.org/10.1145/1922649.1922658>
- Chen, Zhenpeng, Chong Wang, Weisong Sun, Xuanzhe Liu, Jie M. Zhang, and Yang Liu. 2025. *Promptware Engineering: Software Engineering for Prompt-Enabled Systems.* arXiv:2503.02400. <https://arxiv.org/abs/2503.02400>
- Dohmke, Thomas. 2024. *GitHub Copilot Workspace: Welcome to the Copilot-native Developer Environment.* GitHub Blog. <https://github.blog/news-insights/product-news/github-copilot-workspace/>
- Swaminathan, Nikhil, and Deepak Singh. 2025. *Introducing Kiro.* Kiro Blog. <https://kiro.dev/blog/introducing-kiro/>
- GitHub. 2026. *What is Spec-Driven Development?* GitHub Spec Kit Documentation. <https://github.github.io/spec-kit/concepts/sdd.html>
- Adzic, Gojko. 2011. *Specification by Example: How Successful Teams Deliver the Right Software.* Manning Publications.
