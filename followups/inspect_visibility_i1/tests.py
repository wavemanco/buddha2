"""Boundary and actual saved-log checks; no providers or native reruns."""

import copy
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import importer, paths, setup


class ImportChecks(unittest.TestCase):
    def test_private_escape_unknown_precede_io(self):
        for path in [".env", "x/AUTH.JSON", "../result.json", "/result.json", "x\\result.json", "C:/result.json", "x/./result.json", "x//result.json"]:
            with self.subTest(path=path), patch.object(Path, "lstat", side_effect=AssertionError("metadata touched")):
                with self.assertRaises(ValueError):
                    importer.safe_read(Path("/never-open"), path)
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata touched")):
            with self.assertRaises(ValueError):
                importer.read_cases(Path("/never-open"), ["unknown"])
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata touched")):
            for root in [Path("/inputs/../elsewhere"), Path("/private/.env")]:
                with self.assertRaises(ValueError):
                    importer.safe_read(root, "result.json")
            for raw in ["/out/../outside", "/out/.env/result", "/outside/result", "/out/./result"]:
                with self.assertRaises(ValueError):
                    paths.checked_path(raw, Path("/out"), missing=True)

    def test_link_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "linked"):
                importer.safe_read(root, "link/result.json")

    def test_strict_json(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'null trailing']:
            with self.assertRaises(ValueError):
                importer.decode(raw)

    def test_hash_mismatch_rejected(self):
        with patch.object(importer, "safe_read", return_value=b"{}"):
            with self.assertRaisesRegex(ValueError, "hash"):
                importer.read_cases(Path("/inputs"), list(importer.CASES))

    def test_reuse_copies_only_manifested_wheel_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, out = root / "old", root / "new"
            (old / "wheels").mkdir(parents=True)
            out.mkdir()
            data = b"synthetic exact wheel bytes"
            wheel = "fixture-1.0-py3-none-any.whl"
            (old / "wheels" / wheel).write_bytes(data)
            (old / "wheels" / ".env").write_bytes(b"private tripwire fixture")
            (old / "wheels" / "unlisted.whl").symlink_to(root / "outside-unopened")
            manifest = [{"filename": wheel, "sha256": hashlib.sha256(data).hexdigest()}]
            (old / "wheel-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (old / "resolution.json").write_bytes(b"{}")
            actual_stat, actual_read = Path.lstat, Path.read_bytes
            touched = []

            def guarded_stat(path, *args, **kwargs):
                if path.name in {".env", "unlisted.whl", "outside-unopened"}:
                    raise AssertionError("unlisted/private metadata touched")
                return actual_stat(path, *args, **kwargs)

            def guarded_read(path, *args, **kwargs):
                touched.append(path.name)
                if path.name in {".env", "unlisted.whl", "outside-unopened"}:
                    raise AssertionError("unlisted/private bytes touched")
                return actual_read(path, *args, **kwargs)

            with patch.object(Path, "lstat", guarded_stat), patch.object(Path, "read_bytes", guarded_read):
                setup.copy_reviewed_wheels(old, out, root)
            self.assertEqual([p.name for p in (out / "wheels").iterdir()], [wheel])
            self.assertEqual((out / "wheels" / wheel).read_bytes(), data)
            self.assertEqual(touched, ["wheel-manifest.json", wheel, "resolution.json"])
            for bad in [{"filename": "../bad.whl", "sha256": "0" * 64}, {"filename": ".env", "sha256": "0" * 64}, {"filename": wheel, "sha256": 0}, "not-an-object"]:
                (old / "wheel-manifest.json").write_text(json.dumps([bad]), encoding="utf-8")
                with patch.object(Path, "lstat", guarded_stat):
                    with self.assertRaises(ValueError):
                        setup.copy_reviewed_wheels(old, root / "must-not-exist", root)
            (old / "wheel-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            for leaf in ["wheel-manifest.json", "resolution.json"]:
                path = old / leaf
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(root / "outside-unopened")

                def deny_link_read(candidate, *args, **kwargs):
                    if candidate.name == leaf:
                        raise AssertionError("linked control file read")
                    return actual_read(candidate, *args, **kwargs)

                with patch.object(Path, "read_bytes", deny_link_read):
                    with self.assertRaisesRegex(ValueError, "linked"):
                        setup.copy_reviewed_wheels(old, root / "must-not-exist", root)
                path.unlink()
                path.write_bytes(original)

    def test_actual_frozen_inputs_and_failure_meaning(self):
        cases = importer.read_cases(Path("/inputs"), list(importer.CASES))
        fixed, failed = [importer.project(case) for case in cases]
        self.assertTrue(fixed["native_reply_ok"])
        self.assertFalse(failed["native_reply_ok"])
        self.assertTrue(failed["fixture_expectation_passed"])
        self.assertIsNone(failed["native_final_text"])
        self.assertNotEqual(fixed["qualified_id"], failed["qualified_id"])
        self.assertEqual(fixed["native_result"]["failure"], None)
        self.assertIn("failure", fixed["native_result"])
        self.assertNotIn("temperature", fixed["native_wire"]["records"][0]["request"])

    def test_changed_status_config_role_rejected(self):
        case = importer.read_cases(Path("/inputs"), list(importer.CASES))[0]
        for key, value in [("native_reply_ok", False), ("passed", 1), ("provider_calls", 1), ("label", "unknown")]:
            altered = copy.deepcopy(case["result"])
            altered[key] = value
            with self.assertRaises(ValueError):
                importer.validate_case(case["case"], altered, case["wire"])
        for key, value in [("model", "unknown"), ("role", "grader")]:
            altered = copy.deepcopy(case["wire"])
            altered["records"][0][key] = value
            with self.assertRaises(ValueError):
                importer.validate_case(case["case"], case["result"], altered)
        altered = copy.deepcopy(case["wire"])
        altered["records"][0]["request"]["output_config"] = {"effort": "low"}
        with self.assertRaises(ValueError):
            importer.validate_case(case["case"], case["result"], altered)

    def test_z_deliberate_containment_negatives(self):
        counts = importer.block_execution()
        from inspect_ai.model import Model, ModelAPI

        with self.assertRaisesRegex(RuntimeError, "construction forbidden"):
            Model(None)
        with self.assertRaisesRegex(RuntimeError, "construction forbidden"):
            ModelAPI.__init__(object())
        with socket.socket() as connection:
            with self.assertRaisesRegex(RuntimeError, "network forbidden"):
                connection.connect(("203.0.113.1", 443))
        with self.assertRaisesRegex(RuntimeError, "network forbidden"):
            socket.getaddrinfo("example.invalid", 443)
        self.assertEqual(len(counts["model_constructor_attempts"]), 2)
        self.assertEqual(len(counts["external_socket_attempts"]), 2)
        Path("/out/containment-negative.json").write_text(json.dumps({
            "deliberate_expected_probes": counts, "all_blocked_before_execution": True,
            "not_actual_import_attempt_counts": True}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
