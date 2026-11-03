"""Fail-before-credential boundary and actual SDK mock stdin checks."""
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess  # nosec B404
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest
from buddha2.phase2_am1_controls import BILLING_PROFILE
from buddha2.phase2_dispatch import build_request, writer_lock
from followups.phase3a_v1 import launch
from followups.phase3a_v1.accounting import IMAGE_ID
from followups.phase3a_v1.support import ROOT
from followups.phase3a_v1.tests.test_accounting import AUTHORITY, slots

STUDY = Path("/results/phase3a-r2-v1/launch-fixture/study.json")
GRANT = Path("/results/phase3a-r2-v1/launch-fixture/grant.json")
INSPECTION = Path("/results/phase3a-r2-v1/launch-fixture/inspection.json")


def checked(mode="mock"):
    fixture = mode != "provider"
    run = "/results/phase3a-r2-v1/" + "a" * 64 + ("/mock" if fixture else "/live")
    return {"study_sha256": "a" * 64, "source_sha256": "b" * 64, "policy_sha256": "c" * 64,
            "control_policy_sha256": "d" * 64, "launcher_sha256": "e" * 64,
            "runtime_sha256": "9" * 64,
            "grant_sha256": "f" * 64, "journal_id": "1" * 64, "run": run,
            "journal": run + "/journal", "fixture": fixture, "billing_profile": BILLING_PROFILE,
            "slot_count": 775, "cap_micro_usd": 205860000, "first_pair_cap_micro_usd": 50860000,
            "study_path": str(STUDY), "grant_path": str(GRANT), "mode": mode,
            "stage": "first", "provider_calls": 0, "credentials_read": False,
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
         "command": launch.command(STUDY, GRANT, "first", mode, INSPECTION),
         "mounts": [{"type": "bind", "source": launch.HOST_PROJECT, "destination": "/workspace", "rw": False},
                    {"type": "bind", "source": launch.HOST_RUNS, "destination": "/results", "rw": True}]}
    return reseal({"kind": "phase3a-host-inspection-v1", "preflight": value, "container": c})


def reseal(value):
    value["inspection_sha256"] = digest({k: v for k, v in value.items() if k != "inspection_sha256"})
    return value


