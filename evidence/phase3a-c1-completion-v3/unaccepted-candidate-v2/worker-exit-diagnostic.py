"""Offline actual-SDK reproduction; no production source mutation or real keys."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

from followups.phase3a_c1_completion_v3 import worker
from followups.phase3a_c1_completion_v3.deadline import KnownDeadlineStop
from followups.phase3a_c1_completion_v3.tests.test_deadline import bind, fixture_transport
from followups.phase3a_v1 import accounting as core

ROOT = Path('/workspace')
OUTPUT = Path('/results/phase3a-c1-completion-v3/worker-exit-diagnostic-v1')
SOURCE = Path('/results/phase3a-c1-completion-v3/verification-v2/source-before.json')
REAL_MAIN = worker.main


def delayed_worker_main(connection, behavior):
    REAL_MAIN(connection, behavior)
    time.sleep(0.6)


def current_hashes(expected):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in expected}


def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    before = current_hashes(source['files'])
    assert before == source['files']
    transport = fixture_transport()
    try:
        with patch.object(worker, 'main', delayed_worker_main):
            intent, allocation, body = bind(transport)
            response = transport.create('plan', body)
        result = core._result(intent, response)
        audit = transport.commit(intent['slot_id'], result)
        stopped = False
        try:
            bind(transport)
        except KnownDeadlineStop:
            stopped = True
        after = current_hashes(source['files'])
        assert before == after
        assert result['status'] == 'response' and audit['sdk_invoked'] is True
        assert audit['parent_capture_monotonic'] <= allocation.deadline_monotonic
        assert audit['late_known'] is False and audit['cleanup_failed'] is True
        assert audit['worker_stopped'] is True and audit['owner_stop_required'] is False
        assert stopped and len(transport.fixture_records) == 1
        proof = {'kind': 'phase3a-r2-delayed-worker-exit-diagnostic-v1', 'passed': True,
            'source_sha256': source['sha256'], 'source_files': len(before),
            'source_before_after_exact': True, 'fixture': True, 'real_provider_calls': 0,
            'policy': audit['budget']['policy'], 'post_worker_main_exit_delay_seconds': .6,
            'one_actual_sdk_mock_http_request': len(transport.fixture_records),
            'result_status': result['status'], 'terminal_reserved_micro_usd': result['reserved_micro_usd'],
            'known_cleanup_stop_reproduced': stopped, 'audit': audit,
            'interpretation': 'Timely known receipt followed by 0.6s process exit delay is force-terminated by the current 0.3s join and classified cleanup_failed, despite the unchanged 60s cleanup allowance.'}
        (OUTPUT / 'result.json').write_text(json.dumps(proof, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({k: proof[k] for k in ('passed', 'source_sha256', 'source_files',
            'one_actual_sdk_mock_http_request', 'known_cleanup_stop_reproduced')}, sort_keys=True))
        print(json.dumps({k: audit[k] for k in ('parent_capture_monotonic', 'cleanup_elapsed_seconds',
            'cleanup_failed', 'worker_stopped', 'owner_stop_required', 'elapsed_seconds')}, sort_keys=True))
    finally:
        transport.close()


if __name__ == '__main__':
    main()