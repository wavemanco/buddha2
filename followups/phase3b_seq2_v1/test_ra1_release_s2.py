"""RA1 admission, authority, capture and packet binding regressions; pure fixtures."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import support
from .support import BASE, ROOT


class RA1ReleaseTests(unittest.TestCase):
    def test_current_authority_rejects_changed_scope_and_retains_target_semantics(self):
        original = support.read
        actual = support.release_authority()
        self.assertFalse(actual["target_is_hard_abort"])
        for field, bad in (("real_API_cap_usd", 1), ("max_candidates", 3),
                           ("keys_authorized", True), ("target_is_hard_abort", True)):
            def changed(path):
                value = original(path)
                if Path(path) == ROOT / "evidence/phase3b-ra1-v1/authority.json":
                    value = copy.deepcopy(value)
                    value[field] = bad
                return value
            with self.subTest(field=field), patch.object(support, "read", side_effect=changed):
                with self.assertRaises(ContractError):
                    support.release_authority()
        for name in ("evidence/phase3b-ra1-v1/am1-authority.json",
                     "specifications/amendments/phase3b-release-acceptance-am1-1.0.md"):
            original_hash = support.file_hash
            def changed_hash(path):
                return "0" * 64 if Path(path) == ROOT / name else original_hash(path)
            with self.subTest(amended_hash=name), patch.object(support, "file_hash", side_effect=changed_hash):
                with self.assertRaises(ContractError):
                    support.release_authority()
        for field, bad in (("approved_full_remaining_RA1_block", False),
                           ("positive_bootstrap_test_total_seconds", 4),
                           ("positive_bootstrap_test_cleanup_seconds", 2)):
            def changed_amendment(path):
                value = original(path)
                if Path(path) == ROOT / "evidence/phase3b-ra1-v1/am1-authority.json":
                    value = copy.deepcopy(value)
                    value[field] = bad
                return value
            with self.subTest(amended_scope=field), patch.object(support, "read", side_effect=changed_amendment):
                with self.assertRaises(ContractError):
                    support.release_authority()

    def test_new_capture_scope_never_reopens_bd1_or_foreign_destinations(self):
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BASE, prefix="ra1-capture-unit-") as raw:
            base = Path(raw)
            good = base / "ra1-unit-preflight-v1/suite-1"
            good.mkdir(parents=True)
            with patch.object(support, "BASE", base), patch.object(support, "release_authority"):
                self.assertEqual(support.bootstrap_capture_path(str(good)), good)
                for target in (base / "bd1-unit-preflight-v1/suite-1", base / "foreign", good / ".env"):
                    with self.subTest(target=target), self.assertRaises(ContractError):
                        support.bootstrap_capture_path(str(target))

    def operator(self):
        spec = importlib.util.spec_from_file_location("ra1_admission_unit", ROOT / "evidence/phase3b-ra1-v1/ra1_operator.py")
        if spec is None or spec.loader is None:
            self.fail("RA1 operator unavailable")
        module: Any = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_new_two_candidate_counter_is_exclusive_and_does_not_reopen_old_limits(self):
        BASE.mkdir(parents=True, exist_ok=True)
        operator = self.operator()
        with tempfile.TemporaryDirectory(dir=BASE, prefix="ra1-admission-unit-") as raw:
            root = Path(raw)
            here = root / "evidence/phase3b-ra1-v1"
            here.mkdir(parents=True)
            with patch.object(operator, "ROOT", root), patch.object(operator, "HERE", here):
                for number in (1, 2):
                    value = {"source_sha256": str(number) * 64, "unit_fixture": True}
                    (here / f"candidate-{number}.json").write_text(json.dumps(value), encoding="utf-8")
                    (here / "release-config.json").write_text(json.dumps({
                        "kind": "phase3b-ra1-release-config-v1", "candidate": number,
                        "verification": "verification-ra1-v" + str(number),
                        "authority": "evidence/phase3b-ra1-v1/authority.json"}), encoding="utf-8")
                    with self.assertRaises(ContractError):
                        operator.admit("main", value)
                    operator.admit("candidate", value)
                    for label in ("main", "S13", "saved", "cold"):
                        record = operator.admit(label, value)
                        self.assertTrue(record["consumed_before_child_work"])
                        before = (here / f"admissions/c{number}-{label}.json").read_bytes()
                        with self.assertRaises(ContractError):
                            operator.admit(label, value)
                        self.assertEqual((here / f"admissions/c{number}-{label}.json").read_bytes(), before)
                config = json.loads((here / "release-config.json").read_text(encoding="utf-8"))
                config["candidate"] = 3
                config["verification"] = "verification-ra1-v3"
                (here / "release-config.json").write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    operator.settings()

    def test_preflight_counter_rejects_stream_named_receipt_before_source_metadata(self):
        spec = importlib.util.spec_from_file_location("ra1_preflight_counter_unit", ROOT / "evidence/phase3b-ra1-v1/run_units.py")
        if spec is None or spec.loader is None:
            self.fail("RA1 preflight operator unavailable")
        module: Any = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BASE, prefix="ra1-preflight-counter-unit-") as raw:
            here = Path(raw)
            admissions = here / "preflight-admissions"
            admissions.mkdir()
            def forbidden(_):
                raise AssertionError("foreign stream-named receipt reached metadata/content helper")
            with patch.object(module, "HERE", here), \
                 patch.object(module.os, "listdir", return_value=["suite-stdout.json"]), \
                 patch.object(module, "helper", return_value=SimpleNamespace(source_bytes=forbidden)):
                with self.assertRaisesRegex(ValueError, "before metadata"):
                    module.admission_history()


if __name__ == "__main__":
    unittest.main()
