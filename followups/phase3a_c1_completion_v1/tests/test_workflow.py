"""Fresh-study gates, counted readiness reuse and saved paired evaluation."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash
from buddha2.phase2_dispatch import writer_lock
from followups.phase3a_c1_completion_v1 import accounting
from followups.phase3a_c1_completion_v1 import workflow as w
from followups.phase3a_v1.tests.test_accounting import Transport


class NoCalls:
    fixture = True
    def __init__(self):
        self.calls = []
    def create(self, role, request):
        self.calls.append((role, request))
        raise AssertionError('a rejected controller invocation attempted transport')


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        w.BASE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='workflow-tests-', dir=w.BASE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        name = 'followups/phase3a_c1_completion_v1/workflow.py'
        files = {name: file_hash(w.ROOT / name)}
        self.source = {'kind': 'isolated-controller-test-source', 'files': files,
                       'sha256': digest(files), 'fixture_nonce': self.root.name}
        self.runtime = w.runtime_identity()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(w, 'source_identity', return_value=self.source))
        self.stack.enter_context(patch.object(w, 'runtime_identity', return_value=self.runtime))
        self.study_path = self.root / 'release/study.json'
        self.study = w.prepare(self.study_path.parent, source=self.source, runtime=self.runtime)
        self.grant_path = self.study_path.parent / 'mock-grant.json'
        self.write(self.grant_path, w.make_grant(self.study_path, True))
        self.run_path, self.journal = w.paths(self.study, True)
        self.addCleanup(self.remove_run)

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

    def remove_run(self):
        for target, boundary in ((self.run_path.parent, w.NATIVE), (self.journal.parent.parent, w.BASE)):
            self.assertTrue(target.is_relative_to(boundary) and target != boundary)
            if target.exists():
                shutil.rmtree(target)

    def test_prepare_freezes_fresh_full_worklist_and_readiness_is_first_primary(self):
        loaded = w.load_study(self.study_path)
        self.assertEqual(loaded['study_sha256'], self.study['study_sha256'])
        self.assertNotIn(loaded['study_sha256'], accounting.RETIRED_STUDIES)
        self.assertEqual(len(loaded['slots']), 775)
        self.assertEqual(loaded['tasks'][0]['arm_order'], ['adaptive', 'fixed'])
        self.assertEqual(loaded['readiness_is_primary'], 'p3a-01:adaptive')
        self.assertEqual(loaded['readiness_max_micro_usd'], 20_000_000)
        self.assertEqual(loaded['prior_live_episode']['reserved_micro_usd'], 11_440_000)
        checked = w.preflight(self.study_path, self.grant_path, True, 'readiness')
        self.assertEqual(checked['study_sha256'], loaded['study_sha256'])
        self.assertEqual(checked['provider_calls'], 0)
        self.assertFalse(self.journal.exists())

    def test_resealed_foreign_source_or_mode_grant_fails_before_any_transport(self):
        grant = w.read(self.grant_path)
        for changes in ({'source_sha256': '0' * 64}, {'fixture': False}, {'study_sha256': 'a' * 64}):
            with self.subTest(changes=changes):
                bad = grant | changes
                bad['grant_sha256'] = digest({k: v for k, v in bad.items() if k != 'grant_sha256'})
                self.write(self.grant_path, bad)
                transport = NoCalls()
                with self.assertRaises(ContractError):
                    w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
                self.assertEqual(transport.calls, [])
        self.assertFalse(self.journal.exists())

    def test_resealed_method_task_or_historical_liability_change_cannot_be_regranted(self):
        original = self.study_path.read_bytes()
        variants = []
        changed = copy.deepcopy(self.study)
        changed['tasks'][0]['prompt'] = 'An unauthorized replacement task.'
        variants.append(changed)
        changed = copy.deepcopy(self.study)
        changed['prior_live_episode']['reserved_micro_usd'] = 0
        variants.append(changed)
        changed = copy.deepcopy(self.study)
        changed['seed_procedure_sha256'] = '0' * 64
        variants.append(changed)
        changed = copy.deepcopy(self.study)
        changed['readiness_is_primary'] = 'p3a-02:adaptive'
        variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed['study_sha256']):
                changed['study_sha256'] = digest({k: v for k, v in changed.items() if k != 'study_sha256'})
                self.write(self.study_path, changed)
                with self.assertRaises(ContractError):
                    w.load_study(self.study_path)
                with self.assertRaises(ContractError):
                    w.make_grant(self.study_path, True)
                self.study_path.write_bytes(original)

    def test_study_source_or_retained_seed_change_rejects_before_transport(self):
        transport = NoCalls()
        changed_source = copy.deepcopy(self.source)
        changed_source['fixture_nonce'] = 'different-controller-source'
        with patch.object(w, 'source_identity', return_value=changed_source), self.assertRaises(ContractError):
            w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        seed = self.study_path.parent / 'seed/systemprompt.md'
        value = json.loads(seed.read_text(encoding='utf-8'))
        value['answer_system'] += '\nA changed retained seed.'
        seed.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(ContractError):
            w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        self.assertEqual(transport.calls, [])

    def test_missing_or_resealed_fake_readiness_pass_cannot_unlock_first_pair(self):
        transport = NoCalls()
        with self.assertRaises(ContractError):
            w.run(self.study_path, self.grant_path, stage='first', transport=transport)
        self.write(self.run_path / 'readiness-review.json', w.seal({
            'kind': 'phase3a-c1-counted-readiness-review-v1', 'passed': True,
            'study_sha256': self.study['study_sha256'], 'source_sha256': self.study['source_sha256'],
            'fixture': True, 'branch_sha256': '0' * 64, 'proof': {}, 'inspection': {}}))
        for stage in ('first', 'all'):
            with self.subTest(stage=stage), self.assertRaises(ContractError):
                w.preflight(self.study_path, self.grant_path, True, stage)
        self.assertEqual(transport.calls, [])

    def test_known_readiness_failure_blocks_reentry_without_an_unknown_charge(self):
        self.write(self.run_path / 'readiness-failure.json', w.seal({
            'kind': 'phase3a-c1-readiness-known-stop-v1', 'study_sha256': self.study['study_sha256'],
            'fixture': True, 'reason': 'synthetic terminal condition', 'unknown_charge_inferred': False}))
        transport = NoCalls()
        for stage in ('readiness', 'all'):
            with self.subTest(stage=stage), self.assertRaises(ContractError):
                w.run(self.study_path, self.grant_path, stage=stage, transport=transport)
        self.assertEqual(transport.calls, [])
        self.assertFalse(self.journal.exists())

    def test_second_workflow_owner_cannot_reach_dispatch(self):
        transport = NoCalls()
        with writer_lock(self.run_path / 'owner'):
            with self.assertRaises(ContractError):
                w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        self.assertEqual(transport.calls, [])
        self.assertFalse(self.journal.exists())

    def test_unknown_first_request_remains_held_and_is_not_resent(self):
        transport = Transport(fault='unknown')
        summary = w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        self.assertEqual(len(transport.calls), 1)
        state = accounting.replay(self.journal)
        self.assertEqual(state['status'], 'blocked-unknown')
        self.assertGreater(state['reserved_micro_usd'], 0)
        self.assertIsNotNone(summary)
        with self.assertRaises(ContractError):
            w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        self.assertEqual(len(transport.calls), 1)

    def test_readiness_observer_stops_unfinished_but_preserves_valid_shape_repair_and_holds(self):
        from harness2.core.proposer import ProposerError

        notes = '<notes>kept -> KEEP_BASE -> synthetic complete evidence, no efficacy claim.</notes>'
        cases = [('valid', False, True, True, False), ('invalid_harvest', False, True, True, False),
                 ('empty', False, True, True, True), ('boundary_stopped', False, True, True, True),
                 ('valid', True, True, True, True), ('empty', False, False, True, False),
                 ('empty', False, True, False, False)]
        for status, terminal, observe, can_stop, expected in cases:
            with self.subTest(status=status, terminal=terminal, observe=observe, can_stop=can_stop):
                proposer = object.__new__(w.ReadinessProposer)
                stopped: list[str] = []
                proposer.observe = observe
                proposer.known_stop = stopped.append
                proposer.can_stop = lambda value=can_stop: value
                proposer.final_response = None
                reply = SimpleNamespace(text=notes)
                with patch.object(w.CompatibleProposer, 'call', return_value=reply), patch.object(
                        proposer, 'phase3a_evidence', return_value={'sessions': {
                            'inv1.a1': {'status': status, 'terminal_note_used': terminal}}}):
                    self.assertIs(proposer.call('fixture', None, 'inv1.a1'), reply)
                self.assertEqual(stopped, ['unfinished_editor_session'] if expected else [])
        for saved, final in (('I need more time.', None), (notes, 'I need more time.'),
                             (notes, '<notes>A different saved output.</notes>')):
            with self.subTest(saved=saved, final=final):
                proposer = object.__new__(w.ReadinessProposer)
                stopped = []
                proposer.observe = True
                proposer.known_stop = stopped.append
                proposer.can_stop = lambda: True
                proposer.final_response = (lambda session, value=final: value) if final is not None else None
                with patch.object(w.CompatibleProposer, 'call', return_value=SimpleNamespace(text=saved)), patch.object(
                        proposer, 'phase3a_evidence', return_value={'sessions': {
                            'inv1.a1': {'status': 'valid', 'terminal_note_used': False}}}):
                    proposer.call('fixture', None, 'inv1.a1')
                self.assertEqual(stopped, ['unfinished_editor_session'])
        for can_stop in (True, False):
            proposer = object.__new__(w.ReadinessProposer)
            stopped = []
            proposer.observe = True
            proposer.known_stop = stopped.append
            proposer.can_stop = lambda value=can_stop: value
            with patch.object(w.CompatibleProposer, 'call', side_effect=ProposerError('synthetic unfinished')):
                with self.assertRaises(ProposerError):
                    proposer.call('fixture', None, 'inv1.a1')
            self.assertEqual(stopped, ['unfinished_editor_session'] if can_stop else [])

    def test_pinned_eighth_control_is_known_stop_before_intent_and_blocks_queued_plan(self):
        from followups.phase3a_v1 import editor
        from followups.phase3a_v1.tests.test_accounting import request

        transport = NoCalls()
        editor_request = request('editor')
        editor_request['messages'] = [{'role': 'user', 'content': [{'type': 'text', 'text': editor.terminal_note()}]}]
        plan_slot = next(slot for slot, row in self.study['slots'].items()
                         if row['cell'] == 'p3a-01:adaptive' and row['role'] == 'plan')
        def exhausted_native(*args, dispatch, **kwargs):
            with self.assertRaises(accounting.ReadinessStop):
                dispatch('p3a-01.adaptive.editor.inv1.a1.t08', 'editor', editor_request)
            with self.assertRaises(accounting.ReadinessStop):
                dispatch(plan_slot, 'plan', request())
            raise accounting.ReadinessStop('synthetic pinned-terminal outcome')
        with patch.object(w.native, 'run_adaptation', side_effect=exhausted_native):
            summary = w.run(self.study_path, self.grant_path, stage='readiness', transport=transport)
        state = accounting.replay(self.journal)
        self.assertEqual(state['status'], 'ready')
        self.assertEqual(state['attempts'], 0)
        self.assertEqual(state['intents'], {})
        self.assertEqual(state['reserved_micro_usd'], 0)
        self.assertEqual(transport.calls, [])
        stopped = w.checked(w.read(self.run_path / 'readiness-failure.json'))
        self.assertEqual(stopped['reason'], 'forced_terminal_control_before_dispatch')
        self.assertFalse(stopped['unknown_charge_inferred'])
        self.assertFalse(summary['readiness_passed'])

    @unittest.skipUnless(Path('/opt/phase3a-opencode').is_dir(), 'requires pinned actual OpenCode')
    def test_actual_empty_editor_stops_before_probe_or_other_editor_admission(self):
        from followups.phase3a_c1_completion_v1.mocks import StudyMock

        class EmptyMock(StudyMock):
            def _editor_content(self, body, slot):
                return [{'type': 'text', 'text': ''}], 'end_turn'

        with EmptyMock() as mock:
            result = w.run(self.study_path, self.grant_path, stage='readiness', transport=mock.transport)
            state = accounting.replay(self.journal)
            self.assertEqual(state['status'], 'ready')
            self.assertEqual(state['attempts'], 13)
            self.assertEqual(mock.http_calls, 13)
            self.assertEqual(state['reserved_micro_usd'], 0)
            self.assertTrue(all(row['status'] == 'response' for row in state['results'].values()))
            self.assertEqual(sum(row['role'] == 'editor' for row in state['results'].values()), 1)
            stopped = w.checked(w.read(self.run_path / 'readiness-failure.json'))
            self.assertEqual(stopped['reason'], 'unfinished_editor_session')
            self.assertFalse(stopped['unknown_charge_inferred'])
            self.assertFalse((self.run_path / 'readiness-review.json').exists())
            self.assertFalse(result['readiness_passed'])
            before = mock.http_calls
            with self.assertRaises(ContractError):
                w.run(self.study_path, self.grant_path, stage='all', transport=mock.transport)
            self.assertEqual(mock.http_calls, before)

    @unittest.skipUnless(Path('/opt/phase3a-opencode').is_dir(), 'requires pinned actual OpenCode')
    def test_counted_first_pair_reuses_readiness_seals_before_judging_and_reports_without_calls(self):
        from followups.phase3a_c1_completion_v1.mocks import StudyMock
        from followups.phase3a_c1_completion_v1.report import write_report
        owner = self
        class CheckedMock(StudyMock):
            def _handle(self, request, *, http_module):
                if self._selected is not None and self._selected[0] in {'group', 'quality'}:
                    pilot = owner.study['slots'][self._selected[1]]['pair']
                    owner.assertTrue((owner.run_path / 'seals' / (pilot + '.json')).is_file())
                return super()._handle(request, http_module=http_module)

        with CheckedMock() as mock:
            w.run(self.study_path, self.grant_path, stage='readiness', transport=mock.transport)
            state = accounting.replay(self.journal)
            self.assertEqual(state['attempts'], 68)
            self.assertEqual({self.study['slots'][slot]['cell'] for slot in state['results']}, {'p3a-01:adaptive'})
            adaptive = self.run_path / 'branches/p3a-01-adaptive.json'
            adaptive_bytes = adaptive.read_bytes()
            before = mock.http_calls
            with self.assertRaises(ContractError):
                w.run(self.study_path, self.grant_path, stage='first', transport=mock.transport)
            self.assertEqual(mock.http_calls, before)
            w._barrier(self.study_path, self.study, self.grant_path, True, 'readiness')
            w.run(self.study_path, self.grant_path, stage='first', transport=mock.transport)
            self.assertEqual(adaptive.read_bytes(), adaptive_bytes)
            state = accounting.replay(self.journal)
            self.assertEqual(state['attempts'], 174)
            self.assertEqual(mock.http_calls, 174)
            self.assertEqual(state['cells']['p3a-01:adaptive']['attempts'], 68)
            events = accounting.events(self.journal)
            seal = w.read(self.run_path / 'seals/p3a-01.json')
            first_judge = min(event['index'] for event in events if event['kind'] == 'intent'
                              and event['record']['role'] in {'group', 'quality'})
            self.assertLess(seal['journal_prefix']['index'], first_judge)
            self.assertFalse(any(event['index'] > seal['journal_prefix']['index'] and event['kind'] == 'intent'
                and event['record']['role'] not in {'group', 'quality'} for event in events))
            w._barrier(self.study_path, self.study, self.grant_path, True, 'first')
            before = mock.http_calls
            journal_bytes = (self.journal / 'events.jsonl').read_bytes()
            w.run(self.study_path, self.grant_path, stage='first', transport=mock.transport)
            self.assertEqual(mock.http_calls, before)
            self.assertEqual((self.journal / 'events.jsonl').read_bytes(), journal_bytes)
            for name in ('report', 'replay'):
                with ExitStack() as guards:
                    for target in ('anthropic.Anthropic', 'anthropic.AsyncAnthropic', 'openai.OpenAI',
                                   'openai.AsyncOpenAI', 'socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
                        guards.enter_context(patch(target, side_effect=AssertionError('saved report attempted external activity')))
                    write_report(w.snapshot(self.study_path, self.grant_path, True), self.run_path / 'reports' / name)
            names = sorted(path.name for path in (self.run_path / 'reports/report').iterdir())
            self.assertEqual(set(names), {name + '.json' for name in ('rows', 'coverage', 'analysis',
                'summary', 'accounting', 'protocol', 'readiness')} | {'PHASE3A_REPORT.md'})
            self.assertTrue(all((self.run_path / 'reports/report' / name).read_bytes() ==
                (self.run_path / 'reports/replay' / name).read_bytes() for name in names))
            self.assertEqual(mock.http_calls, before)