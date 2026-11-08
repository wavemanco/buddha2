"""P4 child scope and finances reuse the existing ledger without provider calls."""
from __future__ import annotations

import copy
import threading
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash
from buddha2.phase2_dispatch import build_request
from followups.phase3b_seq2_v1 import accounting, native, strategy
from followups.phase3b_seq2_v1 import ledger_core as core
from followups.phase3b_seq2_v1 import transport as bounded
from followups.phase3b_seq2_v1.test_workflow_s2 import minimal_study
from followups.phase4_cm1_v1 import policy


def slots_for(kind: str, pair: str) -> dict:
    """Synthetic tasks, actual native/C-N ID functions; no saved live row is relabelled."""
    slots: dict = {}
    if kind == "inference":
        for run_id in native.adaptive_run_ids("synthetic-p4-policy", pair).values():
            ids = strategy.slot_ids(run_id)
            for role, names in (("plan", [ids["plan"]]), ("answer", ids["answers"]), ("rank", [ids["rank"]])):
                for name in names:
                    slots[name] = {"role": role, "cell": pair + ":adaptive", "pair": pair}
        labels = [(f"{stage}.a{attempt}", "editor")
            for stage in ("inv1", "dom1", "c1", "inv2", "dom2", "c2") for attempt in (1, 2)]
        for label, role in [*labels, ("select.seq2", "native_selector")]:
            for turn in range(1, 25):
                slots[f"{pair}.adaptive.editor.{label}.t{turn:02}"] = {
                    "role": role, "cell": pair + ":adaptive", "pair": pair,
                    "conversation": pair + ":adaptive:" + label, "turn": turn}
    if kind in {"inference", "dev"}:
        for pool in range(1, 9):
            run = f"synthetic-{pair}-pool-{pool:02}"
            for candidate in range(1, 13):
                ids = strategy.slot_ids(f"{run}/candidate-{candidate:02}")
                for role, names in (("plan", [ids["plan"]]), ("answer", ids["answers"]), ("rank", [ids["rank"]])):
                    for name in names:
                        slots[name] = {"role": role, "cell": pair + ":fixed", "pair": pair}
            slots[strategy.slot_ids(run)["selector"]] = {"role": "fixed_selector", "cell": pair + ":fixed", "pair": pair}
        slots[strategy.slot_ids(f"synthetic-{pair}-final")["selector"]] = {
            "role": "fixed_selector", "cell": pair + ":fixed", "pair": pair}
    else:
        for target in ("fixed", "c1", "c2"):
            for ordering in ("primary", "reverse", "rotate"):
                prefix = native.Phase3NativeAssessment.slot_prefix(f"synthetic-{pair}-{target}-{ordering}")
                slots[prefix + ".group"] = {"role": "group", "cell": "assessment", "pair": pair}
                if ordering == "primary":
                    for index in range(10):
                        slots[f"{prefix}.quality.{index:02}"] = {
                            "role": "quality", "cell": "assessment", "pair": pair}
    return slots


def profile_for(kind="inference", pair="p4-01", **changes) -> tuple[dict, dict]:
    slots = slots_for(kind, pair)
    values = {"parent_sha256": "a" * 64, "authorization_sha256": file_hash(policy.AUTHORITY),
        "allocation_sha256": "b" * 64, "remaining_total_micro_usd": 1_200_000_000,
        "remaining_allocation_micro_usd": policy.ALLOCATIONS[kind]}
    if kind == "assessment":
        values["generation_study_sha256"] = "f" * 64
    values.update(changes)
    return policy.make(kind, pair, slots=slots, **values), slots


def authority_for(profile: dict, study: str, fixture=True) -> tuple[dict, dict]:
    authority = {"study_sha256": study, "authorization_id": "synthetic-p4-policy",
        "authorized": not fixture, "cap_micro_usd": profile["phase_micro_usd"],
        "canary_cap_micro_usd": profile["first_micro_usd"], "expansion_authorized": False,
        "control_policy_sha256": core.am1.CONTROL_SHA256, "billing_profile": core.am1.BILLING_PROFILE}
    return authority, {"source_sha256": "c" * 64, "policy_sha256": digest(profile), "launcher_sha256": "d" * 64}


