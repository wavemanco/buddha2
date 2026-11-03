"""P2-R host inspection, stdin-only secret and fail-before-client boundaries."""

import copy
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2 import IMAGE_ID
from buddha2.phase2_dispatch import writer_lock
from buddha2.phase2_release_launch import (
    _ENVIRONMENT,
    HOST_PROJECT,
    HOST_RUNS,
    _bind_credentials,
    _credentials,
    _path,
    execute,
    execution_command,
    main,
    validate_inspection,
)

STUDY = Path("/results/launch-fixture/study.json")
GRANT = Path("/results/launch-fixture/grant.json")
INSPECTION = Path("/results/launch-fixture/inspection.json")


def checked(mode="mock"):
    return {"kind": "phase2-release-preflight-v1", "study_sha256": "a" * 64,
            "control_policy_sha256": "b" * 64, "launcher_sha256": "c" * 64,
            "grant_sha256": "d" * 64, "journal_id": "e" * 64,
            "study_path": str(STUDY), "grant_path": str(GRANT), "stage": "first", "mode": mode,
            "fixture": mode != "provider", "configuration_only": mode == "provider-config",
            "run": "/results/phase2-release-r018/" + "a" * 64 + ("/live" if mode == "provider" else "/mock"),
            "credential_access": False, "provider_requests": 0}


def inspection(mode="mock"):
    value = checked(mode)
    container = {
        "container_id": "f" * 64, "image": IMAGE_ID, "image_os": "linux", "image_architecture": "amd64",
        "network_mode": "bridge" if mode in ("provider", "provider-config") else "none",
        "read_only_rootfs": True, "privileged": False, "publish_all_ports": False,
        "pids_limit": 256, "memory": 4294967296, "nano_cpus": 2000000000,
        "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none",
        "working_dir": "/workspace", "entrypoint": ["python"], "open_stdin": True, "tty": False,
        "port_bindings": {}, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges"],
        "state_at_inspection": "created",
        "environment_names": sorted(_ENVIRONMENT),
        "command": execution_command(STUDY, GRANT, "first", mode, INSPECTION),
        "mounts": [{"type": "bind", "source": HOST_PROJECT, "destination": "/workspace", "rw": False},
                   {"type": "bind", "source": HOST_RUNS, "destination": "/results", "rw": True}],
    }
    record = {"kind": "phase2-release-host-inspection-v1", "preflight": value, "container": container}
    return record | {"inspection_sha256": digest(record)}


def reseal(record):
    record["inspection_sha256"] = digest({key: value for key, value in record.items() if key != "inspection_sha256"})
    return record


