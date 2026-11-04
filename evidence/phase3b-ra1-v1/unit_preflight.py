"""RA1 unit-only entry; no campaign, grant or provider dispatch."""
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
from followups.phase3b_seq2_v1.support import BASE, ROOT, read, release_authority, safe

PREFIX = "ra1-unit-preflight-v1"
DEFINITION_SHA = "377b6dfdf4b3192a834f5fedfc0df7400f5f27128012ac6a245ef1b00925027d"


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run(mode: str, raw: str) -> int:
    if mode not in {"suite", "windows"}:
        raise ValueError("explicit RA1 unit mode required")
    release_authority()
    output = safe(Path(raw))
    allowed = (ROOT / "runs/phase3b-seq2-v1" if mode == "windows" else BASE) / PREFIX
    if output.parent != allowed or output.name not in {f"{mode}-{n}" for n in (1, 2, 3)} or not output.is_dir():
        raise ValueError("fresh existing RA1 child output required")
    authority = json.loads((ROOT / "evidence/phase3b-ra1-v1/authority.json").read_text(encoding="utf-8"))
    if authority.get("definition") != "specifications/amendments/phase3b-release-acceptance-1.0.md":
        raise ValueError("unexpected RA1 definition path")
    definition = ROOT / "specifications/amendments/phase3b-release-acceptance-1.0.md"
    if (authority.get("definition_sha256") != DEFINITION_SHA
            or hashlib.sha256(definition.read_bytes()).hexdigest() != DEFINITION_SHA
            or authority.get("aggregate_focused_engineering_target_seconds") != 14400
            or authority.get("real_API_cap_usd") != 0 or authority.get("frozen_control_edits_authorized") is not False):
        raise ValueError("RA1 direct authority differs")
    manifest = read(output / "manifest.json")
    if manifest["mode"] != mode:
        raise ValueError("RA1 admitted mode differs")
    manifest_sha = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    admission = read(ROOT / "evidence/phase3b-ra1-v1/preflight-admissions" / (output.name + ".json"))
    review = read(ROOT / "runs/phase3b-seq2-v1" / PREFIX / output.name / "prospective-review.json")
    if (admission.get("mode") != mode or admission.get("manifest_sha256") != manifest_sha
            or admission.get("source_sha256") != manifest["source_sha256"]
            or admission.get("preflight_set_counted_at_Linux_admission") is not True
            or review.get("passed") is not True or review.get("reviewer") != "/root/ra1_path_review"
            or review.get("manifest_sha256") != manifest_sha):
        raise ValueError("actual RA1 preflight admission/review does not bind this invocation")
    for name, expected in manifest["files"].items():
        relative = Path(name)
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise ValueError("nonrelative RA1 source input")
        target = safe(ROOT / relative, roots=(ROOT,))
        if not target.is_file():
            raise ValueError("RA1 source input is not ordinary")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("RA1 reviewed source changed")
    os.environ["BUDDHA2_RA1_OUTPUT"] = str(output)
    verify.save(output / "context.json", {"entry_module": "__main__",
        "entry_file": sys.modules["__main__"].__file__, "executable": sys.executable,
        "cwd": str(Path.cwd()), "pythonpath": os.environ.get("PYTHONPATH"),
        "argv": sys.argv, "mode": mode, "production_unit_runner": "verify.run_tests",
        "importtime_option_enabled": sys._xoptions.get("importtime") is True,
        "campaign_prepare_omitted": True, "actual_spawn_collector_unchanged": True})
    # Discover the complete production inventory with unchanged import ordering.
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
    verify.save(output / "result.json", {"kind": "phase3b-ra1-unit-preflight-v1", "unit_only": True,
        "mode": mode, **result, "started_ids": started, "unrun_ids": expected[len(started):],
        "declared_ids": expected, "source_sha256": manifest["source_sha256"],
        "fixture_mock_activity_permitted": True, "real_provider_calls": 0,
        "release_acceptance_claimed": False})
    return 0 if passed else 1
