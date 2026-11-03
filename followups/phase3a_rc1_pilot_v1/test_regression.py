"""Offline ownership regressions for the reused-helper container launcher."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import regression
from .support import BASE


class RegressionBoundaryTests(unittest.TestCase):
    def test_foreign_image_never_starts_and_fresh_records_are_retained(self):
        self.check_boundary(existing_create=False)

    def test_record_publication_error_still_removes_only_owned_container(self):
        self.check_boundary(existing_create=True)

    def check_boundary(self, *, existing_create: bool):
        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="regression-unit-", dir=BASE) as directory:
            root = Path(directory)
            output = root / "runs" / regression.PREFIX / "fixture"
            (output / "release").mkdir(parents=True)
            (output / "release/study.json").write_text(json.dumps(
                {key: str(index + 1) * 64 for index, key in enumerate(regression.BINDINGS)}), encoding="utf-8")
            for name in regression.DIAGNOSTICS:
                target = root / "runs" / regression.PREFIX / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{"fixture_only": true}', encoding="utf-8")
            create = output / "regression-create.json"
            if existing_create:
                create.write_bytes(b"SYNTHETIC existing fixture must not be overwritten")
            commands = []
            owner = "a" * 64
            def run(arguments, **kwargs):
                commands.append(arguments)
                if arguments[1] == "create":
                    return {"exit_code": 0, "stdout": owner + "\n", "stderr": ""}
                if arguments[1] == "inspect":
                    return {"exit_code": 0, "stdout": json.dumps([{
                        "Image": "sha256:" + "b" * 64, "HostConfig": {}, "Mounts": [],
                        "State": {"Running": False}}]), "stderr": ""}
                if arguments[1:] == ["rm", owner]:
                    return {"exit_code": 0, "stdout": owner, "stderr": ""}
                self.fail("unexpected container operation")
            with patch.object(regression, "ROOT", root), patch.object(regression, "_run", side_effect=run):
                if existing_create:
                    with self.assertRaises(FileExistsError):
                        regression.complete_regression(output)
                    self.assertEqual(create.read_bytes(), b"SYNTHETIC existing fixture must not be overwritten")
                else:
                    report = regression.complete_regression(output)
                    self.assertFalse(report["passed"])
                    self.assertTrue(create.is_file())
            self.assertFalse(any(command[1] == "start" for command in commands))
            self.assertEqual(commands[-1], ["docker", "rm", owner])
            self.assertTrue((output / "regression-cleanup.json").is_file())
            invocation = commands[0]
            self.assertIn("--read-only", invocation)
            self.assertEqual(invocation[invocation.index("--network") + 1], "none")
            self.assertEqual(sum(arg.startswith("type=bind,") for arg in invocation), 1)
            self.assertIn("/results:rw,nosuid,nodev,size=1073741824,mode=1777", invocation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
