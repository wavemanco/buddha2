"""The public entry is lazy, source-bound, and inspection never authorizes calls."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from buddha2 import experiment
from buddha2.artifacts import digest


class ExperimentCLI(unittest.TestCase):
    def study(self, source=None):
        source = source or {"kind": "current-v2", "files": {}, "sha256": "source"}
        body = {"kind": "study-v2", "source": source, "source_sha256": source["sha256"],
                "tasks": [{"parent_task_id": "development-1"}]}
        return {**body, "study_sha256": digest(body)}

    def support(self, study):
        return SimpleNamespace(SOURCE_KIND="current-v2", path=lambda p: p,
            read=Mock(return_value=study), source_identity=Mock(return_value=study["source"]))

    def invoke(self, args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = experiment.main(args)
        return result, output.getvalue(), error.getvalue()

    def test_help_does_not_initialize_native_or_provider_runtime(self):
        with patch.object(experiment, "_backend", side_effect=AssertionError("runtime imported")):
            with self.assertRaises(SystemExit) as result, contextlib.redirect_stdout(io.StringIO()):
                experiment.main(["--help"])
        self.assertEqual(result.exception.code, 0)

    def test_existing_operations_receive_original_arguments(self):
        for command, forwarded in (("prepare", ["prepare", "--output", "x"]),
                                   ("launch", ["--command", "preflight"])):
            backend = SimpleNamespace(main=Mock(return_value=7))
            args = forwarded if command == "prepare" else [command, *forwarded]
            with patch.object(experiment, "_backend", return_value=backend):
                self.assertEqual(experiment.main(args), 7)
            backend.main.assert_called_once_with(forwarded)

    def test_timing_decision_routes_without_a_provider_or_workflow_backend(self):
        for action in ("continue", "stop"):
            result = {"decision": action, "provider_calls": 0, "financial_authority_changed": False}
            backend = SimpleNamespace(decide=Mock(return_value=result))
            with self.subTest(action=action), patch.object(experiment, "_backend", return_value=backend) as imported:
                code, output, _ = self.invoke(["timing", "--request", "review-01.request.json",
                                               "--decision", action])
            self.assertEqual((code, json.loads(output)), (0, result))
            imported.assert_called_once_with("deadline")
            backend.decide.assert_called_once_with(Path("review-01.request.json"), action)

    def test_inspection_is_compact_and_never_launch_approval(self):
        study = self.study()
        support = self.support(study)
        with patch.object(experiment, "_backend", return_value=support):
            result, output, _ = self.invoke(["inspect", "--study", "study.json"])
        value = json.loads(output)
        self.assertEqual(result, 0)
        self.assertTrue(value["source_matches_current"])
        self.assertFalse(value["inspection_is_launch_approval"])
        self.assertEqual(value["provider_calls"], 0)
        self.assertNotIn("files", value)

    def test_historical_inspection_does_not_open_current_or_retained_source(self):
        study = self.study({"kind": "historical-v1", "sha256": "old"})
        support = self.support(study)
        with patch.object(experiment, "_backend", return_value=support):
            result, output, _ = self.invoke(["inspect", "--study", "study.json"])
        self.assertEqual(result, 0)
        self.assertTrue(json.loads(output)["historical_profile"])
        support.source_identity.assert_not_called()

    def test_private_capture_names_are_rejected_before_backend_access(self):
        for name in ("source/study.json", "effective-source/study.json", "retained/study.json",
                     "capture/study.json", "prior-source/study.json", "source-snapshot/study.json",
                     ".env/study.json", ".cache/study.json", "auth.json", "credential-binding.json"):
            with self.subTest(name=name), patch.object(experiment, "_backend") as backend:
                result, _, _ = self.invoke(["inspect", "--study", name])
                self.assertEqual(result, 2)
                backend.assert_not_called()

    def test_modified_descriptor_and_malformed_source_fail_closed(self):
        for field, value in (("tasks", []), ("source", [])):
            study = self.study()
            study[field] = value
            if field == "source":
                study["study_sha256"] = digest({k: v for k, v in study.items() if k != "study_sha256"})
            with self.subTest(field=field), patch.object(experiment, "_backend", return_value=self.support(study)):
                result, _, error = self.invoke(["inspect", "--study", "study.json"])
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(error)["provider_calls"], 0)

    def test_backend_rejects_a_foreign_import_origin(self):
        for origin in (str(experiment.ROOT / "tests/not-native.py"), None):
            foreign = SimpleNamespace(__file__=origin)
            with self.subTest(origin=origin), patch.object(
                experiment.importlib, "import_module", return_value=foreign
            ), patch.object(Path, "resolve", side_effect=AssertionError("foreign metadata")):
                with self.assertRaises(ValueError):
                    experiment._backend("workflow")

    def test_backend_accepts_only_the_expected_checkout_module(self):
        expected = experiment.ROOT / "followups/phase3b_seq2_v1/workflow.py"
        module = SimpleNamespace(__file__=str(expected))
        with patch.object(experiment.importlib, "import_module", return_value=module):
            self.assertIs(experiment._backend("workflow"), module)

    def test_same_header_does_not_hide_a_different_source_map(self):
        study = self.study()
        support = self.support(study)
        support.source_identity.return_value = {**study["source"], "files": {"different.py": "changed"}}
        with patch.object(experiment, "_backend", return_value=support):
            result, output, _ = self.invoke(["inspect", "--study", "study.json"])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output)["source_matches_current"])

    def test_main_exposes_current_experiment(self):
        from buddha2.__main__ import main
        with patch.object(experiment, "main", return_value=9) as delegated:
            self.assertEqual(main(["experiment", "--help"]), 9)
            delegated.assert_called_once_with(["--help"])


if __name__ == "__main__":
    unittest.main()
