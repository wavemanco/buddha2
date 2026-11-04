"""Current source identity excludes historical campaigns and private inputs."""
from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import adapter, editor, evidence, support, workflow


class SourceSnapshotCases(unittest.TestCase):
    def test_declared_definition_binds_authority_and_native_evidence_without_reading_editorial_markdown(self):
        original = Path.open
        def no_editorial(candidate, *args, **kwargs):
            self.assertNotEqual(candidate.name.casefold(), "phase3b_definition.md")
            return original(candidate, *args, **kwargs)
        with patch.object(Path, "open", no_editorial):
            authority = support.validate_authority()
            self.assertEqual(authority["definition_sha256"], support.DECLARED_DEFINITION_SHA256)
            self.assertNotIn("PHASE3B_DEFINITION.md", support.source_identity()["files"])
            self.assertEqual(evidence._live_profile().definition_sha256, support.DECLARED_DEFINITION_SHA256)
            with patch.object(editor.AccountedProposer, "__init__", return_value=None), \
                    patch.object(Path, "is_symlink", return_value=False), \
                    patch.object(Path, "is_junction", return_value=False, create=True):
                proposer = adapter.CompatibleProposer(pilot="p3b-01", study_sha256="a" * 64,
                    dispatch=lambda *args: self.fail("unexpected dispatch"), fixture=True,
                    audit_dir=support.ROOT / "runs/phase3b-seq2-v1/native/declaration-unit/editor-audit",
                    halt=lambda *args: self.fail("unexpected halt"))
            self.assertEqual(proposer._c1_binding["definition_sha256"], support.DECLARED_DEFINITION_SHA256)

    def test_declared_definition_cannot_authorize_changed_identity_caps_or_method(self):
        authority = support.read(support.AUTHORITY)
        for key, value in (("definition_sha256", "0" * 64), ("new_cap_micro_usd", 180000001),
                ("new_max_attempts", 2345), ("models_and_billing_profile_unchanged", False)):
            with self.subTest(field=key), patch.object(support, "read", return_value={**authority, key: value}), \
                    self.assertRaisesRegex(ContractError, "authority differs"):
                support.validate_authority()

    def test_portable_development_inputs_preserve_tasks_without_parent_run_reads(self):
        original = workflow.read
        baseline = workflow._scientific_inputs()
        def current_only(target):
            self.assertEqual(target, support.ROOT / "configs/phase3b-development.json")
            return original(target)
        with patch.object(workflow, "read", side_effect=current_only):
            tasks = workflow.frozen_tasks()
        self.assertEqual([task["parent_task_id"] for task in tasks],
            [task["parent_task_id"] for task in baseline["tasks"]])
        self.assertEqual([task["pilot_id"] for task in tasks], [f"p3b-{index:02}" for index in range(1, 5)])
        self.assertEqual(tasks[0]["arm_order"], ["adaptive", "fixed"])
        self.assertEqual(workflow._scientific_inputs(), baseline)

    def test_foreign_short_or_duplicate_development_task_inputs_are_rejected(self):
        baseline = workflow._scientific_inputs()
        for change in ({"kind": "foreign"}, {"tasks": baseline["tasks"][:3]},
                {"tasks": [baseline["tasks"][0]] * 4}):
            with self.subTest(change=list(change)), patch.object(workflow, "read", return_value={**baseline, **change}), \
                    self.assertRaisesRegex(ContractError, "development inputs"):
                workflow.frozen_tasks()

    def test_local_imports_of_bound_code_are_also_bound(self):
        names = set(support._source_inputs())
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            module = name.removeprefix("src/").removesuffix(".py").replace("/", ".")
            package = module.removesuffix(".__init__") if module.endswith(".__init__") else module.rsplit(".", 1)[0]
            tree = ast.parse((support.ROOT / name).read_text(encoding="utf-8-sig"))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(item.name for item in node.names)
                elif isinstance(node, ast.ImportFrom):
                    prefix = package.split(".")[:len(package.split(".")) - node.level + 1] if node.level else []
                    base = ".".join(prefix + ([node.module] if node.module else []))
                    imports.add(base)
                    imports.update(base + "." + item.name for item in node.names if item.name != "*")
            for imported in imports:
                if not imported.startswith(("buddha2.", "followups.")):
                    continue
                relative = ("src/" if imported.startswith("buddha2.") else "") + imported.replace(".", "/")
                for candidate in (relative + ".py", relative + "/__init__.py"):
                    if (support.ROOT / candidate).is_file():
                        self.assertIn(candidate, names, f"{name} imports unbound {candidate}")

    def test_effective_identity_covers_reused_helpers_without_historical_artifacts(self):
        hashed = []
        original = support.file_hash

        def public_hash(path):
            name = Path(path).relative_to(support.ROOT).as_posix()
            support._source_name(name)
            hashed.append(name)
            return original(path)

        with patch.object(support, "file_hash", side_effect=public_hash), \
                patch.object(support, "release_authority", side_effect=AssertionError("old campaign read")):
            source = support.source_identity()
            preserved = support.preserve()
        self.assertEqual(source["kind"], "buddha2-effective-source-v2")
        self.assertEqual(source["sha256"], digest({k: v for k, v in source.items() if k != "sha256"}))
        self.assertTrue({"followups/phase3b_seq2_v1/editor.py", "src/buddha2/phase2_native.py",
            "followups/phase3a_c1_completion_v3/adapter.py", "followups/phase3a_v1/strategy.py",
            "strategies/fixed/phase2.json", "upstreams.lock.json"}.issubset(source["files"]))
        self.assertFalse(any("runs" in Path(name).parts or name.endswith(".zip") for name in hashed))
        self.assertEqual(preserved["source_sha256"], source["sha256"])
        self.assertFalse(preserved["historical_artifacts_rewritten"])
        self.assertEqual(support.source_snapshot_policy(source["files"])["canonical_originals"], {})

    def test_effective_file_change_changes_identity(self):
        source = support.source_identity()
        original = support.file_hash
        target = support.ROOT / "followups/phase3b_seq2_v1/editor.py"
        with patch.object(support, "file_hash", side_effect=lambda path:
                "0" * 64 if Path(path) == target else original(path)):
            changed = support.source_identity()
        self.assertNotEqual(changed["sha256"], source["sha256"])

    def test_private_captured_and_noncanonical_names_fail_before_metadata(self):
        for name in (".ENV", "x/.env.local", "x/auth.json", "x/credentials.json",
                "x/credential-binding.json", ".writer.lock", "x/.cache/a", "x/__pycache__/a",
                "runs/old.py", "x/source/old.py", "x/prior-source/old.py", "x/old.STDOUT.log",
                "x/stderr/old.py", "../escape", "/absolute", "a\\b", "a:b", ".", "a//b", "a/./b"):
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("unsafe metadata")), \
                    self.assertRaises(ContractError):
                support.source_snapshot_policy({name: "0" * 64})

    def test_manifest_names_are_checked_before_content_hashing(self):
        manifest = {"kind": "buddha2-effective-source-inputs-v2", "files": ["runs/old.py"]}
        with patch.object(support, "read", return_value=manifest), \
                patch.object(support, "file_hash", side_effect=AssertionError("unsafe content")), \
                self.assertRaises(ContractError):
            support.source_identity()

    def test_linked_effective_source_is_rejected(self):
        target = support.ROOT / "followups/phase3b_seq2_v1/editor.py"
        original = Path.lstat

        def linked(path, *args, **kwargs):
            return SimpleNamespace(st_mode=0o120777, st_file_attributes=0x400) \
                if path == target else original(path, *args, **kwargs)

        with patch.object(Path, "lstat", linked), self.assertRaisesRegex(ContractError, "linked"):
            support.source_identity()

    def test_old_prepared_study_is_rejected_before_current_or_historical_source_reads(self):
        old = {"kind": "phase3b-seq2-study-v1"}
        with patch.object(workflow, "path", side_effect=lambda value: value), \
                patch.object(workflow, "read", return_value=copy.deepcopy(old)), \
                patch.object(workflow, "source_identity", side_effect=AssertionError("source read")), \
                self.assertRaisesRegex(ContractError, "study seal"):
            workflow.load_study(Path("unused-study.json"))


if __name__ == "__main__":
    unittest.main()
