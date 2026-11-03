"""Offline HI packet, inspected-container and real Windows bootstrap boundaries."""
from __future__ import annotations

import copy
import json
import os
import subprocess  # nosec B404
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash

from . import launch

PWSH = Path(r"C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe")
WINDOWS_PS = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")


def windows_root():
    root = launch.ROOT / "runs/phase3a-readiness-recovery-v1/tests-launch-windows"
    if not root.is_absolute() or not root.is_relative_to(launch.ROOT / "runs"):
        raise ValueError("host test output escaped research runs")
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_windows(runtime, script, arguments):
    with tempfile.TemporaryDirectory(prefix="script-", dir=windows_root()) as directory:
        target = Path(directory) / "check.ps1"
        target.write_text(script, encoding="utf-8", newline="\n")
        return subprocess.run([str(runtime), "-NoProfile", "-File", str(target), *map(str, arguments)],
            cwd=launch.ROOT, capture_output=True, text=True, timeout=45, check=False)  # nosec B603



def checked(mode="mock"):
    sha = "a" * 64
    fixture = mode not in {"provider", "provider-config"}
    return {"study_sha256": sha, "source_sha256": "b" * 64, "policy_sha256": "c" * 64,
            "runtime_sha256": "d" * 64, "launcher_sha256": "e" * 64, "grant_sha256": "f" * 64,
            "run": str(launch.NATIVE / sha / ("mock" if fixture else "live")),
            "journal": str(launch.accounting.canonical_journal(sha, fixture)), "fixture": fixture,
            "study_path": str(launch.BASE / "unit/study.json"), "grant_path": str(launch.BASE / "unit/grant.json"),
            "mode": mode, "stage": "all", "configuration_only": mode == "provider-config",
            "supervisor_agent": "/root/rp2_supervisor", "fixture_supervision_rehearsal": False}


def reseal(record):
    record["inspection_sha256"] = digest({k: v for k, v in record.items() if k != "inspection_sha256"})
    return record


def inspection(value, target):
    actual = {"container_id": "2" * 64, "image": launch.accounting.IMAGE_ID,
        "image_os": "linux", "image_architecture": "amd64", "network_mode": "bridge" if value["mode"] in {"provider", "provider-config"} else "none",
        "read_only_rootfs": True, "privileged": False, "publish_all_ports": False, "pids_limit": 256,
        "memory": 4294967296, "nano_cpus": 2000000000,
        "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none",  # nosec B108
        "working_dir": "/workspace", "entrypoint": ["python"], "open_stdin": True,
        "tty": False, "port_bindings": {}, "state_at_inspection": "created", "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"], "environment_names": sorted(launch._ENVIRONMENT),
        "command": launch.command(Path(value["study_path"]), Path(value["grant_path"]), "all", value["mode"], target,
                                  value["supervisor_agent"]),
        "mounts": [{"type": "bind", "source": launch.HOST_PROJECT, "destination": "/workspace", "rw": False},
                   {"type": "bind", "source": launch.HOST_RUNS, "destination": "/results", "rw": True}]}
    return reseal({"kind": "phase3a-rp2-host-inspection-v1", "preflight": value, "container": actual})