class LauncherTests(unittest.TestCase):
    def test_r2_host_keeps_both_prior_launchers_and_changes_only_output_namespace(self):
        original = (ROOT / "phase3a.ps1").read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         "9458cc558b4d170ed8f312854edaa2ea065a0a6b1ea0c97cc141a010a1c17c1f")
        prior = (ROOT / "phase3a-r1.ps1").read_bytes()
        self.assertEqual(hashlib.sha256(prior).hexdigest(),
                         "5775b3d9f4ea8dd6a33698bb39b6e3fe97281f854b7864515e95cbf6dbe69bb2")
        self.assertEqual(prior, original.replace(b"phase3a-v1\\launcher", b"phase3a-r1-v1\\launcher").replace(
            b"/results/phase3a-v1/launcher/", b"/results/phase3a-r1-v1/launcher/"))
        self.assertEqual(prior.count(b"phase3a-r1-v1\\launcher"), 1)
        self.assertEqual(prior.count(b"/results/phase3a-r1-v1/launcher/"), 1)
        expected = prior.replace(b"phase3a-r1-v1\\launcher", b"phase3a-r2-v1\\launcher").replace(
            b"/results/phase3a-r1-v1/launcher/", b"/results/phase3a-r2-v1/launcher/")
        self.assertEqual((ROOT / "phase3a-r2.ps1").read_bytes(), expected)

    @unittest.skipUnless(shutil.which("pwsh"), "Requires the actual Windows PowerShell7 host")
    def test_host_helper_overlay_changes_only_ready_wait_and_preserves_hash_guard(self):
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("PowerShell7 host is unavailable")
        script = r"""param([string]$Root, [string]$Changed)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens=$null; $errors=$null
$launcher=[Management.Automation.Language.Parser]::ParseFile((Join-Path $Root 'phase3a-r2.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Phase3A parser rejected'}
$adapter=@($launcher.EndBlock.Statements|Where-Object {$_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -ceq 'Get-FrozenHelperBlock'})
if($adapter.Count -ne 1){throw 'Wrong adapter inventory'}
. ([ScriptBlock]::Create($adapter[0].Extent.Text))
$legacy=Join-Path $Root 'phase2-release.ps1'
$before=(Get-FileHash -LiteralPath $legacy -Algorithm SHA256).Hash.ToLowerInvariant()
$legacyAst=[Management.Automation.Language.Parser]::ParseFile($legacy,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Retained parser rejected'}
$imports=Get-FrozenHelperBlock $legacy
$definitions=@($imports.Ast.EndBlock.Statements)
if($definitions.Count -ne 13 -or @($definitions|Where-Object {$_ -isnot [Management.Automation.Language.FunctionDefinitionAst]}).Count){throw 'Nonfunction main body was imported'}
$old='$readyTask.Wait(120000)'; $new='$readyTask.Wait(600000)'
foreach($definition in $definitions){
    $original=@($legacyAst.EndBlock.Statements|Where-Object {$_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -ceq $definition.Name})
    if($original.Count -ne 1){throw 'Retained function differs'}
    $expected=$original[0].Extent.Text
    if($definition.Name -ceq 'Invoke-ProviderExecution'){
        if([regex]::Matches($expected,[regex]::Escape($old)).Count -ne 1){throw 'Ambiguous old Ready token'}
        $expected=$expected.Replace($old,$new)
    }
    if($definition.Extent.Text -cne $expected){throw 'More than the Ready literal changed'}
}
if([regex]::Matches($imports.ToString(),[regex]::Escape($new)).Count -ne 1 -or $imports.ToString().Contains($old)){throw 'Wrong Ready overlay'}
. $imports
if((Get-Command Read-MaskedKey).CommandType -ne 'Function'){throw 'Masked entry helper missing'}
$rejected=$false
try{[void](Get-FrozenHelperBlock $Changed)}catch{$rejected=$true}
if(-not $rejected){throw 'Modified retained helper passed its byte guard'}
$after=(Get-FileHash -LiteralPath $legacy -Algorithm SHA256).Hash.ToLowerInvariant()
if($before -cne $after){throw 'Retained source changed'}
[ordered]@{functions=$definitions.Count;ready_wait_ms=600000;other_functions_byte_equal=$true;wrong_hash_rejected=$rejected;legacy_sha256=$after}|ConvertTo-Json -Compress
"""
        directory = ROOT / "runs/phase3a-r2-v1"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="helper-overlay-", dir=directory) as tmp:
            altered, check = Path(tmp) / "changed.ps1", Path(tmp) / "check.ps1"
            altered.write_bytes((ROOT / "phase2-release.ps1").read_bytes() + b"\n# Deliberately altered fixture.\n")
            check.write_text(script, encoding="utf-8")
            # The resolved PowerShell receives only a fixed AST check and fixed test paths, without a shell.
            result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-File", str(check),  # nosec B603
                "-Root", str(ROOT), "-Changed", str(altered)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["functions"], 13)
        self.assertEqual(evidence["ready_wait_ms"], 600000)
        self.assertTrue(evidence["other_functions_byte_equal"])
        self.assertTrue(evidence["wrong_hash_rejected"])
        self.assertEqual(evidence["legacy_sha256"], "489e7df6edf0bbd610e60c99b5bd6a17b38c78bd86d97cd58fed2bff02e4c479")

    def test_preflight_rejects_wrong_scope_source_and_journal_before_clients(self):
        good = checked()
        def read(path):
            return {"fixture": True, "authority": AUTHORITY | {"study_sha256": good["study_sha256"]}} if path == GRANT else {
                "slots": slots(), "editor_tools": {}}
        with (patch.object(launch, "runtime_guard"), patch.object(launch, "read_json", side_effect=read),
              patch.object(launch, "_workflow_preflight", return_value=good)):
            value = launch.preflight(STUDY, GRANT, "first", "mock")
            self.assertEqual(value["slot_count"], 775)
            self.assertEqual(value["cap_micro_usd"], 205860000)
            self.assertEqual(value["first_pair_cap_micro_usd"], 50860000)
            with self.assertRaises(ContractError):
                launch.preflight(STUDY, GRANT, "remaining", "mock")
        for update in ({"source_sha256": "wrong"}, {"runtime_sha256": "wrong"}, {"run": "/results/other"},
                       {"run": "/results/phase3a-v1/" + "a" * 64 + "/mock"},
                       {"run": "/results/phase3a-r1-v1/" + "a" * 64 + "/mock"},
                       {"journal": good["run"] + "/other"}, {"fixture": False},
                       {"provider_calls": 1}, {"credentials_read": True}):
            with (patch.object(launch, "runtime_guard"),
                  patch.object(launch, "read_json", side_effect=read),
                  patch.object(launch, "_workflow_preflight", return_value=good | update),
                  patch("followups.phase3a_v1.transport.Transport") as client):
                with self.assertRaises(ContractError):
                    launch.preflight(STUDY, GRANT, "first", "mock")
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
              patch("followups.phase3a_v1.transport.Transport") as client):
            with self.assertRaises(ContractError):
                launch.execute(STUDY, GRANT, "first", "provider", INSPECTION)
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
                    launch.execute(STUDY, GRANT, "first", mode, INSPECTION)
                keys.assert_not_called()
                run.assert_not_called()

    def test_actual_owner_lock_rejects_concurrency_before_readiness(self):
        Path("/results/phase3a-r2-v1/launch-tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/results/phase3a-r2-v1/launch-tests") as tmp:
            value = checked("provider") | {"run": tmp}
            with (writer_lock(Path(tmp) / "launch-owner"),
                  patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "_credentials") as keys,
                  patch("sys.stdout", new_callable=io.StringIO) as output):
                with self.assertRaises(ContractError):
                    launch.execute(STUDY, GRANT, "first", "provider", INSPECTION)
                self.assertEqual(output.getvalue(), "")
                keys.assert_not_called()

    def test_live_claim_is_read_only_until_publish_then_identical_resume_only(self):
        directory = Path("/results/phase3a-r2-v1/launch-tests")
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as tmp, patch.object(launch, "RESULTS", Path(tmp)):
            value = checked("provider")
            value["run"] = str(Path(tmp) / value["study_sha256"] / "live")
            path = Path(tmp) / "live-study.json"
            expected = launch._live_study_claim(value)
            self.assertFalse(path.exists())
            self.assertEqual(launch._live_study_claim(value, publish=True), expected)
            before = path.read_bytes()
            self.assertEqual(launch._live_study_claim(value), expected)
            self.assertEqual(launch._live_study_claim(value, publish=True), expected)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(set(expected), {"kind", *launch._BINDINGS})
            self.assertEqual(expected["kind"], "phase3a-r2-live-study-claim-v1")
            for mode in ("mock", "provider-config", "preflight"):
                with self.assertRaises(ContractError):
                    launch._live_study_claim(value | {"mode": mode}, publish=True)
            for key in launch._BINDINGS:
                changed = value | {key: "8" * 64}
                if key == "study_sha256":
                    changed["run"] = str(Path(tmp) / changed[key] / "live")
                for publish in (False, True):
                    with self.assertRaises(ContractError):
                        launch._live_study_claim(changed, publish=publish)
            self.assertEqual(path.read_bytes(), before)

    def test_r1_claim_kind_cannot_be_reused_for_r2(self):
        directory = Path("/results/phase3a-r2-v1/launch-tests")
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as tmp, patch.object(launch, "RESULTS", Path(tmp)):
            value = checked("provider")
            value["run"] = str(Path(tmp) / value["study_sha256"] / "live")
            legacy = launch._live_study_claim(value) | {"kind": "phase3a-r1-live-study-claim-v1"}
            path = Path(tmp) / "live-study.json"
            raw = (json.dumps(legacy, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            path.write_bytes(raw)
            for publish in (False, True):
                with self.assertRaises(ContractError):
                    launch._live_study_claim(value, publish=publish)
            self.assertEqual(path.read_bytes(), raw)

    def test_live_claim_concurrent_publish_has_one_immutable_winner(self):
        directory = Path("/results/phase3a-r2-v1/launch-tests")
        directory.mkdir(parents=True, exist_ok=True)
        for same in (False, True):
            with tempfile.TemporaryDirectory(dir=directory) as tmp, patch.object(launch, "RESULTS", Path(tmp)):
                first = checked("provider")
                first["run"] = str(Path(tmp) / first["study_sha256"] / "live")
                second = first if same else first | {"grant_sha256": "8" * 64}
                barrier = threading.Barrier(2)
                results: list[tuple[str, dict | None]] = []

                def publish(value):
                    barrier.wait(timeout=5)
                    try:
                        results.append(("ok", launch._live_study_claim(value, publish=True)))
                    except ContractError:
                        results.append(("rejected", None))

                threads = [threading.Thread(target=publish, args=(value,)) for value in (first, second)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
                accepted = [record for status, record in results if status == "ok"]
                self.assertEqual(len(results), 2)
                self.assertEqual(len(accepted), 2 if same else 1)
                self.assertEqual(json.loads((Path(tmp) / "live-study.json").read_text(encoding="utf-8")), accepted[0])
                self.assertFalse(list(Path(tmp).glob(".pending-*")))

    def test_existing_other_live_claim_rejects_actual_preflight_before_readiness(self):
        directory = Path("/results/phase3a-r2-v1/launch-tests")
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as tmp, patch.object(launch, "RESULTS", Path(tmp)):
            value = checked("provider")
            value["run"] = str(Path(tmp) / value["study_sha256"] / "live")
            value["journal"] = value["run"] + "/journal"
            launch._live_study_claim(value | {"grant_sha256": "8" * 64}, publish=True)

            def read(path):
                if path == GRANT:
                    return {"fixture": False, "authority": AUTHORITY | {
                        "study_sha256": value["study_sha256"], "authorized": True}}
                return {"slots": slots(), "editor_tools": {}}

            with (patch.object(launch, "runtime_guard"), patch.object(launch, "read_json", side_effect=read),
                  patch.object(launch, "_workflow_preflight", return_value=value),
                  patch.object(launch, "_credentials") as keys,
                  patch("followups.phase3a_v1.transport.Transport") as client,
                  patch("sys.stdout", new_callable=io.StringIO) as output):
                with self.assertRaisesRegex(ContractError, "already claims"):
                    launch.execute(STUDY, GRANT, "first", "provider", INSPECTION)
                keys.assert_not_called()
                client.assert_not_called()
                self.assertEqual(output.getvalue(), "")

    def test_concurrent_other_claim_after_final_preflight_cannot_construct_sdk(self):
        directory = Path("/results/phase3a-r2-v1/launch-tests")
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as tmp, patch.object(launch, "RESULTS", Path(tmp)):
            value = checked("provider")
            value["run"] = str(Path(tmp) / value["study_sha256"] / "live")
            value["journal"] = value["run"] + "/journal"
            keys = {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}

            def credentials(stream):
                launch._live_study_claim(value | {"grant_sha256": "8" * 64}, publish=True)
                return keys

            with (patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "read_json", return_value=inspection(value)),
                  patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])),
                  patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
                  patch.object(launch, "_credentials", side_effect=credentials),
                  patch.object(launch, "_bind_credentials") as bind,
                  patch("followups.phase3a_v1.transport.Transport") as client,
                  patch("sys.stdout", new_callable=io.StringIO)):
                with self.assertRaises(ContractError):
                    launch.execute(STUDY, GRANT, "first", "provider", INSPECTION)
                bind.assert_not_called()
                client.assert_not_called()
            self.assertEqual(set(keys.values()), {""})

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

        def claim(*args, **kwargs):
            self.assertTrue(kwargs["publish"])
            order.append("claim")

        def construct(**kwargs):
            order.append("client")
            return transport

        with (patch.object(launch, "preflight", return_value=value),
              patch.object(launch, "read_json", return_value=inspection(value)),
              patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch.object(launch, "_credentials", side_effect=keys),
              patch.object(launch, "_live_study_claim", side_effect=claim),
              patch.object(launch, "_bind_credentials", side_effect=bind),
              patch("followups.phase3a_v1.transport.Transport", side_effect=construct),
              patch.object(launch, "_workflow_run", return_value={"provider_calls": 0}),
              patch("sys.stdout", output)):
            self.assertEqual(launch.execute(STUDY, GRANT, "first", "provider", INSPECTION), {"provider_calls": 0})
        self.assertEqual(order, ["stdin", "claim", "bind", "client"])
        transport._anthropic.close.assert_called_once()
        transport._openai.close.assert_called_once()

    def test_fake_stdin_pipe_exercises_actual_pinned_sdk_mock_without_sockets(self):
        Path("/results/phase3a-r2-v1/launch-tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/results/phase3a-r2-v1/launch-tests") as tmp:
            value = checked() | {"run": tmp}
            payload = json.dumps({"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"})

            def run(study, grant, stage, transport):
                transport.select("group", "launcher-fixture.group")
                response = transport.create("group", build_request("group", messages=[{"role": "user", "content": "Synthetic fixture"}]))
                self.assertEqual(response["model"], "gpt-5.6-luna")
                return {"provider_calls": 0, "fixture": True}

            with (patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "read_json", return_value=inspection(value)),
                  patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "mock", "BUDDHA2_OFFLINE": "1"}),
                  patch.object(launch, "_workflow_run", side_effect=run),
                  patch.object(launch, "_live_study_claim") as claim,
                  patch("sys.stdin", io.StringIO(payload)), patch("sys.stdout", new_callable=io.StringIO) as output):
                result = launch.execute(STUDY, GRANT, "first", "mock", INSPECTION)
            self.assertEqual(result["new_mock_http_calls"], 1)
            self.assertNotIn("fixture-not-a-secret", output.getvalue())
            self.assertTrue((Path(tmp) / "wire/launcher-fixture.group.json").is_file())
            self.assertFalse((Path(tmp) / "credential-binding.json").exists())
            claim.assert_not_called()

    def test_source_change_during_key_entry_fails_before_binding_or_client(self):
        value = checked("provider")
        keys = {"anthropic_api_key": "fixture-a", "openai_api_key": "fixture-o"}
        with (patch.object(launch, "preflight", side_effect=[value, value, value | {"source_sha256": "3" * 64}]),
              patch.object(launch, "read_json", return_value=inspection(value)),
              patch.object(Path, "iterdir", return_value=iter([Path("lo"), Path("eth0")])),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch.object(launch, "_credentials", return_value=keys),
              patch.object(launch, "_bind_credentials") as bind,
              patch("followups.phase3a_v1.transport.Transport") as client,
              patch("sys.stdout", new_callable=io.StringIO)):
            with self.assertRaisesRegex(ContractError, "changed during credential entry"):
                launch.execute(STUDY, GRANT, "first", "provider", INSPECTION)
            bind.assert_not_called()
            client.assert_not_called()
        self.assertEqual(set(keys.values()), {""})

    def test_entrypoint_suppresses_unknown_exception_text(self):
        with (patch.object(launch, "preflight", side_effect=RuntimeError("never-print-this")),
              patch("sys.stderr", new_callable=io.StringIO) as errors):
            code = launch.main(["--command", "preflight", "--study", str(STUDY), "--grant", str(GRANT), "--stage", "first", "--mode", "mock"])
        self.assertEqual(code, 2)
        self.assertNotIn("never-print-this", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
