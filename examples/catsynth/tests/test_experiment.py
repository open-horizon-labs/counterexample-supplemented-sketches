import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment.run_experiment import (
    BASELINE,
    DEVELOPER_OUTPUT_SCHEMA,
    ExperimentError,
    baseline_workspace,
    snapshot_generation,
    validate_strategy,
)
import experiment.run_experiment as experiment
from catsynth.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerError,
    DEFAULT_CODEX_MODEL,
)


class ExperimentTests(unittest.TestCase):
    @staticmethod
    def _evaluation(case, passed):
        expected = dict(case["expected"])
        expected["cited_rules"] = sorted(expected["cited_rules"])
        expected["oracle_tags"] = sorted(expected.get("oracle_tags", []))
        actual = dict(expected)
        if not passed:
            actual["operation"] = "abstain" if expected["operation"] != "abstain" else "recommend"
        fields = {
            key: {
                "expected": expected[key], "actual": actual[key],
                "match": expected[key] == actual[key],
            }
            for key in ("operation", "breed", "cited_rules", "oracle_tags")
        }
        return {
            "id": case["id"], "scenario_id": case["scenario_id"],
            "candidate": {}, "actual": actual, "expected": expected,
            "fields": fields, "passed": passed, "oracle_trace": None,
        }

    def test_iterative_flow_targets_one_failure_and_gates_full_corpus(self):
        cases = json.loads(experiment.CASES_PATH.read_text())[:2]
        developer_calls = []
        gate_sizes = []

        def fake_developer(workspace, promoted, active_failure, arm, phase, label,
                           client, ledger, complete_corpus=None):
            del arm, label, client, ledger, complete_corpus
            developer_calls.append((phase, active_failure and active_failure["id"]))
            (workspace / "strategy.py").write_text(
                "def recommend(profile, breeds, rules, oracle_tags):\n"
                "    return {'operation': 'recommend', 'breed': breeds[0]['name'], "
                "'cited_rules': [], 'rationale': 'generated'}\n"
            )
            (workspace / "oracle_prompt.txt").write_text(
                'Read {note}; return {"tags": []}.\n'
            )
            return {"strategy_py": "generated", "oracle_prompt": "generated"}, {
                "error": None, "request": {}, "response": {}, "content": "{}",
                "reasoning": "", "usage": {}, "diffs": {},
            }

        def fake_oracle(case, observed, client, ledger):
            del observed, client, ledger
            promoted = dict(case)
            return promoted, {"reference_agreement": True, "parsed": promoted}

        introductions = iter([
            self._evaluation(cases[0], False),
            self._evaluation(cases[1], False),
        ])

        def fake_evaluate(*_args, **_kwargs):
            return next(introductions)

        regression_results = iter([
            [self._evaluation(experiment.initial_acceptance_case(), True)],
            [self._evaluation(cases[0], True)],
            [self._evaluation(cases[0], False), self._evaluation(cases[1], True)],
            [self._evaluation(cases[0], True), self._evaluation(cases[1], True)],
            [self._evaluation(cases[0], True), self._evaluation(cases[1], True)],
        ])

        def fake_gate(workspace, promoted, client, ledger, label):
            del workspace, client, ledger, label
            gate_sizes.append(len(promoted))
            evaluated = next(regression_results)
            return {
                "passed": all(item["passed"] for item in evaluated),
                "passed_count": sum(item["passed"] for item in evaluated),
                "total": len(evaluated), "cases": evaluated,
            }

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(experiment, "call_developer", side_effect=fake_developer), \
             patch.object(experiment, "call_oracle", side_effect=fake_oracle), \
             patch.object(experiment, "evaluate_case", side_effect=fake_evaluate), \
             patch.object(experiment, "run_gate", side_effect=fake_gate):
            result = experiment.run_iterative(
                Path(tmp), cases, object(), experiment.Ledger(), max_repairs=4,
            )

        self.assertEqual(developer_calls, [
            ("initial", None),
            ("repair", cases[0]["id"]),
            ("repair", cases[1]["id"]),
            ("repair", cases[0]["id"]),
        ])
        self.assertEqual(gate_sizes, [0, 1, 2, 2, 2])
        self.assertTrue(result["final_gate"]["passed"])
        self.assertIn("sketch_after", result["initial_generation"])

    def test_promotion_preserves_restricted_catalog_and_rule_order(self):
        case = dict(json.loads(experiment.CASES_PATH.read_text())[0])
        case["breed_names"] = ["Persian", "Siberian"]
        case["rule_sequence"] = ["allergy_requires_hypoallergenic"]
        response = {
            "operation": case["expected"]["operation"],
            "breed": case["expected"]["breed"],
            "cited_rules": case["expected"]["cited_rules"],
            "oracle_tags": case["expected"]["oracle_tags"],
            "sketch_rule": case["sketch_rule"],
            "explanation": "reviewed",
        }
        client = SimpleNamespace(chat=lambda *args, **kwargs: SimpleNamespace(
            content=json.dumps(response), request={}, response={}, reasoning="", usage={}
        ))
        promoted, _ = experiment.call_oracle(
            case, {"operation": "recommend"}, client, experiment.Ledger()
        )
        self.assertEqual(promoted["breed_names"], case["breed_names"])
        self.assertEqual(promoted["rule_sequence"], case["rule_sequence"])

    def test_repair_prompt_contains_one_active_failure_not_full_corpus(self):
        cases = json.loads(experiment.CASES_PATH.read_text())[:2]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "strategy.py").write_text("def recommend():\n    pass\n")
            (workspace / "oracle_prompt.txt").write_text("{note}\n")
            (workspace / "SKETCH.md").write_text("# Current sketch\n")
            messages = experiment.developer_messages(
                workspace, cases, {"id": cases[1]["id"]},
                "iterative", "repair",
            )
        payload = json.loads(messages[1]["content"])
        self.assertNotIn("promoted_corpus", payload)
        self.assertNotIn("complete_corpus", payload)
        self.assertEqual(payload["active_failing_counterexample"]["id"], cases[1]["id"])
        self.assertEqual(payload["current_sketch_md"], "# Current sketch\n")
        self.assertEqual(
            payload["known_code_contract"]["rule_fields"],
            experiment.known_code_contract()["rule_fields"],
        )

    def test_single_shot_prompt_is_clean_room_and_self_contained(self):
        promoted = json.loads(experiment.CASES_PATH.read_text())
        complete = experiment.complete_case_packets(promoted)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            experiment.baseline_workspace(workspace)
            messages = experiment.developer_messages(
                workspace, promoted, None, "one_shot_repair", "one_shot",
                complete_corpus=complete,
            )
        payload = json.loads(messages[1]["content"])
        self.assertIn("clean-room", messages[0]["content"])
        self.assertIn("There is no active failure", messages[0]["content"])
        self.assertIsNone(payload["active_failing_counterexample"])
        self.assertEqual(len(payload["complete_corpus"]), 14)
        allergy = payload["complete_corpus"][0]
        self.assertIn("profile", allergy)
        self.assertEqual(
            allergy["relevant_rule_rows"][0]["cat_attribute"],
            "hypoallergenic",
        )
        self.assertIn("rule_fields", payload["known_code_contract"])
        empty = next(item for item in payload["complete_corpus"]
                     if item["id"] == "ce-011-empty-catalog-escalates")
        self.assertEqual(empty["candidate_breeds"], [])

    def test_all_extended_cases_match_executable_reference(self):
        cases = json.loads(experiment.CASES_PATH.read_text())
        self.assertEqual(len(cases), 14)
        active_rules = sorted({
            rule_id for case in cases for rule_id in case.get("rule_ids", [])
        })
        for case in cases:
            with self.subTest(case=case["id"]):
                reference = experiment.reference_expected(
                    experiment.profile_for_case(case),
                    case["expected"].get("oracle_tags", []),
                    active_rules,
                    case.get("breed_names"),
                )
                self.assertEqual(reference, case["expected"])

    def test_spec_regression_cases_match_executable_reference(self):
        ce_cases = json.loads(experiment.CASES_PATH.read_text())
        spec_cases = json.loads(experiment.SPEC_CASES_PATH.read_text())
        self.assertEqual(len(spec_cases), 6)
        active_rules = sorted({
            rule_id for case in [*ce_cases, *spec_cases]
            for rule_id in case.get("rule_ids", [])
        })
        for case in spec_cases:
            with self.subTest(case=case["id"]):
                reference = experiment.reference_expected(
                    experiment.profile_for_case(case),
                    case["expected"].get("oracle_tags", []),
                    active_rules,
                    case.get("breed_names"),
                    case.get("rule_sequence"),
                )
                self.assertEqual(reference, case["expected"])

    def test_spec_first_initial_prompt_contains_no_examples(self):
        complete_spec = experiment.COMPLETE_SPEC_PATH.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            experiment.baseline_workspace(workspace)
            messages = experiment.spec_developer_messages(
                workspace, complete_spec, None,
            )
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["phase"], "spec_first")
        self.assertEqual(payload["complete_immutable_specification"], complete_spec)
        self.assertEqual(payload["current_strategy_py"], "")
        self.assertEqual(payload["current_oracle_prompt"], "")
        self.assertIsNone(payload["visible_gate_failures"])
        self.assertNotIn("complete_corpus", payload)
        self.assertNotIn("active_failing_counterexample", payload)
        for case in [
            *json.loads(experiment.CASES_PATH.read_text()),
            *json.loads(experiment.SPEC_CASES_PATH.read_text()),
        ]:
            self.assertNotIn(case["id"], complete_spec)
            self.assertNotIn(case["scenario_id"], complete_spec)

    def test_hidden_regression_suite_covers_extended_policy_boundaries(self):
        hidden = experiment.hidden_cases()
        self.assertEqual(len(hidden), 21)
        ids = {case["id"] for case in hidden}
        self.assertTrue({
            "hidden-soft-single-candidate",
            "hidden-duplicate-soft-synonym",
            "hidden-negated-travel",
            "hidden-blank-allergy",
            "hidden-empty-catalog",
            "hidden-invalid-rule",
            "hidden-effective-citation",
            "hidden-post-soft-tiebreak",
            "hidden-multi-tag-synonym",
            "hidden-scoped-negation-multi",
            "hidden-normalized-severe",
            "hidden-nonapplicable-invalid",
            "hidden-duplicate-soft-rows",
            "hidden-reversed-rule-order",
        }.issubset(ids))

    def test_one_shot_repair_prompt_contains_current_files_and_all_visible_failures(self):
        promoted = json.loads(experiment.CASES_PATH.read_text())[:2]
        failures = [{"id": promoted[0]["id"]}, {"id": promoted[1]["id"]}]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "strategy.py").write_text("def recommend():\n    pass\n")
            (workspace / "oracle_prompt.txt").write_text("Classify {note}.\n")
            (workspace / "SKETCH.md").write_text("# Current repaired sketch\n")
            messages = experiment.developer_messages(
                workspace, promoted, failures, "one_shot_repair", "one_shot_repair",
            )
        payload = json.loads(messages[1]["content"])
        self.assertIn("one-shot-generated", messages[0]["content"])
        self.assertIsNone(payload["active_failing_counterexample"])
        self.assertEqual(payload["active_failing_counterexamples"], failures)
        self.assertNotIn("complete_corpus", payload)
        self.assertEqual(payload["current_sketch_md"], "# Current repaired sketch\n")
        self.assertIn("def recommend", payload["current_strategy_py"])
        self.assertEqual(payload["current_oracle_prompt"], "Classify {note}.\n")

    def test_one_shot_cost_includes_repairs_until_visible_gate_passes(self):
        promoted = json.loads(experiment.CASES_PATH.read_text())[:2]
        calls = []

        def fake_developer(workspace, promoted_cases, active_failure, arm, phase, label,
                           client, ledger, complete_corpus=None):
            del promoted_cases, client, ledger
            calls.append({
                "arm": arm, "phase": phase, "label": label,
                "failures": active_failure, "corpus": complete_corpus,
            })
            (workspace / "strategy.py").write_text(
                "def recommend(profile, breeds, rules, oracle_tags):\n"
                "    return {'operation': 'recommend', 'breed': breeds[0]['name'], "
                "'cited_rules': [], 'rationale': 'generated'}\n"
            )
            (workspace / "oracle_prompt.txt").write_text("Classify {note}.\n")
            (workspace / "SKETCH.md").write_text(f"# Batch attempt {len(calls)}\n")
            return {"strategy_py": "generated"}, {"error": None, "usage": {}}

        failed_gate = {
            "passed": False, "passed_count": 1, "total": 3,
            "cases": [
                self._evaluation(experiment.initial_acceptance_case(), True),
                self._evaluation(promoted[0], False),
                self._evaluation(promoted[1], False),
            ],
        }
        passed_gate = {
            "passed": True, "passed_count": 3, "total": 3,
            "cases": [
                self._evaluation(experiment.initial_acceptance_case(), True),
                self._evaluation(promoted[0], True),
                self._evaluation(promoted[1], True),
            ],
        }
        gates = iter([failed_gate, passed_gate])

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(experiment, "call_developer", side_effect=fake_developer), \
             patch.object(experiment, "run_gate", side_effect=lambda *_a, **_k: next(gates)):
            result = experiment.run_one_shot_repair(
                Path(tmp), promoted, "# Final sketch\n", object(),
                experiment.Ledger(), max_repairs=2,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["phase"], "one_shot")
        self.assertEqual(len(calls[0]["corpus"]), 2)
        self.assertEqual(calls[1]["phase"], "one_shot_repair")
        self.assertIsNone(calls[1]["corpus"])
        self.assertEqual(
            [item["id"] for item in calls[1]["failures"]],
            [promoted[0]["id"], promoted[1]["id"]],
        )
        self.assertEqual(result["repair_attempts"], 1)
        self.assertEqual(result["visible_failure_feedback_events"], 2)
        self.assertTrue(result["final_gate"]["passed"])

    def test_narrative_tag_case_checks_only_the_promoted_tag_field(self):
        case = json.loads(experiment.CASES_PATH.read_text())[2]

        class TagClient:
            def chat(self, *_args, **_kwargs):
                return experiment.ChatResult(
                    content='{"tags":["avoid_needy"]}', reasoning="", usage={},
                    request={}, response={},
                )

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "strategy.py").write_text(
                "def recommend(profile, breeds, rules, oracle_tags):\n"
                "    return {'operation': 'recommend', 'breed': 'Balinese', "
                "'cited_rules': [], 'rationale': 'tag-only checkpoint'}\n"
            )
            (workspace / "oracle_prompt.txt").write_text("Classify {note}.\n")
            result = experiment.evaluate_case(
                workspace, case, set(), TagClient(), experiment.Ledger(), "tag-only",
            )
        self.assertTrue(result["passed"])
        self.assertEqual(result["checked_fields"], ["oracle_tags"])
        self.assertFalse(result["fields"]["breed"]["match"])
        self.assertFalse(result["fields"]["breed"]["checked"])
        packet = experiment.failure_packet(case, result)
        self.assertEqual(packet["checked_fields"], ["oracle_tags"])
        self.assertEqual(packet["actual"], {"oracle_tags": ["avoid_needy"]})
        self.assertNotIn("breed", packet["actual"])
        self.assertNotIn("breed", packet["expected"])

    def test_reviewed_counterexample_overrules_model_spec_disagreement(self):
        case = json.loads(experiment.CASES_PATH.read_text())[0]

        class WrongSpecClient:
            def chat(self, *_args, **_kwargs):
                return experiment.ChatResult(
                    content=json.dumps({
                        "operation": "recommend", "breed": "Persian",
                        "cited_rules": [], "oracle_tags": [],
                        "sketch_rule": "General hard-policy clause.",
                        "explanation": "Model proposed the wrong expected output.",
                    }),
                    reasoning="", usage={}, request={}, response={},
                )

        promoted, record = experiment.call_oracle(
            case, {"operation": "recommend", "breed": "Persian"},
            WrongSpecClient(), experiment.Ledger(),
        )
        self.assertEqual(promoted["expected"], case["expected"])
        self.assertEqual(promoted["sketch_rule"], case["sketch_rule"])
        self.assertFalse(record["reference_agreement"])
        self.assertEqual(record["promotion_authority"], "reviewed_reference")
        self.assertEqual(record["model_sketch_rule_proposal"], "General hard-policy clause.")

    def test_failed_initial_anchor_is_repaired_before_ce1(self):
        calls = []
        sketches_seen = []

        def fake_developer(workspace, promoted, active_failure, arm, phase, label,
                           client, ledger, complete_corpus=None):
            del promoted, arm, label, client, ledger, complete_corpus
            calls.append((phase, active_failure and active_failure["id"]))
            sketches_seen.append((workspace / "SKETCH.md").read_text())
            (workspace / "strategy.py").write_text(
                "def recommend(profile, breeds, rules, oracle_tags):\n"
                "    return {'operation': 'recommend', 'breed': breeds[0]['name'], "
                "'cited_rules': [], 'rationale': 'generated'}\n"
            )
            (workspace / "oracle_prompt.txt").write_text("Read {note}.\n")
            (workspace / "SKETCH.md").write_text(f"# Revised sketch {len(calls)}\n")
            return {
                "strategy_py": "generated", "oracle_prompt": "generated",
                "sketch_md": f"# Revised sketch {len(calls)}",
            }, {"error": None, "diffs": {}}

        gates = iter([
            {"passed": False, "passed_count": 0, "total": 1,
             "cases": [self._evaluation(experiment.initial_acceptance_case(), False)]},
            {"passed": True, "passed_count": 1, "total": 1,
             "cases": [self._evaluation(experiment.initial_acceptance_case(), True)]},
            {"passed": True, "passed_count": 1, "total": 1,
             "cases": [self._evaluation(experiment.initial_acceptance_case(), True)]},
        ])

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(experiment, "call_developer", side_effect=fake_developer), \
             patch.object(experiment, "run_gate", side_effect=lambda *_a, **_k: next(gates)):
            result = experiment.run_iterative(
                Path(tmp), [], object(), experiment.Ledger(), max_repairs=1,
            )

            self.assertEqual(calls, [
                ("initial", None),
                ("repair", "initial-preference-ranking"),
            ])
            self.assertIn("# Initial CatSynth sketch", sketches_seen[0])
            self.assertEqual(sketches_seen[1], "# Revised sketch 1\n")
            self.assertEqual(len(result["initial_generation"]["attempts"]), 2)
            generations = sorted((Path(tmp) / "generations").iterdir())
            self.assertEqual([path.name for path in generations], [
                "000-initial-generation",
                "001-repair-initial-preference-ranking-attempt-01",
            ])
            active = json.loads((generations[1] / "active_failure.json").read_text())
            self.assertEqual(active["id"], "initial-preference-ranking")

    def test_passing_proposal_is_rejected_as_not_a_counterexample(self):
        case = json.loads(experiment.CASES_PATH.read_text())[0]

        def fake_initial(workspace, promoted, active_failure, arm, phase, label,
                         client, ledger, complete_corpus=None):
            del promoted, active_failure, arm, phase, label, client, ledger, complete_corpus
            (workspace / "strategy.py").write_text(
                "def recommend(profile, breeds, rules, oracle_tags):\n"
                "    return {'operation': 'recommend', 'breed': breeds[0]['name'], "
                "'cited_rules': [], 'rationale': 'generated'}\n"
            )
            (workspace / "oracle_prompt.txt").write_text("Read {note}.\n")
            return {"strategy_py": "generated"}, {"error": None}

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(experiment, "call_developer", side_effect=fake_initial), \
             patch.object(experiment, "call_oracle") as oracle, \
             patch.object(experiment, "evaluate_case", return_value=self._evaluation(case, True)):
            result = experiment.run_iterative(
                Path(tmp), [case], object(), experiment.Ledger(), max_repairs=2,
            )
        self.assertFalse(oracle.called)
        self.assertEqual(result["promoted"], [])
        self.assertEqual(result["cycles"][0]["status"], "coverage-not-promoted")

    def test_full_regression_includes_initial_anchor_and_promoted_cases(self):
        case = json.loads(experiment.CASES_PATH.read_text())[0]
        seen = []

        def fake_evaluate(workspace, evaluated_case, active_rules, client, ledger, label):
            del workspace, active_rules, client, ledger, label
            seen.append(evaluated_case["id"])
            return self._evaluation(evaluated_case, True)

        with patch.object(experiment, "evaluate_case", side_effect=fake_evaluate):
            gate = experiment.run_gate(
                Path("/tmp"), [case], object(), experiment.Ledger(), "regression",
            )
        self.assertTrue(gate["passed"])
        self.assertEqual(seen, ["initial-preference-ranking", case["id"]])

    def test_codex_backend_pins_spark_low_and_minimal_other_controls(self):
        class FakeCodex(CodexAppServerClient):
            def __init__(self):
                self.model = DEFAULT_CODEX_MODEL
                self.cwd = "/tmp"
                self.timeout = 1
                self.initialization_transcript = []
                self.requests = []
                self.events = iter([
                    {
                        "method": "item/completed",
                        "params": {"item": {
                            "type": "agentMessage",
                            "text": '{"strategy_py":"pass","oracle_prompt":"{note}"}',
                        }},
                    },
                    {
                        "method": "thread/tokenUsage/updated",
                        "params": {"tokenUsage": {"last": {
                            "inputTokens": 100, "outputTokens": 20,
                            "totalTokens": 120, "cachedInputTokens": 40,
                            "reasoningOutputTokens": 3,
                        }}},
                    },
                    {"method": "turn/completed", "params": {}},
                ])

            def _rpc(self, method, params, transcript):
                self.requests.append((method, params))
                if method == "thread/start":
                    return {"result": {"thread": {"id": "thread-1"}}}
                if method == "turn/start":
                    return {"result": {"turn": {"id": "turn-1"}}}
                raise AssertionError(method)

            def _read(self, timeout=None):
                return next(self.events)

        client = FakeCodex()
        result = client.chat(
            [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": "Repair it."},
            ],
            extra={"output_schema": DEVELOPER_OUTPUT_SCHEMA},
        )
        thread = client.requests[0][1]
        turn = client.requests[1][1]
        self.assertEqual(DEFAULT_CODEX_MODEL, "gpt-5.3-codex-spark")
        self.assertEqual(turn["model"], "gpt-5.3-codex-spark")
        self.assertEqual(turn["effort"], "low")
        self.assertEqual(turn["summary"], "none")
        self.assertEqual(turn["personality"], "none")
        self.assertNotIn("collaborationMode", turn)
        self.assertNotIn("multiAgentMode", turn)
        self.assertEqual(turn["environments"], [])
        self.assertEqual(turn["permissions"], ":read-only")
        self.assertEqual(turn["outputSchema"], DEVELOPER_OUTPUT_SCHEMA)
        self.assertFalse(thread["allowProviderModelFallback"])
        self.assertEqual(thread["dynamicTools"], [])
        self.assertEqual(result.usage["reasoning_tokens"], 3)
        self.assertEqual(result.usage["cached_prompt_tokens"], 40)

    def test_generation_snapshot_is_complete_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            baseline_workspace(workspace)
            gate = {"passed": False, "passed_count": 0, "total": 1, "cases": []}
            developer = {"content": "replacement", "usage": {"total_tokens": 10}}
            snapshot = root / "generations" / "001-example-attempt-01"

            snapshot_generation(snapshot, workspace, [], gate, developer)

            self.assertEqual(
                (snapshot / "strategy.py").read_bytes(),
                (BASELINE / "strategy.py").read_bytes(),
            )
            self.assertEqual(
                (snapshot / "oracle_prompt.txt").read_bytes(),
                (BASELINE / "oracle_prompt.txt").read_bytes(),
            )
            self.assertTrue((snapshot / "SKETCH.md").is_file())
            self.assertEqual(
                (snapshot / "SKETCH.md").read_bytes(),
                experiment.INITIAL_SKETCH_PATH.read_bytes(),
            )
            self.assertEqual(json.loads((snapshot / "gate.json").read_text()), gate)
            self.assertEqual(json.loads((snapshot / "developer.json").read_text()), developer)

    def test_strategy_validator_rejects_scenario_specific_imports(self):
        source = """import os
def recommend(profile, breeds, rules, oracle_tags):
    return {'operation': 'abstain', 'breed': None, 'cited_rules': [], 'rationale': ''}
"""
        with self.assertRaises(ExperimentError):
            validate_strategy(source)

    def test_strategy_validator_rejects_fixture_specific_branching(self):
        source = """def recommend(profile, breeds, rules, oracle_tags):
    if profile.get('scenario_id') == 'soft_rules_compose':
        return {'operation': 'recommend', 'breed': 'British Shorthair', 'cited_rules': [], 'rationale': ''}
    return {'operation': 'escalate', 'breed': None, 'cited_rules': [], 'rationale': ''}
"""
        with self.assertRaisesRegex(ExperimentError, "prohibited case literal"):
            validate_strategy(source)

    def test_strategy_validator_allows_generic_scenario_id_safeguard(self):
        source = """def recommend(profile, breeds, rules, oracle_tags):
    safe_rules = [rule for rule in rules if rule.get('trait') != 'scenario_id']
    return {'operation': 'escalate', 'breed': None, 'cited_rules': [], 'rationale': str(len(safe_rules))}
"""
        validate_strategy(source)

    def test_generated_strategy_sandbox_allows_pure_map_and_filter(self):
        source = """def recommend(profile, breeds, rules, oracle_tags):
    names = list(map(lambda breed: breed.get('name'), filter(lambda breed: isinstance(breed, dict), breeds)))
    return {'operation': 'recommend', 'breed': names[0], 'cited_rules': [], 'rationale': 'generic'}
"""
        recommend = experiment.load_recommend(source)
        result = recommend({}, [{"name": "Generic"}], [], [])
        self.assertEqual(result["breed"], "Generic")

    def test_codex_adapter_detects_usage_limit_instead_of_empty_completion(self):
        transcript = [{
            "direction": "server",
            "message": {
                "method": "error",
                "params": {"error": {
                    "codexErrorInfo": "usageLimitExceeded",
                    "message": "try again later",
                }},
            },
        }]
        error = CodexAppServerClient._terminal_error(transcript)
        self.assertEqual(error["codexErrorInfo"], "usageLimitExceeded")
        self.assertTrue(issubclass(CodexAppServerError, RuntimeError))


if __name__ == "__main__":
    unittest.main()