class LaunchChecks(unittest.TestCase):
    def test_rehearsal_is_strict_bool_and_never_provider_enabled(self):
        cases = [("provider", True), ("provider-config", True), ("mock", 1), ("mock", "true"), ("mock", None)]
        for mode, flag in cases:
            value = {**checked(mode), "provider_calls": 0, "credentials_read": False}
            with self.subTest(mode=mode, flag=flag), patch.object(launch.accounting, "runtime_guard"), \
                    patch.object(launch, "_completion_path", side_effect=lambda p: p), \
                    patch.object(launch, "read_json", side_effect=[{"fixture": value["fixture"]}, {"fixture_supervision_rehearsal": flag}]), \
                    patch.object(launch, "_workflow_preflight", return_value=value), \
                    patch.object(launch, "_accepted_packet", side_effect=AssertionError("rehearsal reached paid packet")):
                with self.assertRaisesRegex(ContractError, "strictly mock-only"):
                    launch.preflight(Path(value["study_path"]), Path(value["grant_path"]), "all", mode,
                                     supervisor_agent=value["supervisor_agent"])

    def test_supervisor_handle_is_explicit_and_part_of_inspected_argv(self):
        value = checked()
        target = launch.BASE / "unit/inspection.json"
        record = inspection(value, target)
        self.assertEqual(record["container"]["command"][-2:], ["--supervisor-agent", value["supervisor_agent"]])
        record["container"]["command"][-1] = "/root/stale_supervisor"
        with self.assertRaises(ContractError):
            launch.validate_inspection(reseal(record), value, target)
        for absent in (None, "", "/root", "other", "/root/a;bad"):
            with self.subTest(agent=absent), self.assertRaises(ContractError):
                launch.supervision.agent_name(absent)

    def test_actual_H1_image_and_full_container_contract(self):
        for mode in ["mock", "provider"]:
            value = checked(mode)
            target = launch.BASE / "unit/inspection.json"
            record = inspection(value, target)
            launch.validate_inspection(record, value, target)
            for field, wrong in [("image", "sha256:" + "0" * 64), ("network_mode", "host"),
                                 ("privileged", True), ("log_driver", "json-file"), ("read_only_rootfs", False)]:
                altered = copy.deepcopy(record)
                altered["container"][field] = wrong
                with self.subTest(mode=mode, field=field), self.assertRaises(ContractError):
                    launch.validate_inspection(reseal(altered), value, target)
            for field in ["environment_names", "mounts"]:
                altered = copy.deepcopy(record)
                altered["container"][field].append("ANTHROPIC_API_KEY" if field == "environment_names" else
                    {"type": "bind", "source": r"C:\Users\arvik", "destination": "/host", "rw": False})
                with self.subTest(field=field), self.assertRaises(ContractError):
                    launch.validate_inspection(reseal(altered), value, target)

    def test_private_old_escape_paths_rejected_before_metadata(self):
        for value in [launch.BASE / "x/AUTH.JSON", launch.BASE / "x/../public.json",
                      Path("/results/phase3a-c1-completion-v4/foreign.json"), Path("relative.json")]:
            with self.subTest(path=str(value)), patch.object(Path, "lstat", side_effect=AssertionError("metadata touched")):
                with self.assertRaises(ContractError):
                    launch._completion_path(value)

    def test_single_review_packet_is_bound_and_drift_is_rejected(self):
        test_base = windows_root() if os.name == "nt" else launch.BASE
        test_base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hi-launch-packet-", dir=test_base) as directory:
            root = Path(directory)
            evidence = root / "evidence/phase3a-readiness-recovery-v1"
            evidence.mkdir(parents=True)
            study = root / "release/study.json"
            study.parent.mkdir()
            def write(target, value):
                target.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            write(study.parent / "offline-gate.json", {"passed": True})
            value = checked("provider")
            bindings = {key: value[key] for key in launch._BINDINGS if key != "grant_sha256"}
            gate = file_hash(study.parent / "offline-gate.json")
            review = evidence / "independent-acceptance.json"
            write(review, {"passed": True, **bindings, "offline_gate_file_sha256": gate})
            archive = evidence / "offline-kit-v1.zip"
            archive.write_bytes(b"SYNTHETIC unit packet digest; independently audited archives are separate")
            manifest_path = evidence / "offline-kit-v1.manifest.json"
            manifest = {"passed": True, "mode": "offline", "study_sha256": value["study_sha256"],
                "source_sha256": value["source_sha256"], "archive": archive.relative_to(root).as_posix(),
                "archive_sha256": file_hash(archive), "member_sha256": {review.relative_to(root).as_posix(): file_hash(review)}}
            write(manifest_path, manifest)
            receipt_path = evidence / "packet-acceptance.json"
            receipt = {"passed": True, **bindings, "archive": manifest["archive"], "archive_sha256": manifest["archive_sha256"],
                       "manifest_sha256": file_hash(manifest_path), "offline_gate_file_sha256": gate}
            write(receipt_path, receipt)
            with patch.object(launch, "ROOT", root), patch.object(launch, "BASE", test_base):
                accepted = launch._accepted_packet(study, value)
                self.assertEqual(accepted["independent_acceptance_sha256"], file_hash(review))
                for field in [*bindings, "manifest_sha256", "offline_gate_file_sha256"]:
                    write(receipt_path, {**receipt, field: "9" * 64})
                    with self.subTest(field=field), self.assertRaises(ContractError):
                        launch._accepted_packet(study, value)
                write(receipt_path, receipt)
                archive.write_bytes(b"SYNTHETIC changed after acceptance")
                with self.assertRaises(ContractError):
                    launch._accepted_packet(study, value)

    @unittest.skipUnless(os.name == "nt", "actual Windows PowerShell check")
    def test_windows_bootstrap_PS5_and_private_rejection(self):
        source = launch.ROOT / "phase3a-readiness-recovery.ps1"
        code = "param([string]$Target)\n$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::ParseFile($Target,[ref]$t,[ref]$e);if($e.Count){exit 2};'PS5_PARSE_OK'"
        result = run_windows(WINDOWS_PS, code, [source])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PS5_PARSE_OK", result.stdout)
        for private in ["AUTH.JSON", ".env", "credentials.json", "live.STDOUT.json", "old_stderr.txt"]:
            result = subprocess.run([str(WINDOWS_PS), "-NoProfile", "-File", str(source),
                "-Study", "phase3a-readiness-recovery-v1/unit/" + private,
                "-Grant", "phase3a-readiness-recovery-v1/unit/grant.json"], cwd=launch.ROOT,
                capture_output=True, text=True, timeout=30, check=False)  # nosec B603
            self.assertEqual(result.returncode, 1)
            self.assertIn("bootstrap rejected", result.stderr)

    @unittest.skipUnless(os.name == "nt", "actual Windows junction check")
    def test_windows_core_private_stream_skips_and_junction_ancestor(self):
        base = windows_root()
        with tempfile.TemporaryDirectory(prefix="hi-windows-", dir=base) as temporary:
            temp = Path(temporary)
            self.assertTrue(temp.is_relative_to(base))
            script = r"""
param([string]$Core,[string]$TestRoot)
$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Core,[ref]$t,[ref]$e)
if($e.Count){throw 'core parse failed'}
$wanted=@('Assert-NoReparse','Assert-PublicProjectTree','Assert-PublicCompletionInput')
$definitions=@($ast.EndBlock.Statements|Where-Object{$_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -in $wanted})
if($definitions.Count -ne 3){throw 'helper inventory differs'}
. ([ScriptBlock]::Create((($definitions|ForEach-Object{$_.Extent.Text}) -join "`n")))
[void][IO.Directory]::CreateDirectory((Join-Path $TestRoot 'real'))
foreach($name in @('.env','AUTH.JSON','live.stdout.log','old_stderr.txt')){
 [void](New-Item -ItemType Junction -Path (Join-Path $testRoot $name) -Target (Join-Path $testRoot 'real'))
}
Assert-PublicProjectTree $testRoot
foreach($name in @('live.STDOUT.json','old_stderr.txt')){
 $rejected=$false;try{Assert-PublicCompletionInput ('phase3a-readiness-recovery-v1/unit/' + $name)}catch{$rejected=$_.Exception.Message -eq 'Input is not a public ordinary completion path'}
 if(-not $rejected){throw 'stream input not lexically rejected'}
 $rejected=$false;try{Assert-NoReparse (Join-Path $TestRoot $name)}catch{$rejected=$_.Exception.Message -eq 'Private path rejected before metadata'}
 if(-not $rejected){throw 'stream path reached metadata'}
}
[void](New-Item -ItemType Junction -Path (Join-Path $testRoot 'public-link') -Target (Join-Path $testRoot 'real'))
$rejected=$false;try{Assert-NoReparse (Join-Path $testRoot 'public-link\missing\x.json')}catch{$rejected=$true}
if(-not $rejected){throw 'junction ancestor accepted'}
'PRIVATE_AND_STREAM_SKIPPED';'JUNCTION_ANCESTOR_REJECTED'
"""
            result = run_windows(PWSH, script, [launch.ROOT / "phase3a-readiness-recovery-core.ps1", temp])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PRIVATE_AND_STREAM_SKIPPED", result.stdout)
            self.assertIn("JUNCTION_ANCESTOR_REJECTED", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
