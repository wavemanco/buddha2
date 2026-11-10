"""Paid-result continuation through real journals and mocked, owned SDK calls."""
from __future__ import annotations

import copy
import os
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_dispatch import build_request
from followups.phase3b_seq2_v1 import accounting
from followups.phase3b_seq2_v1 import ledger_core as core
from followups.phase3b_seq2_v1 import transport as bounded
from followups.phase3b_seq2_v1.mocks import SDKMock
from followups.phase4_cm1_v1 import policy
from tests.test_phase4_policy import authority_for, profile_for


def _request():
    return build_request("plan", messages=[{"role": "user", "content": "SYNTHETIC continuation task"}],
                         system="SYNTHETIC plan instructions")


def _ledger(transport, execution: str, *, continuation=None):
    extra = {} if continuation is None else {"continuation": continuation}
    profile, slots = profile_for("dev", "dev02", **extra)
    authority, bindings = authority_for(profile, execution)
    bindings["source_sha256"] = digest(["synthetic consumer version", execution])
    return accounting.Ledger(accounting.canonical_journal(execution, True), study_sha256=execution,
        slots=slots, authority=authority, transport=transport, bindings=bindings, stage="p4",
        admission_guard=lambda state: None, profile=profile)


def _plans(ledger):
    return [slot for slot, row in ledger.manifest["inputs"]["slots"].items() if row["role"] == "plan"]


def _completed_origin(execution: str, *, crash=False):
    with SDKMock() as mock:
        ledger = _ledger(mock.transport, execution)
        result = ledger.dispatch(_plans(ledger)[0], "plan", _request())
        if crash:
            # The request transaction is durable; no higher-level completion checkpoint exists.
            os._exit(23)
        ledger.halt("synthetic stop after a committed provider result")
    return ledger, result


