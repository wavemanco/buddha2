"""Preserve the uncertain R1 stop; stdlib only, no keys, SDKs or dispatch."""
import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path('/workspace')
BASE = Path('/results/phase3a-r1-v1')
STUDY = '44d12d6ff196a9481bd6106541ad62d8161fff50fa7a1fd6eef899df4f627012'
RELEASE = BASE / 'release-v1'
RUN = BASE / STUDY / 'live'
REPORT = BASE / 'live-stop-v1'
OUT = ROOT / 'evidence/phase3a-r1-v1/live-stop-v1'
SKIP = {'credential-binding.json', '.writer.lock'}
BANNED = SKIP | {'.env', 'credentials.json', 'auth.json'}
NAMES = ('rows.json', 'coverage.json', 'analysis.json', 'summary.json', 'accounting.json', 'protocol.json', 'PHASE3A_REPORT.md')
KEY = re.compile(rb'(?<![A-Za-z0-9_-])(?:sk-ant-[A-Za-z0-9_-]{24,}|sk-proj-[A-Za-z0-9_-]{24,}|sk-[A-Za-z0-9_-]{40,})')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path):
    assert path.is_absolute() and '..' not in path.parts and path.name not in BANNED
    assert (path.is_relative_to(ROOT) or path.is_relative_to('/results'))
    assert not any(p.is_symlink() for p in (path, *path.parents))
    assert stat.S_ISREG(path.lstat().st_mode)
    return path


def blob(path):
    return checked(path).read_bytes()


