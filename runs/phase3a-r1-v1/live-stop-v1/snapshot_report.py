"""Report the held R1 dataset twice; never construct SDK clients or resume work."""
import hashlib
import json
import stat
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/workspace')
BASE = Path('/results/phase3a-r1-v1')
RELEASE = BASE / 'release-v1'
RETAINED = Path('/retained-release')
INPUT = Path('/retained-run')
OUT = Path('/export')
TARGET = BASE / 'live-stop-v1'
SKIP = {'credential-binding.json', '.writer.lock'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        assert path.read_bytes() == raw
    else:
        with path.open('xb') as stream:
            stream.write(raw)


def cp(source, target):
    assert source.name not in SKIP and stat.S_ISREG(source.lstat().st_mode) and not source.is_symlink()
    raw = source.read_bytes()
    value = hashlib.sha256(raw).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(raw)
    assert sha(source) == sha(target) == value
    return value


study = read(RETAINED / 'study.json')
assert study['study_sha256'] == '44d12d6ff196a9481bd6106541ad62d8161fff50fa7a1fd6eef899df4f627012'
run = BASE / study['study_sha256'] / 'live'
inputs, excluded = {}, []
for name in ('study.json', 'live-grant.json'):
    inputs['release/' + name] = cp(RETAINED / name, RELEASE / name)
for directory in ('seed', 'source'):
    for path in sorted((RETAINED / directory).rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            name = path.relative_to(RETAINED).as_posix()
            inputs['release/' + name] = cp(path, RELEASE / name)
for path in sorted(INPUT.rglob('*')):
    name = path.relative_to(INPUT).as_posix()
    # Exclude private bindings and locks by name before stat/read/copy/hash.
    if path.name in SKIP:
        excluded.append(name)
        continue
    assert path.name not in {'.env', 'credentials.json', 'auth.json'}
    mode = path.lstat().st_mode
    assert stat.S_ISREG(mode) or stat.S_ISDIR(mode)
    if stat.S_ISREG(mode):
        inputs['run/' + name] = cp(path, run / name)
claim = ROOT / 'runs/phase3a-r1-v1/live-study.json'
inputs['scope/live-study.json'] = cp(claim, BASE / 'live-study.json')
assert len(study['source']['files']) == 149
assert all(sha(ROOT / name) == sha(RELEASE / 'source' / name) == value
           for name, value in study['source']['files'].items())

from followups.phase3a_v1 import workflow

attempts = []


def forbidden(*args, **kwargs):
    attempts.append('blocked')
    raise AssertionError('Held evidence reporting forbids SDK construction and socket connections')


summaries = []
with ExitStack() as stack:
    for name in ('anthropic.Anthropic', 'anthropic.AsyncAnthropic', 'openai.OpenAI', 'openai.AsyncOpenAI',
                 'socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
        stack.enter_context(patch(name, side_effect=forbidden))
    for directory in ('report', 'replay'):
        value = workflow.report(RELEASE / 'study.json', RELEASE / 'live-grant.json', TARGET / directory, False,
                                cutoff='2026-10-29T04:22:06Z')
        assert value['attempts'] == value['provider_calls'] == 91
        assert value['spent_micro_usd'] == 1401860 and value['reserved_micro_usd'] == 11440000
        assert value['primary_scored'] == 0 and value['complete_primary'] is False
        assert value['status'] == 'incomplete' and value['authentic_live_path'] is False
        assert value['journal_status'] != 'ready'
        assert value['prior_real_phase3a_spent_micro_usd'] == 1293437
        summaries.append({k: v for k, v in value.items() if k != 'report_output'})
assert not attempts and summaries[0] == summaries[1]
names = ('rows.json', 'coverage.json', 'analysis.json', 'summary.json', 'accounting.json', 'protocol.json', 'PHASE3A_REPORT.md')
outputs = {}
for name in names:
    assert (TARGET / 'report' / name).read_bytes() == (TARGET / 'replay' / name).read_bytes()
    for directory in ('report', 'replay'):
        outputs[directory + '/' + name] = cp(TARGET / directory / name, OUT / directory / name)
assert all(sha(INPUT / name[4:]) == value for name, value in inputs.items() if name.startswith('run/'))
assert all(sha(ROOT / name) == value for name, value in study['source']['files'].items())
assert sha(claim) == inputs['scope/live-study.json']
put(OUT / 'raw-inputs.json', {'kind': 'phase3a-r1-live-stop-input-inventory-v1',
    **{k: study[k] for k in ('study_sha256', 'source_sha256', 'policy_sha256', 'runtime_sha256', 'launcher_sha256')},
    'files': inputs, 'excluded_before_reading': excluded, 'canonical_run': str(run),
    'original_inputs_preserved': True})
put(OUT / 'replay-proof.json', {'kind': 'phase3a-r1-live-stop-report-replay-v1', 'passed': True,
    **{k: study[k] for k in ('study_sha256', 'source_sha256', 'policy_sha256', 'runtime_sha256', 'launcher_sha256')},
    'fixture': False, 'saved_intents': 91, 'saved_known_requests': 90, 'saved_unknown_requests': 1,
    'report_cutoff': '2026-10-29T04:22:06Z',
    'saved_spent_micro_usd': 1401860, 'saved_reserved_micro_usd': 11440000,
    'reporting_provider_calls': 0, 'SDK_or_socket_attempts': 0, 'real_credentials_read': False,
    'original_inputs_preserved': True, 'same_absolute_results_paths': True, 'input_files': len(inputs),
    'report_files_byte_equal': 7, 'output_sha256': outputs,
    'limitation': 'Read-only reporting of a held uncertain dataset. No resend, resume, liability release, repair or repetition.'})
print(json.dumps({'passed': True, 'inputs': len(inputs), 'report_files_byte_equal': 7,
                  'saved_intents': 91, 'saved_known_requests': 90, 'saved_unknown_requests': 1,
                  'reporting_calls': 0, 'SDK_or_socket_attempts': 0}))
