"""Pure synthetic checks for typed bootstrap diagnostics; no worker invocation."""
import builtins
import importlib.util
import unittest
from unittest.mock import patch

from .test_bootstrap import ROOT, bootstrap_observation


class BD1DiagnosticTests(unittest.TestCase):
    def test_spawn_entry_defers_workflow_import_until_guarded_functions(self):
        original = builtins.__import__
        def checked(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "followups.phase3b_seq2_v1" and "workflow" in fromlist:
                raise AssertionError("spawn entry eagerly imported workflow")
            return original(name, globals, locals, fromlist, level)
        spec = importlib.util.spec_from_file_location("bd1_spawn_entry_unit", ROOT / "evidence/phase3b-seq2-c2-v1/composed_acceptance.py")
        if spec is None or spec.loader is None:
            raise AssertionError("spawn-entry fixture cannot load")
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", checked):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.runtime_output))
        self.assertTrue(callable(module.saved_replay))

    def test_error_and_cleanup_retained_without_unrelated_payload(self):
        result = bootstrap_observation({"canonical_status": "failed", "canonical_error_type": "canonical_timeout",
            "worker_stopped": True, "cleanup_proof": "stopped", "unrelated_payload": "omitted",
            "summary": {"import_privacy": {"dotenv_open_denials": 1, "harness2_config_imported": True,
                                          "unrelated_payload": "omitted"}}})
        self.assertEqual(result["canonical_error_type"], "canonical_timeout")
        self.assertTrue(result["worker_stopped"])
        self.assertEqual(result["import_privacy"], {"dotenv_open_denials": 1, "harness2_config_imported": True})
        self.assertNotIn("unrelated_payload", result)

    def test_untyped_or_unbounded_diagnostic_rejected(self):
        for result in ({"worker_stopped": 1}, {"canonical_error_type": "arbitrary payload with spaces"},
                       {"summary": {"import_privacy": {"dotenv_open_denials": True}}}):
            with self.subTest(fields=tuple(result)), self.assertRaises(ValueError):
                bootstrap_observation(result)
