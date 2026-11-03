"""Prospective SS01-SS10: canonical originals, public copies and zero stream-copy IO."""
from __future__ import annotations

import builtins
import copy
import importlib.util
import io
import os
import stat
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from . import support, workflow


def stream_name(value) -> bool:
    if not isinstance(value, (str, bytes, os.PathLike)):
        return False
    return any("stdout" in part.casefold() or "stderr" in part.casefold()
        for part in os.fsdecode(os.fspath(value)).replace("\\", "/").split("/"))


@contextmanager
def no_retained_stream_io():
    """Trap construction and lower metadata/content/write calls, before delegation."""
    attempts = []

    def guard(value):
        if isinstance(value, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(value)).replace("\\", "/")
            if "/source/" in name.casefold() and stream_name(name):
                attempts.append(name)
                raise AssertionError("retained stream path reached a lower filesystem call")

    def wrapped(original, *, second=False):
        def call(value, *args, **kwargs):
            guard(value)
            if second and args:
                guard(args[0])
            return original(value, *args, **kwargs)
        return call

    division = Path.__truediv__

    def divide(left, right):
        if "source" in (part.casefold() for part in left.parts) and stream_name(right):
            attempts.append(str(right))
            raise AssertionError("retained stream destination was constructed")
        result = division(left, right)
        guard(result)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(Path, "__truediv__", divide))
        for module, name in ((os, "stat"), (os, "lstat"), (os, "open"), (os, "mkdir"),
                (os, "listdir"), (os, "scandir"), (os, "unlink"), (io, "open"), (builtins, "open")):
            stack.enter_context(patch.object(module, name, wrapped(getattr(module, name))))
        for name in ("link", "rename", "replace"):
            stack.enter_context(patch.object(os, name, wrapped(getattr(os, name), second=True)))
        yield attempts


def lexical_stream_inventory(directory: Path) -> list[str]:
    """Never stat a stream entry, even if an accidental copy exists."""
    found = []
    for name in os.listdir(directory):
        if stream_name(name):
            found.append(name)
            continue
        if name.casefold() in support.PRIVATE:
            continue
        item = directory / name
        if item.is_dir():
            found.extend(lexical_stream_inventory(item))
    return found


