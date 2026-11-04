"""BD1 unit-only entry; no campaign, grant or provider dispatch."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.phase3b_seq2_v1 import verify
from followups.phase3b_seq2_v1.support import BASE, ROOT, safe

PREFIX = "bd1-unit-preflight-v1"
DEFINITION_SHA = "ada47bc29d12521022e2e3ba93112138049420270d8845534b603ca46b7d6af3"


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run(mode: str, raw: str) -> int:
    if mode not in {"bootstrap", "suite", "windows"}:
        raise ValueError("explicit BD1 unit mode required")
    output = safe(Path(raw))
    allowed = (ROOT / "runs/phase3b-seq2-v1" if mode == "windows" else BASE) / PREFIX
    if not output.is_relative_to(allowed) or output == allowed or not output.is_dir():
        raise ValueError("fresh existing BD1 child output required")
    authority = json.loads((ROOT / "evidence/phase3b-bd1-v1/authority.json").read_text(encoding="utf-8"))
    if authority.get("definition") != "specifications/amendments/phase3b-bootstrap-diagnostic-1.0.md":
        raise ValueError("unexpected BD1 definition path")
    definition = ROOT / "specifications/amendments/phase3b-bootstrap-diagnostic-1.0.md"
    if (authority.get("definition_sha256") != DEFINITION_SHA
            or hashlib.sha256(definition.read_bytes()).hexdigest() != DEFINITION_SHA
            or authority.get("aggregate_focused_engineering_limit_seconds") != 7200
            or authority.get("real_API_cap_usd") != 0 or authority.get("frozen_control_edits_authorized") is not False):
        raise ValueError("BD1 direct authority differs")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest["mode"] != mode:
        raise ValueError("BD1 admitted mode differs")
    for name, expected in manifest["files"].items():
        relative = Path(name)
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise ValueError("nonrelative BD1 source input")
        target = safe(ROOT / relative, roots=(ROOT,))
        if not target.is_file():
            raise ValueError("BD1 source input is not ordinary")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("BD1 reviewed source changed")
    os.environ["BUDDHA2_BD1_OUTPUT"] = str(output)
    verify.save(output / "context.json", {"entry_module": "__main__",
        "entry_file": sys.modules["__main__"].__file__, "executable": sys.executable,
        "cwd": str(Path.cwd()), "pythonpath": os.environ.get("PYTHONPATH"),
        "argv": sys.argv, "mode": mode, "production_unit_runner": "verify.run_tests",
        "importtime_option_enabled": sys._xoptions.get("importtime") is True,
        "campaign_prepare_omitted": True, "actual_spawn_collector_unchanged": True})
    # Discover every production module before selecting the historical prefix;
    # this retains the same discovery/import ordering as verify.run_tests.
    suite = unittest.defaultTestLoader.discover(str(ROOT / "followups/phase3b_seq2_v1"),
                                               pattern="test*.py", top_level_dir=str(ROOT))
    cases = list(flatten(suite))
    ids = [case.id() for case in cases]
    if ids != manifest["discovered_ids"]:
        raise ValueError("actual unit discovery differs from prospective inventory")
    verify.save(output / "discovered.json", {"ids": ids, "count": len(ids)})
    if mode == "suite":
        passed = verify.run_tests(output, manifest["unit_bindings"])
        result = json.loads((output / "tests.json").read_text(encoding="utf-8"))
    else:
        selected = manifest["selected_ids"]
        chosen = [case for case in cases if case.id() in selected]
        if [case.id() for case in chosen] != selected:
            raise ValueError("ordered target inventory differs")
        log = io.StringIO()
        with patch("sys.stdout", log), patch("sys.stderr", log):
            tested = unittest.TextTestRunner(stream=log, verbosity=2, failfast=True).run(unittest.TestSuite(chosen))
        (output / "tests.log").write_text(log.getvalue(), encoding="utf-8", newline="\n")
        passed = tested.wasSuccessful()
        result = {"passed": passed, "tests": tested.testsRun, "failures": len(tested.failures),
                  "errors": len(tested.errors), "skipped_test_ids": [case.id() for case, _ in tested.skipped]}
        verify.save(output / "tests.json", result)
    started = re.findall(r"^\w+ \(([^)]+)\) \.\.\.", (output / "tests.log").read_text(encoding="utf-8"), re.MULTILINE)
    expected = manifest["selected_ids"]
    if len(started) != result["tests"] or started != expected[:len(started)]:
        raise ValueError("unit result inventory cannot reconcile")
    verify.save(output / "result.json", {"kind": "phase3b-bd1-unit-preflight-v1", "unit_only": True,
        "mode": mode, **result, "started_ids": started, "unrun_ids": expected[len(started):],
        "declared_ids": expected, "source_sha256": manifest["source_sha256"],
        "fixture_mock_activity_permitted": True, "real_provider_calls": 0,
        "release_acceptance_claimed": False})
    return 0 if passed else 1
