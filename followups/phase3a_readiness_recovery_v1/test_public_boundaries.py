"""Public stream names must be denied before any metadata operation."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import launch, report
from .support import BASE


class PublicBoundaryTests(TestCase):
    def test_report_and_launcher_reject_stream_components_before_metadata(self):
        for name in ("live.STDOUT.json", "old_stderr.txt", "folder.stdout/report"):
            target = BASE / "unit" / name
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("metadata reached")):
                with self.assertRaises(ContractError):
                    launch._completion_path(target)
                with self.assertRaises(ContractError):
                    report.write_report({}, target)