class ReleaseLaunchTests(unittest.TestCase):
    def test_supported_mock_and_provider_configuration_inspections_are_distinct(self):
        for mode in ("mock", "provider", "provider-config"):
            validate_inspection(inspection(mode), checked(mode), inspection=INSPECTION)
        with self.assertRaises(ContractError):
            validate_inspection(inspection("mock"), checked("provider"), inspection=INSPECTION)
        self.assertNotIn("fixture-not-a-secret", json.dumps(inspection()))
        self.assertNotIn("API_KEY", json.dumps(inspection()))

    def test_recomputed_hash_cannot_authorize_unsafe_image_mount_environment_or_command(self):
        changes = [
            lambda row: row["container"].update(image="sha256:" + "0" * 64),
            lambda row: row["container"].update(network_mode="bridge"),
            lambda row: row["container"].update(privileged=True),
            lambda row: row["container"].update(memory=1),
            lambda row: row["container"].update(read_only_rootfs=False),
            lambda row: row["container"]["command"].append("--unbound-argument"),
            lambda row: row["container"]["environment_names"].append("OPENAI_API_KEY"),
            lambda row: row["container"]["mounts"][0].update(rw=True),
            lambda row: row["container"]["mounts"][0].update(source=r"C:\outside\project"),
            lambda row: row["container"]["mounts"].append({"type": "bind", "source": r"C:\outside", "destination": "/extra", "rw": False}),
            lambda row: row["container"].update(port_bindings={"8080/tcp": [{"HostPort": "8080"}]}),
            lambda row: row["preflight"].update(grant_sha256="0" * 64),
        ]
        for change in changes:
            row = copy.deepcopy(inspection())
            change(row)
            with self.assertRaises(ContractError):
                validate_inspection(reseal(row), checked(), inspection=INSPECTION)
        row = inspection()
        row["inspection_sha256"] = "0" * 64
        with self.assertRaises(ContractError):
            validate_inspection(row, checked(), inspection=INSPECTION)

    def test_only_explicit_bounded_stdin_keys_are_accepted(self):
        valid = {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}
        self.assertEqual(_credentials(io.StringIO(json.dumps(valid))), valid)
        for bad in ({}, valid | {"extra": "x"}, valid | {"openai_api_key": ""},
                    valid | {"anthropic_api_key": "space is invalid"}, valid | {"openai_api_key": "x\ny"},
                    valid | {"anthropic_api_key": "x" * 4097}):
            with self.assertRaises(ContractError):
                _credentials(io.StringIO(json.dumps(bad)))
        with self.assertRaises(ContractError):
            _credentials(io.StringIO("x" * 16385))

    def test_invalid_release_fails_before_stdin_or_transport_construction(self):
        fake_release = types.ModuleType("buddha2.phase2_release")
        fake_release.launch_execute = Mock(side_effect=AssertionError("must not execute"))
        stream = Mock()
        stream.read.side_effect = AssertionError("must not read keys")
        with (patch.dict(sys.modules, {"buddha2.phase2_release": fake_release}),
              patch("buddha2.phase2_release_launch.preflight", side_effect=ContractError("rejected")),
              patch("sys.stdin", stream),
              patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=AssertionError("must not create client"))):
            with self.assertRaises(ContractError):
                execute(STUDY, GRANT, "first", "provider", INSPECTION)
        stream.read.assert_not_called()
        fake_release.launch_execute.assert_not_called()

    def test_configuration_only_record_can_never_dispatch_or_read_credentials(self):
        fake_release = types.ModuleType("buddha2.phase2_release")
        fake_release.launch_execute = Mock(side_effect=AssertionError("must not execute"))
        stream = Mock()
        stream.read.side_effect = AssertionError("must not read keys")
        with (patch.dict(sys.modules, {"buddha2.phase2_release": fake_release}),
              patch("buddha2.phase2_release_launch.preflight", return_value=checked("provider-config")),
              patch("buddha2.phase2_release_launch.read_json", return_value=inspection("provider-config")),
              patch("sys.stdin", stream)):
            with self.assertRaisesRegex(ContractError, "configuration inspection"):
                execute(STUDY, GRANT, "first", "provider-config", INSPECTION)
        stream.read.assert_not_called()
        fake_release.launch_execute.assert_not_called()

    def test_actual_runtime_mode_must_match_before_provider_stdin_is_read(self):
        fake_release = types.ModuleType("buddha2.phase2_release")
        fake_release.launch_execute = Mock(side_effect=AssertionError("must not execute"))
        stream = Mock()
        stream.read.side_effect = AssertionError("must not read keys")
        with (patch.dict(sys.modules, {"buddha2.phase2_release": fake_release}),
              patch("buddha2.phase2_release_launch.preflight", return_value=checked("provider")),
              patch("buddha2.phase2_release_launch.read_json", return_value=inspection("provider")),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "mock", "BUDDHA2_OFFLINE": "1"}),
              patch("sys.stdin", stream)):
            with self.assertRaisesRegex(ContractError, "runtime network"):
                execute(STUDY, GRANT, "first", "provider", INSPECTION)
        stream.read.assert_not_called()

    def test_provider_handshake_precedes_stdin_and_client_construction(self):
        output = io.StringIO()
        events = []

        class ExplicitInput(io.StringIO):
            def read(self, *args):
                self.assert_ready = json.loads(output.getvalue().strip())
                if self.assert_ready.get("credential_input_ready") is not True:
                    raise AssertionError("keys read before readiness handshake")
                events.append("stdin")
                return super().read(*args)

        transport = types.SimpleNamespace(_anthropic=Mock(), _openai=Mock())

        def construct(**kwargs):
            self.assertEqual(events, ["stdin"])
            self.assertEqual(binding.call_count, 1)
            self.assertEqual(kwargs["anthropic_api_key"], "fixture-a")
            self.assertEqual(kwargs["openai_api_key"], "fixture-o")
            events.append("client")
            return transport

        fake_release = types.ModuleType("buddha2.phase2_release")
        fake_release.launch_execute = Mock(return_value={"fixture_provider_boundary": True})
        stream = ExplicitInput(json.dumps({"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}))
        with (patch.dict(sys.modules, {"buddha2.phase2_release": fake_release}),
              patch("buddha2.phase2_release_launch.preflight", return_value=checked("provider")),
              patch("buddha2.phase2_release_launch.read_json", return_value=inspection("provider")),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch("buddha2.phase2_release_launch.Path.iterdir", return_value=[Path("/sys/class/net/lo"), Path("/sys/class/net/eth0")]),
              patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=construct),
              patch("buddha2.phase2_release_launch.write_once") as binding,
              patch("sys.stdin", stream), patch("sys.stdout", output)):
            result = execute(STUDY, GRANT, "first", "provider", INSPECTION)
        self.assertEqual(result, {"fixture_provider_boundary": True})
        self.assertEqual(events, ["stdin", "client"])
        self.assertNotIn("fixture-a", output.getvalue())
        self.assertNotIn("fixture-o", output.getvalue())
        transport._anthropic.close.assert_called_once()
        transport._openai.close.assert_called_once()
        binding.assert_called_once()
        self.assertNotIn("fixture-a", json.dumps(binding.call_args.args[1]))
        self.assertNotIn("fixture-o", json.dumps(binding.call_args.args[1]))

    def test_credential_binding_is_hashed_idempotent_and_rejects_key_changes(self):
        with tempfile.TemporaryDirectory(dir="/results") as temporary:
            value = checked("provider") | {"run": temporary}
            keys = {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}
            first = _bind_credentials(value, keys)
            self.assertEqual(_bind_credentials(value, keys), first)
            self.assertNotIn("fixture-a", json.dumps(first))
            self.assertNotIn("fixture-o", json.dumps(first))
            for fingerprint in first["credential_fingerprints"].values():
                self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
            with self.assertRaisesRegex(ContractError, "immutable artifact"):
                _bind_credentials(value, keys | {"openai_api_key": "fixture-changed"})

    def test_concurrent_launch_is_rejected_before_readiness_stdin_or_sdk(self):
        output = io.StringIO()
        stream = Mock()
        with tempfile.TemporaryDirectory(dir="/results") as temporary:
            value = checked("provider") | {"run": temporary}
            with (writer_lock(Path(temporary) / "launch-owner"),
                  patch("buddha2.phase2_release_launch.preflight", return_value=value),
                  patch("buddha2.phase2_dispatch.DirectSDKTransport") as client,
                  patch("sys.stdin", stream), patch("sys.stdout", output)):
                with self.assertRaisesRegex(ContractError, "concurrent writer"):
                    execute(STUDY, GRANT, "first", "provider", INSPECTION)
            client.assert_not_called()
            stream.read.assert_not_called()
            self.assertEqual(output.getvalue(), "")

    def test_unapproved_input_paths_are_rejected(self):
        for path in (Path("relative.json"), Path("/tmp/input.json"), Path("/results/../tmp/input.json")):
            with self.assertRaises(ContractError):
                _path(path)

    def test_entrypoint_suppresses_unknown_exception_text(self):
        output, errors = io.StringIO(), io.StringIO()
        with (patch("buddha2.phase2_release_launch.preflight", side_effect=RuntimeError("fixture-secret-must-not-appear")),
              patch("sys.stdout", output), patch("sys.stderr", errors)):
            result = main(["check", "--study", str(STUDY), "--grant", str(GRANT),
                           "--stage", "first", "--mode", "provider"])
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("fixture-secret-must-not-appear", errors.getvalue())
        self.assertTrue(json.loads(errors.getvalue())["raw_error_suppressed"])


if __name__ == "__main__":
    unittest.main()
