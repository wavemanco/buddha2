"""Cold import and spawned-worker dotenv denial without filesystem probing."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from . import core_view

ROOT = Path(__file__).resolve().parents[2]


class BootstrapTests(unittest.TestCase):
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
module = importlib.import_module('followups.phase3a_h1_integrated_v1')
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
        self.assertTrue(result['worker_stopped'])
        self.assertEqual(result['canonical_status'], 'complete')
        self.assertEqual(result['summary']['import_privacy']['dotenv_open_denials'], 1)
