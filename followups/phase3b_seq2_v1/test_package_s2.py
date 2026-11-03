"""Packager privacy denials must precede all metadata, including direct inputs."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .support import ROOT


class PackagePrivacyTests(unittest.TestCase):
    def producer(self):
        spec = importlib.util.spec_from_file_location("s2_packet_json_test", ROOT / "evidence/phase3b-seq2-v1/package_public.py")
        if spec is None or spec.loader is None:
            self.fail("packet producer is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_packet_reader_rejects_duplicate_nonfinite_and_nonobject_data(self):
        module = self.producer()
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "record.json"
            for raw in ('{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}', '[]'):
                target.write_text(raw, encoding="utf-8")
                with self.subTest(raw=raw), patch.object(module, "safe", return_value=target), self.assertRaises(ValueError):
                    module.read("public-fixture.json")
            target.write_text('{"a": 1}', encoding="utf-8")
            with patch.object(module, "safe", return_value=target):
                self.assertEqual(module.read("public-fixture.json"), {"a": 1})

    def test_every_private_or_cache_component_is_rejected_before_metadata(self):
        entry = ROOT / "evidence/phase3b-seq2-v1/package_public.py"
        spec = importlib.util.spec_from_file_location("s2_packet_privacy_test", entry)
        self.assertIsNotNone(spec)
        if spec is None or spec.loader is None:
            self.fail("packet producer is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        names = (".ENV", "auth.json", "credentials.json", ".writer.lock", "credential-binding.json",
                 "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache", "stdout.log", "stderr.log")
        with patch.object(Path, "lstat", side_effect=AssertionError("private metadata attempted")):
            for name in names:
                relative = "runs/phase3b-seq2-v1/verification-fixture/" + name + "/marker.json"
                with self.subTest(name=name):
                    self.assertFalse(module.public(relative))
                    with self.assertRaises(ValueError):
                        module.safe(relative, missing=True)
