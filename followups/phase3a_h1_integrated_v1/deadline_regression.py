"""Versioned HI fixture deadlines for SDK-startup-dependent reused-helper checks.

These are new semantic checks, not passing results for the frozen 2-second cases.
Only fixture scheduling changes: provider production guards remain untouched.
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from buddha2.artifacts import digest, read_json
from followups.phase3a_c1_completion_v3 import accounting as a
from followups.phase3a_c1_completion_v3.deadline import KnownDeadlineStop, Policy
from followups.phase3a_c1_completion_v3.tests import test_accounting as frozen_accounting
from followups.phase3a_c1_completion_v3.tests.fixtures import Transport
from followups.phase3a_c1_completion_v3.tests.test_deadline import BINDINGS, bind, fixture_transport
from followups.phase3a_c1_completion_v3.transport import audit_path, validate_audit
from followups.phase3a_v1 import accounting as core
from followups.phase3a_v1.tests.test_accounting import request
from followups.phase3a_v1.transport import TransportFailure

FIXTURE_POLICY = {"completion": 10, "cleanup": 2, "editor_minimum": .01, "editor_margin": .01}
FIXTURE_DELAYS = {"response": 30, "body": 30, "cleanup": 30, "cancel": .02}


def fixture_policy():
    return Policy(**FIXTURE_POLICY)


class HIDeadlineChecks(unittest.TestCase):
    def test_cancellation_suppressed_late_complete_is_known_accounting_only(self):
        t = fixture_transport(fixture_policy=fixture_policy(), fixture_behavior={
            "response_delay": 30, "ignore_cancel": True, "cancel_delay": .02})
        self.addCleanup(t.close)
        intent, allocation, body = bind(t)
        response = t.create("plan", body)
        result = core._result(intent, response)
        self.assertEqual(result["status"], "response")
        audit = t.commit(intent["slot_id"], result)
        self.assertTrue(audit["late_known"])
        self.assertGreater(audit["parent_capture_monotonic"], allocation.deadline_monotonic)
        self.assertFalse(audit["owner_stop_required"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)
        self.assertTrue(audit["sdk_invoked"], "fixture must reach the actual SDK before its deadline")

    def test_uncooperative_sdk_loop_is_killed_and_reaped_without_resend(self):
        t = fixture_transport(fixture_policy=fixture_policy(), fixture_behavior={"block_loop": True})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        started = time.monotonic()
        with self.assertRaises(TransportFailure) as caught:
            t.create("plan", body)
        self.assertLess(time.monotonic() - started, 14)
        self.assertEqual(caught.exception.failure["category"], "timeout")
        result = core._result(intent, None, failure=caught.exception.failure)
        audit = t.commit(intent["slot_id"], result)
        self.assertTrue(audit["worker_stopped"])
        self.assertFalse(audit["owner_stop_required"])
        self.assertEqual(t.fixture_records, [])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        self.assertTrue(audit["sdk_invoked"], "fixture must reach the actual SDK before its deadline")

    def test_delayed_body_is_inside_completion_not_merely_header_arrival(self):
        t = fixture_transport(fixture_policy=fixture_policy(), fixture_behavior={"body_delay": 30})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        with self.assertRaises(TransportFailure) as caught:
            t.create("plan", body)
        audit = t.commit(intent["slot_id"], core._result(intent, None, failure=caught.exception.failure))
        self.assertEqual(len(t.fixture_records), 1)
        self.assertIsNone(audit["parent_capture_monotonic"])
        self.assertEqual(audit["terminal_status"], "unknown")
        self.assertTrue(audit["worker_stopped"])
        self.assertTrue(audit["sdk_invoked"], "fixture must reach the actual SDK before its deadline")

    def test_known_response_with_unfinished_cleanup_requires_known_stop(self):
        t = fixture_transport(fixture_policy=fixture_policy(), fixture_behavior={"cleanup_delay": 30})
        self.addCleanup(t.close)
        intent, _, body = bind(t)
        response = t.create("plan", body)
        result = core._result(intent, response)
        audit = t.commit(intent["slot_id"], result)
        self.assertEqual(result["status"], "response")
        self.assertFalse(audit["late_known"])
        self.assertTrue(audit["cleanup_failed"])
        self.assertTrue(audit["worker_stopped"])
        with self.assertRaises(KnownDeadlineStop):
            bind(t)
        validate_audit(audit, intent=intent, result=result, bindings=BINDINGS)
        self.assertTrue(audit["sdk_invoked"], "fixture must reach the actual SDK before its deadline")


class HIAccountingChecks(frozen_accounting.AccountingTests):
    # Only the three mapped overrides are loaded; fixture setup/ledger stay unchanged.
    def test_known_late_latch_precedes_result_and_no_output_is_forwarded(self):
        policy = fixture_policy()
        transport = Transport(fixture_policy=policy, fixture_behavior={
            'response_delay': 30, 'ignore_cancel': True, 'cancel_delay': .02})
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
        self.assertTrue(read_json(audit_path(self.study, True, slot))["sdk_invoked"])

    def test_crash_after_late_result_before_audit_or_halt_still_blocks_admission(self):
        class SimulatedCrash(BaseException):
            pass

        policy = fixture_policy()
        transport = Transport(fixture_policy=policy, fixture_behavior={
            'response_delay': 30, 'ignore_cancel': True, 'cancel_delay': .02})
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
        self.assertTrue(transport._outcomes[slot]["sdk_invoked"])

    def test_known_cleanup_failure_with_proven_stopped_worker_needs_no_owner_exit(self):
        policy = fixture_policy()
        transport = Transport(fixture_policy=policy, fixture_behavior={'cleanup_delay': 30})
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
        self.assertTrue(read_json(audit_path(self.study, True, slot))["sdk_invoked"])


REPLACEMENTS = {'followups.phase3a_c1_completion_v3.tests.test_deadline.DeadlineTests.test_cancellation_suppressed_late_complete_is_known_accounting_only': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIDeadlineChecks.test_cancellation_suppressed_late_complete_is_known_accounting_only', 'followups.phase3a_c1_completion_v3.tests.test_deadline.DeadlineTests.test_uncooperative_sdk_loop_is_killed_and_reaped_without_resend': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIDeadlineChecks.test_uncooperative_sdk_loop_is_killed_and_reaped_without_resend', 'followups.phase3a_c1_completion_v3.tests.test_deadline.DeadlineTests.test_delayed_body_is_inside_completion_not_merely_header_arrival': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIDeadlineChecks.test_delayed_body_is_inside_completion_not_merely_header_arrival', 'followups.phase3a_c1_completion_v3.tests.test_deadline.DeadlineTests.test_known_response_with_unfinished_cleanup_requires_known_stop': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIDeadlineChecks.test_known_response_with_unfinished_cleanup_requires_known_stop', 'followups.phase3a_c1_completion_v3.tests.test_accounting.AccountingTests.test_known_late_latch_precedes_result_and_no_output_is_forwarded': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIAccountingChecks.test_known_late_latch_precedes_result_and_no_output_is_forwarded', 'followups.phase3a_c1_completion_v3.tests.test_accounting.AccountingTests.test_crash_after_late_result_before_audit_or_halt_still_blocks_admission': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIAccountingChecks.test_crash_after_late_result_before_audit_or_halt_still_blocks_admission', 'followups.phase3a_c1_completion_v3.tests.test_accounting.AccountingTests.test_known_cleanup_failure_with_proven_stopped_worker_needs_no_owner_exit': 'followups.phase3a_h1_integrated_v1.deadline_regression.HIAccountingChecks.test_known_cleanup_failure_with_proven_stopped_worker_needs_no_owner_exit'}
