"""R3 profile/replay, actual-SDK equivalence and shared resource guards."""
from __future__ import annotations

import copy
import shutil
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from buddha2 import phase2_am1_controls as am1
from buddha2.artifacts import ContractError, digest, read_json
from followups.phase3a_c1_completion_v3 import accounting as old
from followups.phase3a_c1_completion_v3.tests.fixtures import Transport
from followups.phase3a_c1_completion_v4 import accounting as a
from followups.phase3a_c1_completion_v4.deadline import KnownDeadlineStop, OwnerStopRequired, Policy
from followups.phase3a_c1_completion_v4.transport import audit_path
from followups.phase3a_v1 import accounting as core
from followups.phase3a_v1.tests.test_accounting import request
from followups.phase3a_v1.tests.test_accounting import slots as old_slots


def slots():
    value = old_slots()
    for name, row in list(value.items()):
        if row['role'] == 'editor' and row['turn'] == 8:
            for turn in range(9, 17):
                value[name[:-2] + f'{turn:02}'] = {**row, 'turn': turn}
    return value


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.study = digest({'case': self.id(), 'nonce': uuid.uuid4().hex})
        self.journal = a.canonical_journal(self.study, True)
        self.slots = slots()
        self.bindings = {'source_sha256': '2' * 64, 'policy_sha256': digest(a.POLICY),
                         'launcher_sha256': '4' * 64}
        self.authority = {'study_sha256': self.study, 'authorization_id': 'R3-only-fixture',
            'authorized': False, 'cap_micro_usd': 205860000, 'canary_cap_micro_usd': 50860000,
            'expansion_authorized': False, 'control_policy_sha256': am1.CONTROL_SHA256,
            'billing_profile': am1.BILLING_PROFILE}
        self.addCleanup(self.cleanup, self.journal, a.PREFIX)

    def cleanup(self, journal, prefix):
        target = journal.parent.parent
        self.assertEqual(target.parent, Path('/results') / prefix)
        if target.exists():
            shutil.rmtree(target)

    def ledger(self, transport=None, **kwargs):
        transport = transport or Transport()
        self.addCleanup(transport.close)
        return a.Ledger(self.journal, study_sha256=self.study, slots=self.slots,
            authority=self.authority, bindings=self.bindings, transport=transport, **kwargs)

    def test_exact_new_inventory_and_immutable_old_profile(self):
        before = copy.deepcopy(core.POLICY)
        core._slot_scope(old_slots())
        a._slot_scope(self.slots)
        self.assertEqual(len(self.slots), 967)
        with self.assertRaises(ContractError):
            core._slot_scope(self.slots)
        with self.assertRaises(ContractError):
            a._slot_scope(old_slots())
        ledger = self.ledger()
        result = ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        self.assertEqual(result['status'], 'response')
        self.assertEqual(ledger.state()['transport_audit_summary']['validated_audits'], 1)
        self.assertEqual(ledger.manifest['kind'], 'phase3a-r3-ledger-v1')
        self.assertEqual(ledger.manifest['inputs']['policy'], a.POLICY)
        self.assertEqual(len(ledger.manifest['inputs']['slots']), 967)
        self.assertEqual(core.POLICY, before)
        self.assertEqual(old.POLICY, before)

    def test_exact_editor_turn_identity_and_extra_slots_each_rejected(self):
        key = 'p3a-01.adaptive.editor.inv1.a1.t09'
        bad_cases = []
        value = copy.deepcopy(self.slots)
        value[key + '.alias'] = value.pop(key)
        bad_cases.append(value)
        for field, changed in [('turn', True), ('turn', 17), ('conversation', 'p3a-01:adaptive:inv1.a3'),
                               ('cell', 'p3a-01:fixed'), ('role', 'answer')]:
            value = copy.deepcopy(self.slots)
            value[key][field] = changed
            bad_cases.append(value)
        value = copy.deepcopy(self.slots)
        value['extra.plan'] = {'role': 'plan', 'pair': 'p3a-01', 'cell': 'p3a-01:adaptive'}
        bad_cases.append(value)
        for value in bad_cases:
            with self.subTest(slot=value.get(key)):
                with self.assertRaises(ContractError):
                    a._slot_scope(value)

    def test_old_sources_studies_and_wrong_policy_rejected_before_any_journal(self):
        for retired in a.RETIRED_STUDIES:
            with self.assertRaises(ContractError):
                a.canonical_journal(retired, True)
        for retired in a.RETIRED_SOURCES:
            with self.assertRaises(ContractError):
                a.validate_authority(self.study, self.authority, True,
                                     self.bindings | {'source_sha256': retired})
        with self.assertRaises(ContractError):
            a.validate_authority(self.study, self.authority, True,
                                 self.bindings | {'policy_sha256': digest(old.POLICY)})
        self.assertFalse(self.journal.exists())

    def test_actual_sdk_first_eight_results_equivalent_and_sixteen_turns_count_once(self):
        previous_study = digest({'old-profile-fixture': self.study})
        previous_journal = old.canonical_journal(previous_study, True)
        self.addCleanup(self.cleanup, previous_journal, old.PREFIX)
        old_transport, new_transport = Transport(), Transport()
        self.addCleanup(old_transport.close)
        old_ledger = old.Ledger(previous_journal, study_sha256=previous_study, slots=old_slots(),
            authority=self.authority | {'study_sha256': previous_study},
            bindings=self.bindings | {'policy_sha256': digest(old.POLICY)}, transport=old_transport)
        ledger = self.ledger(new_transport)
        conversation = 'p3a-01:adaptive:inv1.a1'
        deadline = time.monotonic() + 600
        old_transport.register_conversation(conversation, deadline)
        new_transport.register_conversation(conversation, deadline)
        for turn in range(1, 17):
            slot = f'p3a-01.adaptive.editor.inv1.a1.t{turn:02}'
            result = ledger.dispatch(slot, 'editor', request('editor'))
            if turn <= 8:
                previous = old_ledger.dispatch(slot, 'editor', request('editor'))
                for field in ['status', 'spent_micro_usd', 'reserved_micro_usd', 'input_tokens', 'output_tokens']:
                    self.assertEqual(result[field], previous[field])
                for field in ['model', 'text', 'usage', 'stop_reason', 'provider_response']:
                    self.assertEqual(result['response'][field], previous['response'][field])
            audit = read_json(audit_path(self.study, True, slot))
            self.assertEqual(audit['budget']['conversation_deadline'], deadline)
        state = ledger.state()
        self.assertEqual(state['attempts'], 16)
        self.assertEqual(state['transport_audit_summary']['validated_audits'], 16)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(len(new_transport.calls), 16)
        self.assertEqual(ledger.dispatch(slot, 'editor', request('editor')), result)
        self.assertEqual(len(new_transport.calls), 16)
        with self.assertRaises(ContractError):
            ledger.dispatch('p3a-01.adaptive.editor.inv1.a1.t17', 'editor', request('editor'))
        self.assertEqual(len(new_transport.calls), 16)

    def test_editor_sequence_cannot_skip_old_or_new_rounds(self):
        transport = Transport()
        ledger = self.ledger(transport)
        with self.assertRaises(ContractError):
            ledger.dispatch('p3a-01.adaptive.editor.inv1.a1.t09', 'editor', request('editor'))
        self.assertEqual(transport.calls, [])
        self.assertEqual(ledger.state()['attempts'], 0)

    def test_shape_attempts_share_cell_caps_and_global_admission_ceiling_is_independent(self):
        state = core._start({'run_id': 'x', 'inputs': {'fixture': True, 'study_sha256': self.study}})
        meta = self.slots['p3a-01.adaptive.editor.inv1.a2.t01']
        reservation = core._reservation('editor')
        for field, value in [('attempts', 96), ('spent_micro_usd', 20000000 - reservation['micro_usd'] + 1),
                             ('input_tokens', 4000000 - reservation['input'] + 1),
                             ('output_tokens', 786432 - reservation['output'] + 1)]:
            trial = copy.deepcopy(state)
            trial['cells']['p3a-01:adaptive'][field] = value
            with self.subTest(field=field), self.assertRaises(a.CellBudgetStop):
                a._admit(trial, meta, reservation)
        state['attempts'] = 775
        with self.assertRaises(a.PhaseBudgetStop):
            a._admit(state, meta, reservation)
        state['status'] = 'blocked-unknown'
        with self.assertRaises(a.LiabilityStop):
            a._admit(state, meta, reservation)
        state['status'] = 'halted-integrity'
        with self.assertRaises(a.IntegrityStop):
            a._admit(state, meta, reservation)

    def test_actual_sdk_shape_attempts_share_dollar_cap_before_next_intent(self):
        transport = Transport(input_tokens=900000)
        ledger = self.ledger(transport)
        for shape in (1, 2):
            conversation = f'p3a-01:adaptive:inv1.a{shape}'
            transport.register_conversation(conversation, time.monotonic() + 600)
            ledger.dispatch(f'p3a-01.adaptive.editor.inv1.a{shape}.t01', 'editor', request('editor'))
        with self.assertRaises(a.CellBudgetStop):
            ledger.dispatch('p3a-01.adaptive.editor.inv1.a1.t02', 'editor', request('editor'))
        state = ledger.state()
        self.assertEqual(state['attempts'], 2)
        self.assertEqual(state['spent_micro_usd'], 9901320)
        self.assertEqual(len(transport.calls), 2)
        self.assertIn('p3a-01:adaptive', state['stopped_cells'])

    def test_actual_sdk_ninety_six_admissions_stop_despite_unused_potential_slots(self):
        transport = Transport()
        ledger = self.ledger(transport)
        selected = [(name, row['role']) for name, row in self.slots.items()
                    if row['cell'] == 'p3a-01:adaptive' and row['role'] != 'editor']
        for stage in ('inv1', 'dom1', 'agg1'):
            for shape in (1, 2):
                conversation = f'p3a-01:adaptive:{stage}.a{shape}'
                transport.register_conversation(conversation, time.monotonic() + 600)
                selected += [(f'p3a-01.adaptive.editor.{stage}.a{shape}.t{turn:02}', 'editor')
                             for turn in range(1, 9)]
        self.assertEqual(len(selected), 96)
        for slot, role in selected:
            ledger.dispatch(slot, role, request(role))
        with self.assertRaises(a.CellBudgetStop):
            ledger.dispatch('p3a-01.adaptive.editor.inv1.a1.t09', 'editor', request('editor'))
        self.assertEqual(ledger.state()['attempts'], 96)
        self.assertEqual(len(transport.calls), 96)
        self.assertEqual(len(a.events(self.journal)), 193)

    def test_post_lock_expiry_recomputes_before_intent_with_both_locks_held(self):
        transport = Transport(fixture_policy=Policy(completion=2, cleanup=.6,
            editor_minimum=.01, editor_margin=.01))
        ledger = self.ledger(transport)
        slot = 'p3a-01.adaptive.editor.inv1.a1.t01'
        transport.register_conversation(self.slots[slot]['conversation'], time.monotonic() + .15)
        original = transport.prepare
        observed, outcomes = [], []

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
            probe_thread.join(2)
            self.assertFalse(probe_thread.is_alive())
            return original(*args, **kwargs)

        def dispatch():
            try:
                ledger.dispatch(slot, 'editor', request('editor'))
            except BaseException as exc:
                outcomes.append(exc)

        with patch.object(transport, 'prepare', side_effect=prepare):
            with ledger._core._lock:
                worker = threading.Thread(target=dispatch)
                worker.start()
                time.sleep(.2)
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(observed, [(True, True)])
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], KnownDeadlineStop)
        self.assertEqual(ledger.state()['attempts'], 0)
        self.assertEqual(transport.calls, [])
        self.assertEqual(ledger.state()['deadline_stop']['reason'], 'pre_intent_deadline')

    def test_concurrent_state_and_dispatch_never_classify_active_intent_as_unknown(self):
        transport = Transport(fault='slow')
        ledger = self.ledger(transport)
        errors, snapshots = [], []

        def dispatch(slot):
            try:
                ledger.dispatch(slot, 'plan', request())
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=dispatch, args=('p3a-01.adaptive.plan.00',))
        second = threading.Thread(target=dispatch, args=('p3a-01.adaptive.plan.01',))
        reader = threading.Thread(target=lambda: snapshots.append(ledger.state()))
        first.start()
        second.start()
        reader.start()
        for worker in (first, second, reader):
            worker.join(15)
            self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.maximum_inflight, 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]['active_unsettled_intents'], [])
        self.assertEqual(snapshots[0]['durable_unknown_results'], 0)
        self.assertEqual(ledger.state()['attempts'], 2)

    def test_unknown_result_retains_full_hold_and_blocks_every_new_round(self):
        transport = Transport(fault='unknown')
        observed = []
        ledger = self.ledger(transport, fixture_owner_exit=lambda *x: observed.append(x))
        with self.assertRaises(OwnerStopRequired):
            ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        state = ledger.state()
        self.assertEqual(state['status'], 'blocked-unknown')
        self.assertEqual(state['reserved_micro_usd'], 2540960)
        self.assertEqual(state['durable_unknown_results'], 1)
        self.assertEqual(state['deadline_stop']['reason'], 'unknown_terminal')
        self.assertEqual(len(observed), 1)
        with self.assertRaises(KnownDeadlineStop):
            ledger.dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)

    def test_known_late_latch_remains_terminal_and_cannot_rescue_more_rounds(self):
        transport = Transport(fixture_policy=Policy(completion=5, cleanup=2,
            editor_minimum=.01, editor_margin=.01), fixture_behavior={
                'response_delay': 30, 'ignore_cancel': True, 'cancel_delay': .02})
        ledger = self.ledger(transport)
        with self.assertRaises(KnownDeadlineStop):
            ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        state = ledger.state()
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['spent_micro_usd'], 400)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(state['transport_audit_summary']['late_known'], 1)
        self.assertEqual([x['kind'] for x in a.events(self.journal)], ['intent', 'result', 'halt'])
        with self.assertRaises(KnownDeadlineStop):
            ledger.dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)

    def test_crash_after_late_result_before_audit_still_cannot_resume(self):
        class SimulatedCrash(BaseException):
            pass

        transport = Transport(fixture_policy=Policy(completion=5, cleanup=2,
            editor_minimum=.01, editor_margin=.01), fixture_behavior={
                'response_delay': 30, 'ignore_cancel': True, 'cancel_delay': .02})
        ledger = self.ledger(transport)

        def crash(*args):
            raise SimulatedCrash()

        with patch.object(transport, 'commit', side_effect=crash):
            with self.assertRaises(SimulatedCrash):
                ledger.dispatch('p3a-01.adaptive.plan.00', 'plan', request())
        state = ledger.state()
        self.assertEqual(state['core_status'], 'ready')
        self.assertEqual(state['status'], 'stopped-known-deadline')
        self.assertEqual(state['deadline_stop']['reason'], 'known_late_response')
        self.assertEqual(state['spent_micro_usd'], 400)
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(state['transport_audit_summary']['missing_or_invalid_slots'],
                         ['p3a-01.adaptive.plan.00'])
        self.assertEqual([x['kind'] for x in a.events(self.journal)], ['intent', 'result'])
        with self.assertRaises(KnownDeadlineStop):
            self.ledger(transport).dispatch('p3a-01.adaptive.plan.01', 'plan', request())
        self.assertEqual(len(transport.calls), 1)

    def test_history_carries_r2_once_and_mock_totals_never_become_actual(self):
        state = {'fixture': False, 'spent_micro_usd': 0, 'reserved_micro_usd': 0, 'attempts': 0}
        totals = a.historical_totals(state)
        self.assertEqual(totals['cumulative_known_micro_usd'], 13101271)
        self.assertEqual(totals['cumulative_reserved_micro_usd'], 22880000)
        self.assertEqual(totals['cumulative_max_exposure_micro_usd'], 35981271)
        self.assertEqual(totals['cumulative_provider_calls'], 904)
        self.assertFalse(totals['historical_unknown_released'])
        self.assertIsNone(a.historical_totals(state | {'fixture': True})['cumulative_known_micro_usd'])
