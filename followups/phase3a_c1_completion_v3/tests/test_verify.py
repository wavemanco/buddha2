"""The host verifier consumes the literal public PowerShell output contract."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from followups.phase3a_c1_completion_v3 import verify


class VerifyTests(unittest.TestCase):
    def test_check_records_bind_all_five_identities_without_body_override(self):
        study = {key: str(index) * 64 for index, key in enumerate(verify.BINDINGS)}
        with patch("buddha2.artifacts.write_once") as output:
            record = verify._record(Path("/results/phase3a-c1-completion-v3/unit"), "fixture", study,
                                    {"passed": True, "source_sha256": "foreign"})
        self.assertTrue(record["passed"])
        self.assertEqual({key: record[key] for key in verify.BINDINGS}, study)
        output.assert_called_once()

    def test_output_scope_and_private_names_fail_before_metadata(self):
        for name in ("runs/phase3a-c1-completion-v2/old", "runs/phase3a-c1-completion-v3/../escape",
                     "runs/phase3a-c1-completion-v3/Credential-Binding.JSON", "runs/phase3a-c1-completion-v3/.env/child"):
            with self.subTest(name=name), patch.object(Path, "is_symlink", side_effect=AssertionError("private/foreign metadata")):
                with self.assertRaises(ValueError):
                    verify._host_output(name)

    def test_host_passes_runs_relative_inputs_and_uses_actual_result_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pwsh = root / "pwsh"
            pwsh.write_text("fixture executable marker")
            output = root / "runs/phase3a-c1-completion-v3/verification"
            launcher = root / "runs/phase3a-c1-completion-v3/launcher"
            commands = []
            def execute(command, **kwargs):
                commands.append(command)
                if "--inside" in command:
                    (output / "matrix.json").write_text(json.dumps({
                        "study_path": "/results/phase3a-c1-completion-v3/verification/release/study.json",
                        "mock_grant_path": "/results/phase3a-c1-completion-v3/verification/release/mock-grant.json",
                        "live_grant_path": "/results/phase3a-c1-completion-v3/verification/release/live-grant.json"}))
                elif "-Action" in command:
                    action = command[command.index("-Action") + 1]
                    for option in ("-Study", "-Grant"):
                        self.assertTrue(command[command.index(option) + 1].startswith("phase3a-c1-completion-v3/"))
                    launcher.mkdir(parents=True, exist_ok=True)
                    (launcher / (action + ".inspection.json")).write_text("{}")
                    if action == "mock":
                        (launcher / (action + ".result.json")).write_text("{}")
                else:
                    self.assertEqual(command[-4:-1], [verify.MODULE, "--seal", "--output"])
                return SimpleNamespace(returncode=0)
            with patch.object(verify, "ROOT", root), patch.object(verify, "PWSH", pwsh), \
                    patch.object(verify.shutil, "which", return_value="/fixture/docker"), \
                    patch.object(verify.subprocess, "check_output", return_value=(verify.IMAGE + "\n").encode()), \
                    patch.object(verify.subprocess, "run", side_effect=execute):
                self.assertEqual(verify.host("runs/phase3a-c1-completion-v3/verification"), 0)
            rows = json.loads((output / "launcher-host.json").read_text())
            self.assertTrue(rows[0]["runtime_path"].endswith("mock.result.json"))
            self.assertIsNone(rows[1]["runtime_path"])
            self.assertEqual(len(commands), 4)


if __name__ == "__main__":
    unittest.main()
