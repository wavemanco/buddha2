"""One guarded saved-only S2 resume; no generator, SDK client or subprocess."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
import traceback
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/workspace')
BASE = Path('/results/phase3b-seq2-v1')
VERIFY = BASE / 'verification-v2'
REVIEW = VERIFY / 'external-reviews/recovery-review-v1'
OUTPUT = REVIEW / 'r1'
SOURCE = '0b154f40fd0418b5d86a218abf23050d9b0db26a2195dbad828a6c6a3f4073aa'
STUDY = '160fa663c793f3ac0878031f3ffaa9d6db57b4349069bc9460756e147b2b68ee'
NATIVE = BASE / 'native' / STUDY / 'mock'
JOURNAL = BASE / STUDY / 'mock/journal'
COUNTS: dict[str, int] = {}


class ForbiddenActivity(RuntimeError):
    pass


def blocked(kind):
    def reject(*args, **kwargs):
        COUNTS[kind] = COUNTS.get(kind, 0) + 1
        raise ForbiddenActivity(kind)
    return reject


def audit(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.spawn', 'os.posix_spawn')) or event.startswith(('os.fork', 'os.exec', 'pty.spawn')) or event == 'os.system':
        blocked('audit:' + event)()


def raw_hash(target):
    value = hashlib.sha256()
    with Path(target).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(target, value):
    with Path(target).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def progress(stage):
    with (OUTPUT / 'progress.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(),
                                 'stage': stage, 'elapsed_seconds': time.monotonic() - START}, sort_keys=True) + '\n')


def inventory():
    from followups.phase3b_seq2_v1.support import PRIVATE, safe

    result = {}

    def walk(directory, prefix):
        for name in sorted(os.listdir(directory)):
            if name.casefold() in PRIVATE or 'stdout' in name.casefold() or 'stderr' in name.casefold():
                continue  # lexical exclusion before any metadata
            target = directory / name
            if target == REVIEW or target == NATIVE / 'reports/replay':
                continue  # only the new evidence and previously absent replay destination
            target = safe(target)
            info = target.lstat()
            relative = prefix + '/' + target.relative_to(directory).as_posix()
            if stat.S_ISDIR(info.st_mode):
                walk(target, relative)
            elif stat.S_ISREG(info.st_mode):
                result[relative] = {'sha256': raw_hash(target), 'bytes': info.st_size,
                                    'mode': stat.S_IMODE(info.st_mode)}
            else:
                raise ValueError('nonordinary saved input')

    roots = ((VERIFY, 'verification'), (NATIVE, 'native'), (JOURNAL.parent, 'physical-journal-and-audits'),
             (BASE / 'native/capacity-verification-v2', 'capacity'),
             (BASE / 'visibility-exports' / STUDY / 'mock', 'visibility-exports'))
    for directory, prefix in roots:
        directory = safe(directory)
        if directory.exists():
            walk(directory, prefix)
        else:
            result[prefix] = {'absent': True}
    return result


def perform(spec):
    sys.addaudithook(audit)
    with ExitStack() as guards:
        # SDK construction is blocked before importing any project workflow module.
        for target in ('anthropic.Anthropic', 'anthropic.AsyncAnthropic', 'openai.OpenAI', 'openai.AsyncOpenAI'):
            guards.enter_context(patch(target, side_effect=blocked(target)))
        from followups.phase3b_seq2_v1 import accounting, workflow
        from followups.phase3b_seq2_v1.report import NAMES, write_report
        from followups.phase3b_seq2_v1.support import checked, preserve, read, require, source_identity
        from followups.phase3b_seq2_v1.transport import Transport

        class DenyAllFixtureTransport(Transport):
            """Satisfy the real Ledger type contract; initialize no SDK or worker."""
            fixture = True

            def __init__(self):
                pass

            def __getattribute__(self, name):
                if name in {'fixture', '__class__'}:
                    return object.__getattribute__(self, name)
                return blocked('deny_transport.attribute:' + name)()

        for target in (
            'buddha2.phase2_dispatch.DirectSDKTransport.__init__',
            'followups.phase3b_seq2_v1.transport.Transport.__init__',
            'followups.phase3b_seq2_v1.transport.Transport.create',
            'followups.phase3b_seq2_v1.accounting.Ledger.dispatch',
            'followups.phase3b_seq2_v1.mocks.StudyMock.__enter__',
            'followups.phase3b_seq2_v1.mocks.SDKMock._handle',
            'followups.phase3b_seq2_v1.native.run_adaptation',
            'followups.phase3b_seq2_v1.workflow.ReadinessProposer.__init__',
            'httpx.Client.send', 'httpx.AsyncClient.send',
            'httpx2.Client.send', 'httpx2.AsyncClient.send',
            'harness2.core.proposer.Proposer.call', 'harness2.core.schedule.run_task',
            'multiprocessing.process.BaseProcess.start',
            'subprocess.Popen', 'subprocess.run', 'os.system',
            'socket.create_connection', 'socket.getaddrinfo', 'socket.gethostbyname',
            'socket.gethostbyname_ex', 'socket.gethostbyaddr',
            'socket.socket.connect', 'socket.socket.connect_ex',
        ):
            guards.enter_context(patch(target, side_effect=blocked(target)))
        require({p.name for p in Path('/sys/class/net').iterdir()} == {'lo'}, 'network-none required')
        require(raw_hash(Path(__file__)) == spec['worker_sha256'], 'worker changed')
        require(spec['source_sha256'] == SOURCE and spec['study_sha256'] == STUDY, 'foreign recovery inputs')
        study_path = VERIFY / 'release/study.json'
        grant_path = VERIFY / 'release/mock-grant.json'
        matrix = checked(read(VERIFY / 'matrix.json'))
        require(matrix['passed'] is True and matrix['source_sha256'] == SOURCE and matrix['study_sha256'] == STUDY,
                'complete current matrix required')
        require(matrix['mock_http_calls'] == 1364 and matrix['real_provider_calls'] == 0, 'foreign matrix population')
        for name in ('first-pair', 'closure'):
            value = checked(read(NATIVE / 'visibility' / name / 'status.json'))
            require(value['canonical_status'] == 'complete' and value['worker_stopped'] is True
                    and value['reports_published'] is True and value['fixture'] is True,
                    'original canonical checkpoint incomplete')
        names = tuple(name + '.json' for name in NAMES) + ('PHASE3B_REPORT.md',)
        require(not (NATIVE / 'reports/replay').exists(), 'replay destination must be absent')
        final_hashes = {name: raw_hash(NATIVE / 'reports/final' / name) for name in names}
        progress('before-inventory')
        before = inventory()
        save(OUTPUT / 'input-before.json', before)
        progress('before-source-history')
        source_before, history_before = source_identity(), preserve()
        require(source_before == read(VERIFY / 'source-before.json')
                and source_before['sha256'] == SOURCE
                and history_before == read(VERIFY / 'preservation-before.json'), 'original source/history changed')
        save(OUTPUT / 'source-before.json', source_before)
        save(OUTPUT / 'history-before.json', history_before)
        journal_before = raw_hash(JOURNAL / 'events.jsonl')
        progress('actual-saved-workflow-run-start')
        repeated = workflow.run(study_path, grant_path, stage='all', transport=DenyAllFixtureTransport())
        progress('actual-saved-workflow-run-finished')
        require(repeated == matrix['summary'], 'actual repeated run summary differs')
        progress('snapshot-report-start')
        data = workflow.snapshot(study_path, grant_path, True)
        write_report(data, NATIVE / 'reports/replay')
        progress('snapshot-report-finished')
        replay_hashes = {name: raw_hash(NATIVE / 'reports/replay' / name) for name in names}
        require(final_hashes == replay_hashes, 'report replay bytes differ')
        require(raw_hash(JOURNAL / 'events.jsonl') == journal_before, 'journal changed')
        state = accounting.replay(JOURNAL)
        require(state['attempts'] == len(state['intents']) == len(state['results']) == 1364
                and state['reserved_micro_usd'] == 0 and not state['active_unsettled_intents']
                and state['durable_unknown_results'] == 0, 'saved accounting population changed')
        progress('after-source-history')
        source_after, history_after = source_identity(), preserve()
        save(OUTPUT / 'source-after.json', source_after)
        save(OUTPUT / 'history-after.json', history_after)
        require(source_before == source_after and history_before == history_after, 'source/history changed')
        progress('after-inventory')
        after = inventory()
        save(OUTPUT / 'input-after.json', after)
        require(before == after and not any(COUNTS.values()), 'saved input changed or forbidden activity attempted')
        return {'passed': True, 'actual_workflow_run_matches_original_summary': True,
                'original_invocation_passed': False, 'source_unchanged': True, 'history_unchanged': True,
                'ordinary_inputs_unchanged': True, 'journal_unchanged': True, 'original_mock_http_calls': 1364,
                'new_mock_calls': 0, 'new_journal_results': 0, 'real_provider_calls': 0,
                'counter_basis': 'Fail-before-action guards, zero new intents/results and unchanged physical proof/wire',
                'report_files': list(names), 'final_report_sha256': final_hashes,
                'replay_report_sha256': replay_hashes, 'fixture': True,
                'scientific_complete': False, 'authentic_live_path': False}


START = time.monotonic()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    value = {'kind': 'phase3b-s2-saved-only-continuation-result-v1', 'passed': False,
             'source_sha256': SOURCE, 'study_sha256': STUDY, 'worker_sha256': raw_hash(Path(__file__)),
             'spec_sha256': raw_hash(args.spec), 'new_mock_calls': 0, 'real_provider_calls': 0}
    try:
        value.update(perform(spec))
    except BaseException as exc:
        value.update(passed=False, failure_type=type(exc).__name__, failure_message=str(exc),
                     failure_traceback=traceback.format_exc())
    value.update(forbidden_attempts=COUNTS, elapsed_seconds=time.monotonic() - START,
                 finished_utc=datetime.now(timezone.utc).isoformat())
    save(OUTPUT / 'result.json', value)
    print(json.dumps({'passed': value['passed'], 'failure_type': value.get('failure_type'),
                      'forbidden_attempts': COUNTS, 'elapsed_seconds': value['elapsed_seconds']}, sort_keys=True))
    return 0 if value['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
