"""Contract checks use synthetic copies; static R2 contexts stay read-only."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from followups.phase3a_compat_c1_v1 import contract


class ContractTests(unittest.TestCase):
    history: Path
    native: Path
    missions: dict[str, str]
    test_root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.history = contract.ROOT / (
            "runs/phase3a-r2-v1/17f35cf72cad95351e726cd9f02824be78db35a0a16c3f83db9e7bae9d762032/live/search"
        )
        cls.native = next((cls.history / "p3a-01/adaptive/native").glob("*/*/context"))
        cls.missions = {}
        for label in ("inv1", "dom1", "agg1"):
            file = next((cls.history / "p3a-01/adaptive/editor-audit").glob(label + ".a1.*.mission.md"))
            cls.missions[label] = file.read_text(encoding="utf-8")
        output_root = os.environ.get("BUDDHA2_OUTPUT_ROOT")
        results = (Path(output_root) / "phase3a-compat-c1-v1" if output_root
                   else contract.ROOT / "runs/phase3a-compat-c1-v1")
        cls.test_root = results / "unit-contract"
        cls.test_root.mkdir(parents=True, exist_ok=True)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=self.test_root)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def context(self, label: str = "inv1") -> Path:
        context = self.work / label
        shutil.copytree(self.native / label, context)
        for path in context.rglob("*"):
            if path.is_file() and "/harness/" not in path.as_posix():
                path.write_text("SYNTHETIC fixture evidence; no actual model judgment.\n", encoding="utf-8")
        strategy = {"answer_system": "SYNTHETIC answer instructions", "plan_system": "SYNTHETIC plan instructions",
                    "rank_system": "SYNTHETIC rank instructions"}
        for path in context.rglob("systemprompt.md"):
            path.write_text(json.dumps(strategy), encoding="utf-8")
        return context

    def build(self, context: Path, label: str = "inv1.a1", mission: str | None = None) -> dict:
        return contract.prepare_contract(mission or self.missions[label.split(".")[0]], context, label)

    def fingerprint(self, context: Path) -> dict[str, str]:
        return {p.relative_to(context).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in context.rglob("*") if p.is_file()}

    def test_three_roles_complete_manifest_and_no_writes(self) -> None:
        for role, label, count in (("INV", "inv1", 5), ("DOM", "dom1", 5), ("AGG", "agg1", 15)):
            with self.subTest(role=role):
                context = self.context(label)
                before = self.fingerprint(context)
                result = self.build(context, label + ".a1")
                self.assertEqual(result["manifest"]["role"], role)
                self.assertEqual(len(result["manifest"]["required_evidence"]), count)
                self.assertEqual(before, self.fingerprint(context))
                self.assertEqual(result, self.build(context, label + ".a1"))
                self.assertIn("KEEP_BASE is valid", result["effective_mission"])
                self.assertIn("rounds", result["effective_mission"])
                self.assertNotIn("So prefer, in this order", result["effective_mission"])
                self.assertNotIn("failed in 2/1", result["effective_mission"])

    def test_all_twelve_exposed_contexts_conform_without_changes(self) -> None:
        for pilot in ("p3a-01", "p3a-02", "p3a-03", "p3a-04"):
            native = next((self.history / pilot / "adaptive/native").glob("*/*/context"))
            for label in ("inv1", "dom1", "agg1"):
                with self.subTest(pilot=pilot, label=label):
                    context = native / label
                    before = self.fingerprint(context)
                    result = self.build(context, label + ".a1")
                    self.assertTrue(result["manifest"]["input_strategy_valid"])
                    self.assertEqual(before, self.fingerprint(context))
                    self.assertEqual(len(result["manifest"]["context_inventory"]), len(before))

    def test_long_lines_unicode_and_crlf_have_lossless_readable_views(self) -> None:
        context = self.context()
        content = ("😀é\"\\" * 5000 + "\r\nsecond line\r\n").encode("utf-8")
        path = "deliverables/base1/answers.json.txt"
        (context / path).write_bytes(content)
        result = self.build(context)
        entry = next(row for row in result["manifest"]["required_evidence"] if row["path"] == path)
        parts = []
        self.assertGreater(len(entry["chunks"]), 1)
        for chunk in entry["chunks"]:
            text = result["evidence_files"][chunk["path"]]
            self.assertEqual(chunk["offset"], 1)
            self.assertEqual(chunk["limit"], len(text.splitlines()))
            self.assertLess(len(text.encode("ascii")), 50 * 1024)
            self.assertTrue(all(len(line) < 2000 for line in text.splitlines()))
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), chunk["sha256"])
            view = json.loads(text)
            self.assertEqual(view["source_path"], path)
            parts.extend(view["text"])
        self.assertEqual("".join(parts).encode("utf-8"), content)
        self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())

    def test_empty_diff_still_has_an_explicit_lossless_view(self) -> None:
        context = self.context("agg1")
        (context / "pool/inv1/harness.diff").write_bytes(b"")
        result = self.build(context, "agg1.a1")
        row = next(x for x in result["manifest"]["required_evidence"] if x["path"] == "pool/inv1/harness.diff")
        self.assertEqual(row["bytes"], 0)
        self.assertEqual(len(row["chunks"]), 1)
        self.assertEqual(json.loads(result["evidence_files"][row["chunks"][0]["path"]])["text"], [])

    def test_private_names_rejected_before_stat_or_read(self) -> None:
        context = self.context()
        original = Path.lstat
        for name in ("credential-binding.json", ".writer.lock"):
            path = context / name
            path.write_text("SYNTHETIC forbidden fixture")
            def guarded(candidate: Path):
                if candidate.name == name:
                    raise AssertionError("private file metadata must not be inspected")
                return original(candidate)
            with self.subTest(name=name), mock.patch.object(Path, "lstat", guarded):
                with self.assertRaises(contract.ContractError):
                    self.build(context)
            path.unlink()

    def test_missing_or_foreign_evidence_rejected(self) -> None:
        context = self.context()
        source = context / "rollouts/base1.md"
        source.unlink()
        with self.assertRaises(contract.ContractError):
            self.build(context)
        source.write_text("SYNTHETIC", encoding="utf-8")
        (context / "assessment.json").write_text("SYNTHETIC forbidden artifact", encoding="utf-8")
        with self.assertRaises(contract.ContractError):
            self.build(context)

    def test_derived_file_collision_and_unexpected_empty_directory_rejected(self) -> None:
        context = self.context()
        marker = context / contract.MANIFEST_NAME
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaises(contract.ContractError):
            self.build(context)
        marker.unlink()
        (context / "unexpected").mkdir()
        with self.assertRaises(contract.ContractError):
            self.build(context)

    def test_changed_compatibility_file_rejected(self) -> None:
        context = self.context()
        (context / "harness/skills/README.md").write_text("SYNTHETIC changed stub", encoding="utf-8")
        with self.assertRaises(contract.ContractError):
            self.build(context)

    def test_symlink_evidence_rejected(self) -> None:
        context = self.context()
        source = context / "task.md"
        original = self.work / "elsewhere.txt"
        source.rename(original)
        try:
            source.symlink_to(original)
        except OSError:
            self.skipTest("host does not allow unprivileged symbolic links")
        with self.assertRaises(contract.ContractError):
            self.build(context)

    def test_non_utf8_evidence_rejected(self) -> None:
        context = self.context()
        (context / "task.md").write_bytes(b"\xff")
        with self.assertRaises(contract.ContractError):
            self.build(context)

    def test_invalid_current_json_requires_actual_native_repair(self) -> None:
        context = self.context()
        path = context / "harness/systemprompt.md"
        for invalid in ("{}", '{"answer_system":"a","answer_system":"b","plan_system":"p","rank_system":"r"}',
                        '{"answer_system":NaN,"plan_system":"p","rank_system":"r"}',
                        '{"answer_system":"\\ud800","plan_system":"p","rank_system":"r"}'):
            with self.subTest(invalid=invalid):
                path.write_text(invalid, encoding="utf-8")
                with self.assertRaises(contract.ContractError):
                    self.build(context)
        repair = self.missions["inv1"] + contract._REPAIR + "invalid JSON shape" + contract._REPAIR_END
        result = self.build(context, "inv1.a2", repair)
        self.assertFalse(result["manifest"]["input_strategy_valid"])
        self.assertIsNone(result["manifest"]["input_effective_strategy_sha256"])
        self.assertEqual(result["manifest"]["native_repair_diagnostic"], "invalid JSON shape")
        self.assertIn("Repair the current file", result["effective_mission"])

    def test_invalid_candidate_is_not_laundered_as_current_repair(self) -> None:
        context = self.context("agg1")
        (context / "pool/dom1/harness/systemprompt.md").write_text("{}", encoding="utf-8")
        repair = self.missions["agg1"] + contract._REPAIR + "repair current" + contract._REPAIR_END
        with self.assertRaises(contract.ContractError):
            self.build(context, "agg1.a2", repair)

    def test_unknown_stage_or_native_mission_drift_rejected(self) -> None:
        context = self.context()
        for label, mission in (("inv2.a1", self.missions["inv1"]), ("inv1.a3", self.missions["inv1"]),
                               ("dom1.a1", self.missions["inv1"]),
                               ("inv1.a1", self.missions["inv1"] + "\nSYNTHETIC injected instruction"),
                               ("inv1.a2", self.missions["inv1"])):
            with self.subTest(label=label):
                with self.assertRaises(contract.ContractError):
                    self.build(context, label, mission)

    def test_pinned_source_drift_fails_without_changing_source(self) -> None:
        context = self.context()
        with mock.patch.dict(contract.UPSTREAM_FILES, {"prompts.py": "0" * 64}):
            with self.assertRaises(contract.ContractError):
                self.build(context)

    def test_context_mutation_during_preparation_rejected(self) -> None:
        context = self.context()
        original = contract._views
        calls = 0

        def mutate(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                (context / "task.md").write_text("SYNTHETIC changed during read", encoding="utf-8")
            return original(*args)

        with mock.patch.object(contract, "_views", side_effect=mutate):
            with self.assertRaises(contract.ContractError):
                self.build(context)

    def test_original_path_is_rejected_before_any_filesystem_probe(self) -> None:
        with mock.patch.object(contract, "_ordinary", side_effect=AssertionError("must not probe original")):
            with self.assertRaises(contract.ContractError):
                contract._inventory(Path("C:/Users/arvik/code/buddha2"), set())

    def test_outside_path_is_rejected_before_any_filesystem_probe(self) -> None:
        with mock.patch.object(contract, "_ordinary", side_effect=AssertionError("must not probe outside")):
            with self.assertRaises(contract.ContractError):
                contract._inventory(Path.home() / "outside-c1-synthetic-nonexistent", set())


if __name__ == "__main__":
    unittest.main()
