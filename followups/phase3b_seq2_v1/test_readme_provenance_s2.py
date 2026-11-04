"""Narrative documentation no longer changes the effective experiment identity."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from . import support


class ReadmeProvenanceCases(unittest.TestCase):
    def test_readme_and_old_archive_changes_are_not_runtime_inputs(self):
        baseline = support.source_identity()
        original = support.file_hash

        def changed(path):
            name = Path(path).relative_to(support.ROOT).as_posix()
            if name in {"README.md", "README_LEGACY.md"} or name.endswith(".zip"):
                self.fail("historical or narrative file reached the effective source reader")
            return original(path)

        with patch.object(support, "file_hash", side_effect=changed):
            self.assertEqual(support.source_identity(), baseline)
        self.assertNotIn("README.md", baseline["files"])
        self.assertNotIn("README_LEGACY.md", baseline["files"])


if __name__ == "__main__":
    unittest.main()
