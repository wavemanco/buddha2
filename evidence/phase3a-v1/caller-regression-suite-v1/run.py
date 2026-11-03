"""Isolated candidate regression; no live release, clients, keys or source edits."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.phase3a_v1 import accounting
from followups.phase3a_v1.mocks import SDKMock
from followups.phase3a_v1.tests.test_editor_attacks import AttackMock

ROOT = Path('/workspace')
OUT = Path('/export')
DATA = ROOT / 'evidence/phase3a-v1/caller-regression-v1'
proof = json.loads((DATA / 'proof.json').read_text(encoding='utf-8'))
candidate_text = (DATA / 'candidate-accounting-function.py').read_text(encoding='utf-8')
assert hashlib.sha256(candidate_text.encode()).hexdigest() == proof['candidate_function_sha256']
namespace = dict(accounting.__dict__)
exec(compile(candidate_text, 'candidate-accounting-function.py', 'exec'), namespace)
candidate = namespace['_editor_request']
study = json.loads((ROOT / 'runs/phase3a-v1/release-v3/study.json').read_text(encoding='utf-8'))


def source_exact():
    return all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
               for name, value in study['source']['files'].items())


def inject_caller(original):
    def handle(self, request, *, http_module):
        response = original(self, request, http_module=http_module)
        if not self.records or self.records[-1]['role'] != 'editor':
            return response
        payload = response.json()
        for block in payload.get('content', []):
            if block.get('type') == 'tool_use':
                block['caller'] = {'type': 'direct'}
        self.records[-1]['response'] = copy.deepcopy(payload)
        return http_module.Response(response.status_code, json=payload,
                                    headers={'request-id': 'fixture-caller-regression-suite'})
    return handle


assert source_exact()
modules = [
    'followups.phase3a_v1.tests.test_accounting',
    'followups.phase3a_v1.tests.test_editor',
    'followups.phase3a_v1.tests.test_editor_attacks',
    'followups.phase3a_v1.tests.test_editor_shape',
]
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
with (OUT / 'tests.log').open('x', encoding='utf-8', buffering=1) as stream:
    with patch.object(accounting, '_editor_request', candidate), \
         patch.object(SDKMock, '_handle', inject_caller(SDKMock._handle)), \
         patch.object(AttackMock, '_handle', inject_caller(AttackMock._handle)):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
assert source_exact(), 'frozen production source changed'
record = {
    'kind': 'phase3a-isolated-candidate-regression-suite-v1',
    'passed': result.wasSuccessful(),
    'fixture': True,
    'candidate_function_sha256': proof['candidate_function_sha256'],
    'candidate_applied_only_in_isolated_test_process': True,
    'frozen_production_source_142_unchanged': True,
    'SDK_mocks_inject_direct_caller_into_editor_tool_responses': True,
    'real_provider_calls': 0,
    'real_credentials_read': False,
    'tests_run': result.testsRun,
    'skipped': len(result.skipped),
    'failures': len(result.failures),
    'errors': len(result.errors),
    'modules': modules,
    'limitation': 'Validator and editor regressions only; not a frozen R1 release gate or live effectiveness test.',
}
with (OUT / 'proof.json').open('x', encoding='utf-8') as stream:
    stream.write(json.dumps(record, sort_keys=True, indent=2) + '\n')
print(json.dumps(record))
raise SystemExit(0 if result.wasSuccessful() else 1)
