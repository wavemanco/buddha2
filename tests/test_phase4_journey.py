"""One real native/OpenCode journey with accounted SDK mocks, never confirmation data."""
from __future__ import annotations

import copy
import json
import os
import unittest
import uuid
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_once
from followups.phase3b_seq2_v1 import accounting, native, strategy, verify
from followups.phase3b_seq2_v1.mocks import StudyMock
from followups.phase3b_seq2_v1.support import BASE, LAUNCHER, NATIVE, ROOT, seal
from followups.phase4_cm1_v1 import assessment, control, policy, release, snapshot, workflow


class OnePoolMock(StudyMock):
    """Fixture usage makes one whole fixed pool sufficient; production rules are unchanged."""
    def __init__(self, fixed_slots):
        super().__init__()
        self.fixed_slots = fixed_slots

    def _handle(self, request, *, http_module):
        response = super()._handle(request, http_module=http_module)
        if self._selected and self._selected[1] in self.fixed_slots:
            payload = response.json()
            payload["usage"]["input_tokens"] = 10_000
            self.records[-1]["response"] = copy.deepcopy(payload)
            return http_module.Response(response.status_code, json=payload,
                headers={"request-id": self.records[-1]["request_id"]})
        return response


class JourneyCoordinator(workflow.Coordinator):
    """Retain the actual closed ledger handles for a no-dispatch replay assertion."""
    def __init__(self, *args):
        super().__init__(*args)
        self.ledgers = []

    def close(self, ledger, result):
        value = super().close(ledger, result)
        self.ledgers.append(ledger)
        return value


