"""Declared cheap RA1 launch/domain/static checks, never a study worklist."""
from __future__ import annotations

import importlib.util
import json
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / ".upstream/harness2")]
from followups.phase3b_seq2_v1 import verify  # noqa: E402

OUT = ROOT / "runs/phase3b-seq2-v1/ra1-component-v3"
PROBE = r'''
import errno,importlib.util,json,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
from buddha2.artifacts import ContractError
from followups.phase3b_seq2_v1 import verify
from followups.phase3b_seq2_v1.support import BASE,publish
root=BASE/'ra1-component-v3'
denied=Path('/workspace/evidence/phase3b-ra1-v1/denied-component-marker.json')
try:
    with denied.open('x',encoding='utf-8') as stream:stream.write('{}')
except OSError as exc:
    if exc.errno!=errno.EROFS:raise
else:raise ValueError('readonly source became writable')
try:publish(denied,{'fixture':True})
except ContractError:pass
else:raise ValueError('runtime writer accepted source evidence path')
target=root/'exclusive-marker.json'
publish(target,{'fixture':True,'real_provider_calls':0})
before=target.read_bytes()
try:publish(target,{'changed':True})
except ContractError:pass
else:raise ValueError('exclusive writer overwrote existing marker')
if before!=target.read_bytes():raise ValueError('existing marker changed')
spec=importlib.util.spec_from_file_location('ra1_runtime_entry','/workspace/evidence/phase3b-seq2-c2-v1/composed_acceptance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with patch.object(module,'recovery_config',return_value={'verification':'ra1-component-v3'}):
    if module.runtime_output(str(root))!=root:raise ValueError('runtime domain rejected')
    for value in ('/workspace/runs/phase3b-seq2-v1/ra1-component-v3',str(BASE),str(BASE/'foreign'),str(BASE/'a/../ra1-component-v3')):
        try:module.runtime_output(value)
        except ValueError:pass
        else:raise ValueError('foreign runtime domain accepted')
suite=unittest.defaultTestLoader.loadTestsFromName('followups.phase3b_seq2_v1.test_ra1_release_s2')
tested=unittest.TextTestRunner(stream=sys.stdout,verbosity=2,failfast=True).run(suite)
if not tested.wasSuccessful():raise ValueError('RA1 pure component regression failed')
deadline=time.monotonic()+500
statics=[]
for command in verify.static_commands():
    remaining=deadline-time.monotonic()
    if remaining<=0:raise ValueError('finite component static budget exhausted')
    result=verify.execute(command,timeout=min(120,remaining))
    statics.append(result)
verify.save(root/'statics.json',{'passed':all(row['exit_code']==0 for row in statics),'commands':statics})
if not all(row['exit_code']==0 for row in statics):raise ValueError('RA1 affected static checks failed')
print(json.dumps({'passed':True,'domain_guard_actual_function':True,'only_fixture_verification_name_patched':True,
 'readonly_and_exclusive_writers':True,'pure_tests':tested.testsRun,'static_checks':len(statics),
 'preflight_study_native_worklist_calls':0,'real_provider_calls':0}))
'''


def host_checks():
    spec = importlib.util.spec_from_file_location("ra1_component_operator", ROOT / "evidence/phase3b-ra1-v1/ra1_operator.py")
    if spec is None or spec.loader is None:
        raise ValueError("RA1 operator unavailable")
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    env = operator.clean_environment(ROOT)
    # This actual executable path has spaces on the supported host; arguments
    # remain an array through the same managed-child primitive as release launch.
    result = operator.run_child([sys.executable, "-B", "-c", "import json,sys; print(json.dumps(sys.argv[1:]))", "space argument", "ü"],
                                cwd=ROOT, env=env, timeout=20)
    verify.save(OUT / "host-argv.json", result)
    if result["exit_code"] != 0 or json.loads(result["output"]) != ["space argument", "ü"] or not result["settled"]:
        raise ValueError("actual managed host argument path failed")
    direct = operator.run_child([sys.executable, "-B", str(ROOT / "evidence/phase3b-ra1-v1/effort.py")],
                                cwd=ROOT, env=env, timeout=20)
    verify.save(OUT / "host-direct-script.json", direct)
    if direct["exit_code"] != 0 or json.loads(direct["output"])["target_is_hard_abort"] is not False:
        raise ValueError("actual direct-script import path regression")