class ContinuationLedgerTests(unittest.TestCase):
    def fresh_id(self):
        return digest(["synthetic continuation", uuid.uuid4().hex])

    def successor(self, transport, origins, logical):
        binding = accounting.continuation_binding(origins, logical_study_sha256=logical)
        ledger = _ledger(transport, self.fresh_id(), continuation=binding)
        return accounting.ContinuationLedger(ledger, origins=binding["origins"],
            logical_study_sha256=logical)

    def test_halted_origin_reuses_exact_paid_response_and_only_missing_work_is_sent(self):
        logical = self.fresh_id()
        old, original = _completed_origin(logical)
        reference = accounting.journal_reference(old.journal)
        before = (old.journal / "events.jsonl").read_bytes()
        old_state = old.state()
        with SDKMock() as mock:
            resumed = self.successor(mock.transport, [reference], logical)
            first, second = _plans(resumed)[:2]
            replayed = resumed.dispatch(first, "plan", _request())
            self.assertEqual(replayed, original)
            self.assertEqual(replayed["study_sha256"], logical)
            self.assertEqual(mock.http_calls, 0)
            self.assertEqual(resumed.execution_state()["attempts"], 0)
            self.assertEqual(resumed.state()["spent_micro_usd"], old_state["spent_micro_usd"])
            new = resumed.dispatch(second, "plan", _request())
            self.assertEqual(mock.http_calls, 1)
            self.assertEqual(new["study_sha256"], logical)
            self.assertNotEqual(resumed.state()["execution_study_sha256"], logical)
            self.assertEqual(resumed.state()["attempts"], 2)
            self.assertEqual(resumed.execution_state()["attempts"], 1)
            self.assertEqual(resumed.state()["spent_micro_usd"],
                original["spent_micro_usd"] + new["spent_micro_usd"])
            self.assertEqual(resumed.dispatch(second, "plan", _request()), new)
            self.assertEqual(mock.http_calls, 1)
        self.assertEqual((old.journal / "events.jsonl").read_bytes(), before)
        self.assertEqual(accounting.journal_reference(old.journal), reference)

    def test_changed_request_and_resealed_origin_pin_cannot_reuse_or_redispatch(self):
        logical = self.fresh_id()
        old, _ = _completed_origin(logical)
        reference = accounting.journal_reference(old.journal)
        with SDKMock() as mock:
            resumed = self.successor(mock.transport, [reference], logical)
            changed = _request()
            changed["messages"][0]["content"] = "SYNTHETIC changed producer input"
            with self.assertRaises(ContractError):
                resumed.dispatch(_plans(resumed)[0], "plan", changed)
            forged = {**reference, "events_sha256": "0" * 64}
            forged["sha256"] = digest({k: v for k, v in forged.items() if k != "sha256"})
            with self.assertRaises(ContractError):
                accounting.read_reference(forged)
            self.assertEqual(mock.http_calls, 0)
            self.assertEqual(resumed.execution_state()["attempts"], 0)

    def test_origin_mutation_after_pin_is_rejected_without_changing_successor(self):
        logical = self.fresh_id()
        old, _ = _completed_origin(logical)
        reference = accounting.journal_reference(old.journal)
        stream = old.journal / "events.jsonl"
        original = stream.read_bytes()
        with SDKMock() as mock:
            resumed = self.successor(mock.transport, [reference], logical)
            successor_before = {name: (resumed.journal / name).read_bytes()
                if (resumed.journal / name).exists() else None
                for name in ("manifest.json", "events.jsonl")}
            try:
                stream.write_bytes(original + b"\n")
                with self.assertRaises(ContractError):
                    resumed.dispatch(_plans(resumed)[0], "plan", _request())
                self.assertEqual(mock.http_calls, 0)
                successor_after = {name: (resumed.journal / name).read_bytes()
                    if (resumed.journal / name).exists() else None
                    for name in ("manifest.json", "events.jsonl")}
                self.assertEqual(successor_after, successor_before)
            finally:
                stream.write_bytes(original)

    def test_unsettled_origin_intent_is_quarantined_and_never_resent(self):
        logical = self.fresh_id()
        with SDKMock() as mock:
            old = _ledger(mock.transport, logical)
            slot = _plans(old)[0]
            intent = core._intent(old.manifest, slot, _request(), 1)
            core._append_event(old.journal, "intent", intent, [])
            before = (old.journal / "events.jsonl").read_bytes()
            reference = accounting.journal_reference(old.journal)
            with self.assertRaises(accounting.LiabilityStop):
                self.successor(mock.transport, [reference], logical)
            self.assertEqual(mock.http_calls, 0)
            state, _ = accounting.read_reference(reference)
            self.assertEqual(state["reserved_micro_usd"], core._reservation("plan")["micro_usd"])
            self.assertEqual((old.journal / "events.jsonl").read_bytes(), before)

    def test_carried_cost_is_verified_and_remains_part_of_cell_admission(self):
        logical = self.fresh_id()
        old, original = _completed_origin(logical)
        reference = accounting.journal_reference(old.journal)
        binding = accounting.continuation_binding([reference], logical_study_sha256=logical)
        altered = copy.deepcopy(binding)
        altered["carried_cells"]["dev02:fixed"]["spent_micro_usd"] = 0
        with SDKMock() as mock:
            with self.assertRaises(ContractError):
                wrong = _ledger(mock.transport, self.fresh_id(), continuation=altered)
                accounting.ContinuationLedger(wrong, origins=[reference], logical_study_sha256=logical)
            resumed = self.successor(mock.transport, [reference], logical)
            incremental = resumed.execution_state()
            profile = resumed.manifest["inputs"]["policy"]
            reservation = core._reservation("plan")
            incremental["cells"]["dev02:fixed"]["spent_micro_usd"] = (
                profile["cell_micro_usd"] - reservation["micro_usd"] - original["spent_micro_usd"] + 1)
            meta = resumed.manifest["inputs"]["slots"][_plans(resumed)[1]]
            with self.assertRaises(accounting.CellBudgetStop):
                accounting._admit(incremental, meta, reservation, policy=profile)
            self.assertEqual(mock.http_calls, 0)

    def test_successor_of_successor_flattens_origins_without_double_cost_or_resend(self):
        logical = self.fresh_id()
        first, paid_one = _completed_origin(logical)
        first_ref = accounting.journal_reference(first.journal)
        with SDKMock() as mock:
            second = self.successor(mock.transport, [first_ref], logical)
            slots = _plans(second)
            second.dispatch(slots[0], "plan", _request())
            paid_two = second.dispatch(slots[1], "plan", _request())
            second.halt("synthetic second execution stop")
            second_ref = accounting.journal_reference(second.journal)
        with SDKMock() as mock:
            third = self.successor(mock.transport, [second_ref], logical)
            self.assertEqual(third.dispatch(slots[0], "plan", _request()), paid_one)
            self.assertEqual(third.dispatch(slots[1], "plan", _request()), paid_two)
            self.assertEqual(mock.http_calls, 0)
            self.assertEqual(third.state()["attempts"], 2)
            self.assertEqual(third.state()["spent_micro_usd"],
                paid_one["spent_micro_usd"] + paid_two["spent_micro_usd"])
            binding = accounting.continuation_binding([first_ref, second_ref, first_ref],
                logical_study_sha256=logical)
            self.assertEqual(len(binding["origins"]), 2)

    def test_zero_call_origin_cannot_cross_phase_or_same_role_run_namespace(self):
        for old_kind, new_kind, pair, foreign_slots in (
                ("assessment", "inference", "p4-01", False),
                ("dev", "dev", "dev02", True)):
            with self.subTest(origin_kind=old_kind, foreign_slots=foreign_slots), SDKMock() as mock:
                origin_execution, successor_execution = self.fresh_id(), self.fresh_id()
                logical = self.fresh_id() if old_kind == "assessment" else origin_execution
                extra = {"generation_study_sha256": logical} if old_kind == "assessment" else {}
                old_profile, old_slots = profile_for(old_kind, pair, **extra)
                authority, bindings = authority_for(old_profile, origin_execution)
                origin = accounting.Ledger(accounting.canonical_journal(origin_execution, True),
                    study_sha256=origin_execution, slots=old_slots, authority=authority,
                    transport=mock.transport, bindings=bindings, stage="p4",
                    admission_guard=lambda state: None, profile=old_profile)
                reference = accounting.journal_reference(origin.journal)
                continuation = accounting.continuation_binding([reference], logical_study_sha256=logical)
                target_profile, target_slots = profile_for(new_kind, pair)
                if foreign_slots:
                    target_slots = {"foreign/" + name: row for name, row in target_slots.items()}
                allocation = {key: value for key, value in target_profile["phase4_child"].items()
                              if key not in {"kind", "pair", "slots_sha256"}}
                allocation["continuation"] = continuation
                with self.assertRaisesRegex(ContractError, "origin|continuation"):
                    target_profile = policy.make(new_kind, pair, slots=target_slots, **allocation)
                    authority, bindings = authority_for(target_profile, successor_execution)
                    successor = accounting.Ledger(accounting.canonical_journal(successor_execution, True),
                        study_sha256=successor_execution, slots=target_slots, authority=authority,
                        transport=mock.transport, bindings=bindings, stage="p4",
                        admission_guard=lambda state: None, profile=target_profile)
                    accounting.ContinuationLedger(successor, origins=continuation["origins"],
                        logical_study_sha256=logical)
                self.assertEqual(mock.http_calls, 0)
                self.assertEqual(origin.state()["attempts"], 0)
                self.assertEqual(accounting.journal_reference(origin.journal), reference)
                events = accounting.canonical_journal(successor_execution, True) / "events.jsonl"
                self.assertEqual(events.read_bytes() if events.exists() else b"", b"")

    def test_warm_cache_rejects_changed_or_deleted_owned_transport_audit(self):
        for mutation in ("changed", "deleted"):
            with self.subTest(mutation=mutation):
                logical = self.fresh_id()
                old, result = _completed_origin(logical)
                reference = accounting.journal_reference(old.journal)
                accounting.read_reference(reference)
                audit = bounded.audit_path(logical, True, result["slot_id"])
                original = audit.read_bytes()
                with SDKMock() as mock:
                    resumed = self.successor(mock.transport, [reference], logical)
                    try:
                        if mutation == "deleted":
                            audit.unlink()
                        else:
                            audit.write_bytes(original + b"\n")
                        with patch.object(accounting, "_replay", side_effect=AssertionError("warm cache replayed")):
                            with self.assertRaisesRegex(ContractError, "provenance changed"):
                                accounting.read_reference(reference)
                            with self.assertRaisesRegex(ContractError, "provenance changed"):
                                resumed.dispatch(result["slot_id"], "plan", _request())
                        self.assertEqual(mock.http_calls, 0)
                        events = resumed.journal / "events.jsonl"
                        self.assertEqual(events.read_bytes() if events.exists() else b"", b"")
                    finally:
                        audit.write_bytes(original)

    def test_warm_cache_rejects_added_stop_sidefiles_without_journal_replay(self):
        logical = self.fresh_id()
        old, _ = _completed_origin(logical)
        reference = accounting.journal_reference(old.journal)
        accounting.read_reference(reference)
        targets = [old.journal / "deadline-stop.json", old.journal / "transport-audit-failure.json",
                   accounting.NATIVE / logical / "mock" / "canonical-stop.json"]
        for target in targets:
            with self.subTest(sidefile=target.name):
                self.assertFalse(target.exists())
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_bytes(b"{}")
                    with patch.object(accounting, "_replay", side_effect=AssertionError("warm cache replayed")):
                        with self.assertRaisesRegex(ContractError, "provenance changed"):
                            accounting.read_reference(reference)
                finally:
                    target.unlink()

    def test_process_exit_after_durable_response_reuses_it_without_a_stage_checkpoint(self):
        logical = self.fresh_id()
        worker = ("from tests.test_continuation import _completed_origin; "
                  "import sys; _completed_origin(sys.argv[1], crash=True)")
        completed = subprocess.run([sys.executable, "-B", "-c", worker, logical],
            capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(completed.returncode, 23, completed.stderr)
        journal = accounting.canonical_journal(logical, True)
        reference = accounting.journal_reference(journal)
        prior, _ = accounting.read_reference(reference)
        self.assertEqual(prior["attempts"], 1)
        self.assertEqual(len(prior["results"]), 1)
        self.assertFalse((journal.parent / "stage-checkpoint.json").exists())
        slot, original = next(iter(prior["results"].items()))
        with SDKMock() as mock:
            resumed = self.successor(mock.transport, [reference], logical)
            self.assertEqual(resumed.dispatch(slot, "plan", _request()), original)
            self.assertEqual(mock.http_calls, 0)
            self.assertEqual(resumed.execution_state()["attempts"], 0)


if __name__ == "__main__":
    unittest.main()
