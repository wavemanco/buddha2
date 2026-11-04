"""Pure RA1 accounting-policy checks; no worker or campaign admission."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ra1_effort_checks", HERE / "effort.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("RA1 effort check module is unavailable")
EFFORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EFFORT)


class EffortPolicyTests(unittest.TestCase):
    def test_target_is_review_not_abort(self):
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        with patch.object(EFFORT, "now", return_value=future), patch("sys.argv", ["effort.py"]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = EFFORT.main()
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(result["review_due"])
        self.assertFalse(result["target_is_hard_abort"])
        self.assertEqual(result["review_milestones_reached"], [7200, 10800, 14400])

    def test_conservative_charges_count_once(self):
        result = EFFORT.status()
        self.assertEqual(result["bootstrap_charge_seconds"], 180)
        self.assertEqual(result["additional_charge_seconds"], 40)
        self.assertAlmostEqual(result["active_seconds"], result["measured_seconds"] + 220, places=5)

    def test_boolean_and_nonpositive_charge_rejected(self):
        original = Path.read_text
        for seconds in (True, 0, -1):
            def changed(path, *args, **kwargs):
                raw = original(path, *args, **kwargs)
                if path.parent == HERE / "charges":
                    value = json.loads(raw)
                    value["seconds"] = seconds
                    return json.dumps(value)
                return raw
            with self.subTest(seconds=seconds), patch.object(Path, "read_text", changed):
                with self.assertRaisesRegex(ValueError, "invalid conservative effort charge"):
                    EFFORT.status()

    def test_excluded_charge_names_rejected_before_metadata(self):
        original_list = os.listdir
        original_link = Path.is_symlink
        for name in ("stdout.json", "has-stderr.json", "auth.json", ".env"):
            def listing(path):
                return [name] if Path(path) == HERE / "charges" else original_list(path)
            def metadata(path):
                if path.parent == HERE / "charges":
                    self.fail("excluded charge path reached metadata")
                return original_link(path)
            with self.subTest(name=name), patch.object(os, "listdir", listing), patch.object(Path, "is_symlink", metadata):
                with self.assertRaisesRegex(ValueError, "rejected before metadata"):
                    EFFORT.status()

    def test_linked_charge_rejected(self):
        original = Path.is_symlink
        def linked(path):
            return True if path.parent == HERE / "charges" else original(path)
        with patch.object(Path, "is_symlink", linked):
            with self.assertRaisesRegex(ValueError, "ordinary file"):
                EFFORT.status()


if __name__ == "__main__":
    unittest.main(verbosity=2)
