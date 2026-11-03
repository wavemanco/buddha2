"""Exercise the public offline grant command with the retained user authority."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.rank_format_v1 import cli, workflow
from followups.rank_format_v1.support import RESULTS, read_json


class CLITests(unittest.TestCase):
    def test_fixture_grant_reads_authority_and_writes_an_immutable_record(self):
        with tempfile.TemporaryDirectory(dir=RESULTS) as directory:
            output = Path(directory) / "grant.json"
            value = {"fixture": True, "authorization": {"authorized": False}}
            with patch.object(workflow, "grant_template", return_value=value) as make:
                self.assertEqual(cli.main(["grant", "--study", str(Path(directory) / "study.json"),
                                           "--output", str(output), "--fixture"]), 0)
                make.assert_called_once_with(Path(directory) / "study.json", fixture=True,
                                             authorized=True)
            self.assertEqual(read_json(output), value)