class Phase4PolicyTests(unittest.TestCase):
    def test_assessment_scientific_identity_survives_serial_transport_binding(self):
        profile, slots = profile_for("assessment")
        execution = "e" * 64
        authority, bindings = authority_for(profile, execution)
        manifest = {"run_id": "1" * 64, "inputs": {"study_sha256": execution,
            "policy": profile, "slots": slots, "authority": authority, "fixture": True, "bindings": bindings}}
        slot = next(name for name, row in slots.items() if row["role"] == "quality")
        body = build_request("quality", messages=[{"role": "user", "content": "Synthetic quality"}])
        intent = core._intent(manifest, slot, body, 1)
        self.assertEqual(intent["study_sha256"], "f" * 64)
        self.assertTrue(intent["dispatch_id"].startswith(manifest["run_id"]))
        self.assertEqual(core._start(manifest)["study_sha256"], execution)
        transport = object.__new__(bounded.Transport)
        transport.fixture = True
        transport._closed = transport._terminal = False
        transport._policy = bounded.POLICY
        transport._local = threading.local()
        transport._soft_clocks = transport._conversations = {}
        allocation = transport.prepare(slot, "quality", slots[slot], accounting._bindings(manifest))
        transport.bind_intent(intent, allocation)
        self.assertEqual(transport._local.context["intent"], intent)
        with self.assertRaises(ContractError):
            profile_for("assessment", generation_study_sha256=None)
        with self.assertRaises(ContractError):
            profile_for(generation_study_sha256="f" * 64)
        legacy = {**manifest, "inputs": {**manifest["inputs"], "policy": accounting.POLICY}}
        self.assertEqual(core._intent(legacy, slot, body, 1)["study_sha256"], execution)
        self.assertEqual(accounting._bindings(legacy)["study_sha256"], execution)

    def test_p4_journal_capacity_is_checked_before_intent_and_preserves_legacy(self):
        profile, _ = profile_for()
        intent = {"cell": "p4-01:fixed", "request": {"synthetic": True}}
        remaining = len(core._wire(intent)) + 65_536 + 2_000_000
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=1_500_000_000 - remaining)):
            accounting._intent_capacity(Path("/results/synthetic-capacity"), intent, profile)
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=1_500_000_000 - remaining + 1)), \
                self.assertRaisesRegex(accounting.CellBudgetStop, "journal_byte_capacity"):
            accounting._intent_capacity(Path("/results/synthetic-capacity"), intent, profile)
        with patch.object(Path, "stat", side_effect=AssertionError("legacy capacity changed")):
            accounting._intent_capacity(Path("/results/synthetic-capacity"), intent, accounting.POLICY)

    def test_finite_child_profiles_bind_actual_worklists_and_remaining_caps(self):
        for kind, pair, count, cap in (("inference", "p4-24", 1569, 150_000_000),
                ("dev", "dev02", 1161, 75_000_000), ("assessment", "p4-01", 39, 250_000_000)):
            with self.subTest(kind=kind):
                profile, slots = profile_for(kind, pair)
                self.assertEqual(policy.validate(profile, slots), profile)
                self.assertEqual(profile["maximum_admitted_attempts"], count)
                self.assertEqual(profile["phase_micro_usd"], cap)
                self.assertEqual(profile["phase4_child"]["slots_sha256"], digest(slots))
                self.assertEqual(profile["execution_pairs"], [pair])
        profile, _ = profile_for(remaining_total_micro_usd=12_000_000,
            remaining_allocation_micro_usd=14_000_000)
        self.assertEqual(profile["phase_micro_usd"], 12_000_000)

    def test_wrong_parent_authority_policy_scope_and_turn_population_are_rejected(self):
        profile, slots = profile_for()
        for key, value in (("phase_micro_usd", 150_000_001), ("cell_micro_usd", 75_000_001),
                ("maximum_admitted_attempts", 1570), ("role_payload_bytes", {})):
            changed = {**profile, key: value}
            with self.subTest(key=key), self.assertRaises(ContractError):
                policy.validate(changed, slots)
        with self.assertRaises(ContractError):
            profile_for(authorization_sha256="0" * 64)
        for kind, pair in (("dev", "p4-01"), ("inference", "dev04"), ("assessment", "p4-25")):
            with self.subTest(kind=kind, pair=pair), self.assertRaises(ContractError):
                policy.make(kind, pair, slots=slots)
        for field, value in (("pair", "p4-02"), ("role", "quality"), ("turn", 25)):
            changed = copy.deepcopy(slots)
            name = next(name for name, row in changed.items() if row["role"] == "editor")
            changed[name][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                policy.validate(profile, changed)
        changed_authority = {"kind": "phase4-cm1-authorization-v1", "authorized": True}
        with patch.object(policy, "read_json", return_value=changed_authority), self.assertRaises(ContractError):
            policy.validate(profile, slots)

    def test_legacy_identity_and_payload_rejection_remain_unchanged(self):
        study = minimal_study()
        authority, bindings = authority_for(accounting.POLICY, "e" * 64)
        tools = {}
        inputs = {"study_sha256": "e" * 64, "slots": study["slots"], "authority": authority,
            "fixture": True, "bindings": bindings, "policy": accounting.POLICY, "editor_tools": tools}
        self.assertEqual(accounting.journal_identity(study_sha256="e" * 64, slots=study["slots"],
            authority=authority, fixture=True, bindings=bindings, editor_tools=tools), digest(inputs))
        self.assertEqual(accounting.policy_for(study["slots"]), accounting.POLICY)
        body = build_request("plan", messages=[{"role": "user", "content": "x" * 100_000}], system="Synthetic plan")
        with self.assertRaises(ContractError):
            core.validate_request("plan", body)
        profile, _ = profile_for()
        core.validate_request("plan", body, policy=profile)
        with self.assertRaises(ContractError):
            core.validate_request("plan", body, policy={**profile, "role_payload_bytes": {}})
        with self.assertRaises(ContractError):
            core.validate_request("plan", {**body, "model": "another-model"}, policy=profile)

    def test_p4_money_attempt_and_unknown_guards_are_not_relaxed(self):
        profile, slots = profile_for()
        state = core._start({"run_id": "f" * 64, "inputs": {
            "policy": profile, "fixture": True, "study_sha256": "e" * 64}})
        meta = next(row for row in slots.values() if row["role"] == "editor")
        reservation = core._reservation("editor")
        self.assertEqual(reservation["micro_usd"], 11_440_000)
        for scope in ("phase", "cell", "attempt", "unknown"):
            value = copy.deepcopy(state)
            expected = accounting.PhaseBudgetStop
            if scope == "phase":
                value["spent_micro_usd"] = profile["phase_micro_usd"]
            elif scope == "cell":
                value["spent_micro_usd"] = value["cells"][meta["cell"]]["spent_micro_usd"] = 65_000_000
                expected = accounting.CellBudgetStop
            elif scope == "attempt":
                value["attempts"] = profile["maximum_admitted_attempts"]
            else:
                value["status"] = "blocked-unknown"
                value["reserved_micro_usd"] = reservation["micro_usd"]
                expected = accounting.LiabilityStop
            with self.subTest(scope=scope), self.assertRaises(expected):
                accounting._admit(value, meta, reservation, policy=profile)

    def test_actual_manifest_pending_replay_keeps_reservation_and_never_resends(self):
        profile, slots = profile_for("assessment")
        study = digest(["synthetic-p4-pending", uuid.uuid4().hex])
        authority, bindings = authority_for(profile, study)
        inputs = {"study_sha256": study, "slots": slots, "authority": authority,
            "fixture": True, "bindings": bindings, "policy": profile, "editor_tools": {}}
        manifest = {"kind": "phase3b-seq2-ledger-v1", "inputs": inputs,
            "run_id": accounting.journal_identity(study_sha256=study, slots=slots,
                authority=authority, fixture=True, bindings=bindings, profile=profile)}
        journal = accounting.canonical_journal(study, True)
        core._publish(journal / "manifest.json", manifest)
        slot = next(name for name, row in slots.items() if row["role"] == "quality")
        body = build_request("quality", messages=[{"role": "user", "content": "Synthetic quality input"}])
        intent = core._intent(manifest, slot, body, 1)
        core._append_event(journal, "intent", intent, [])
        before = (journal / "events.jsonl").read_bytes()
        first, _, _ = accounting._replay(journal)
        second, _, _ = accounting._replay(journal)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "blocked-unknown")
        self.assertEqual(first["reserved_micro_usd"], 11_440_000)
        self.assertEqual(first["attempts"], 1)
        self.assertEqual((journal / "events.jsonl").read_bytes(), before)
        with self.assertRaises(accounting.LiabilityStop):
            accounting._admit(first, slots[slot], core._reservation("quality"), policy=profile)

    def test_p4_cannot_open_a_child_without_parent_admission_guard(self):
        profile, slots = profile_for()
        study = digest(["synthetic-p4-no-guard", uuid.uuid4().hex])
        authority, bindings = authority_for(profile, study)
        journal = accounting.canonical_journal(study, True)
        with self.assertRaisesRegex(ContractError, "parent admission guard"):
            accounting.Ledger(journal, study_sha256=study, slots=slots, authority=authority,
                transport=SimpleNamespace(fixture=True), bindings=bindings, stage="p4", profile=profile)
        self.assertFalse(journal.exists())
