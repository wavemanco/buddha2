"""Owned H1 component probe of readonly code versus runtime output domains."""
from __future__ import annotations

import json
import subprocess  # nosec B404
import traceback
from pathlib import Path

from followups.phase3b_seq2_v1 import verify

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/phase3b-seq2-v1/or1-writer-domain-v1"
PROBE = r'''
import errno,json
from pathlib import Path
from buddha2.artifacts import ContractError
from followups.phase3b_seq2_v1.support import BASE,publish
denied=Path('/workspace/evidence/phase3b-or1-v1/denied-runtime-counter-probe.json')
if denied.exists(): raise ValueError('fresh denied probe required')
readonly=False
try:
    with denied.open('x',encoding='utf-8') as f:f.write('{}')
except OSError as exc:
    if exc.errno!=errno.EROFS:raise
    readonly=True
if not readonly:raise ValueError('readonly source unexpectedly writable')
guarded=False
try:publish(denied,{'fixture':True})
except ContractError:guarded=True
if not guarded:raise ValueError('runtime publish accepted host evidence')
target=BASE/'or1-writer-domain-v1/allowed-runtime-marker.json'
publish(target,{'fixture':True,'provider_calls':0,'kind':'or1-component-marker'})
before=target.read_bytes();exclusive=False
try:publish(target,{'fixture':True,'provider_calls':0,'kind':'changed'})
except ContractError:exclusive=True
if not exclusive or target.read_bytes()!=before:raise ValueError('runtime marker was overwritten')
print(json.dumps({'passed':readonly and guarded and exclusive,'readonly_evidence_denied':readonly,
 'runtime_publish_evidence_denied':guarded,'runtime_marker_written':True,'runtime_marker_exclusive':exclusive,
 'provider_calls':0,'generation_calls':0,'release_admissions':0}))
'''


def main() -> int:
    if Path.cwd().resolve() != ROOT or OUT.exists():
        raise ValueError("fresh exact component output required")
    OUT.mkdir(parents=True)
    args = verify.container_args(OUT, mode="inside")
    args[2:2] = ["--log-driver", "none"]
    args[args.index(verify.IMAGE) + 1:] = ["-B", "-c", PROBE]
    owner, passed = None, False
    def command(args, timeout):
        try:
            return verify.execute(args, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"command": args, "exit_code": 124, "stdout": "", "stderr": str(exc),
                    "exception_type": type(exc).__name__, "traceback": traceback.format_exc(),
                    "partial_output": repr(getattr(exc, "stdout", None)),
                    "partial_error": repr(getattr(exc, "stderr", None))}
    try:
        created = command(args, 60)
        verify.save(OUT / "create.json", created)
        owner = created["stdout"].strip()
        if created["exit_code"] or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
            owner = None
            raise ValueError("component probe has no exact owner")
        inspected = command(["docker", "inspect", owner], 60)
        actual = json.loads(inspected["stdout"])[0]
        host = actual["HostConfig"]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        if (actual["Image"] != verify.IMAGE or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
                or mounts != verify.expected_mounts(OUT) or host["Privileged"] or host["PidsLimit"] != 256
                or host["Memory"] != 4294967296 or host["NanoCpus"] != 2000000000
                or host["CapDrop"] != ["ALL"] or host["SecurityOpt"] not in (["no-new-privileges"], ["no-new-privileges:true"])
                or host["Tmpfs"] != {"/tmp": "rw,nosuid,nodev,size=1073741824,mode=1777"}  # nosec B108
                or host["LogConfig"]["Type"] != "none"):
            raise ValueError("component containment differs")
        verify.save(OUT / "inspection.json", {"passed": True, "owner": owner,
                    "image": actual["Image"], "network": "none", "mounts": actual["Mounts"], "readonly": True})
        executed = command(["docker", "start", "--attach", owner], 120)
        verify.save(OUT / "execution.json", executed)
        proof = json.loads(executed["stdout"])
        passed = executed["exit_code"] == 0 and proof.get("passed") is True
    except BaseException as exc:
        verify.save(OUT / "failure.json", {"passed": False, "type": type(exc).__name__,
                    "message": str(exc), "traceback": traceback.format_exc()})
    finally:
        cleanup: dict = {"passed": False, "owner": owner}
        if owner:
            cleanup["stop"] = command(["docker", "stop", "--time", "10", owner], 30)
            cleanup["remove"] = command(["docker", "rm", owner], 30)
            cleanup["absence"] = command(["docker", "inspect", "--format", "{{json .State.Running}}", owner], 15)
            cleanup["passed"] = cleanup["remove"]["exit_code"] == 0 and cleanup["absence"]["exit_code"] != 0 and "no such object" in cleanup["absence"]["stderr"].casefold()
        verify.save(OUT / "cleanup.json", cleanup)
    verify.save(OUT / "result.json", {"passed": passed and cleanup["passed"], "provider_calls": 0,
                                      "generation_calls": 0, "release_admissions": 0})
    return 0 if passed and cleanup["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
