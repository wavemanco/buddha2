"""Stage scope and no-reset checks around the unchanged request ledger."""
from __future__ import annotations

import copy
import shutil
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_c1_completion_v1 import accounting as a
from followups.phase3a_v1 import accounting as core
from followups.phase3a_v1.tests.test_accounting import Transport, request, slots


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.study = digest({"case": self.id(), "nonce": uuid.uuid4().hex})
        self.journal = a.canonical_journal(self.study, True)
        self.slots = slots()
        self.bindings = {"source_sha256": "2" * 64, "policy_sha256": digest(a.POLICY), "launcher_sha256": "4" * 64}
        self.authority = {"study_sha256": self.study, "authorization_id": "new-completion-fixture",
            "authorized": False, "cap_micro_usd": a.POLICY["phase_micro_usd"],
            "canary_cap_micro_usd": a.POLICY["first_micro_usd"], "expansion_authorized": False,
            "control_policy_sha256": am1.CONTROL_SHA256, "billing_profile": am1.BILLING_PROFILE}
        self.addCleanup(self.cleanup)

    def cleanup(self):
        parent = self.journal.parent.parent
        self.assertEqual(parent.parent, Path('/results') / a.PREFIX)
        if parent.exists():
            shutil.rmtree(parent)

    def ledger(self, transport=None, **kwargs):
        return a.Ledger(self.journal, study_sha256=self.study, slots=self.slots,
            authority=self.authority, bindings=self.bindings, transport=transport or Transport(), **kwargs)

    def test_fresh_identity_canonical_path_and_authority_precede_ledger_mutation(self):
        self.assertEqual(a.canonical_journal(self.study, False),
                         Path('/results/phase3a-r2-v1') / self.study / 'live/journal')
        for retired in a.RETIRED_STUDIES:
            with self.assertRaises(ContractError):
                a.canonical_journal(retired, False)
        with self.assertRaises(ContractError):
            self.ledger(stage='first')
        bad = self.authority | {'cap_micro_usd': a.POLICY['phase_micro_usd'] + 1}
        with self.assertRaises(ContractError):
            a.validate_authority(self.study, bad, True, self.bindings)
        with self.assertRaises(ContractError):
            a.validate_authority(self.study, self.authority, True,
                                 self.bindings | {'policy_sha256': '0' * 64})
        self.assertFalse(self.journal.exists())
        missing: Any = None
        with self.assertRaises(ContractError):
            a.validate_authority(self.study, self.authority, True, missing)
        with self.assertRaises(ContractError):
            a.journal_identity(study_sha256=self.study, slots=self.slots, authority=self.authority,
                               fixture=True, bindings=missing)
        with self.assertRaises(ContractError):
            a.Ledger(self.journal, study_sha256=self.study, slots=self.slots,
                     authority=self.authority, transport=Transport(), bindings=missing)
        self.assertFalse(self.journal.exists())

    def test_readiness_scope_rejects_fixed_and_judges_without_transport(self):
        transport = Transport()
        ledger = self.ledger(transport)
        with self.assertRaises(a.AuthorityError):
            ledger.dispatch('p3a-01.fixed.plan.00', 'plan', request())
        self.assertEqual(transport.calls, [])
        self.assertEqual(ledger.state()['status'], 'halted-integrity')
        self.assertEqual(ledger.state()['attempts'], 0)

    def test_first_stage_counts_readiness_once_and_preserves_exact_known_replay(self):
        transport = Transport()
        readiness = self.ledger(transport)
        result = readiness.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        phase = self.ledger(transport, stage='first', readiness_validator=lambda _: None)
        self.assertEqual(phase.dispatch('p3a-01.adaptive.plan.00', 'plan', request()), result)
        phase.dispatch('p3a-01.fixed.plan.00', 'plan', request())
        state = phase.state()
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(state['attempts'], 2)
        self.assertEqual(state['spent_micro_usd'], 800)
        self.assertEqual(state['cells']['p3a-01:adaptive']['attempts'], 1)
        self.assertEqual(state['run_id'], readiness.state()['run_id'])
        self.assertEqual(state, a.replay(self.journal))
        self.assertEqual(len(a.events(self.journal)), 4)

    def test_known_readiness_stop_stays_uncharged_and_blocks_a_new_wrapper(self):
        transport = Transport()
        stopped = self.journal.parent / 'known-readiness-stop.json'
        def guard(_):
            if stopped.exists():
                raise a.ReadinessStop('known terminal outcome; no new request')
        ledger = self.ledger(transport, readiness_validator=guard)
        ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        write_once(stopped, {'kind': 'synthetic-known-readiness-stop', 'study_sha256': self.study})
        for owner in (ledger, self.ledger(transport, readiness_validator=guard)):
            with self.assertRaises(a.ReadinessStop):
                owner.dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(ledger.state()['status'], 'ready')
        self.assertEqual(ledger.state()['attempts'], 1)
        self.assertEqual(ledger.state()['reserved_micro_usd'], 0)

    def test_bad_review_or_source_evidence_halts_before_any_new_request(self):
        transport = Transport()
        def reject(_):
            raise ContractError('the bound readiness evidence changed')
        ledger = self.ledger(transport, stage='first', readiness_validator=reject)
        with self.assertRaises(a.IntegrityStop):
            ledger.dispatch('p3a-01.fixed.plan.00', 'plan', request())
        self.assertEqual(len(transport.calls), 0)
        self.assertEqual(ledger.state()['status'], 'halted-integrity')
        self.assertEqual(ledger.state()['attempts'], 0)

    def test_unknown_liability_remains_reserved_across_stage_and_no_resend(self):
        transport = Transport(fault='unknown')
        ledger = self.ledger(transport)
        result = ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        self.assertEqual(result['status'], 'unknown')
        later = self.ledger(transport, stage='first', readiness_validator=lambda _: None)
        for slot in ('p3a-01.adaptive.plan.00', 'p3a-01.fixed.plan.00'):
            with self.assertRaises(a.LiabilityStop):
                later.dispatch(slot, 'plan', request())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(later.state()['reserved_micro_usd'], am1.reservation('plan'))
        self.assertEqual(a.historical_totals(later.state())['cumulative_known_micro_usd'], None)
        live_numbers = a.historical_totals(later.state() | {'fixture': False})
        self.assertEqual(live_numbers['cumulative_reserved_micro_usd'], 11_440_000 + am1.reservation('plan'))
        self.assertFalse(live_numbers['historical_unknown_released'])

    def test_joint_cell_budget_is_not_reset_when_readiness_becomes_first_stage(self):
        transport = Transport(input_tokens=1_000_000)
        readiness = self.ledger(transport)
        for i in range(4):
            readiness.dispatch(f'p3a-01.adaptive.plan.{i:02}', 'plan', request())
        phase = self.ledger(transport, stage='first', readiness_validator=lambda _: None)
        with self.assertRaises(a.CellBudgetStop):
            phase.dispatch('p3a-01.adaptive.answer.00', 'answer', request('answer'))
        self.assertEqual(len(transport.calls), 4)
        self.assertIn('p3a-01:adaptive', phase.state()['stopped_cells'])
        phase.dispatch('p3a-01.fixed.plan.00', 'plan', request())
        self.assertEqual(len(transport.calls), 5)
        self.assertEqual(phase.state()['cells']['p3a-01:adaptive']['input_tokens'], 4_000_000)
        self.assertEqual(a.POLICY, core.POLICY)

    def test_queued_branch_observes_known_stop_before_admission(self):
        transport = Transport(fault='slow')
        stop = threading.Event()
        def guard(_):
            if stop.is_set():
                raise a.ReadinessStop('first branch ended at the terminal condition')
        original = transport.create
        def create(role, body):
            response = original(role, body)
            stop.set()
            return response
        replacement = patch.object(transport, "create", side_effect=create)
        replacement.start()
        self.addCleanup(replacement.stop)
        ledger = self.ledger(transport, admission_guard=guard)
        outcomes = []
        def worker(slot):
            try:
                outcomes.append(ledger.dispatch(slot, 'plan', request()))
            except a.ReadinessStop as exc:
                outcomes.append(exc)
        threads = [threading.Thread(target=worker, args=(f'p3a-01.adaptive.plan.{i:02}',)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(sum(isinstance(value, a.ReadinessStop) for value in outcomes), 1)
        self.assertEqual(ledger.state()['attempts'], 1)
        self.assertEqual(ledger.state()['status'], 'ready')

    def test_remaining_stage_still_requires_original_first_pair_review(self):
        transport = Transport()
        ledger = self.ledger(transport, stage='remaining', readiness_validator=lambda _: None)
        with self.assertRaises(a.AuthorityError):
            ledger.dispatch('p3a-02.adaptive.plan.00', 'plan', request())
        self.assertEqual(transport.calls, [])

    def test_historical_exposure_is_carried_once_and_cannot_be_released_by_current_zero(self):
        state = {'fixture': False, 'spent_micro_usd': 0, 'reserved_micro_usd': 0, 'attempts': 0}
        summary = a.historical_totals(state)
        self.assertEqual(summary['cumulative_known_micro_usd'], 10_487_885)
        self.assertEqual(summary['cumulative_reserved_micro_usd'], 11_440_000)
        self.assertEqual(summary['cumulative_max_exposure_micro_usd'], 21_927_885)
        self.assertEqual(summary['cumulative_provider_calls'], 842)
        self.assertLess(summary['cumulative_max_exposure_micro_usd'] + a.POLICY['phase_micro_usd'], 250_000_000)
        self.assertIsNone(a.historical_totals(state | {'fixture': True})['cumulative_max_exposure_micro_usd'])
        changed = copy.deepcopy(summary)
        changed['historical']['reserved_micro_usd'] = 0
        self.assertEqual(a.historical_totals(state)['historical']['reserved_micro_usd'], 11_440_000)


if __name__ == '__main__':
    unittest.main()