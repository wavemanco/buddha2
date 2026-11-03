"""The demonstration exposes no live route and cannot overwrite foreign evidence."""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.phase3a_compat_c1_v1 import cli


class CliTests(unittest.TestCase):
    def test_synthetic_task_metadata_satisfies_the_actual_portfolio_contract(self):
        from followups.phase3a_v1 import strategy, workflow
        tasks = cli.synthetic_tasks()
        self.assertEqual(len(tasks), 4)
        for entry in tasks:
            strategy._task(workflow._task(entry))
            self.assertIn("synthetic", entry["source_context"]["dataset"])

    def test_output_must_be_fresh_scoped_absolute_and_nontraversing(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"BUDDHA2_OUTPUT_ROOT": temporary}):
            root = Path(temporary) / "phase3a-compat-c1-v1"
            output = root / "new-demo"
            self.assertEqual(cli.output_path(str(output)), output)
            self.assertFalse(output.exists())
            for invalid in ("relative", str(Path(temporary) / "foreign"), str(root), str(root / "x/../y")):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    cli.output_path(invalid)
            output.mkdir(parents=True)
            with self.assertRaises(ValueError):
                cli.output_path(str(output))

    def test_linked_output_ancestor_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"BUDDHA2_OUTPUT_ROOT": temporary}):
            root = Path(temporary) / "phase3a-compat-c1-v1"
            root.mkdir()
            target = Path(temporary) / "other"
            target.mkdir()
            try:
                (root / "linked").symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("host does not permit unprivileged links")
            with self.assertRaises(ValueError):
                cli.output_path(str(root / "linked/new"))

    def test_no_live_or_provider_command_exists(self):
        for command in ("live", "run", "launch", "provider"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main([command])
                self.assertEqual(raised.exception.code, 2)

    def test_network_precondition_precedes_import_or_provider_construction(self):
        with patch.object(cli.sys, "platform", "win32"), self.assertRaises(ValueError):
            cli.demo(Path("/not-read-or-created"))

    def test_wrong_runtime_root_rejected_before_inspecting_network_or_outputs(self):
        with patch.dict(os.environ, {"BUDDHA2_OUTPUT_ROOT": "/tmp"}), \
                patch.object(cli.Path, "iterdir", side_effect=AssertionError("must not inspect")), \
                self.assertRaises(ValueError):
            cli._offline_runtime()

    def test_main_wrong_root_never_probes_the_foreign_output(self):
        with patch.dict(os.environ, {"BUDDHA2_OUTPUT_ROOT": "/tmp"}), \
                patch.object(cli.Path, "is_symlink", side_effect=AssertionError("must not probe")), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["demo", "--output", "/tmp/phase3a-compat-c1-v1/foreign"]), 1)


if __name__ == "__main__":
    unittest.main()
