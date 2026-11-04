"""Cold import and spawned-worker dotenv denial without filesystem probing."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

from . import core_view

ROOT = Path(__file__).resolve().parents[2]


def bootstrap_observation(result):
    """Retain typed fixture diagnostics after the real collector has stopped."""
    observed: dict[str, object] = {}
    for key in ('canonical_status', 'report_status', 'visibility_status', 'report_variant',
                'canonical_error_type', 'projection_error_type', 'report_error_type', 'held_report_error_type',
                'cleanup_proof'):
        if key in result:
            value = result[key]
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', value):
                raise ValueError('invalid bounded bootstrap diagnostic field')
            observed[key] = value
    for key in ('worker_stopped', 'financial_state_validated', 'reports_published'):
        if key in result:
            if type(result[key]) is not bool:
                raise ValueError('invalid boolean bootstrap diagnostic field')
            observed[key] = result[key]
    summary = result.get('summary')
    if isinstance(summary, dict) and isinstance(summary.get('import_privacy'), dict):
        privacy = summary['import_privacy']
        privacy_observed: dict[str, int | bool] = {}
        observed['import_privacy'] = privacy_observed
        for key in ('dotenv_open_denials', 'harness2_config_imported'):
            if key in privacy:
                value = privacy[key]
                if (key == 'dotenv_open_denials' and (type(value) is not int or value < 0)
                        or key == 'harness2_config_imported' and type(value) is not bool):
                    raise ValueError('invalid import-privacy diagnostic field')
                privacy_observed[key] = value
    return observed


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_pins_actual_core_and_forwards_the_named_supervisor(self):
        bootstrap = (ROOT / "phase3b-seq2.ps1").read_text(encoding="utf-8")
        core = ROOT / "phase3b-seq2-core.ps1"
        match = re.search(r"\(Get-HISHA256 \$core\) -cne '([0-9a-f]{64})'", bootstrap)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1) if match else None, hashlib.sha256(core.read_bytes()).hexdigest())
        self.assertIn("@('-SupervisorAgent', $SupervisorAgent)", bootstrap)
        self.assertIn("@('--supervisor-agent', $SupervisorAgent)", core.read_text(encoding="utf-8"))

    def cold(self, *, no_harness=False):
        source = """
import importlib, io, json, os, sys
from pathlib import Path
lower = io.open
private_io = []
def boundary(file, *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)):
        parts = os.fsdecode(os.fspath(file)).replace(chr(92), '/').split('/')
        if any(p.casefold() == '.env' for p in parts):
            private_io.append(True)
            raise AssertionError('private lower IO reached')
    return lower(file, *args, **kwargs)
io.open = boundary
if NO_HARNESS:
    sys.path = [p for p in sys.path if '.upstream/harness2' not in p.replace(chr(92), '/')]
module = importlib.import_module('followups.phase3b_seq2_v1')
assert io.open is boundary
original_import = module.importlib.import_module
def fail_import(name):
    raise RuntimeError('SYNTHETIC IMPORT FAILURE')
module.importlib.import_module = fail_import
try:
    try:
        module._import_config()
    except RuntimeError:
        pass
finally:
    module.importlib.import_module = original_import
assert io.open is boundary
assert not private_io
if not NO_HARNESS:
    config = importlib.import_module('harness2.config')
    assert Path(config.__file__) == Path(__ROOT_LITERAL__) / '.upstream/harness2/harness2/config.py'
print(json.dumps({'telemetry': module.IMPORT_PRIVACY, 'private_actual_io': len(private_io), 'open_restored': True}))
""".replace("NO_HARNESS", repr(no_harness)).replace("__ROOT_LITERAL__", repr(ROOT.as_posix()))
        environment = {name: value for name, value in os.environ.items()
                       if name in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, "-B", "-c", source], cwd=ROOT, env=environment,
                                capture_output=True, text=True, check=False, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_cold_parent_import_denies_dotenv_before_lower_io_and_restores_open(self):
        result = self.cold()
        self.assertEqual(result['private_actual_io'], 0)
        self.assertTrue(result['open_restored'])
        self.assertEqual(result['telemetry']['dotenv_open_denials'], 1)
        self.assertTrue(result['telemetry']['harness2_config_imported'])

    def test_export_only_import_without_harness2_restores_open(self):
        result = self.cold(no_harness=True)
        self.assertEqual(result['telemetry']['dotenv_open_denials'], 0)
        self.assertFalse(result['telemetry']['harness2_config_imported'])

    def test_fresh_spawned_core_worker_uses_the_same_import_boundary(self):
        spec = {'bindings': dict.fromkeys(core_view.BINDINGS, 'a' * 64), 'checkpoint': 'closure', 'fixture': True}
        result = core_view.collect(spec, deadline=time.monotonic() + 4, cleanup=1, behavior='bootstrap')
        observed = bootstrap_observation(result)
        destination = os.environ.get('BUDDHA2_BD1_OUTPUT')
        if destination:
            from .support import BASE, safe
            target = safe(Path(destination))
            if not target.is_relative_to(BASE / 'bd1-unit-preflight-v1') or not target.is_dir():
                raise ValueError('BD1 diagnostic output escaped its existing namespace')
            with (target / 'bootstrap-result.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(observed, stream, sort_keys=True, indent=2)
                stream.write('\n')
        release_destination = os.environ.get('BUDDHA2_RA1_OUTPUT')
        if release_destination:
            from .support import bootstrap_capture_path
            target = bootstrap_capture_path(release_destination)
            with (target / 'bootstrap-result.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(observed, stream, sort_keys=True, indent=2)
                stream.write('\n')
        message = json.dumps(observed, sort_keys=True)
        self.assertTrue(result['worker_stopped'], message)
        self.assertEqual(result['canonical_status'], 'complete', message)
        self.assertEqual(result['summary']['import_privacy']['dotenv_open_denials'], 1, message)
