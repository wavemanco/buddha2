"""Offline policy CLI and preserved execution-source boundaries."""

import contextlib
import copy
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash, read_json, tree_hashes, write_once
from buddha2.phase2 import PROJECT
from buddha2.phase2_policy import (
    ORIGINAL_STUDY,
    _input,
    _original_sources,
    load_execution,
    main,
    original_study,
    prepare_policy,
    save_bundle,
    validate_execution_study,
)


class PolicyBoundaryTests(unittest.TestCase):
    def setUp(self):
        output_root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs"))
        self.temporary = tempfile.TemporaryDirectory(prefix="test-policy-", dir=output_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.study_path = PROJECT / "runs/phase2-r010/frozen-study/study.json"
        self.old = original_study()
        self.old_hash = file_hash(self.study_path)
        self.archive_path = PROJECT / "evidence/phase2-r010/phase2a-kit.zip"
        self.archive_hash = file_hash(self.archive_path)
        self.native = patch("buddha2.phase2_native.NativeAssessment",
                            return_value=SimpleNamespace(identity=self.old["native_evaluator"]))
        self.native.start()
        self.addCleanup(self.native.stop)

    def assert_preserved(self):
        self.assertEqual(file_hash(self.study_path), self.old_hash)
        self.assertEqual(file_hash(self.archive_path), self.archive_hash)
        self.assertEqual(original_study()["study_sha256"], ORIGINAL_STUDY)

    def test_preserved_source_archive_verifies_and_changed_dispatch_requires_historical_source(self):
        _original_sources(self.old)
        # AM-1 deliberately changes dispatch accounting. The old current-source
        # compatibility promise is no longer true; retain the strict guard and
        # replay historical outputs under their exact archived implementation.
        with self.assertRaisesRegex(ContractError, "execution replay compatibility needs review"):
            validate_execution_study(self.old, self.study_path)
        self.assert_preserved()

    def test_corrupted_source_archive_is_rejected_without_using_current_sources_as_substitute(self):
        fake = self.root / "fake-project"
        archive = fake / "evidence/phase2-r010/phase2a-kit.zip"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"corrupt historical archive")
        with patch("buddha2.phase2_policy.PROJECT", fake):
            with self.assertRaisesRegex(ContractError, "historical source archive differs"):
                _original_sources(self.old)
        self.assert_preserved()

    def test_prepare_preserves_tasks_profiles_sample_and_freezes_new_code_without_reselection(self):
        output = self.root / "prepared"
        with patch("buddha2.phase2.select_tasks", side_effect=AssertionError("must not reselect tasks")):
            result = prepare_policy(output)
            second = prepare_policy(output)
        self.assertEqual(result, second)
        refreshed = read_json(output / "study.json")
        self.assertNotEqual(refreshed["study_sha256"], ORIGINAL_STUDY)
        self.assertEqual(refreshed["parent_preparation_sha256"], ORIGINAL_STUDY)
        for key in ("tasks", "human_check", "profiles", "worklist", "templates", "source_audit",
                    "exposure", "admission", "caps", "failure_policy", "native_evaluator",
                    "upstream_pins", "shared_generator_settings_sha256", "procedure_hashes"):
            self.assertEqual(refreshed[key], self.old[key], key)
        self.assertFalse(refreshed["execution_authorized"])
        self.assertFalse(refreshed["selection_rule"]["benchmark_requires_humans"])
        self.assertFalse(result["human_collection_started"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse(result["live_ready"])
        self.assertEqual(refreshed["package_files"], tree_hashes(output / "source"))
        self.assertEqual(refreshed["package_files"], tree_hashes(PROJECT / "src/buddha2"))
        self.assertNotIn("two eligible pilot-output readers and availability",
                         refreshed["remaining_live_prerequisites"])
        self.assertIn("verified provider input-admission bound", refreshed["remaining_live_prerequisites"])
        self.assert_preserved()

    def test_retained_new_source_tampering_or_changed_execution_inputs_cannot_pass_policy_validation(self):
        output = self.root / "prepared"
        prepare_policy(output)
        refreshed = read_json(output / "study.json")
        changed = copy.deepcopy(refreshed)
        changed["tasks"][0]["prompt"] += " changed"
        changed["study_sha256"] = digest({k: v for k, v in changed.items() if k != "study_sha256"})
        with self.assertRaisesRegex(ContractError, "execution changed outside the policy update"):
            validate_execution_study(changed, output / "study.json")
        (output / "source/phase2_human.py").write_text("changed retained source", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "retained execution source bundle differs"):
            validate_execution_study(refreshed, output / "study.json")
        self.assert_preserved()

    def test_loading_saved_historical_artifacts_is_read_only_and_never_constructs_transport(self):
        # The full native/journal replay is covered by the actual offline CLI
        # walkthrough; here isolate loader writes and accidental live dispatch.
        saved = PROJECT / "runs/phase2-r010/walkthrough-complete"
        first = sorted((saved / "portfolios").glob("*.json"))[0]
        portfolio = read_json(first)
        from buddha2.phase2_contracts import slot_prefix

        prefix = slot_prefix(portfolio["task"]["id"], portfolio["provenance"]["method"],
                             portfolio["provenance"]["repeat"])
        assessment = read_json(saved / "assessments" / f"{prefix}.json")
        run = self.root / "saved"
        write_once(run / "portfolios" / first.name, portfolio)
        write_once(run / "assessments" / f"{prefix}.json", assessment)
        before = tree_hashes(run)
        state = {"fixture": True, "results": {}, "status": "ready"}
        with (patch("buddha2.phase2_policy.replay_dispatch", return_value=state) as replay,
              patch("buddha2.phase2_dispatch.DirectSDKTransport",
                    side_effect=AssertionError("no provider transport")),
              patch("buddha2.phase2.generate_order", side_effect=AssertionError("no generation")),
              patch("buddha2.phase2.rank_order", side_effect=AssertionError("no ranking"))):
            with self.assertRaisesRegex(ContractError, "execution replay compatibility needs review"):
                load_execution(self.study_path, run)
        # Refuse before a journal can be interpreted using changed accounting.
        replay.assert_not_called()
        self.assertEqual(tree_hashes(run), before)
        self.assert_preserved()

    def test_cli_bad_artifacts_fail_with_exit_two_without_starting_any_provider(self):
        malformed = self.root / "malformed.json"
        malformed.write_text("not JSON", encoding="utf-8")
        with (patch("buddha2.__main__._offline"), patch("buddha2.__main__._upstreams"),
              patch("buddha2.phase2_dispatch.DirectSDKTransport",
                    side_effect=AssertionError("no provider transport")),
              contextlib.redirect_stderr(io.StringIO()) as errors):
            result = main(["inspect", "--study", str(malformed)])
        self.assertEqual(result, 2)
        self.assertIn("ContractError", errors.getvalue())
        self.assert_preserved()

    def test_input_link_escape_and_immutable_decision_overwrite_are_refused(self):
        linked = self.root / "linked.json"
        target = self.root / "target.json"
        write_once(target, {"bound": True})
        linked.symlink_to(target)
        with self.assertRaisesRegex(ContractError, "cannot traverse links"):
            _input(linked)
        bundle = {"decision": {"selected_method": "A"}}
        save_bundle(self.root / "closed", bundle)
        save_bundle(self.root / "closed", bundle)
        with self.assertRaisesRegex(ContractError, "immutable artifact already differs"):
            save_bundle(self.root / "closed", {"decision": {"selected_method": "B"}})
        self.assertEqual(read_json(self.root / "closed/decision.json"), bundle["decision"])


if __name__ == "__main__":
    unittest.main()
