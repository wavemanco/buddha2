"""Fail-before-credential boundary and actual SDK mock stdin checks."""
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2 import IMAGE_ID
from buddha2.phase2_am1_controls import BILLING_PROFILE
from buddha2.phase2_dispatch import build_request, writer_lock
from followups.rank_format_v1 import launch

STUDY = Path("/results/rank-launch-fixture/study.json")
GRANT = Path("/results/rank-launch-fixture/grant.json")
INSPECTION = Path("/results/rank-launch-fixture/inspection.json")


def checked(mode="mock"):
    fixture = mode != "provider"
    run = ("/results/phase2b-rank-format-v1/" + "a" * 64 + "/mock" if fixture
           else "/results/phase2-am1/" + "a" * 64 + "/first-block")
    return {"study_sha256": "a" * 64, "source_sha256": "b" * 64, "policy_sha256": "c" * 64,
            "control_policy_sha256": "d" * 64, "launcher_sha256": "e" * 64,
            "grant_sha256": "f" * 64, "journal_id": "1" * 64, "run": run,
            "journal": run + "/journal", "fixture": fixture, "billing_profile": BILLING_PROFILE,
            "slot_count": 44, "role_counts": {"group": 4, "quality": 40}, "cap_micro_usd": 30000000,
            "study_path": str(STUDY), "grant_path": str(GRANT), "mode": mode,
            "configuration_only": mode == "provider-config"}


def inspection(value):
    mode = value["mode"]
    c = {"container_id": "2" * 64, "image": IMAGE_ID, "image_os": "linux", "image_architecture": "amd64",
         "network_mode": "bridge" if mode in ("provider", "provider-config") else "none",
         "read_only_rootfs": True, "privileged": False, "publish_all_ports": False,
         "pids_limit": 256, "memory": 4294967296, "nano_cpus": 2000000000,
         "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none",
         "working_dir": "/workspace", "entrypoint": ["python"], "open_stdin": True,
         "tty": False, "port_bindings": {}, "state_at_inspection": "created", "cap_drop": ["ALL"],
         "security_opt": ["no-new-privileges"], "environment_names": sorted(launch._ENVIRONMENT),
         "command": launch.command(STUDY, GRANT, mode, INSPECTION),
         "mounts": [{"type": "bind", "source": launch.HOST_PROJECT, "destination": "/workspace", "rw": False},
                    {"type": "bind", "source": launch.HOST_RUNS, "destination": "/results", "rw": True}]}
    return reseal({"kind": "rank-format-host-inspection-v1", "preflight": value, "container": c})


def reseal(value):
    value["inspection_sha256"] = digest({k: v for k, v in value.items() if k != "inspection_sha256"})
    return value


