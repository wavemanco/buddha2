"""Synthetic closed-record bindings and native presentation; no corpus or provider."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash
from followups.phase4_cm1_v1 import snapshot as s


def seal(value):
    return value | {"sha256": digest(value)}


class SnapshotTests(unittest.TestCase):
    def source_records(self, base, *, confirmation=False, fixture=True):
        task = {"id": "synthetic-01", "prompt": "SYNTHETIC task only"}
        study = {"kind": "buddha2-phase4-cm1-v1", "source": {"sha256": "1" * 64},
            "source_sha256": "1" * 64, "launcher_sha256": "2" * 64,
            "method": {"definition_sha256": "3" * 64}, "method_sha256": "4" * 64,
            "confirmation_source_sha256": "5" * 64, "exposure_inventory_sha256": "6" * 64,
            "editor_tools": {}, "development": [{"pilot_id": "dev02", "task": task},
                {"pilot_id": "dev04", "task": task | {"id": "synthetic-02"}}]}
        study["study_sha256"] = digest(study)
        pair, kind = ("p4-01", "inference") if confirmation else ("dev02", "dev")
        allocation = seal({"parent_sha256": study["study_sha256"], "ordinal": 1,
                           "child_kind": kind, "pair": pair, "task_sha256": digest(task)})
        profile = {"phase4_child": {"parent_sha256": study["study_sha256"], "kind": kind, "pair": pair}}
        child = digest({"parent": study["study_sha256"], "allocation": allocation,
                        "profile": profile, "task_sha256": digest(task)})
        bindings = {"source_sha256": study["source_sha256"], "policy_sha256": digest(profile),
                    "launcher_sha256": study["launcher_sha256"]}
        opened = seal({"kind": "phase4-cm1-child-open-v1", "child_sha256": child,
            "allocation": allocation, "profile": profile, "task": task,
            "bindings": bindings, "slots": {}, "authority": {"study_sha256": child}})
        value = ({"kind": "phase4-cm1-generation-v1", "task": task, "pair": pair,
                  "generation_study_sha256": child, "adaptive": None, "fixed": None}
                 if confirmation else {"portfolio": None, "status": "failed"})
        state = {"intents": {}, "results": {}, "status": "ready", "attempts": 0,
                 "spent_micro_usd": 0, "reserved_micro_usd": 0, "transport_audit_summary": {}}
        journal = base / "synthetic-journal"
        closure = seal({"kind": "phase4-cm1-child-close-v1", "parent_sha256": study["study_sha256"],
            "child_sha256": child, "child_kind": kind, "pair": pair, "open_sha256": opened["sha256"],
            "journal": str(journal), "result_sha256": digest(value),
            **{k: state[k] for k in ("status", "attempts", "spent_micro_usd", "reserved_micro_usd", "transport_audit_summary")}})
        folder = base / "children" / f"001-{kind}-{pair}"
        folder.mkdir(parents=True)
        for name, obj in (("open.json", opened), ("closure.json", closure), ("result.json", value)):
            (folder / name).write_text(json.dumps(obj), encoding="utf-8")
        manifest = {"inputs": {"study_sha256": child, "slots": {}, "authority": opened["authority"],
            "fixture": fixture, "bindings": bindings, "policy": profile, "editor_tools": {}}}
        if confirmation and not fixture:
            rows = [{"source_task_id": "synthetic-01" if i == 1 else f"synthetic-{i:02d}",
                     "prompt_sha256": digest(task["prompt"] if i == 1 else f"SYNTHETIC unseen {i}")}
                    for i in range(1, 25)]
            selected = {"frozen_method_sha256": study["method_sha256"],
                "source_sha256": study["confirmation_source_sha256"],
                "exposure_inventory_sha256": study["exposure_inventory_sha256"],
                "eligibility_passed": True, "selected": rows}
            selected["manifest_sha256"] = digest(selected)
            path = base / "confirmation-manifest.json"
            path.write_text(json.dumps(selected), encoding="utf-8")
            (base / "started.json").write_text(json.dumps({"study_sha256": study["study_sha256"],
                "confirmation_manifest_sha256": file_hash(path)}), encoding="utf-8")
        return study, folder, (journal, state, manifest, {})

    def build(self, study, base, ledger, **changes):
        def read(path, observed):
            observed[path] = file_hash(path)
            return json.loads(path.read_text(encoding="utf-8"))

        fake = types.SimpleNamespace(KIND="buddha2-phase4-cm1-v1", path=lambda p: p,
                                     source_identity=lambda: study["source"])
        package = sys.modules["followups.phase4_cm1_v1"]
        with ExitStack() as stack:
            stack.enter_context(patch.object(package, "release", fake, create=True))
            stack.enter_context(patch.object(s, "_read", side_effect=read))
            if isinstance(ledger, dict):
                stack.enter_context(patch.object(s, "_ledger", side_effect=lambda opened, *_: ledger[opened["child_sha256"]]))
            else:
                stack.enter_context(patch.object(s, "_ledger", return_value=ledger))
            return s.build_snapshot(study, base, fixture=changes.get("fixture", True), status="partial")

    def test_qualification_missing_cases_stay_missing_and_sources_do_not_change(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            study, folder, ledger = self.source_records(base)
            before = {p: p.read_bytes() for p in folder.iterdir()}
            result = self.build(study, base, ledger)
            self.assertEqual(result["scope"], "qualification_only")
            self.assertEqual(len(result["cases"]), 2)
            self.assertTrue(all(c["outputs"] is None and c["started_at"] is None for c in result["cases"]))
            self.assertEqual(before, {p: p.read_bytes() for p in folder.iterdir()})

    def test_fixture_uses_actual_unit_and_live_saved_manifest_keeps_all24_without_corpus(self):
        for fixture, count in ((True, 1), (False, 24)):
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as name:
                base = Path(name)
                study, _, ledger = self.source_records(base, confirmation=True, fixture=fixture)
                result = self.build(study, base, ledger, fixture=fixture)
                self.assertEqual(len(result["cases"]), count)
                self.assertEqual(sum(bool(c["prompt"]) for c in result["cases"]), 1)

    def test_result_and_open_source_tampering_rejects(self):
        for filename in ("result.json", "open.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as name:
                base = Path(name)
                study, folder, ledger = self.source_records(base)
                path = folder / filename
                value = json.loads(path.read_text())
                if filename == "result.json":
                    value["status"] = "forged"
                else:
                    value["bindings"]["source_sha256"] = "0" * 64
                    value = seal({k: v for k, v in value.items() if k != "sha256"})
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ContractError):
                    self.build(study, base, ledger)

    def test_failed_generation_with_all_missing_targets_still_exports_its_case(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            study, first, generation_ledger = self.source_records(base, confirmation=True)
            generation_open = json.loads((first / "open.json").read_text())
            task = generation_open["task"]
            generation_child = generation_open["child_sha256"]
            allocation = seal({"parent_sha256": study["study_sha256"], "ordinal": 2,
                "child_kind": "assessment", "pair": "p4-01", "task_sha256": digest(task)})
            profile = {"phase4_child": {"parent_sha256": study["study_sha256"], "kind": "assessment",
                "pair": "p4-01", "generation_study_sha256": generation_child}}
            child = digest({"parent": study["study_sha256"], "allocation": allocation,
                            "profile": profile, "task_sha256": digest(task)})
            bindings = {"source_sha256": study["source_sha256"], "policy_sha256": digest(profile),
                        "launcher_sha256": study["launcher_sha256"]}
            opened = seal({"kind": "phase4-cm1-child-open-v1", "child_sha256": child, "task": task,
                "allocation": allocation, "profile": profile, "bindings": bindings, "slots": {},
                "authority": {"study_sha256": child}, "generation_study_sha256": generation_child})
            row = {"prompt_id": task["id"], "pair": "p4-01", "selected_checkpoint": None,
                   "targets": dict.fromkeys(("fixed", "c1", "c2"))}
            journal, state, _, audits = generation_ledger
            manifest = {"inputs": {"study_sha256": child, "slots": {}, "authority": opened["authority"],
                "fixture": True, "bindings": bindings, "policy": profile, "editor_tools": {}}}
            closure = seal({"kind": "phase4-cm1-child-close-v1", "parent_sha256": study["study_sha256"],
                "child_sha256": child, "child_kind": "assessment", "pair": "p4-01",
                "open_sha256": opened["sha256"], "journal": str(journal), "result_sha256": digest(row),
                **{k: state[k] for k in ("status", "attempts", "spent_micro_usd", "reserved_micro_usd", "transport_audit_summary")}})
            folder = base / "children/002-assessment-p4-01"
            folder.mkdir()
            for filename, value in (("open.json", opened), ("closure.json", closure), ("result.json", row)):
                (folder / filename).write_text(json.dumps(value), encoding="utf-8")
            result = self.build(study, base, {generation_child: generation_ledger,
                                             child: (journal, state, manifest, audits)})
            case = result["cases"][0]
            self.assertIsNone(case["outputs"])
            self.assertEqual(case["metrics"]["targets"], dict.fromkeys(("fixed", "c1", "c2")))
            forged = seal({"kind": "phase4-cm1-target-assessment-v1", "fixture": True,
                           "official": {"fixture": True, "task_id": task["id"]}})
            with self.assertRaises(ContractError):
                s._targets(row | {"targets": {"fixed": forged, "c1": None, "c2": None}}, None, task, True)

    def test_dates_cache_costs_and_unknown_requests_are_truthful_metadata(self):
        request = {"model": "claude-sonnet-5-5", "max_tokens": 4096,
                   "messages": [{"content": "DO NOT COPY RAW REQUEST"}]}
        intent = {"role": "answer", "study_sha256": "a" * 64, "request": request,
                  "request_sha256": digest(request), "reservation": {"micro_usd": 2540960},
                  "cell": "p4-01:adaptive", "pair": "p4-01"}
        usage = {"input_tokens": 2, "output_tokens": 3, "cache_creation_input_tokens": 5,
                 "cache_read_input_tokens": 7}
        response = {"model": "claude-sonnet-5-5", "usage": usage, "text": "DO NOT COPY RESPONSE"}
        result = {"status": "response", "response": response, "input_tokens": 14, "output_tokens": 3,
                  "spent_micro_usd": 123, "reserved_micro_usd": 0}
        state = {"study_sha256": "b" * 64, "intents": {"known": intent, "unknown": intent},
                 "results": {"known": result}}
        audit = {"budget": {"started_utc": "2026-11-08T12:00:00Z"},
                 "finished_utc": "2026-11-08T12:00:02Z", "elapsed_seconds": 2}
        events, models, undated = s.project_requests(state, {"known": audit})
        model = models["claude-sonnet-5-5"]
        self.assertEqual((model["input_tokens"], model["total_tokens"]), (2, 17))
        self.assertEqual((model["input_tokens_cache_write"], model["input_tokens_cache_read"]), (5, 7))
        self.assertEqual(model["total_cost"], 0.000123)
        self.assertEqual(events[0]["timestamp"], "2026-11-08T12:00:00Z")
        self.assertEqual(events[0]["data"]["cell"], "p4-01:adaptive")
        self.assertEqual(events[0]["data"]["child_sha256"], "b" * 64)
        self.assertEqual(events[0]["data"]["request_study_sha256"], "a" * 64)
        self.assertEqual(len(undated), 1)
        self.assertIsNone(undated[0]["spent_micro_usd"])
        self.assertNotIn("DO NOT COPY", json.dumps([events, undated]))


if __name__ == "__main__":
    unittest.main()
