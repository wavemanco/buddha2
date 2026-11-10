"""Successor execution through the actual controller and owned mocked SDK ledger.

Native/assessment science is synthetic here; their real replay has separate tests.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from buddha2.phase2_dispatch import build_request
from followups.phase3b_seq2_v1 import native
from followups.phase3b_seq2_v1.mocks import SDKMock
from followups.phase3b_seq2_v1.support import BASE
from followups.phase4_cm1_v1 import assessment, policy, release, workflow


class ResumeWorkflowTests(unittest.TestCase):
    def test_original_authorization_cannot_enable_a_paid_successor_grant(self):
        for reference in (None, release._sealed_reference(policy.AUTHORITY)):
            study = {"source_sha256": "f" * 64, "continuation": {"fixture": False, "spending_authorization": reference}}
            with self.subTest(reference=reference is not None), patch.object(release, "load_study", return_value=study):
                with self.assertRaises(ContractError):
                    release.make_grant(Path("/unused-successor-study.json"), False)

    def test_remaining_parent_admissions_cap_child_before_the_next_intent(self):
        from followups.phase3b_seq2_v1 import accounting
        from followups.phase3b_seq2_v1 import ledger_core as core
        from tests.test_phase4_policy import profile_for

        profile, slots = profile_for("dev", "dev02", remaining_admissions=0)
        self.assertEqual(profile["maximum_admitted_attempts"], 0)
        state = core._start({"run_id": "f" * 64, "inputs": {"policy": profile,
                            "fixture": True, "study_sha256": "e" * 64}})
        meta = next(row for row in slots.values() if row["role"] == "plan")
        with self.assertRaises(accounting.PhaseBudgetStop):
            accounting._admit(state, meta, core._reservation("plan"), policy=profile)
        self.assertEqual(state["attempts"], 0)

    def test_actual_run_adopts_qualification_and_known_native_request_before_missing_admissions(self):
        base = BASE / "resume-workflow-tests"
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        token = uuid.uuid4().hex
        original = {"source_sha256": "b" * 64, "source": {"sha256": "b" * 64}, "launcher_sha256": "c" * 64,
            "authorization_sha256": file_hash(policy.AUTHORITY), "execution_tag": "synthetic-resume-" + token,
            "editor_tools": {}, "development": [{"pilot_id": pair, "task": {"id": "synthetic-" + pair},
                "target_micro_usd": 1} for pair in ("dev02", "dev04")]}
        original["study_sha256"] = digest(original)
        previous_study = folder / "original-study.json"
        write_once(previous_study, original)
        body = build_request("plan", messages=[{"role": "user", "content": "SYNTHETIC controller resume"}],
                             system="SYNTHETIC controller instructions")
        task = workflow._tasks(previous_study, original, fixture=True)[0]
        current = [original]
        incomplete = [True]
        native_slots = []

        def fixed(book, ledger, profile, pair, task, target, seed):
            slot = next(name for name, meta in ledger.manifest["inputs"]["slots"].items()
                        if meta["role"] == "plan" and meta["cell"] == pair + ":fixed")
            ledger.dispatch(slot, "plan", body)
            # Only routing/qualification plumbing is synthetic; dollars remain real ledger amounts.
            return {"status": "complete", "spent_micro_usd": target, "target_micro_usd": target}

        def adaptation(task, seed, **kwargs):
            ids = native.adaptive_run_ids(task["id"], kwargs["tag"])
            slots = [workflow.strategy.slot_ids(ids[label])["plan"] for label in ("base1", "base2")]
            native_slots[:] = slots
            kwargs["dispatch"](slots[0], "plan", body)
            if incomplete[0]:
                raise native.RequiredCheckpointStop("SYNTHETIC stop after durable request before stage output")
            kwargs["dispatch"](slots[1], "plan", body)
            return {"status": "complete", "authentic": True, "selected_checkpoint": "c1",
                    "checkpoints": {"c1": None, "c2": None}, "stage_dispositions": []}

        def assess(book, generation):
            ledger, _, _ = book.open("assessment", "p4-01", task,
                                    generation_study_sha256=generation["generation_study_sha256"])
            value = {"prompt_id": task["id"], "pair": "p4-01", "targets": dict.fromkeys(assessment.TARGETS),
                "selected_checkpoint": (generation.get("adaptive") or {}).get("selected_checkpoint"), "stage_dispositions": [],
                "native_micro_usd": generation["native_micro_usd"],
                "fixed_micro_usd": generation["fixed_micro_usd"], "failure": "synthetic-no-grading"}
            book.close(ledger, value)
            return value

        with patch.object(workflow, "load_study", side_effect=lambda path: current[0]), \
             patch.object(release, "grant_for"), \
             patch.object(release, "source_identity", side_effect=lambda: current[0]["source"]), \
             patch.object(workflow, "_tasks", return_value=[task]), \
             patch.object(workflow, "_fixed", side_effect=fixed), \
             patch.object(workflow, "_assessment", side_effect=assess), \
             patch.object(workflow, "_snapshot"), \
             patch.object(workflow, "_retained_native", return_value=None), \
             patch.object(workflow, "_report_generation"), \
             patch.object(workflow, "_report_fixed"), \
             patch.object(workflow, "CompatibleProposer", Mock()), \
             patch.object(native, "run_adaptation", side_effect=adaptation):
            write_once(folder / "unused-grant.json", {"fixture": True})
            with SDKMock() as old_mock:
                first = workflow.run(previous_study, folder / "unused-grant.json", stage="all", transport=old_mock.transport)
                self.assertEqual(old_mock.http_calls, 3)
                self.assertEqual(first["attempts"], 3)
            original_run, _ = release.paths(original, True)
            original_outcome = (original_run / "outcome.json").read_bytes()
            children = release.continuation_children(previous_study, True)
            streams = {}
            for entry in children:
                execution = entry["journal"]["execution_study_sha256"]
                events = workflow.accounting.canonical_journal(execution, True) / "events.jsonl"
                streams[execution] = events.read_bytes() if events.exists() else None
            proof = folder / "synthetic-compatibility.json"
            write_once(proof, {"kind": "synthetic-controller-test-only", "passed": True})
            successor = copy.deepcopy(original)
            successor["source_sha256"] = "d" * 64
            successor["source"] = {"sha256": "d" * 64}
            successor["continuation"] = {"fixture": True, "children": children, "compatibility": release._sealed_reference(proof),
                "required_artifact_recovery": None, "funding_origin_study_sha256": original["study_sha256"],
                "sha256": digest(["synthetic", token])}
            successor["study_sha256"] = digest(successor)
            current[0], incomplete[0] = successor, False
            with SDKMock() as new_mock:
                resumed = workflow.resume(folder / "successor-study.json", folder / "unused-grant.json",
                                          stage="all", transport=new_mock.transport)
                self.assertEqual(new_mock.http_calls, 2)
                self.assertEqual(resumed["attempts"], 5)
                self.assertEqual(resumed["reserved_micro_usd"], 0)
                self.assertGreater(resumed["spent_micro_usd"], first["spent_micro_usd"])
                self.assertEqual(resumed["spent_by_allocation_micro_usd"]["dev"],
                                 first["spent_by_allocation_micro_usd"]["dev"])
                self.assertEqual(len(resumed["closed_children"]), 2)
                self.assertEqual(workflow.report(folder / "successor-study.json", folder / "unused-grant.json"), resumed)
                with self.assertRaises(ContractError):
                    workflow.resume(folder / "successor-study.json", folder / "unused-grant.json",
                                    stage="all", transport=new_mock.transport)
                self.assertEqual(new_mock.http_calls, 2)
            self.assertEqual((original_run / "outcome.json").read_bytes(), original_outcome)
            for execution, before in streams.items():
                events = workflow.accounting.canonical_journal(execution, True) / "events.jsonl"
                self.assertEqual(events.read_bytes() if events.exists() else None, before)


if __name__ == "__main__":
    unittest.main()
