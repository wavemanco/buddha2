"""Authenticate the offline candidate and manage its exact Windows child."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import subprocess  # nosec B404
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "evidence/phase3b-ra1-v1"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json",
           "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".git"}


def ordinary(root: Path, target: Path) -> bytes:
    relative = target.relative_to(root)
    if not relative.parts or ".." in relative.parts or relative.drive or any(
            q.casefold() in PRIVATE or "stdout" in q.casefold() or "stderr" in q.casefold()
            for q in relative.parts):
        raise ValueError("excluded candidate path before metadata")
    checked = root
    for part in relative.parts:
        checked /= part
        info = checked.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("candidate path crosses a link")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("nonordinary candidate input")
    return checked.read_bytes()


def settings() -> dict:
    value = json.loads(ordinary(ROOT, HERE / "release-config.json"))
    number = value.get("candidate")
    if (value.get("kind") != "phase3b-ra1-release-config-v1" or type(number) is not int
            or number not in (1, 2) or value.get("verification") != "verification-ra1-v" + str(number)
            or value.get("authority") != "evidence/phase3b-ra1-v1/authority.json"):
        raise ValueError("invalid RA1 source-bound configuration")
    return value


def admit(kind: str, candidate: dict) -> dict:
    """One immutable receipt per bounded admission, written before child work."""
    from buddha2.artifacts import write_once
    from followups.phase3b_seq2_v1.support import file_hash, read, require, safe
    limits = {"candidate": 2, "main": 2, "S13": 2, "saved": 2, "cold": 2}
    require(kind in limits, "unknown RA1 admission kind")
    number = settings()["candidate"]
    require(candidate == read(HERE / f"candidate-{number}.json"), "RA1 admission candidate differs")
    directory = safe(HERE / "admissions")
    prior = []
    for index in (1, 2):
        for label in limits:
            item = safe(directory / f"c{index}-{label}.json")
            if not item.exists():
                continue
            row = read(item)
            frozen = read(HERE / f"candidate-{index}.json")
            require(row.get("candidate") == index and row.get("admission") == label
                and row.get("source_sha256") == frozen["source_sha256"]
                and row.get("candidate_sha256") == file_hash(HERE / f"candidate-{index}.json"),
                "RA1 admission history changed or is foreign")
            prior.append(row)
    require(sum(row["admission"] == kind for row in prior) < limits[kind]
        and not any(row["candidate"] == number and row["admission"] == kind for row in prior),
        "RA1 admission cap or per-candidate allowance exhausted")
    require(kind == "candidate" or any(row["candidate"] == number and row["admission"] == "candidate"
        for row in prior), "RA1 candidate has not been admitted")
    value = {"kind": "phase3b-ra1-admission-v1", "candidate": number, "admission": kind,
             "source_sha256": candidate["source_sha256"],
             "candidate_sha256": file_hash(HERE / f"candidate-{number}.json"),
             "admitted_at_utc": datetime.now(timezone.utc).isoformat(),
             "real_provider_calls": 0, "consumed_before_child_work": True}
    write_once(safe(directory / f"c{number}-{kind}.json", roots=(ROOT,)), value)
    return value


def clean_environment(root: Path, environment=None) -> dict:
    values = os.environ if environment is None else environment
    result = {k: values[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if k in values}
    result.update(PYTHONPATH=os.pathsep.join(str(p) for p in (root, root / "src", root / ".upstream/harness2")),
                  BUDDHA2_OUTPUT_ROOT=str(root / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
                  PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return result


def authenticate_candidate(root: Path, candidate_path: Path, review_path: Path,
                           reviewer: str = "/root/ra1_path_review") -> dict:
    """Stdlib-only file authentication; never constructs a workflow or child."""

    candidate_raw = ordinary(root, candidate_path)
    candidate, review = json.loads(candidate_raw), json.loads(ordinary(root, review_path))
    if (review.get("passed") is not True or review.get("reviewer") != reviewer
            or review.get("candidate_sha256") != hashlib.sha256(candidate_raw).hexdigest()
            or review.get("source_sha256") != candidate.get("source_sha256")):
        raise ValueError("candidate review is absent, foreign or mismatched")
    files = candidate.get("candidate_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError("candidate file manifest is missing")
    for name, expected in files.items():
        relative = Path(name)
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise ValueError("nonrelative candidate path")
        if hashlib.sha256(ordinary(root, root / relative)).hexdigest() != expected:
            raise ValueError("reviewed candidate file changed")
    return candidate


def run_child(args, *, cwd: Path, env: dict, timeout: float, cancel=None, driver=False) -> dict:
    """Own one argument-vector child through normal exit, timeout or cancellation."""
    if not args or any(not isinstance(a, str) or "\0" in a for a in args) or timeout <= 0:
        raise ValueError("invalid managed child request")
    result: dict = {"started": False, "pid": None, "child_returncode": None, "exit_code": 127,
              "timed_out": False, "cancelled": False, "settled": True}
    output = error = b""
    try:
        process = subprocess.Popen(args, cwd=cwd, env=env, shell=False,  # nosec B603
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        result.update(error_type=type(exc).__name__, error_message=str(exc))
    else:
        result.update(started=True, pid=process.pid, settled=False)
        deadline = time.monotonic() + timeout
        def stop():
            nonlocal output, error
            if driver and os.name == "nt":
                # Kill only the still-running exact owned driver tree. Docker
                # owners are independently settled from receipts by main().
                killer = subprocess.run([str(Path(env["SYSTEMROOT"]) / "System32/taskkill.exe"),  # nosec B603
                    "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30, check=False)
                result["tree_stop_exit_code"] = killer.returncode
            else:
                process.terminate()
            try:
                output, error = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                output, error = process.communicate(timeout=5)
        try:
            while True:
                cancelled = cancel is not None and cancel.is_set()
                remaining = deadline - time.monotonic()
                if cancelled or remaining <= 0:
                    result.update(cancelled=cancelled, timed_out=not cancelled)
                    stop()
                    break
                try:
                    output, error = process.communicate(timeout=min(0.25, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except KeyboardInterrupt:
            result["cancelled"] = True
            stop()
        finally:
            if process.poll() is None:
                process.kill()
                output, error = process.communicate(timeout=5)
            result.update(child_returncode=process.returncode, settled=process.poll() is not None)
        result["exit_code"] = 130 if result["cancelled"] else 124 if result["timed_out"] else process.returncode
    result.update(output=output.decode("utf-8", errors="replace"), error=error.decode("utf-8", errors="replace"),
                  output_bytes_base64=base64.b64encode(output).decode("ascii"),
                  error_bytes_base64=base64.b64encode(error).decode("ascii"))
    return result


def settle_receipt_owners(phase: str) -> dict:
    """Failure-only fallback: exact successful create receipts, never enumeration."""
    from followups.phase3b_seq2_v1 import verify
    output = ROOT / "runs/phase3b-seq2-v1" / settings()["verification"]
    receipts = [output / ("c2-" + phase + "-create.json")]
    errors = []
    if phase == "boundary":
        boundary = output / "boundary-contract"
        receipts = [boundary / (name + "-create.json") for name in ("negative-tests", "prepare", "core")]
        prepared = boundary / "fixture/prepared.json"
        if prepared.is_file():
            try:
                study = json.loads(prepared.read_text(encoding="utf-8"))["study_sha256"]
                if len(study) != 64 or any(c not in "0123456789abcdef" for c in study):
                    raise ValueError("invalid boundary cleanup identity")
                receipts += [ROOT / "runs/phase3b-seq2-v1/visibility-exports" / study / "mock" / point /
                             "boundary-contract/create.json" for point in ("first-pair", "closure")]
            except Exception as exc:
                errors.append({"receipt": str(prepared), "type": type(exc).__name__, "message": str(exc)})
    outcomes = []
    for receipt in receipts:
        if not receipt.is_file():
            continue
        row = {"receipt": receipt.relative_to(ROOT).as_posix(), "passed": False}
        try:
            record = json.loads(receipt.read_text(encoding="utf-8"))
            owner = record.get("stdout", record.get("output", "")).strip()
            if record.get("exit_code") != 0 or len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
                raise ValueError("invalid successful owner receipt")
            row["owner"] = owner
            state = verify.execute(["docker", "inspect", "--format", "{{json .Image}}", owner], timeout=15)
            row["inspection"] = state
            if state["exit_code"] == 0:
                if state["stdout"].strip('\"\r\n') not in (verify.IMAGE,
                        "sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d"):
                    raise ValueError("receipt owner has foreign image")
                row["stop"] = verify.execute(["docker", "stop", "--time", "10", owner], timeout=30)
                row["remove"] = verify.execute(["docker", "rm", owner], timeout=30)
            absent = verify.execute(["docker", "inspect", "--format", "{{json .State.Running}}", owner], timeout=15)
            row["absence"] = absent
            row["passed"] = absent["exit_code"] != 0 and "no such object" in absent["stderr"].casefold()
        except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
            row.update(error_type=type(exc).__name__, error_message=str(exc))
        outcomes.append(row)
    return {"passed": not errors and all(row["passed"] for row in outcomes), "owners": outcomes, "discovery_errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("candidate", "main", "replay", "windows", "supervised", "host", "seal"))
    parser.add_argument("--supervisor-agent")
    options = parser.parse_args()
    phase = options.phase
    if Path.cwd().resolve() != ROOT:
        raise ValueError("exact RA1 working root required")
    env = clean_environment(ROOT)
    os.environ.clear()
    os.environ.update(env)
    sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / ".upstream/harness2")]
    config = settings()
    number = config["candidate"]
    candidate = authenticate_candidate(ROOT, HERE / f"candidate-{number}.json", HERE / f"prospective-acceptance-{number}.json")
    from followups.phase3b_seq2_v1.support import require, source_identity

    require(source_identity()["sha256"] == candidate["source_sha256"], "current RA1 source changed")
    if phase in {"candidate", "main", "replay", "host"}:
        admit({"candidate": "candidate", "main": "main", "replay": "saved", "host": "S13"}[phase], candidate)
    if phase == "candidate":
        return 0
    driver = ROOT / "evidence/phase3b-seq2-c2-v1/run_composed.py"
    if phase in ("windows", "host"):
        driver = ROOT / "evidence/phase3b-la1-v1/host_acceptance.py"
    args = [sys.executable, "-B", str(driver), phase]
    if phase == "host":
        from followups.phase3b_seq2_v1.supervision import agent_name
        args += ["--supervisor-agent", agent_name(options.supervisor_agent)]
    try:
        result = run_child(args, cwd=ROOT, env=env, timeout=candidate["operator_timeout_seconds"][phase], driver=True)
    except BaseException as exc:
        def partial_bytes(name, failure=exc):
            value = getattr(failure, name, None) or b""
            return value if isinstance(value, bytes) else value.encode("utf-8")
        result = {"exit_code": 1, "settled": False, "exception_type": type(exc).__name__,
                  "exception_message": str(exc), "traceback": traceback.format_exc(),
                  "partial_output_base64": base64.b64encode(partial_bytes("stdout")).decode(),
                  "partial_error_base64": base64.b64encode(partial_bytes("stderr")).decode()}
    if result["exit_code"] != 0:
        try:
            result["failure_owner_cleanup"] = settle_receipt_owners(phase)
        except Exception as exc:
            result["emergency_cleanup_error"] = {"passed": False, "type": type(exc).__name__, "message": str(exc)}
        if phase == "host":
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("la1_host_cleanup", ROOT / "evidence/phase3b-la1-v1/host_acceptance.py")
                if spec is None or spec.loader is None:
                    raise ValueError("host emergency cleanup cannot load")
                helper = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(helper)
                result["host_failure_owner_cleanup"] = helper.emergency_cleanup()
            except Exception as exc:
                result["host_emergency_cleanup_error"] = {"passed": False, "type": type(exc).__name__, "message": str(exc)}
    target = ROOT / "runs/phase3b-seq2-v1" / config["verification"] / ("operator-" + phase + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
