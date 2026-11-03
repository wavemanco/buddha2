"""Narrow artifact guards; no container, provider, socket or subprocess is started."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("keyless_preflight_artifact", HERE / "provider_preflight.py")
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class Guards(unittest.TestCase):
    def test_actual_host_container_command_is_posix(self):
        command = helper.container_command()
        self.assertEqual(command, ["-B", "/workspace/" + helper.REL + "/provider_preflight.py", "--inside"])
        self.assertTrue(command[1].startswith("/workspace/runs/"))
        self.assertTrue(command[1].endswith("/provider-preflight-v2/provider_preflight.py"))
        self.assertNotIn("\\", command[1])

    def test_private_and_stream_before_metadata(self):
        for name in (*helper.PRIVATE, "capture.stderr.log", "stdout.json"):
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("metadata reached")):
                with self.assertRaises(ValueError):
                    helper.safe("runs/" + name)

    def test_escaped_before_metadata(self):
        for name in ("../outside", "/outside", "C:/outside", "runs\\outside"):
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("metadata reached")):
                with self.assertRaises(ValueError):
                    helper.safe(name)

    def test_receipt_mismatch_before_any_json_read(self):
        with patch.object(helper, "sha", return_value="0" * 64), patch.object(helper, "read", side_effect=AssertionError("read reached")):
            with self.assertRaisesRegex(ValueError, "receipt changed"):
                helper.bundle()

    def test_socket_and_subprocess_denial(self):
        for event in ("socket.__new__", "socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"):
            with self.subTest(event=event), self.assertRaises(RuntimeError):
                helper.activity(event, ())

    def test_sdk_constructor_denial(self):
        with self.assertRaises(RuntimeError):
            helper.deny_sdk(api_key="fixture-no-key")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Guards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    proof = {"kind": "phase3a-hi-keyless-preflight-guards-v1", "passed": result.wasSuccessful(),
        "tests": result.testsRun, "provider_calls": 0, "actual_network_or_subprocess_started": False,
        "artifact_guard_functions_exercised": True, "frozen_functions_patched": False}
    with (HERE / "guard-proof-v1.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, indent=2, sort_keys=True)
        stream.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