def read(path):
    return json.loads(blob(path).decode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    study, grant = read(RELEASE / 'study.json'), read(RELEASE / 'live-grant.json')
    assert study['study_sha256'] == STUDY == digest({k: v for k, v in study.items() if k != 'study_sha256'})
    assert len(study['source']['files']) == 149 and study['source_sha256'] == digest(study['source']['files'])
    assert grant['fixture'] is False and grant['study_sha256'] == STUDY
    assert grant['grant_sha256'] == digest({k: v for k, v in grant.items() if k != 'grant_sha256'})
    blobs, paths = {}, {}

    def add(path, expected=None):
        raw = blob(path)
        name = ('runs/' + path.relative_to('/results').as_posix() if path.is_relative_to('/results')
                else path.relative_to(ROOT).as_posix())
        assert expected is None or sha(raw) == expected
        assert KEY.search(raw) is None, 'possible credential token; file only: ' + name
        assert name not in blobs or blobs[name] == raw
        blobs[name], paths[name] = raw, path

    for name, value in study['source']['files'].items():
        add(ROOT / name, value)
        add(RELEASE / 'source' / name, value)
    for path in sorted((RELEASE / 'seed').rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            add(path)
    for name in ('study.json', 'live-grant.json', 'readiness.json'):
        add(RELEASE / name)
    add(BASE / 'live-study.json')
    claim = read(BASE / 'live-study.json')
    assert all(claim[k] == study[k] for k in ('study_sha256', 'source_sha256', 'policy_sha256', 'runtime_sha256', 'launcher_sha256'))
    assert claim['grant_sha256'] == grant['grant_sha256']
    excluded, raw_files = [], {}
    for path in sorted(RUN.rglob('*')):
        # Never stat/read/hash/copy private credential bindings or lock contents.
        if path.name in SKIP:
            excluded.append(path.relative_to(RUN).as_posix())
            continue
        mode = path.lstat().st_mode
        assert stat.S_ISDIR(mode) or stat.S_ISREG(mode)
        if stat.S_ISREG(mode):
            add(path)
            raw = blob(path)
            raw_files[path.relative_to(RUN).as_posix()] = {'sha256': sha(raw), 'bytes': len(raw)}
    assert set(excluded) == {'credential-binding.json', 'journal/.writer.lock', 'launch-owner/.writer.lock', 'owner/.writer.lock'}
    journal = blob(RUN / 'journal/events.jsonl')
    assert journal.endswith(b'\n')
    events = [json.loads(line) for line in journal.splitlines()]
    assert len(events) == 182
    previous, intents, results = None, {}, {}
    for index, event in enumerate(events, 1):
        assert event['index'] == index and event['previous_event_sha256'] == previous
        assert event['event_sha256'] == digest({k: v for k, v in event.items() if k != 'event_sha256'})
        previous = event['event_sha256']
        record = event['record']
        assert record['study_sha256'] == STUDY and record['fixture'] is False
        slot = record['slot_id']
        if event['kind'] == 'intent':
            assert slot not in intents and record['request_sha256'] == digest(record['request'])
            intents[slot] = record
        else:
            assert event['kind'] == 'result' and slot in intents and slot not in results
            assert record['intent_sha256'] == digest(intents[slot])
            results[slot] = record
    known = [r for r in results.values() if r['status'] == 'response']
    unknown = [r for r in results.values() if r['status'] != 'response']
    assert len(intents) == len(results) == 91 and len(known) == 90 and len(unknown) == 1
    assert sum(r['spent_micro_usd'] for r in known) == 1401860
    assert sum(r['reserved_micro_usd'] for r in results.values()) == 11440000
    cost = read(OUT / 'cost-audit.json')
    assert cost['passed'] is True and cost['study_sha256'] == STUDY
    assert cost['journal_sha256'] == sha(journal) and cost['known_requests'] == 90
    assert cost['attempts'] == 91 and cost['spent_micro_usd'] == 1401860
    assert cost['unknown'] == 1 and cost['reserved_micro_usd'] == 11440000
    assert cost['cumulative_known_micro_usd'] == 2695297 and cost['cumulative_known_plus_liability_micro_usd'] == 14135297
    for name in NAMES:
        assert blob(REPORT / 'report' / name) == blob(REPORT / 'replay' / name)
        add(REPORT / 'report' / name)
        add(REPORT / 'replay' / name)
    for name in ('raw-inputs.json', 'replay-proof.json', 'snapshot_report.py', 'snapshot-report.log', 'archive_helper.py'):
        add(REPORT / name)
    proof = read(REPORT / 'replay-proof.json')
    assert proof['passed'] is True and proof['report_files_byte_equal'] == 7
    assert proof['SDK_or_socket_attempts'] == proof['reporting_provider_calls'] == 0
    assert proof['original_inputs_preserved'] is proof['same_absolute_results_paths'] is True
    for name in ('audit.py', 'cost-audit.json', 'prior-report-preservation.json'):
        add(OUT / name)
    assert len(read(OUT / 'prior-report-preservation.json')['reports_unchanged']) == 16
    add(ROOT / 'PHASE3A_R1_LIVE_INTERRUPTION_REPORT.md')
    prefix = BASE / 'launcher/438a0c6f769e4431960bcba2cd8a7ed5'
    for suffix in ('.preflight-container.json', '.preflight.json', '.inspection-draft.json', '.inspection.json', '.result.json'):
        add(Path(str(prefix) + suffix))
    host = read(Path(str(prefix) + '.result.json'))
    assert host['exit_code'] == 0 and host['action'] == 'provider' and host['stream_content_retained'] is False
    offline = ROOT / 'evidence/phase3a-r1-v1/offline-execution-kit-v2.zip'
    offline_manifest = ROOT / 'evidence/phase3a-r1-v1/offline-execution-kit-v2.manifest.json'
    add(offline_manifest)
    assert read(offline_manifest)['archive_sha256'] == sha(blob(offline)) == '2e36cab2b32b3c677adc07de1fd1145951826cfb3ff75d9323ad53ab109a2604'
    if not args.seal:
        print(json.dumps({'checked_only': True, 'members': len(blobs), 'raw_files': len(raw_files), 'source_files': 149}))
        return
    archive = OUT / 'archive.zip'
    assert not archive.exists(), 'archive already sealed'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, raw in sorted(blobs.items()):
            bundle.writestr(name, raw)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(set(bundle.namelist())) == len(blobs)
        assert set(bundle.namelist()) == set(blobs)
        assert all(bundle.read(name) == raw for name, raw in blobs.items())
    assert all(blob(paths[name]) == raw for name, raw in blobs.items())
    manifest = {'kind': 'phase3a-r1-live-stop-archive-v1', 'passed': True, 'fixture': False,
        **{k: study[k] for k in ('study_sha256', 'source_sha256', 'policy_sha256', 'runtime_sha256', 'launcher_sha256')},
        'source_commit': '35651b7', 'grant_sha256': grant['grant_sha256'],
        'archive_sha256': sha(blob(archive)), 'archive_bytes': archive.stat().st_size,
        'member_count': len(blobs), 'member_sha256': {n: sha(v) for n, v in sorted(blobs.items())},
        'raw_file_count': len(raw_files), 'raw_files': raw_files,
        'excluded_names_without_reading_contents': excluded, 'source_logical_files': 149,
        'cost_audit_sha256': sha(blob(OUT / 'cost-audit.json')), 'event_count': 182, 'attempts': 91,
        'known_requests': 90, 'unknown': 1, 'pending': 0, 'spent_micro_usd': 1401860,
        'reserved_micro_usd': 11440000, 'reservation_is_confirmed_spend': False,
        'prior_known_requests': 86, 'prior_spent_micro_usd': 1293437,
        'cumulative_known_micro_usd': 2695297, 'cumulative_known_plus_liability_micro_usd': 14135297,
        'global_halt': True, 'unknown_cause': cost['unknown_cause'], 'scientific_phase_complete': False,
        'primary_scores': 0, 'native_assessments': 0, 'report_replay_files_equal': 7,
        'CRC_and_all_member_SHA256_verified': True, 'inputs_byte_preserved': True,
        'real_credential_contents_read': False, 'new_provider_calls': 0, 'SDK_constructions': 0,
        'original_folder_accessed': False, 'archive_grants_no_new_requests': True,
        'offline_kit_reference': {'path': offline.relative_to(ROOT).as_posix(), 'sha256': sha(blob(offline)), 'embedded_again': False},
        'host_wall_time': {k: host[k] for k in ('started_at_utc', 'finished_at_utc', 'elapsed_wall_seconds', 'wall_time_basis')}}
    target = OUT / 'manifest.json'
    with target.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    closeout = {'kind': 'phase3a-r1-live-stop-closeout-v1', 'status': 'closed-with-unknown-liability',
        **{k: study[k] for k in ('study_sha256', 'source_sha256', 'policy_sha256', 'runtime_sha256', 'launcher_sha256')},
        'attempts': 91, 'known_requests': 90, 'unknown': 1, 'spent_micro_usd': 1401860,
        'reserved_micro_usd': 11440000, 'reservation_is_confirmed_spend': False,
        'prior_known_requests': 86, 'prior_spent_micro_usd': 1293437,
        'cumulative_known_micro_usd': 2695297, 'cumulative_known_plus_liability_micro_usd': 14135297,
        'primary_scores': 0, 'scientific_phase_complete': False, 'global_halt_preserved': True,
        'unknown_cause': cost['unknown_cause'], 'source_files_verified': 149, 'raw_files_verified': len(raw_files),
        'report_replay_files_equal': 7, 'provider_calls_during_closeout': 0, 'SDK_constructions_during_closeout': 0,
        'real_credentials_read_during_closeout': False, 'original_folder_accessed': False,
        'archive_grants_no_new_requests': True,
        'artifacts_sha256': {
            'archive.zip': sha(blob(archive)), 'manifest.json': sha(blob(target)),
            'audit.py': sha(blob(OUT / 'audit.py')), 'cost-audit.json': sha(blob(OUT / 'cost-audit.json')),
            'prior-report-preservation.json': sha(blob(OUT / 'prior-report-preservation.json')),
            'PHASE3A_R1_LIVE_INTERRUPTION_REPORT.md': sha(blob(ROOT / 'PHASE3A_R1_LIVE_INTERRUPTION_REPORT.md')),
            'raw-inputs.json': sha(blob(REPORT / 'raw-inputs.json')),
            'replay-proof.json': sha(blob(REPORT / 'replay-proof.json'))},
        'limitations': ['No external assessment or adaptive-versus-fixed conclusion.',
                        'Unknown delivery/charge remains unresolved and must not be retried or cleared.',
                        'The archive is preservation evidence, not authority for a repetition.']}
    with (OUT / 'closeout.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(closeout, sort_keys=True, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'members': len(blobs), 'raw_files': len(raw_files),
                      'archive_sha256': manifest['archive_sha256'], 'manifest_sha256': sha(blob(target)),
                      'closeout_sha256': sha(blob(OUT / 'closeout.json')),
                      'new_provider_calls': 0, 'SDK_constructions': 0}))


if __name__ == '__main__':
    main()
