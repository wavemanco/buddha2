"""New-scope launcher checks; no providers, account probes or real credentials."""
import contextlib
import copy
import io
import os
import shutil
import subprocess  # nosec B404
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v2 import launch

STUDY = Path("/results/phase3a-c1-completion-v2/unit/study.json")
GRANT = Path("/results/phase3a-c1-completion-v2/unit/grant.json")
INSPECTION = Path("/results/phase3a-c1-completion-v2/unit/inspection.json")


def checked(mode="mock", stage="all"):
    fixture = mode not in ("provider", "provider-config")
    sha = "a" * 64
    return {"study_sha256": sha, "source_sha256": "b" * 64, "policy_sha256": "c" * 64,
        "runtime_sha256": "d" * 64, "launcher_sha256": "e" * 64, "grant_sha256": "f" * 64,
        "run": str(launch.NATIVE / sha / ("mock" if fixture else "live")),
        "journal": str(launch.accounting.canonical_journal(sha, fixture)), "fixture": fixture,
        "provider_calls": 0, "credentials_read": False, "study_path": str(STUDY), "grant_path": str(GRANT),
        "mode": mode, "stage": stage, "configuration_only": mode == "provider-config",
        "control_policy_sha256": "1" * 64, "billing_profile": launch.BILLING_PROFILE}


def reseal(record):
    record["inspection_sha256"] = digest({k: v for k, v in record.items() if k != "inspection_sha256"})
    return record


def inspection(value):
    c = {"container_id": "2" * 64, "image": launch.accounting.IMAGE_ID, "image_os": "linux", "image_architecture": "amd64",
        "network_mode": "bridge" if value["mode"] in ("provider", "provider-config") else "none",
        "read_only_rootfs": True, "privileged": False, "publish_all_ports": False,
        "pids_limit": 256, "memory": 4294967296, "nano_cpus": 2000000000,
        "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none", "working_dir": "/workspace",
        "entrypoint": ["python"], "open_stdin": True, "tty": False, "port_bindings": {}, "state_at_inspection": "created",
        "cap_drop": ["ALL"], "security_opt": ["no-new-privileges"], "environment_names": sorted(launch._ENVIRONMENT),
        "command": launch.command(STUDY, GRANT, value["stage"], value["mode"], INSPECTION),
        "mounts": [{"type": "bind", "source": launch.HOST_PROJECT, "destination": "/workspace", "rw": False},
                   {"type": "bind", "source": launch.HOST_RUNS, "destination": "/results", "rw": True}]}
    return reseal({"kind": "phase3a-c1-completion-host-inspection-v1", "preflight": value, "container": c})


class LaunchTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pwsh"), "requires installed PowerShell7")
    def test_powershell_native_guard_preserves_real_reparse_ancestor_and_link_rejection(self):
        from followups.phase3a_c1_completion_v2.support import ROOT
        code = r'''
$Root='__ROOT__'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Root 'phase3a-c1-completion-r1.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Launcher parser rejected'}
$functions=@($ast.EndBlock.Statements|Where-Object {$_ -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -cin @('Assert-NoReparse','Get-FrozenHelperBlock')})
if($functions.Count -ne 2){throw 'Native guard/helper inventory differs'}
foreach($function in $functions){. ([ScriptBlock]::Create($function.Extent.Text))}
$guard=($functions|Where-Object Name -CEQ 'Assert-NoReparse').Extent.Text
if($guard.Contains('Get-Item') -or $guard.Contains('Test-Path') -or -not $guard.Contains('[IO.File]::GetAttributes') -or -not $guard.Contains('$current.Parent')){throw 'Guard is not the complete native ancestor walk'}
. (Get-FrozenHelperBlock (Join-Path $Root 'phase2-release.ps1'))
if((Get-Command Assert-NoReparse).ScriptBlock.ToString().Contains('Get-Item')){throw 'Frozen import replaced the native guard'}
$source=[IO.File]::ReadAllText((Join-Path $Root 'phase3a-c1-completion-r1.ps1'))
if($source.IndexOf("[Console]::Title =") -gt $source.IndexOf('Assert-PublicProjectTree $projectRoot') -or $source.IndexOf('Validation is active.') -lt 0){throw 'Interactive validation progress is absent before the tree walk'}
$base=Join-Path $Root 'runs\phase3a-c1-completion-v2\unit-guard'
[void][IO.Directory]::CreateDirectory($base)
$directory=Join-Path $base ([Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($directory)
$target=Join-Path $directory 'target';[void][IO.Directory]::CreateDirectory($target)
$file=Join-Path $target 'ordinary.txt';[IO.File]::WriteAllText($file,'SYNTHETIC public guard fixture')
$junction=Join-Path $directory 'junction';$fileLink=Join-Path $directory 'file-link.txt';$linkCreated=$false
try{
 Assert-NoReparse $file
 Assert-NoReparse (Join-Path $target 'not-created\nested\file.txt')
 [void](New-Item -ItemType Junction -Path $junction -Target $target)
 foreach($bad in @($junction,(Join-Path $junction 'ordinary.txt'),(Join-Path $junction 'not-created\nested\file.txt'))){
  $rejected=$false;try{Assert-NoReparse $bad}catch{$rejected=$true}
  if(-not $rejected){throw 'A reparse ancestor was accepted'}
 }
 try{[void][IO.File]::CreateSymbolicLink($fileLink,$file);$linkCreated=$true}catch [UnauthorizedAccessException]{'FILE_LINK_UNAVAILABLE'}catch [IO.IOException]{'FILE_LINK_UNAVAILABLE'}
 if($linkCreated){$rejected=$false;try{Assert-NoReparse $fileLink}catch{$rejected=$true};if(-not $rejected){throw 'A file symbolic link was accepted'};'FILE_LINK_REJECTED'}
 'JUNCTION_ANCESTOR_REJECTED'
}finally{
 if($linkCreated){[IO.File]::Delete($fileLink)}
 if([IO.Directory]::Exists($junction)){[IO.Directory]::Delete($junction)}
 [IO.File]::Delete($file);[IO.Directory]::Delete($target);[IO.Directory]::Delete($directory)
}
'''
        code = code.replace("__ROOT__", str(ROOT).replace("'", "''"))
        result = subprocess.run([shutil.which("pwsh") or "", "-NoProfile", "-NonInteractive", "-Command", code],  # nosec B603
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("JUNCTION_ANCESTOR_REJECTED", result.stdout)
        self.assertTrue("FILE_LINK_REJECTED" in result.stdout or "FILE_LINK_UNAVAILABLE" in result.stdout)
        print(result.stdout.strip())

    @unittest.skipUnless(shutil.which("pwsh"), "requires installed PowerShell7")
    def test_powershell_inputs_reject_private_and_old_scope_before_path_inspection(self):
        from followups.phase3a_c1_completion_v2.support import ROOT
        code = r'''
$Root='__ROOT__'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Root 'phase3a-c1-completion-r1.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Launcher parser rejected'}
$function=@($ast.EndBlock.Statements|Where-Object {$_ -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -ceq 'Assert-PublicCompletionInput'})
if($function.Count -ne 1){throw 'Input helper inventory differs'}
. ([ScriptBlock]::Create($function[0].Extent.Text))
$commands=@($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -cin @('Assert-PublicCompletionInput','Get-RunPath')},$true))
if($commands.Count -ne 4 -or $commands[0].GetCommandName() -cne 'Assert-PublicCompletionInput' -or $commands[1].GetCommandName() -cne 'Assert-PublicCompletionInput' -or $commands[2].GetCommandName() -cne 'Get-RunPath' -or $commands[3].GetCommandName() -cne 'Get-RunPath'){throw 'Both lexical guards must precede path inspection'}
function Assert-NoReparse {throw 'Lexical input validation inspected filesystem metadata'}
foreach($bad in @('phase3a-r2-v1/old/study.json','phase3a-c1-completion-v1/release/study.json','runs/phase3a-c1-completion-v2/study.json','phase3a-c1-completion-v2/unit/Credential-Binding.JSON','phase3a-c1-completion-v2/unit/.writer.lock','phase3a-c1-completion-v2/.env/child','phase3a-c1-completion-v2/unit/auth.json','phase3a-c1-completion-v2/unit/credentials.json','phase3a-c1-completion-v2/../study.json','phase3a-c1-completion-v2//study.json','phase3a-c1-completion-v2/','phase3a-c1-completion-v2/unit/study?.json')){
 $rejected=$false
 try{Assert-PublicCompletionInput $bad}catch{$rejected=$true}
 if(-not $rejected){throw 'Unsafe input was accepted'}
}
Assert-PublicCompletionInput 'phase3a-c1-completion-v2/release/study.json'
Assert-PublicCompletionInput 'phase3a-c1-completion-v2\release\live-grant.json'
'PASS'
'''
        pwsh = shutil.which("pwsh")
        code = code.replace("__ROOT__", str(ROOT).replace("'", "''"))
        result = subprocess.run([pwsh or "", "-NoProfile", "-NonInteractive", "-Command", code],  # nosec B603
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "requires installed PowerShell7")
    def test_powershell_private_names_are_skipped_before_inspection(self):
        from followups.phase3a_c1_completion_v2.support import ROOT
        code = r'''
$Root='__ROOT__'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Root 'phase3a-c1-completion-r1.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Launcher parser rejected'}
$function=@($ast.EndBlock.Statements|Where-Object {$_ -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -ceq 'Assert-PublicProjectTree'})
if($function.Count -ne 1){throw 'Filtered helper inventory differs'}
. ([ScriptBlock]::Create($function[0].Extent.Text))
$seen=[Collections.Generic.List[string]]::new()
function Assert-NoReparse([string]$Path){
 if([IO.Path]::GetFileName($Path) -cin @('credential-binding.json','.writer.lock','.env','auth.json','credentials.json','hidden-child')){throw 'Private entry reached inspection'}
 $seen.Add($Path)
}
$base=Join-Path $Root 'runs\phase3a-c1-completion-v2\unit-walk'
[void][IO.Directory]::CreateDirectory($base)
$directory=Join-Path $base ([Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($directory)
$files=[Collections.Generic.List[string]]::new()
try{
 foreach($name in @('credential-binding.json','.writer.lock','auth.json','credentials.json','public.txt')){
  $path=Join-Path $directory $name;[IO.File]::WriteAllText($path,'SYNTHETIC public exclusion fixture');$files.Add($path)
 }
 $excluded=Join-Path $directory '.env';[void][IO.Directory]::CreateDirectory($excluded)
 $child=Join-Path $excluded 'hidden-child';[IO.File]::WriteAllText($child,'SYNTHETIC');$files.Add($child)
 Assert-PublicProjectTree $directory
 if($seen.Count -ne 2){throw 'Filtered walk inspected unexpected entries'}
 'PASS'
}finally{
 foreach($file in $files){[IO.File]::Delete($file)}
 [IO.Directory]::Delete((Join-Path $directory '.env'))
 [IO.Directory]::Delete($directory)
}
'''
        pwsh = shutil.which("pwsh")
        self.assertIsNotNone(pwsh)
        code = code.replace("__ROOT__", str(ROOT).replace("'", "''"))
        result = subprocess.run([pwsh or "", "-NoProfile", "-NonInteractive", "-Command", code],  # nosec B603
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_old_private_or_traversing_input_is_rejected_before_read(self):
        with patch.object(launch.accounting, "runtime_guard"), patch.object(launch, "read_json") as read:
            for bad in (Path("/results/phase3a-r2-v1/old/credential-binding.json"),
                        Path("/results/phase3a-c1-completion-v1/release/study.json"),
                        launch.BASE / "unit/credential-binding.json", launch.BASE / "unit/Credential-Binding.JSON",
                        launch.BASE / "unit/../study.json"):
                with self.subTest(path=str(bad)), self.assertRaises(ContractError):
                    launch.preflight(STUDY, bad, "readiness", "provider")
            read.assert_not_called()

    def test_preflight_exact_new_roots_and_all_four_stages(self):
        good = checked()
        def read(path):
            return {"fixture": True, "authority": {}} if path == GRANT else {"slots": {}, "editor_tools": {}}
        with (patch.object(launch.accounting, "runtime_guard"), patch.object(launch, "read_json", side_effect=read),
              patch.object(launch.accounting, "journal_identity", return_value="9" * 64),
              patch.object(launch, "_workflow_preflight", return_value=good) as workflow):
            for stage in launch.STAGES:
                result = launch.preflight(STUDY, GRANT, stage, "mock")
                self.assertEqual(result["stage"], stage)
                self.assertEqual(result["readiness_included_micro_usd"], 20000000)
                self.assertEqual(workflow.call_args.args[-1], stage)
                self.assertEqual(workflow.call_args.kwargs, {"configuration_only": False})
            for field, wrong in (("run", "/results/phase3a-r2-v1/" + "a" * 64 + "/mock"),
                                 ("journal", "/results/phase3a-r2-v1/" + "a" * 64 + "/live/journal"),
                                 ("source_sha256", "bad"), ("credentials_read", True)):
                with self.subTest(field=field):
                    workflow.return_value = good | {field: wrong}
                    with self.assertRaises(ContractError):
                        launch.preflight(STUDY, GRANT, "readiness", "mock")

    def test_only_configuration_preflight_can_bypass_the_offline_gate(self):
        def read(path):
            return {"fixture": False, "authority": {}} if path == GRANT else {"slots": {}, "editor_tools": {}}
        with (patch.object(launch.accounting, "runtime_guard"), patch.object(launch, "read_json", side_effect=read),
              patch.object(launch.accounting, "journal_identity", return_value="9" * 64),
              patch.object(launch, "_live_study_claim"),
              patch("followups.phase3a_c1_completion_v2.workflow.preflight") as workflow,
              patch.object(launch, "_credentials") as keys,
              patch("followups.phase3a_v1.transport.Transport") as client):
            for mode, required in (("provider-config", False), ("provider", True), ("preflight", True)):
                workflow.return_value = checked(mode) | {"fixture": False,
                    "run": str(launch.NATIVE / ("a" * 64) / "live"),
                    "journal": str(launch.accounting.canonical_journal("a" * 64, False))}
                launch.preflight(STUDY, GRANT, "readiness", mode)
                self.assertEqual(workflow.call_args.kwargs, {"require_offline_gate": required})
            keys.assert_not_called()
            client.assert_not_called()

    def test_inspection_reuses_full_guards_without_accepting_old_command(self):
        value = checked()
        record = inspection(value)
        launch.validate_inspection(record, value, INSPECTION)
        for key, bad in (("network_mode", "bridge"), ("memory", 0), ("read_only_rootfs", False),
                         ("environment_names", sorted(launch._ENVIRONMENT | {"ANTHROPIC_API_KEY"})),
                         ("command", launch.frozen.command(STUDY, GRANT, "all", "mock", INSPECTION))):
            with self.subTest(key=key):
                changed = copy.deepcopy(record)
                changed["container"][key] = bad
                with self.assertRaises(ContractError):
                    launch.validate_inspection(reseal(changed), value, INSPECTION)
        changed = copy.deepcopy(record)
        changed["container"]["mounts"][0]["rw"] = True
        with self.assertRaises(ContractError):
            launch.validate_inspection(reseal(changed), value, INSPECTION)

    def test_config_only_and_bad_inspection_stop_before_key_read(self):
        for mode in ("provider-config", "mock"):
            value = checked(mode)
            record = inspection(value)
            if mode == "mock":
                record["container"]["network_mode"] = "bridge"
                reseal(record)
            with (patch.object(launch, "preflight", return_value=value),
                  patch.object(launch, "writer_lock", return_value=contextlib.nullcontext()),
                  patch.object(launch, "read_json", return_value=record),
                  patch.object(launch, "_credentials") as keys):
                with self.assertRaises(ContractError):
                    launch.execute(STUDY, GRANT, "all", mode, INSPECTION)
                keys.assert_not_called()

    def test_single_provider_controller_clears_keys_and_closes_clients(self):
        value = checked("provider")
        record = inspection(value)
        keys = {"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"}
        transport = SimpleNamespace(_anthropic=Mock(), _openai=Mock())
        with (patch.object(launch, "preflight", return_value=value),
              patch.object(launch, "writer_lock", return_value=contextlib.nullcontext()),
              patch.object(launch, "read_json", return_value=record), patch.object(launch, "_credentials", return_value=keys),
              patch.object(launch.Path, "iterdir", return_value=[Path("lo"), Path("eth0")]),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch.object(launch, "_live_study_claim") as claim, patch.object(launch, "_bind_credentials") as binding,
              patch("followups.phase3a_v1.transport.Transport", return_value=transport) as client,
              patch.object(launch, "_workflow_run", return_value={"status": "synthetic-controller"}) as workflow,
              contextlib.redirect_stdout(io.StringIO())):
            result = launch.execute(STUDY, GRANT, "all", "provider", INSPECTION)
            self.assertEqual(result["status"], "synthetic-controller")
            self.assertEqual(workflow.call_args.args, (STUDY, GRANT, "all", transport))
            workflow.assert_called_once()
            client.assert_called_once()
            binding.assert_called_once()
            claim.assert_called_once_with(value, publish=True)
        self.assertEqual(set(keys.values()), {""})
        transport._anthropic.close.assert_called_once()
        transport._openai.close.assert_called_once()

    def test_credential_entry_drift_refuses_client_and_clears_input(self):
        value = checked("provider")
        keys = {"anthropic_api_key": "fixture-not-a-secret", "openai_api_key": "fixture-not-a-secret"}
        with (patch.object(launch, "preflight", side_effect=[value, value, value | {"source_sha256": "c" * 64}]),
              patch.object(launch, "writer_lock", return_value=contextlib.nullcontext()),
              patch.object(launch, "read_json", return_value=inspection(value)), patch.object(launch, "_credentials", return_value=keys),
              patch.object(launch.Path, "iterdir", return_value=[Path("lo"), Path("eth0")]),
              patch.dict(os.environ, {"BUDDHA2_RELEASE_LAUNCH_MODE": "provider", "BUDDHA2_OFFLINE": "0"}),
              patch("followups.phase3a_v1.transport.Transport") as client, contextlib.redirect_stdout(io.StringIO())):
            with self.assertRaises(ContractError):
                launch.execute(STUDY, GRANT, "all", "provider", INSPECTION)
            client.assert_not_called()
        self.assertEqual(set(keys.values()), {""})

    def test_new_immutable_claim_rejects_second_grant_and_never_uses_old_claim(self):
        directory = launch.BASE / "unit-claims"
        directory.mkdir(parents=True, exist_ok=True)
        value = checked("provider")
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            with (patch.object(launch, "BASE", Path(temporary)),
                  patch.object(launch.frozen, "_live_study_claim", side_effect=AssertionError("old claim forbidden"))):
                record = launch._live_study_claim(value, publish=True)
                self.assertEqual(record, launch._live_study_claim(value))
                with self.assertRaises(ContractError):
                    launch._live_study_claim(value | {"grant_sha256": "3" * 64})
                with self.assertRaises(ContractError):
                    launch._live_study_claim(value | {"fixture": True})


if __name__ == "__main__":
    unittest.main()
