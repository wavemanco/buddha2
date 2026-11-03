"""Exercise public offline commands on retained synthetic outputs, without generation."""

import copy
import json
import subprocess
import sys
from pathlib import Path

from buddha2.artifacts import digest, file_hash, read_json, write_once

ROOT = Path('/workspace')
OUT = Path('/results/phase2-r012')
STUDY = '/results/phase2-r010/frozen-study/study.json'
RUN = '/results/phase2-r010/walkthrough-complete'
BASE = ['--study', STUDY, '--run', RUN]
commands = []


def command(*args):
    invocation = [sys.executable, '-B', '-m', 'buddha2', 'phase2-policy', *args]
    result = subprocess.run(invocation, capture_output=True, text=True, check=False, timeout=180)
    commands.append({'arguments': invocation[3:], 'exit_code': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


old_manifest = read_json(ROOT / 'runs/phase2-r010/walkthrough-execution-complete.json')['files']
before = {p: file_hash(Path(RUN) / p) for p in old_manifest}
assert before == old_manifest
prepared = command('prepare', '--output', str(OUT / 'frozen-study'))
inspected = command('inspect', '--study', str(OUT / 'frozen-study/study.json'))
assert not inspected['live_ready']
cutoff = '2026-10-26T20:00:00Z'
benchmark = command('decide', *BASE, '--track', 'benchmark', '--cutoff', cutoff,
                    '--output', str(OUT / 'benchmark'))
assert benchmark['synthetic_selected_method'] == 'A' and benchmark['selected_method'] is None
parent = str(OUT / 'benchmark/decision.json')
pending = command('decide', *BASE, '--track', 'human-augmented', '--cutoff', cutoff,
                  '--parent', parent, '--output', str(OUT / 'human-pending'))
assert pending['status'] == 'inconclusive' and pending['human_status'] == 'absent'
command('human-packets', *BASE, '--output', str(OUT / 'packets'))
forms = read_json(Path(RUN) / 'human-fixtures.json')
window = {form['reader_id']: {'delivered_at': '2026-10-25T10:00:00Z',
                            'due_date': form['due_date']} for form in forms}
write_once(OUT / 'inputs/window.json', window)
write_once(OUT / 'inputs/empty.json', [])
closed = command('human-import', *BASE, '--cutoff', '2026-10-31T12:00:00Z',
                 '--submissions', str(OUT / 'inputs/empty.json'),
                 '--window', str(OUT / 'inputs/window.json'), '--output', str(OUT / 'human-window-closed'))
assert not closed['complete']
submissions = []
for form in copy.deepcopy(forms):
    for row in form['judgments']:
        if row['unit_id'] in ('unit-01', 'unit-04'):
            row['status'] = 'substantive concern'
            row['reason'] = 'Synthetic scenario only: concern on A; no real reader.'
    submissions.append({'form': form, 'delivered_at': '2026-10-25T10:00:00Z',
                        'first_exposed_at': '2026-10-25T11:00:00Z',
                        'received_at': '2026-11-01T12:00:00Z'})
write_once(OUT / 'inputs/late-submissions.json', submissions)
late = command('human-import', *BASE, '--cutoff', '2026-11-02T12:00:00Z',
               '--submissions', str(OUT / 'inputs/late-submissions.json'),
               '--previous', str(OUT / 'human-window-closed/human-assessment.json'),
               '--output', str(OUT / 'human-late'))
assert late['complete']
human = command('decide', *BASE, '--track', 'human-augmented', '--cutoff', '2026-11-02T13:00:00Z',
                '--parent', parent, '--human-assessment', str(OUT / 'human-late/human-assessment.json'),
                '--output', str(OUT / 'human-decision'))
assert human['synthetic_selected_method'] == 'B' and human['selected_method'] is None
assert human['execution_sha256'] == benchmark['execution_sha256']
assert human['native_assessment_sha256'] == benchmark['native_assessment_sha256']
context = {'task_outputs_sha256': digest('synthetic-future-output-identity'),
           'effective_method_sha256': benchmark['selected_procedure_sha256'],
           'model_settings_sha256': digest('same-model-settings'),
           'budget_policy_sha256': digest('same-budget'),
           'information_access_sha256': digest('score-blind'), 'native_mode': 'agg-k1'}
write_once(OUT / 'inputs/benchmark-context.json', context)
write_once(OUT / 'inputs/human-context.json', context | {
    'effective_method_sha256': human['selected_procedure_sha256']})
compatibility = command('compatibility', '--parent', parent,
                        '--candidate', str(OUT / 'human-decision/decision.json'),
                        '--parent-context', str(OUT / 'inputs/benchmark-context.json'),
                        '--candidate-context', str(OUT / 'inputs/human-context.json'),
                        '--output', str(OUT / 'divergent-continuation'))
assert not compatibility['can_reuse'] and not compatibility['independent_replication']
# Same command, same evidence/cutoff/output: immutable replay succeeds without dispatch.
assert command('decide', *BASE, '--track', 'benchmark', '--cutoff', cutoff,
               '--output', str(OUT / 'benchmark')) == benchmark
assert read_json(Path(parent)) == benchmark
after = {p: file_hash(Path(RUN) / p) for p in old_manifest}
assert before == after
summary = {'kind': 'phase2-policy-offline-demonstration', 'fixture': True,
           'provider_calls': 0, 'generation_requests': 0, 'human_ratings': 0,
           'experiment_api_spend_usd': 0, 'original_folder_accessed': False,
           'prepared_study_sha256': prepared['study_sha256'],
           'historical_study_sha256_unchanged': benchmark['study_sha256'],
           'historical_files_verified_unchanged': len(after),
           'benchmark_synthetic_seed': benchmark['synthetic_selected_method'],
           'human_without_forms': pending['status'],
           'human_with_late_synthetic_concerns': human['synthetic_selected_method'],
           'same_execution_and_native_assessment': True,
           'divergent_continuation': not compatibility['can_reuse'],
           'benchmark_immutable_replay_identical': True,
           'limitations': ['All human forms, dates and future contexts are synthetic scenarios.',
                          'This is software evidence, not a real method performance result.',
                          'Historical native cutoff is an operator-declared snapshot boundary.'],
           'commands': commands}
write_once(OUT / 'demonstration.json', summary)
print(json.dumps({key: value for key, value in summary.items() if key != 'commands'}))