@unittest.skipUnless(os.getenv("BUDDHA2_NATIVE_JOURNEY") == "1", "explicit pinned native journey only")
class Phase4JourneyTests(unittest.TestCase):
    def test_actual_native_generation_seal_assessment_and_zero_call_saved_replay(self):
        self.assertEqual({path.name for path in Path("/sys/class/net").iterdir()}, {"lo"})
        self.assertEqual(os.environ.get("BUDDHA2_OFFLINE"), "1")
        self.assertFalse(any(name in os.environ for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")))
        identifier = uuid.uuid4().hex
        run = BASE / "phase4-native-journey" / identifier
        self.assertFalse(run.exists())
        source_before = release.source_identity()
        method = {"definition_sha256": file_hash(ROOT / release.DEFINITION), "fixture_only": True}
        study = {"kind": release.KIND, "fixture": True, "fixture_only_scientific_units": 1,
            "source": source_before, "method": method, "method_sha256": digest(method), "development": [],
            "source_sha256": source_before["sha256"], "launcher_sha256": file_hash(LAUNCHER),
            "authorization_sha256": file_hash(policy.AUTHORITY),
            "execution_tag": "p4-fixture-" + identifier,
            "editor_tools": read_json(ROOT / "followups/phase3a_v1/editor-tools.json")}
        study["study_sha256"] = digest(study)
        write_once(run / "study.json", study)
        task = workflow._tasks(run / "study.json", study, fixture=True)[0]
        self.assertEqual(task["source_context"]["dataset"], "synthetic")
        pair = "p4-01"
        seed = run / "seed"
        strategy.materialize_seed(seed)
        worklist = workflow.worklist(study, "inference", pair, task)
        fixed_slots = {name for name, meta in worklist.items() if meta["cell"] == pair + ":fixed"}
        with OnePoolMock(fixed_slots) as mock:
            book = JourneyCoordinator(study, run, mock.transport)
            # Qualification is separately tested; this one-unit fixture makes no cost-match claim.
            book.qualification = True
            with self.assertRaises(ContractError):
                book.open("assessment", pair, task, generation_study_sha256="a" * 64)
            self.assertEqual(len(mock.records), 0)
            generation = workflow._generation(book, pair, task, seed)
            self.assertIsNone(generation["failure"])
            self.assertEqual(generation["required_failures"], [])
            self.assertEqual(generation["adaptive"]["status"], "complete")
            self.assertEqual(generation["fixed"]["status"], "complete")
            self.assertEqual(len(generation["fixed"]["pools"]), 1)
            self.assertIsNone(generation["fixed"]["selection"])
            generation_ledger = book.ledgers[0]
            generation_state = generation_ledger.state()
            self.assertTrue(verify.normal_fixture_path(generation["adaptive"], generation_state["results"]))
            self.assertFalse(any(row["role"] in {"group", "quality"} for row in mock.records))
            self.assertEqual(generation_state["attempts"], len(mock.records))
            self.assertEqual(generation_state["reserved_micro_usd"], 0)
            self.assertEqual(len(generation["adaptive"]["rollouts"]), 8)
            self.assertEqual(len(generation["adaptive"]["stage_dispositions"]), 6)
            with self.assertRaises(ContractError):
                book.open("assessment", pair, task,
                          generation_study_sha256=generation["generation_study_sha256"])
            before_assessment = len(mock.records)
            book.generation_seal = seal({"kind": "phase4-cm1-all-generation-closed-v1",
                "study_sha256": study["study_sha256"], "count": 1, "fixture_only": True,
                "generation_sha256": [digest(generation)]})
            write_once(run / "generation-seal.json", book.generation_seal)
            row = workflow._assessment(book, generation)
            self.assertIsNone(row["failure"])
            self.assertTrue(all(target["complete"] for target in row["targets"].values()))
            self.assertEqual(len(mock.records) - before_assessment, 39)
            assessment_ledger = book.ledgers[1]
            assessment_state = assessment_ledger.state()
            self.assertNotEqual(assessment_ledger.manifest["inputs"]["study_sha256"],
                                generation["generation_study_sha256"])
            self.assertEqual(assessment_state["attempts"], 39)
            self.assertTrue(all(result["study_sha256"] == generation["generation_study_sha256"]
                                for result in assessment_state["results"].values()))
            totals = book.accounting_view()
            self.assertEqual(totals["attempts"], len(mock.records))
            self.assertEqual(totals["spent_micro_usd"], generation_state["spent_micro_usd"]
                             + assessment_state["spent_micro_usd"])
            self.assertEqual(totals["reserved_micro_usd"], 0)
            self.assertFalse(book.blocked)
            self.assertIsNone(book.active)
            self.assertTrue(all(not state["transport_audit_summary"]["missing_or_invalid_slots"]
                                for state in (generation_state, assessment_state)))
            analysis = assessment.analyze_pairs([row])
            self.assertFalse(analysis["scientific_complete"])
            self.assertEqual(analysis["contrasts"]["official"]["utility"]["n"], 1)
            self.assertIsNone(analysis["contrasts"]["official"]["utility"]["interval_95"])
            before = {str(ledger.journal): {name: file_hash(ledger.journal / name)
                for name in ("manifest.json", "events.jsonl")} for ledger in book.ledgers}
            calls_before = len(mock.records)
            child = generation["generation_study_sha256"]
            fixed_id, tag, target_ids = workflow._ids(study, pair)
            search = NATIVE / child / "mock" / pair / "adaptive" / "search"
            replayed_native = native.validate_adaptation(generation["adaptive"], task, seed,
                study_sha256=child, run_root=search, tag=tag, fixture=True,
                results=generation_state["results"], request_policy=generation_ledger.manifest["inputs"]["policy"])
            self.assertEqual(replayed_native, generation["adaptive"])
            replayed_fixed = control.run_fixed(task, seed, study_sha256=child, run_id=fixed_id,
                target_micro_usd=generation["native_micro_usd"], dispatch=generation_ledger.dispatch,
                spent=lambda: generation_ledger.state()["cells"][pair + ":fixed"]["spent_micro_usd"],
                fixture=True, request_policy=generation_ledger.manifest["inputs"]["policy"])
            self.assertEqual(replayed_fixed, generation["fixed"])
            evaluator = native.Phase3NativeAssessment(ROOT / ".upstream/novelty-bench")
            portfolios = {"fixed": generation["fixed"]["portfolio"],
                          **generation["adaptive"]["checkpoints"]}
            replayed_targets = {target: assessment.assess_target(evaluator, portfolio,
                target_ids[target], assessment_ledger.dispatch, official=row["targets"][target]["official"])
                for target, portfolio in portfolios.items()}
            self.assertEqual(replayed_targets, row["targets"])
            self.assertEqual(assessment.analyze_pairs([row]), analysis)
            self.assertEqual(len(mock.records), calls_before)
            self.assertEqual(book.accounting_view(), totals)
            for ledger in book.ledgers:
                self.assertEqual({name: file_hash(ledger.journal / name) for name in before[str(ledger.journal)]},
                                 before[str(ledger.journal)])
                self.assertEqual(accounting.replay(ledger.journal)["reserved_micro_usd"], 0)
            self.assertEqual(release.source_identity(), source_before)
            write_once(run / "analysis.json", analysis)
            projected = snapshot.publish_snapshot(study, run, run / "snapshot.json",
                                                   fixture=True, status="partial")
            self.assertEqual(projected["scope"], "synthetic_fixture_actual_prompt_units")
            self.assertEqual(len(projected["cases"]), 1)
            self.assertFalse(projected["analysis"]["scientific_complete"])
            self.assertTrue(projected["read_only_sources_unchanged"])
            self.assertEqual(projected["cases"][0]["id"], task["id"])
            self.assertTrue(projected["cases"][0]["events"])
            self.assertTrue(projected["cases"][0]["model_usage"])
            self.assertEqual(len(mock.records), calls_before)
            for ledger in book.ledgers:
                self.assertEqual({name: file_hash(ledger.journal / name) for name in before[str(ledger.journal)]},
                                 before[str(ledger.journal)])
            receipt = seal({"kind": "phase4-cm1-one-unit-native-journey-v1", "passed": True,
                "fixture": True, "fixture_only_scientific_units": 1, "scientific_complete": False,
                "actual_native_seq_k": 2, "actual_native_bun_opencode": True,
                "synthetic_proposer_used": False, "native_rollouts": 8, "author_stages": 6,
                "fixed_pools": 1, "fixture_fixed_usage_override_input_tokens": 10_000,
                "assessment_requests": 39, "generation_before_judging": True,
                "generation_and_assessment_distinct_child_ids": True,
                "source_sha256": source_before["sha256"], "mock_sdk_requests": calls_before,
                "external_provider_calls": 0, "real_credentials_used": False,
                "zero_call_saved_replay": True, "journal_hashes_unchanged_on_replay": True,
                "parent_accounting": totals, "generation_sha256": digest(generation),
                "row_sha256": digest(row), "analysis_sha256": digest(analysis),
                "production_snapshot_path": str(run / "snapshot.json"),
                "production_snapshot_sha256": file_hash(run / "snapshot.json"),
                "production_snapshot_cases": 1, "production_snapshot_provider_calls": 0,
                "actual_inspect_export_exercised": False})
            write_once(run / "journey.json", receipt)
            print(json.dumps({"journey_receipt": str(run / "journey.json"),
                              "snapshot_path": str(run / "snapshot.json"),
                              "passed": True, "mock_sdk_requests": calls_before, "provider_calls": 0}))
