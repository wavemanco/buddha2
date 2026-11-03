"""Stage scope and no-reset checks around the unchanged request ledger."""
from __future__ import annotations

import copy
import shutil
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, read_json, write_once
from followups.phase3a_c1_completion_v3 import accounting as a
from followups.phase3a_c1_completion_v3.deadline import KnownDeadlineStop, OwnerStopRequired, Policy
from followups.phase3a_c1_completion_v3.tests.fixtures import Transport
from followups.phase3a_c1_completion_v3.transport import audit_path
from followups.phase3a_v1 import accounting as core
from followups.phase3a_v1.tests.test_accounting import request, slots


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
        transport = transport or Transport()
        self.addCleanup(transport.close)
        return a.Ledger(self.journal, study_sha256=self.study, slots=self.slots,
            authority=self.authority, bindings=self.bindings, transport=transport, **kwargs)

    def test_fresh_identity_canonical_path_and_authority_precede_ledger_mutation(self):
        self.assertIn("1e7edf24a9ac3dff4735c8d7af2b5843d86278830d697b2b8260a6da8528de57", a.RETIRED_STUDIES)
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
        for closed_source in (
            "a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3",
            "e2471ad9e38171cabc2d32615bac797739f378c3f6c7ebc64f8b95f8632d9d26",
            "33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c",
        ):
            with self.assertRaises(ContractError):
                a.validate_authority(self.study, self.authority, True,
                                     self.bindings | {'source_sha256': closed_source})
        self.assertFalse(self.journal.exists())
        missing: Any = None
        with self.assertRaises(ContractError):
            a.validate_authority(self.study, self.authority, True, missing)
        with self.assertRaises(ContractError):
            a.journal_identity(study_sha256=self.study, slots=self.slots, authority=self.authority,
                               fixture=True, bindings=missing)
        unused = Transport()
        self.addCleanup(unused.close)
        with self.assertRaises(ContractError):
            a.Ledger(self.journal, study_sha256=self.study, slots=self.slots,
                     authority=self.authority, transport=unused, bindings=missing)
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

    def test_same_instance_state_waits_for_inflight_actual_sdk_settlement(self):
        transport = Transport()
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.plan.00'
        entered, release = threading.Event(), threading.Event()
        reader_started, reader_done = threading.Event(), threading.Event()
        dispatch_outcomes: list[Any] = []
        reader_outcomes: list[Any] = []
        mocks = transport._http
        if mocks is None:
            self.fail('actual fixture SDK mocks are required')
        mock = mocks['anthropic']
        original = mock.handler

        def delayed(http_request):
            response = original(http_request)
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError('fixture response barrier expired')
            return response

        def dispatch():
            try:
                dispatch_outcomes.append(ledger.dispatch(slot, 'plan', request()))
            except BaseException as error:
                dispatch_outcomes.append(error)

        def reader():
            reader_started.set()
            try:
                reader_outcomes.append(ledger.state())
            except BaseException as error:
                reader_outcomes.append(error)
            finally:
                reader_done.set()

        worker, observer = threading.Thread(target=dispatch), threading.Thread(target=reader)
        with patch.object(mock, 'handler', delayed):
            try:
                worker.start()
                self.assertTrue(entered.wait(timeout=10))
                transient = a.replay(self.journal)
                self.assertEqual(transient['status'], 'blocked-unknown')
                self.assertEqual(transient['results'][slot]['status'], 'unknown')
                self.assertEqual(transient['active_unsettled_intents'], [slot])
                self.assertEqual(transient['durable_unknown_results'], 0)
                self.assertEqual(transient['reserved_micro_usd'], am1.reservation('plan'))
                self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent'])
                observer.start()
                self.assertTrue(reader_started.wait(timeout=2))
                self.assertFalse(reader_done.wait(timeout=.15))
            finally:
                release.set()
                if worker.ident is not None:
                    worker.join(timeout=15)
                if observer.ident is not None:
                    observer.join(timeout=15)
        self.assertFalse(worker.is_alive())
        self.assertFalse(observer.is_alive())
        self.assertEqual(len(dispatch_outcomes), 1)
        self.assertEqual(len(reader_outcomes), 1)
        self.assertIsInstance(dispatch_outcomes[0], dict)
        self.assertIsInstance(reader_outcomes[0], dict)
        final = ledger.state()
        self.assertEqual(reader_outcomes[0], final)
        self.assertEqual(final['status'], 'ready')
        self.assertEqual(final['results'][slot], dispatch_outcomes[0])
        self.assertEqual(final['results'][slot]['status'], 'response')
        self.assertEqual(final['spent_micro_usd'], 400)
        self.assertEqual(final['reserved_micro_usd'], 0)
        self.assertEqual(final['active_unsettled_intents'], [])
        self.assertEqual(final['durable_unknown_results'], 0)
        self.assertEqual(final['transport_audit_summary']['validated_audits'], 1)
        self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent', 'result'])
        self.assertEqual(len(transport.calls), 1)

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
        with self.assertRaises(OwnerStopRequired):
            ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        result = ledger.state()['results']['p3a-01.adaptive.plan.00']
        self.assertEqual(result['status'], 'unknown')
        later = self.ledger(transport, stage='first', readiness_validator=lambda _: None)
        for slot in ('p3a-01.adaptive.plan.00', 'p3a-01.fixed.plan.00'):
            with self.assertRaises(KnownDeadlineStop):
                later.dispatch(slot, 'plan', request())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(later.state()['reserved_micro_usd'], am1.reservation('plan'))
        self.assertEqual(a.historical_totals(later.state())['cumulative_known_micro_usd'], None)
        live_numbers = a.historical_totals(later.state() | {'fixture': False})
        self.assertEqual(live_numbers['cumulative_reserved_micro_usd'], 22_880_000 + am1.reservation('plan'))
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
            thread.join(timeout=15)
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

    def test_delayed_file_lock_entry_recomputes_deadline_before_any_intent(self):
        policy = Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        transport = Transport(fixture_policy=policy)
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.editor.inv1.a1.t01'
        transport.register_conversation(self.slots[slot]['conversation'], time.monotonic() + .15)
        queued, released = threading.Event(), threading.Event()
        original = core.writer_lock
        outcomes: list[Any] = []

        @contextmanager
        def observed_lock(path):
            queued.set()
            self.assertTrue(released.wait(timeout=2))
            with original(path):
                yield

        def dispatch():
            try:
                outcomes.append(ledger.dispatch(slot, 'editor', request('editor')))
            except BaseException as error:
                outcomes.append(error)

        # The frozen flock is nonblocking. This fixture delays entry without
        # changing production lock policy, then acquires the real file lock.
        with patch.object(core, 'writer_lock', observed_lock):
            with original(self.journal):
                worker = threading.Thread(target=dispatch)
                worker.start()
                self.assertTrue(queued.wait(timeout=2))
                time.sleep(.2)
                self.assertEqual(transport.calls, [])
                self.assertEqual(len(a.events(self.journal)), 0)
            released.set()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], KnownDeadlineStop)
        state = ledger.state()
        self.assertEqual(state['attempts'], 0)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['deadline_stop']['reason'], 'pre_intent_deadline')
        self.assertEqual([event['kind'] for event in a.events(self.journal)], ['halt'])
        self.assertEqual(transport.calls, [])

    def test_actual_competing_file_owner_is_rejected_without_intent(self):
        transport = Transport()
        ledger = self.ledger(transport)
        with core.writer_lock(self.journal):
            with self.assertRaisesRegex(ContractError, 'another concurrent writer'):
                ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        self.assertEqual(transport.calls, [])
        self.assertEqual(ledger.state()['attempts'], 0)

    def test_actual_thread_queue_expires_and_prepare_observes_both_locks(self):
        policy = Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        transport = Transport(fixture_policy=policy)
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.editor.inv1.a1.t01'
        transport.register_conversation(self.slots[slot]['conversation'], time.monotonic() + .15)
        queued = threading.Event()
        observed: list[tuple[bool, bool]] = []
        outcomes: list[Any] = []
        original = transport.prepare

        def prepare(*args, **kwargs):
            def probe():
                acquired = ledger._core._lock.acquire(blocking=False)
                if acquired:
                    ledger._core._lock.release()
                try:
                    with core.writer_lock(self.journal):
                        file_locked = False
                except ContractError:
                    file_locked = True
                observed.append((not acquired, file_locked))
            probe_thread = threading.Thread(target=probe)
            probe_thread.start()
            probe_thread.join(timeout=2)
            self.assertFalse(probe_thread.is_alive())
            return original(*args, **kwargs)

        def dispatch():
            queued.set()
            try:
                outcomes.append(ledger.dispatch(slot, 'editor', request('editor')))
            except BaseException as error:
                outcomes.append(error)

        with patch.object(transport, 'prepare', side_effect=prepare):
            with ledger._core._lock:
                worker = threading.Thread(target=dispatch)
                worker.start()
                self.assertTrue(queued.wait(timeout=2))
                time.sleep(.2)
                self.assertEqual(observed, [])
                self.assertEqual(transport.calls, [])
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(observed, [(True, True)])
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], KnownDeadlineStop)
        self.assertEqual(ledger.state()['attempts'], 0)
        self.assertEqual(ledger.state()['deadline_stop']['reason'], 'pre_intent_deadline')
        self.assertEqual(transport.calls, [])

    def test_known_late_latch_precedes_result_and_no_output_is_forwarded(self):
        policy = Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        transport = Transport(fixture_policy=policy, fixture_behavior={
            'response_delay': 10, 'ignore_cancel': True, 'cancel_delay': .02})
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.plan.00'
        original = core._append_event
        observed = []

        def append(journal, kind, record, events):
            if kind == 'result':
                latch = read_json(journal / 'deadline-stop.json')
                self.assertEqual(latch['candidate_result_sha256'], digest(record))
                self.assertEqual(latch['reason'], 'known_late_response')
                observed.append(kind)
            return original(journal, kind, record, events)

        with patch.object(core, '_append_event', side_effect=append):
            with self.assertRaises(KnownDeadlineStop):
                ledger.dispatch(slot, 'plan', request())
        state = ledger.state()
        self.assertEqual(observed, ['result'])
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['results'][slot]['status'], 'response')
        self.assertEqual(state['spent_micro_usd'], 400)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(state['transport_audit_summary']['late_known'], 1)
        self.assertEqual(state['transport_audit_summary']['validated_audits'], 1)
        self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent', 'result', 'halt'])
        for owner in (ledger, self.ledger(transport)):
            with self.assertRaises(KnownDeadlineStop):
                owner.dispatch(slot, 'plan', request())
        self.assertEqual(len(transport.calls), 1)

    def test_crash_after_late_result_before_audit_or_halt_still_blocks_admission(self):
        class SimulatedCrash(BaseException):
            pass

        policy = Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        transport = Transport(fixture_policy=policy, fixture_behavior={
            'response_delay': 10, 'ignore_cancel': True, 'cancel_delay': .02})
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.plan.00'
        original = core._append_event

        def append(journal, kind, record, events):
            if kind == 'result':
                self.assertEqual(read_json(journal / 'deadline-stop.json')['candidate_result_sha256'], digest(record))
            published = original(journal, kind, record, events)
            if kind == 'result':
                raise SimulatedCrash()
            return published

        with patch.object(core, '_append_event', side_effect=append):
            with self.assertRaises(SimulatedCrash):
                ledger.dispatch(slot, 'plan', request())
        state = a.replay(self.journal)
        self.assertEqual(state['core_status'], 'ready')
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['spent_micro_usd'], 400)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(state['transport_audit_summary']['missing_or_invalid_slots'], [slot])
        self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent', 'result'])
        with self.assertRaises(KnownDeadlineStop):
            self.ledger(transport).dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(a.replay(self.journal)['attempts'], 1)

    def test_fixture_owner_exit_observes_durable_unknown_audit_and_latch(self):
        transport = Transport(fault='unknown')
        callbacks = []
        slot = 'p3a-01.adaptive.plan.00'

        def owner_exit(result, disposition):
            state = a.replay(self.journal)
            audit = read_json(audit_path(self.study, True, slot))
            stop = read_json(self.journal / 'deadline-stop.json')
            callbacks.append((result, disposition, state, audit, stop))
            self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent', 'result'])
            self.assertEqual(result['status'], 'unknown')
            self.assertEqual(audit['terminal_result_sha256'], digest(result))
            self.assertEqual(stop['candidate_result_sha256'], digest(result))

        ledger = self.ledger(transport, fixture_owner_exit=owner_exit)
        with patch.object(a.os, '_exit', side_effect=AssertionError('host termination forbidden')):
            with self.assertRaises(OwnerStopRequired):
                ledger.dispatch(slot, 'plan', request())
        self.assertEqual(len(callbacks), 1)
        state = callbacks[0][2]
        self.assertEqual(state['status'], 'blocked-unknown')
        self.assertEqual(state['durable_unknown_results'], 1)
        self.assertEqual(state['active_unsettled_intents'], [])
        self.assertEqual(state['spent_micro_usd'], 0)
        self.assertEqual(state['reserved_micro_usd'], am1.reservation('plan'))
        self.assertEqual(state['transport_audit_summary']['validated_audits'], 1)
        self.assertEqual(len(transport.calls), 1)

    def test_close_exception_cannot_bypass_fixture_owner_exit_after_terminal_commit(self):
        transport = Transport(fault='unknown')
        slot = 'p3a-01.adaptive.plan.00'
        callbacks = []

        def owner_exit(result, disposition):
            state = a.replay(self.journal)
            audit = read_json(audit_path(self.study, True, slot))
            stop = read_json(self.journal / 'deadline-stop.json')
            callbacks.append((result, disposition))
            self.assertEqual([event['kind'] for event in a.events(self.journal)], ['intent', 'result'])
            self.assertEqual(state['status'], 'blocked-unknown')
            self.assertEqual(state['results'][slot], result)
            self.assertEqual(state['spent_micro_usd'], 0)
            self.assertEqual(state['reserved_micro_usd'], am1.reservation('plan'))
            self.assertEqual(audit['terminal_result_sha256'], digest(result))
            self.assertEqual(stop['candidate_result_sha256'], digest(result))
            self.assertEqual(stop['reason'], 'unknown_terminal')

        ledger = self.ledger(transport, fixture_owner_exit=owner_exit)
        original_close = transport.close

        def broken_close():
            original_close()
            raise OSError('fixture cleanup reports failure after real bounded cleanup')

        with patch.object(transport, 'close', side_effect=broken_close) as close, patch.object(
                a.os, '_exit', side_effect=AssertionError('host termination forbidden')):
            with self.assertRaises(OwnerStopRequired):
                ledger.dispatch(slot, 'plan', request())
            self.assertEqual(close.call_count, 1)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(callbacks[0][0]['status'], 'unknown')
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(ledger.state()['transport_audit_summary']['validated_audits'], 1)

    def _audit_publication_failure_still_stops_owner(self, *, known: bool):
        transport = Transport(fault=None if known else 'unknown')
        slot = 'p3a-01.adaptive.plan.00'
        target = audit_path(self.study, True, slot)
        callbacks: list[tuple[dict, dict, dict]] = []
        failed_publications = []

        def owner_exit(result, disposition):
            state = a.replay(self.journal)
            stop = read_json(self.journal / 'deadline-stop.json')
            callbacks.append((result, disposition, state))
            self.assertFalse(target.exists())
            self.assertEqual(stop['candidate_result_sha256'], digest(result))
            self.assertEqual(stop['reason'], 'known_cleanup_failed' if known else 'unknown_terminal')
            kinds = [event['kind'] for event in a.events(self.journal)]
            self.assertEqual(kinds[:2], ['intent', 'result'])
            self.assertEqual(state['results'][slot], result)
            self.assertEqual(state['transport_audit_summary']['missing_or_invalid_slots'], [slot])

        ledger = self.ledger(transport, fixture_owner_exit=owner_exit)
        original_publish = core._publish
        original_stop = Transport._stop

        def publish(path, value):
            if Path(path) == target:
                failed_publications.append(path)
                raise OSError('fixture public audit persistence failure')
            return original_publish(path, value)

        def unproven_cleanup(state, deadline):
            original_stop(state, deadline)
            return False

        with patch.object(core, '_publish', side_effect=publish), patch.object(
                a.os, '_exit', side_effect=AssertionError('host termination forbidden')):
            if known:
                with patch.object(Transport, '_stop', side_effect=unproven_cleanup):
                    with self.assertRaises(OwnerStopRequired):
                        ledger.dispatch(slot, 'plan', request())
            else:
                with self.assertRaises(OwnerStopRequired):
                    ledger.dispatch(slot, 'plan', request())
        self.assertEqual(len(failed_publications), 1)
        self.assertEqual(len(callbacks), 1)
        result, disposition, state = callbacks[0]
        self.assertEqual(result['status'], 'response' if known else 'unknown')
        self.assertEqual(state['status'], 'stopped-known-deadline' if known else 'blocked-unknown')
        self.assertEqual(state['spent_micro_usd'], 400 if known else 0)
        self.assertEqual(state['reserved_micro_usd'], 0 if known else am1.reservation('plan'))
        if known:
            self.assertTrue(disposition['owner_stop_required'])
            self.assertFalse(disposition['worker_stopped'])
        with self.assertRaises(KnownDeadlineStop):
            self.ledger(transport).dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(a.replay(self.journal)['attempts'], 1)

    def test_unknown_audit_publication_failure_cannot_bypass_owner_exit(self):
        self._audit_publication_failure_still_stops_owner(known=False)

    def test_known_unproven_cleanup_audit_failure_cannot_bypass_owner_exit(self):
        self._audit_publication_failure_still_stops_owner(known=True)

    def test_known_cleanup_failure_with_proven_stopped_worker_needs_no_owner_exit(self):
        policy = Policy(completion=2, cleanup=.6, editor_minimum=.01, editor_margin=.01)
        transport = Transport(fixture_policy=policy, fixture_behavior={'cleanup_delay': 10})
        callbacks = []
        ledger = self.ledger(transport, fixture_owner_exit=lambda *values: callbacks.append(values))
        slot = 'p3a-01.adaptive.plan.00'
        with patch.object(a.os, '_exit', side_effect=AssertionError('host termination forbidden')):
            with self.assertRaises(KnownDeadlineStop):
                ledger.dispatch(slot, 'plan', request())
        self.assertEqual(callbacks, [])
        state = ledger.state()
        self.assertEqual(state['deadline_stop']['reason'], 'known_cleanup_failed')
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['results'][slot]['status'], 'response')
        self.assertEqual(state['spent_micro_usd'], 400)
        self.assertEqual(state['reserved_micro_usd'], 0)
        audit = read_json(audit_path(self.study, True, slot))
        self.assertTrue(audit['cleanup_failed'])
        self.assertTrue(audit['worker_stopped'])
        self.assertFalse(audit['owner_stop_required'])
        self.assertEqual(state['transport_audit_summary']['validated_audits'], 1)
        self.assertEqual(len(transport.calls), 1)

    def test_historical_exposure_is_carried_once_and_cannot_be_released_by_current_zero(self):
        state = {'fixture': False, 'spent_micro_usd': 0, 'reserved_micro_usd': 0, 'attempts': 0}
        summary = a.historical_totals(state)
        self.assertEqual(summary['cumulative_known_micro_usd'], 12_231_444)
        self.assertEqual(summary['cumulative_reserved_micro_usd'], 22_880_000)
        self.assertEqual(summary['cumulative_max_exposure_micro_usd'], 35_111_444)
        self.assertEqual(summary['cumulative_provider_calls'], 885)
        self.assertEqual(summary['historical']['known_responses'], 883)
        self.assertEqual(summary['historical']['unknown_responses'], 2)
        self.assertLess(summary['cumulative_max_exposure_micro_usd'] + a.POLICY['phase_micro_usd'], 250_000_000)
        self.assertIsNone(a.historical_totals(state | {'fixture': True})['cumulative_max_exposure_micro_usd'])
        changed = copy.deepcopy(summary)
        changed['historical']['reserved_micro_usd'] = 0
        self.assertEqual(a.historical_totals(state)['historical']['reserved_micro_usd'], 22_880_000)


if __name__ == '__main__':
    unittest.main()