def main():
    if Path.cwd().resolve() != ROOT or OUT.exists():
        raise ValueError("fresh exact RA1 component output required")
    OUT.mkdir(parents=True)
    host_checks()
    runtime = OUT / "runtime"
    (runtime / "ra1-component-v3").mkdir(parents=True)
    args = verify.container_args(OUT, mode="inside")
    broad = f"type=bind,source={ROOT / 'runs/phase3b-seq2-v1'},target=/results/phase3b-seq2-v1"
    args[args.index(broad)] = f"type=bind,source={runtime},target=/results/phase3b-seq2-v1"
    args[2:2] = ["--log-driver", "none"]
    args[args.index(verify.IMAGE) + 1:] = ["-B", "-c", PROBE]
    owner, passed, environment = None, False, []
    try:
        created = verify.execute(args, timeout=60)
        verify.save(OUT / "create.json", created)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            owner = None
            raise ValueError("no exact RA1 component owner")
        actual = json.loads(verify.execute(["docker", "inspect", owner], timeout=60)["stdout"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        environment = sorted(actual["Config"]["Env"])
        allowed = {'PYTHON_VERSION', 'HARNESS2_ROOT', 'PYTHONUNBUFFERED', 'HF_HUB_OFFLINE', 'GPG_KEY', 'PYTHONDONTWRITEBYTECODE', 'BUDDHA2_IMAGE_ID', 'HF_DATASETS_OFFLINE', 'BUDDHA2_OFFLINE', 'LANG', 'TRANSFORMERS_OFFLINE', 'BUDDHA2_TEST_OUTPUT_ROOT', 'BUDDHA2_NB_UPSTREAM', 'OMP_NUM_THREADS', 'TMPDIR', 'PYTHON_SHA256', 'PHASE3A_OPENCODE', 'PHASE3A_BUN', 'PYTHONPATH', 'PYTHONNOUSERSITE', 'PATH', 'TOKENIZERS_PARALLELISM', 'BUDDHA2_OUTPUT_ROOT', 'NOVELTYBENCH_ROOT'}
        verify.save(OUT / "created-configuration-observation.json", {
            "owner": owner, "image": actual["Image"], "network": host["NetworkMode"],
            "mounts": actual["Mounts"], "readonly_root": host["ReadonlyRootfs"],
            "entrypoint": actual["Config"]["Entrypoint"], "working_dir": actual["Config"]["WorkingDir"],
            "environment_names": sorted(item.split("=", 1)[0] for item in environment),
            "command_matches": actual["Config"]["Cmd"] == ["-B", "-c", PROBE],
            "environment_values_retained": False})
        if (actual["Image"] != verify.IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or mounts != {(str(ROOT), "/workspace", False), (str(runtime), "/results/phase3b-seq2-v1", True)}
                or host["Privileged"] or actual["State"]["Running"]
                or host["PidsLimit"] != 256 or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}  # nosec B108
                or host["LogConfig"]["Type"] != "none" or actual["Config"]["Entrypoint"] != ["python"]
                or actual["Config"]["WorkingDir"] != "/workspace" or actual["Config"]["Cmd"] != ["-B", "-c", PROBE]
                or {item.split("=", 1)[0] for item in environment} != allowed):
            raise ValueError("actual RA1 component containment/command/environment differs")
        verify.save(OUT / "inspection.json", {"passed": True, "owner": owner, "image": actual["Image"],
            "network": "none", "mounts": actual["Mounts"], "environment": environment, "readonly_root": True})
        result = verify.execute(["docker", "start", "--attach", owner], timeout=600)
        verify.save(OUT / "execution.json", result)
        passed = result["exit_code"] == 0
    finally:
        cleanup: dict = {"passed": False, "owner": owner}
        if owner:
            deadline = time.monotonic() + 60
            def settle(command, seconds):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup budget exhausted"}
                try:
                    return verify.execute(command, timeout=min(seconds, remaining))
                except (subprocess.TimeoutExpired, OSError) as exc:
                    return {"exit_code": 124, "stdout": "", "stderr": "cleanup command failed", "exception_type": type(exc).__name__}
            terminal = settle(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["terminal"] = terminal
            if terminal["exit_code"] == 0 and terminal["stdout"].strip() == "true":
                cleanup["stop"] = settle(["docker", "stop", "--time", "10", owner], 30)
            cleanup["remove"] = settle(["docker", "rm", owner], 30)
            cleanup["absence"] = settle(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["passed"] = cleanup["remove"]["exit_code"] == 0 and cleanup["absence"]["exit_code"] != 0 and "no such object" in cleanup["absence"]["stderr"].casefold()
        verify.save(OUT / "cleanup.json", cleanup)
    verify.save(OUT / "result.json", {"passed": passed and cleanup["passed"], "container_environment": environment,
        "generation_calls": 0, "real_provider_calls": 0, "preflight_sets_or_release_admissions": 0})
    return 0 if passed and cleanup["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