class LauncherTests(unittest.TestCase):
    def test_preflight_rejects_wrong_scope_source_cap_and_journal_before_clients(self):
        good = checked()
        with (patch.object(launch, "runtime_guard"), patch.object(launch, "read_json", return_value={"fixture": True}),
              patch.object(launch, "_workflow_preflight", return_value=good)):
            self.assertEqual(launch.preflight(STUDY, GRANT, "mock")["slot_count"], 44)
        for update in ({"slot_count": 45}, {"cap_micro_usd": 1},
                       {"role_counts": {"group": 4, "quality": 39, "answer": 1}},
                       {"source_sha256": "wrong"}, {"run": "/results/other"},
                       {"journal": good["run"] + "/other"}, {"fixture": False},
                       {"billing_profile": "private"}):
            with (patch.object(launch, "runtime_guard"),
                  patch.object(launch, "read_json", return_value={"fixture": True}),
                  patch.object(launch, "_workflow_preflight", return_value=good | update),
                  patch("buddha2.phase2_dispatch.DirectSDKTransport") as client):
                with self.assertRaises(ContractError):
                    launch.preflight(STUDY, GRANT, "mock")
                client.assert_not_called()

    def test_resealed_unsafe_inspections_fail_before_stdin(self):
        mutations = [lambda r: r["container"].update(image="other"),
                     lambda r: r["container"].update(network_mode="bridge"),
                     lambda r: r["container"].update(read_only_rootfs=False),
                     lambda r: r["container"].update(privileged=True),
                     lambda r: r["container"]["environment_names"].append("OPENAI_API_KEY"),
                     lambda r: r["container"]["mounts"][0].update(source=r"C:\outside"),
                     lambda r: r["container"]["command"].append("unbound"),
                     lambda r: r["preflight"].update(grant_sha256="0" * 64)]
        for mutate in mutations:
            row = copy.deepcopy(inspection(checked()))
            mutate(row)
            with self.assertRaises(ContractError):
                launch.validate_inspection(reseal(row), checked(), INSPECTION)
        with (patch.object(launch, "preflight", side_effect=ContractError("bad gate")),
              patch.object(launch, "_credentials") as keys,
              patch("buddha2.phase2_dispatch.DirectSDKTransport") as client):
            with self.assertRaises(ContractError):
                launch.execute(STUDY, GRANT, "provider", INSPECTION)
            keys.assert_not_called()
            client.assert_not_called()

    def test_config_and_wrong_runtime_cannot_reach_key_read(self):
        for mode in ("provider-config", "provider"):
            value = checked(mode)
            with (patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "read_json", return_value=inspection(value)),
                  patch.object(launch, "_credentials") as keys,
                  patch.object(launch, "_workflow_run") as run,
                  patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "mock", "BUDDHA2_OFFLINE": "1"})):
                with self.assertRaises(ContractError):
                    launch.execute(STUDY, GRANT, mode, INSPECTION)
                keys.assert_not_called()
                run.assert_not_called()

    def test_actual_owner_lock_rejects_concurrency_before_readiness(self):
        Path("/results/rank-launch-tests").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/results/rank-launch-tests") as tmp:
            value = checked("provider") | {"run": tmp}
            with (writer_lock(Path(tmp) / "launch-owner"),
                  patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "_credentials") as keys,
                  patch("sys.stdout", new_callable=io.StringIO) as output):
                with self.assertRaises(ContractError):
                    launch.execute(STUDY, GRANT, "provider", INSPECTION)
                self.assertEqual(output.getvalue(), "")
                keys.assert_not_called()

    def test_provider_handshake_and_key_binding_precede_client(self):
        value = checked("provider")
        order = []
        output = io.StringIO()
        transport = SimpleNamespace(_anthropic=Mock(), _openai=Mock())

        def keys(stream):
            ready = json.loads(output.getvalue())
            self.assertEqual(ready["study_sha256"], value["study_sha256"])
            self.assertEqual(ready["host_inspection_sha256"], inspection(value)["inspection_sha256"])
            order.append("stdin")
            return {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}

        def bind(*args):
            order.append("bind")

        def construct(**kwargs):
            order.append("client")
            return transport

        with (patch.object(launch, "preflight", return_value=value),
              patch.object(launch, "read_json", return_value=inspection(value)),
              patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch.object(launch, "_credentials", side_effect=keys),
              patch.object(launch, "_bind_credentials", side_effect=bind),
              patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=construct),
              patch.object(launch, "_workflow_run", return_value={"provider_calls": 0}),
              patch("sys.stdout", output)):
            self.assertEqual(launch.execute(STUDY, GRANT, "provider", INSPECTION), {"provider_calls": 0})
        self.assertEqual(order, ["stdin", "bind", "client"])
        transport._anthropic.close.assert_called_once()
        transport._openai.close.assert_called_once()

    def test_fake_stdin_pipe_exercises_actual_pinned_sdk_mock_without_sockets(self):
        Path("/results/rank-launch-tests").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/results/rank-launch-tests") as tmp:
            value = checked() | {"run": tmp}
            payload = json.dumps({"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"})

            def run(study, grant, transport):
                transport.select("group", "launcher-fixture.group")
                response = transport.create("group", build_request("group", messages=[{"role": "user", "content": "Synthetic fixture"}]))
                self.assertEqual(response["model"], "gpt-5.6-luna")
                return {"provider_calls": 0, "fixture": True}

            with (patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "read_json", return_value=inspection(value)),
                  patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "mock", "BUDDHA2_OFFLINE": "1"}),
                  patch.object(launch, "_workflow_run", side_effect=run),
                  patch("sys.stdin", io.StringIO(payload)), patch("sys.stdout", new_callable=io.StringIO) as output):
                result = launch.execute(STUDY, GRANT, "mock", INSPECTION)
            self.assertEqual(result["new_mock_http_calls"], 1)
            self.assertNotIn("fixture-not-a-secret", output.getvalue())
            self.assertTrue((Path(tmp) / "wire/launcher-fixture.group.json").is_file())
            self.assertFalse((Path(tmp) / "credential-binding.json").exists())

    def test_source_change_during_key_entry_fails_before_binding_or_client(self):
        value = checked("provider")
        keys = {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}
        with (patch.object(launch, "preflight", side_effect=[value, value, value | {"source_sha256": "3" * 64}]),
              patch.object(launch, "read_json", return_value=inspection(value)),
              patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch.object(launch, "_credentials", return_value=keys),
              patch.object(launch, "_bind_credentials") as bind,
              patch("buddha2.phase2_dispatch.DirectSDKTransport") as client,
              patch("sys.stdout", new_callable=io.StringIO)):
            with self.assertRaisesRegex(ContractError, "changed during credential entry"):
                launch.execute(STUDY, GRANT, "provider", INSPECTION)
            bind.assert_not_called()
            client.assert_not_called()
        self.assertEqual(set(keys.values()), {""})

    def test_entrypoint_suppresses_unknown_exception_text(self):
        with (patch.object(launch, "preflight", side_effect=RuntimeError("never-print-this")),
              patch("sys.stderr", new_callable=io.StringIO) as errors):
            code = launch.main(["--command", "preflight", "--study", str(STUDY), "--grant", str(GRANT), "--mode", "mock"])
        self.assertEqual(code, 2)
        self.assertNotIn("never-print-this", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