class SourceSnapshotCases(unittest.TestCase):
    source: dict
    streams: dict

    @classmethod
    def setUpClass(cls):
        cls.source = support.source_identity()
        cls.streams = support._offline_streams(cls.source["files"])
        support.safe(support.BASE).mkdir(parents=True, exist_ok=True)

    def namespace(self):
        return tempfile.TemporaryDirectory(prefix="source-snapshot-cases-", dir=support.BASE)

    def producer(self):
        spec = importlib.util.spec_from_file_location("s2_snapshot_packet_test",
            support.ROOT / "evidence/phase3b-seq2-v1/package_public.py")
        if spec is None or spec.loader is None:
            self.fail("packet producer is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def save_tampered_study(self, target: Path, study: dict) -> None:
        study["study_sha256"] = digest({key: value for key, value in study.items() if key != "study_sha256"})
        import json
        target.write_text(json.dumps(study), encoding="utf-8")

    def test_actual_main_supervised_and_auxiliary_prepare_load_and_grant_never_touch_stream_copies(self):
        policies = []
        with self.namespace() as temporary:
            for label, supervised in (("main", False), ("supervised", True), ("native-negative-auxiliary", False)):
                with self.subTest(profile=label), no_retained_stream_io() as attempts:
                    output = Path(temporary) / label / "release"
                    study = workflow.prepare(output, supervised_fixture=supervised)
                    policies.append(study["source_snapshot_policy"])
                    self.assertEqual(study["source"], support.source_identity())
                    self.assertEqual(study["source_snapshot_policy"]["canonical_originals"], self.streams)
                    self.assertEqual(workflow.load_study(output / "study.json"), study)
                    self.assertTrue(workflow.make_grant(output / "study.json", True))
                    self.assertEqual(lexical_stream_inventory(output / "source"), [])
                    for name, expected in study["source"]["files"].items():
                        if name in self.streams:
                            continue
                        self.assertEqual(support.file_hash(output / "source" / name), expected)
                    self.assertEqual(attempts, [])
        self.assertEqual(policies, [policies[0]] * 3)

    def test_missing_extra_tampered_and_foreign_policy_fail_without_retained_stream_access(self):
        with self.namespace() as temporary:
            output = Path(temporary) / "release"
            study = workflow.prepare(output)
            variants = []
            missing = copy.deepcopy(study)
            missing.pop("source_snapshot_policy")
            variants.append(missing)
            for field, value in (("extra", True), ("kind", "foreign"),
                    ("canonical_originals", {}), ("offline_classification_receipt", {
                        "path": "runs/foreign/source/untrusted.stdout.log", "sha256": "0" * 64})):
                changed = copy.deepcopy(study)
                changed["source_snapshot_policy"][field] = value
                variants.append(changed)
            for changed in variants:
                with self.subTest(policy=changed.get("source_snapshot_policy")), no_retained_stream_io() as attempts:
                    self.save_tampered_study(output / "study.json", changed)
                    with self.assertRaisesRegex(ContractError, "snapshot policy"):
                        workflow.load_study(output / "study.json")
                    self.assertEqual(attempts, [])

    def test_missing_or_tampered_public_retained_copy_fails(self):
        with self.namespace() as temporary:
            output = Path(temporary) / "release"
            workflow.prepare(output)
            retained = output / "source/followups/phase3b_seq2_v1/accounting.py"
            raw = retained.read_bytes()
            for missing in (False, True):
                with self.subTest(missing=missing):
                    retained.write_bytes(b"offline-corruption")
                    if missing:
                        retained.unlink()
                    with no_retained_stream_io() as attempts, self.assertRaises((ContractError, FileNotFoundError)):
                        workflow.load_study(output / "study.json")
                    self.assertEqual(attempts, [])
                    retained.write_bytes(raw)

    def test_canonical_original_and_pinned_receipt_tampering_fail(self):
        with self.namespace() as temporary:
            output = Path(temporary) / "release"
            workflow.prepare(output)
            original_hash = support._parent_file_hash
            name = next(iter(self.streams))
            def changed_original(value, expected, streams):
                return "0" * 64 if value == name else original_hash(value, expected, streams)
            with patch.object(support, "_parent_file_hash", side_effect=changed_original), \
                    no_retained_stream_io(), self.assertRaises(ContractError):
                workflow.load_study(output / "study.json")
            file_hash = support.file_hash
            def changed_receipt(value):
                return "0" * 64 if value == support.ROOT / support.OFFLINE_RECEIPT else file_hash(value)
            with patch.object(support, "file_hash", side_effect=changed_receipt), \
                    no_retained_stream_io(), self.assertRaises(ContractError):
                workflow.load_study(output / "study.json")

    def test_private_cache_and_malformed_source_names_fail_before_metadata(self):
        for name in (".ENV", "x/auth.json", "x/Credentials.json", "x/credential-binding.json", ".writer.lock",
                "x/.cache/a", "x/__pycache__/a", "x/.mypy_cache/a", "x/.ruff_cache/a", "x/.pytest_cache/a",
                "../escape", "/absolute", "a\\b", "a:b", ".", "a//b", "a/./b"):
            changed = {**self.source["files"], name: "0" * 64}
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("unsafe metadata")), \
                    self.assertRaises(ContractError):
                support.source_snapshot_policy(changed)

    def test_unknown_or_substituted_stream_fails_before_its_metadata(self):
        unknown = "evidence/unclassified.STDOUT.log"
        original = Path.lstat
        def metadata(value, *args, **kwargs):
            if unknown in value.as_posix():
                self.fail("unknown stream metadata reached")
            return original(value, *args, **kwargs)
        for replace in (False, True):
            changed = {**self.source["files"], unknown: "0" * 64}
            if replace:
                changed.pop(next(iter(self.streams)))
            with self.subTest(replace=replace), patch.object(Path, "lstat", metadata), self.assertRaises(ContractError):
                support.source_snapshot_policy(changed)

    def test_accidental_retained_stream_name_is_skipped_lexically_without_metadata(self):
        with self.namespace() as temporary:
            output = Path(temporary) / "release"
            workflow.prepare(output)
            directory = output / "source"
            listdir = os.listdir
            def listing(value):
                names = listdir(value)
                return names + ["accidental.stdout.log"] if Path(value) == directory else names
            with no_retained_stream_io() as attempts, patch.object(os, "listdir", side_effect=listing):
                self.assertEqual(lexical_stream_inventory(directory), ["accidental.stdout.log"])
                workflow.load_study(output / "study.json")
                self.assertEqual(attempts, [])

    def test_public_copy_symlink_and_original_reparse_fail_before_content(self):
        with self.namespace() as temporary:
            output = Path(temporary) / "release"
            workflow.prepare(output)
            retained = output / "source/followups/phase3b_seq2_v1/accounting.py"
            original = Path.lstat
            def linked(value, *args, **kwargs):
                return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0x400) \
                    if value == retained else original(value, *args, **kwargs)
            with patch.object(Path, "lstat", linked), self.assertRaisesRegex(ContractError, "linked"):
                workflow.load_study(output / "study.json")
            name = next(iter(self.streams))
            canonical = support.ROOT / name
            def reparse(value, *args, **kwargs):
                return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400) \
                    if value == canonical else original(value, *args, **kwargs)
            with patch.object(Path, "lstat", reparse), self.assertRaisesRegex(ContractError, "link"):
                support._parent_file_hash(name, self.streams[name], self.streams)

    def test_standalone_packager_uses_identical_policy_and_only_canonical_classification(self):
        module = self.producer()
        with no_retained_stream_io() as attempts:
            policy = module.source_snapshot_policy(self.source["files"])
            self.assertEqual(policy, support.source_snapshot_policy(self.source["files"]))
            self.assertEqual(set(policy["canonical_originals"]), module.OFFLINE_NAMES)
            for name in self.streams:
                relative = "runs/phase3b-seq2-v1/auxiliary/release/source/" + name
                self.assertFalse(module.public(relative, policy["canonical_originals"]))
                with self.assertRaises(ValueError):
                    module.safe(relative, offline_streams=policy["canonical_originals"])
            self.assertEqual(attempts, [])
        for name in ("evidence/unclassified.stderr.log", "x/.ENV", "x/.cache/a", "../escape", "."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.source_snapshot_policy({**self.source["files"], name: "0" * 64})


if __name__ == "__main__":
    unittest.main()
