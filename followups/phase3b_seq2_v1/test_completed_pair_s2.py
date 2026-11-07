"""Finite immutable-origin join checks; no model, network or journal execution."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import accounting, completed_pair, deadline, remaining, report, snapshot, support, transport
from .test_inspect_s2 import fixture_records
from .test_workflow_s2 import completed_fixture


def split_fixture() -> tuple[dict, dict, dict]:
    study, state, saved = completed_fixture()
    first_branches = {key: value for key, value in saved["branches"].items() if key[0] == "p3b-01"}
    first_ids = {row["id"] for row in study["assessment_plan"] if row["pilot"] == "p3b-01"}
    old_results = {slot: value for slot, value in state["results"].items()
                   if study["slots"][slot]["pair"] == "p3b-01"}
    cert = support.seal({"kind": completed_pair.KIND,
        "generation_study_sha256": completed_pair.GENERATION,
        "assessment_execution_study_sha256": completed_pair.EXECUTION,
        "accounting": {"known_spent_micro_usd": 11_239_856, "provider_calls": 361, "reserved_micro_usd": 0},
        "historical_accounting": {"known_spent_micro_usd": 90_848_979, "provider_calls": 3189,
                                  "reserved_micro_usd": 22_880_000}})
    imported = {"record": cert, "branches": first_branches,
        "assessments": {key: value for key, value in saved["assessments"].items() if key in first_ids},
        "seals": {"p3b-01": saved["seals"]["p3b-01"]}, "results": old_results,
        "intents": {slot: state["intents"][slot] for slot in old_results},
        "slots": {slot: study["slots"][slot] for slot in old_results},
        "audit_intervals": {}, "accounting": cert["accounting"], "supplement_slots": [],
        "origin": {key: cert[key] for key in ("generation_study_sha256", "assessment_execution_study_sha256")}}
    study.update(imported_first_pair=cert, execution_pilots=list(remaining.PILOTS),
                 policy=copy.deepcopy(remaining.POLICY), maximum_admitted_attempts=1758)
    study["slots"] = {slot: value for slot, value in study["slots"].items() if value["pair"] != "p3b-01"}
    for name in ("results", "intents"):
        state[name] = {slot: value for slot, value in state[name].items() if slot not in old_results}
    state["cells"] = {cell: value for cell, value in state["cells"].items() if not cell.startswith("p3b-01:")}
    state["attempts"] -= len(old_results)
    saved["branches"] = {key: value for key, value in saved["branches"].items() if key[0] != "p3b-01"}
    saved["seals"].pop("p3b-01")
    saved["assessments"] = {key: value for key, value in saved["assessments"].items() if key not in first_ids}
    saved["completed_first_pair"] = imported
    return study, state, saved


class CompletedPairTests(unittest.TestCase):
    def test_imported_editor_audit_requires_its_original_full_bindings(self):
        bindings = accounting._bindings({"inputs": {"study_sha256": completed_pair.GENERATION,
            "bindings": {key: char * 64 for key, char in (
                ("source_sha256", "a"), ("policy_sha256", "b"), ("launcher_sha256", "c"))}}})
        slot = "p3b-01.adaptive.editor.inv1.a1.t01"
        clock = deadline.clock_record(study_sha256=bindings["study_sha256"],
            source_sha256=bindings["source_sha256"], pilot="p3b-01", label="inv1.a1",
            fixture=True, editor_profile_sha256="d" * 64, started=100)
        gate = support.seal({"kind": "phase3b-soft-time-gate-v1", "clock_sha256": clock["sha256"],
            "slot_id": slot, "bindings": bindings, "checked_monotonic": 101,
            "soft_deadline_monotonic": clock["grace_deadline_monotonic"], "reviews": []})
        budget = deadline.budget(now=102)
        intent = {"slot_id": slot, "role": "editor", "study_sha256": completed_pair.GENERATION,
                  "fixture": True, "request_sha256": "e" * 64}
        result = {"status": "response", "reserved_micro_usd": 0}
        audit = support.seal({"kind": "phase3b-s2-transport-audit-v2", **bindings,
            "slot_id": slot, "role": "editor", "fixture": True, "intent_sha256": digest(intent),
            "request_sha256": intent["request_sha256"], "budget": budget.record(),
            "parent_capture_monotonic": 103, "finished_utc": "2026-11-06T00:00:01+00:00",
            "capture_point": "parent after complete receipt normalization and frozen core model/usage validation",
            "elapsed_seconds": 1, "cleanup_elapsed_seconds": 0, "sdk_invoked": True,
            "wire_egress": "unknown", "timeout_subtype": None, "completion_category": "known",
            "late_known": False, "deadline_expired": False, "cleanup_failed": False,
            "worker_stopped": True, "owner_stop_required": False, "worker_pid": 1,
            "terminal_result_sha256": digest(result), "terminal_status": "response",
            "terminal_reserved_micro_usd": 0, "conversation_timing": {"clock": clock, "gate": gate}})
        self.assertEqual(transport.validate_audit(audit, intent=intent, result=result, bindings=bindings), audit)
        with self.assertRaisesRegex(ContractError, "invalid bounded transport"):
            transport.validate_audit(audit, intent=intent, result=result,
                bindings={key: value for key, value in bindings.items() if key != "study_sha256"})

    def test_certificate_must_equal_independently_rebuilt_evidence(self):
        record = support.seal({"kind": completed_pair.KIND, "selected_checkpoint": "c1"})
        with patch.object(completed_pair, "_load", return_value=(record, {"record": record})):
            self.assertEqual(completed_pair.verify_certificate(record)["record"], record)
            changed = support.seal({"kind": completed_pair.KIND, "selected_checkpoint": "c2"})
            with self.assertRaises(ContractError):
                completed_pair.verify_certificate(changed)

    def test_join_preserves_original_objects_and_refuses_replacements(self):
        study, _, saved = split_fixture()
        before = copy.deepcopy(saved)
        joined = completed_pair.join(study, saved)
        self.assertEqual(saved, before)
        self.assertIs(joined["branches"]["p3b-01", "adaptive"],
                      saved["completed_first_pair"]["branches"]["p3b-01", "adaptive"])
        saved["branches"]["p3b-01", "adaptive"] = {}
        with self.assertRaises(ContractError):
            completed_pair.join(study, saved)

    def test_four_pair_aggregate_keeps_original_ids_without_double_charging(self):
        study, state, saved = split_fixture()
        before = copy.deepcopy((state, saved))
        data = report.build(study, state, saved, True)
        self.assertEqual((len(data["rows"]), len(data["coverage"]["primary_rows"])), (12, 8))
        self.assertEqual(data["summary"]["assessment_scored"], 12)
        self.assertEqual(data["summary"]["status"], "mock-complete")
        self.assertFalse(data["summary"]["scientific_complete"])
        self.assertEqual(data["summary"]["attempts"], state["attempts"])
        self.assertEqual(data["summary"]["imported_first_pair_accounting"]["provider_calls"], 361)
        self.assertIsNone(data["summary"]["lineage_spent_micro_usd"])
        self.assertEqual((state, saved), before)
        state.update(fixture=False, spent_micro_usd=1_000_000, provider_calls=20)
        resources = report._historical_resources(study, state)
        self.assertEqual(resources["lineage_spent_micro_usd"], 91_848_979)
        self.assertEqual(resources["whole_pilot_known_spent_micro_usd"], 12_239_856)
        self.assertEqual(resources["lineage_provider_calls"], 3209)

    def test_new_checker_hold_preserves_three_imported_assessments(self):
        study, state, saved = split_fixture()
        saved["validation_failure"] = {"classification": "integrity_hold"}
        data = report.build(study, state, saved, True)
        self.assertEqual(data["summary"]["assessment_scored"], 3)
        self.assertEqual([row["status"] for row in data["rows"][:3]], ["scored"] * 3)
        self.assertTrue(all(row["status"] == "unvalidated_integrity_hold" for row in data["rows"][3:]))
        self.assertFalse(data["summary"]["scientific_complete"])

    def test_per_arm_resource_fractions_use_declared_remaining_contract(self):
        study, state, _ = split_fixture()
        for cell, value in state["cells"].items():
            bounds = remaining.POLICY["cell_bounds"][cell.rsplit(":", 1)[1]]
            value.update(attempts=bounds["http"], input_tokens=bounds["input"], output_tokens=bounds["output"])
        utilization = report._resources(study, state)["inference_allowance_utilization"]
        self.assertTrue(all(row["http_fraction"] == row["input_fraction"] == row["output_fraction"] == 1
                            for row in utilization.values()))

    def test_mixed_inspect_projection_preserves_live_origin_under_fixture_banner(self):
        study, data, saved = fixture_records()
        first_keys = [key for key in saved["branches"] if key[0] == "p3b-01"]
        first_ids = {r["assessment_id"] for r in data["rows"] if r["pilot"] == "p3b-01"}
        for key in first_keys:
            branch = saved["branches"][key]
            branch.update(study_sha256=completed_pair.GENERATION, fixture=False)
            portfolios = [branch["result"]["portfolio"], *branch["result"].get("checkpoints", {}).values()]
            for portfolio in portfolios:
                portfolio["fixture"] = False
            branch["portfolio_sha256"] = digest(branch["result"]["portfolio"])
        for row in data["rows"]:
            first = row["pilot"] == "p3b-01"
            row.update(imported=first, origin_fixture=not first,
                generation_study_sha256=completed_pair.GENERATION if first else study["study_sha256"],
                assessment_execution_study_sha256=completed_pair.EXECUTION if first else study["study_sha256"])
            if first:
                branch = saved["branches"][row["pilot"], row["arm"]]["result"]
                portfolio = branch["portfolio"] if row["target"] == "fixed" else branch["checkpoints"][row["target"]]
                assessed = saved["assessments"][row["assessment_id"]]
                assessed.update(fixture=False, portfolio_sha256=digest(portfolio))
                row.update(final_sha256=digest(portfolio), assessment_sha256=digest(assessed))
        for alias in data["coverage"]["primary_rows"]:
            source = next(r for r in data["rows"] if r["pilot"] == alias["pilot"]
                          and r["target"] == ("fixed" if alias["arm"] == "fixed" else alias["selected_checkpoint"]))
            alias.update({k: copy.deepcopy(v) for k, v in source.items() if k != "target"})
        cert = support.seal({"kind": completed_pair.KIND})
        study["imported_first_pair"] = cert
        imported = {"record": cert, "branches": {key: saved["branches"].pop(key) for key in first_keys},
            "assessments": {key: saved["assessments"].pop(key) for key in first_ids},
            "seals": {}, "slots": {}, "audit_intervals": {},
            "origin": {"generation_study_sha256": completed_pair.GENERATION,
                       "assessment_execution_study_sha256": completed_pair.EXECUTION}}
        saved["completed_first_pair"] = imported
        payload = snapshot.build_snapshot(study, data, saved, "closure")
        self.assertTrue(payload["fixture"])
        self.assertFalse(payload["summary"]["scientific_complete"])
        self.assertFalse(payload["finals"][0]["portfolio"]["fixture"])
        self.assertEqual(payload["source_identities"]["imported_first_pair"]["generation_study_sha256"], completed_pair.GENERATION)
        changed = copy.deepcopy(data)
        changed["rows"][0]["generation_study_sha256"] = study["study_sha256"]
        with self.assertRaises(snapshot.CanonicalIntegrityError):
            snapshot.build_snapshot(study, changed, saved, "closure")


if __name__ == "__main__":
    unittest.main()
