"""Harmless actual Windows launch probes; no project workflow or provider use."""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import importlib.util
import json
import os
import subprocess  # nosec B404
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAUNCHER = ROOT / "evidence/phase3b-seq2-c2-v1/launch_candidate.py"
CASES = ("execve-reproduction", "success-argv", "nonzero", "missing-executable",
         "missing-script", "clean-environment", "timeout", "cancellation",
         "auth-changed-source", "auth-missing-review", "auth-foreign-review", "auth-manifest",
         "outer-status-0", "outer-status-7", "execve-minimal")
CHILD = '''import json,os,sys,time
print(json.dumps({"argv":sys.argv[1:],"forbidden_sentinel_present":"LA1_FORBIDDEN_SENTINEL" in os.environ,"required_env":{k:k in os.environ for k in ("SYSTEMROOT","WINDIR","PATH")}},ensure_ascii=False),flush=True)
if sys.argv[1:2]==["sleep"]: time.sleep(60)
raise SystemExit(7 if sys.argv[1:2]==["exit7"] else 0)
'''


def save(target: Path, value) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def clean_env() -> dict:
    return {key: os.environ[key] for key in
            ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if key in os.environ}


def fresh_output(output: Path) -> None:
    if not output.is_absolute() or not output.is_relative_to(HERE) or any(
            part.casefold() in {"..", ".env", "auth.json", "credentials.json", "credential-binding.json",
                ".writer.lock", "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
            or "stdout" in part.casefold() or "stderr" in part.casefold() for part in output.parts):
        raise ValueError("noncanonical/private output before metadata")
    current = HERE
    for part in output.relative_to(HERE).parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked/reparse probe output")
    if output.exists():
        raise ValueError("probe output must be fresh")


def import_launcher():
    spec = importlib.util.spec_from_file_location("la1_probe_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def settled(pid) -> dict:
    """Query this exact owned child only; errors never count as absence."""
    if pid is None:
        return {"verified": True, "classification": "not_started"}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        return {"verified": error == 87, "classification": "absent" if error == 87 else "query_error", "error": error}
    code = ctypes.c_ulong()
    try:
        ok = kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        return {"verified": bool(ok) and code.value != 259, "classification": "exited" if ok and code.value != 259 else "running_or_query_error", "exit_code": code.value}
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


def run(output: Path) -> dict:
    if os.name != "nt" or " " not in sys.executable:
        raise ValueError("fresh LA1-root output and actual spaced Windows interpreter required")
    fresh_output(output)
    output.mkdir(parents=True)
    scripts = output / "harmless scripts ü"
    scripts.mkdir()
    child = scripts / "child script ü.py"
    child.write_text(CHILD, encoding="utf-8")
    arguments = ["space value", 'quote"inside', "trailing\\", "Unicode café 雪"]
    incoming = {**clean_env(), "LA1_FORBIDDEN_SENTINEL": "synthetic-probe-only"}
    env = {key: value for key, value in incoming.items() if key != "LA1_FORBIDDEN_SENTINEL"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    outer = scripts / "execve outer.py"
    outer.write_text("import os,sys\nargs=" + repr([sys.executable, "-B", str(child), *arguments]) +
                     "\nprint('OUTER_ENTERED',flush=True)\nos.execve(sys.executable,args,dict(os.environ))\n", encoding="utf-8")
    repro = subprocess.run([sys.executable, "-B", str(outer)], cwd=ROOT, env=env,  # nosec B603
                           shell=False, capture_output=True, timeout=15, check=False)
    observations = [{"case": "execve-reproduction", "command": [sys.executable, "-B", str(outer)],
        "outer_returncode": repro.returncode, "output_base64": base64.b64encode(repro.stdout).decode(),
        "error_base64": base64.b64encode(repro.stderr).decode(),
        "output": repro.stdout.decode("utf-8", errors="replace"),
        "error": repro.stderr.decode("utf-8", errors="replace"),
        "received_child_json": any(line.startswith(b'{"argv"') for line in repro.stdout.splitlines())}]
    save(output / "execve-reproduction.json", observations[-1])
    launcher = import_launcher()
    env = launcher.clean_environment(ROOT, incoming)
    for name, args, expected in (
            ("success-argv", [sys.executable, "-B", str(child), *arguments], 0),
            ("nonzero", [sys.executable, "-B", str(child), "exit7"], 7),
            ("missing-executable", [str(scripts / "missing.exe")], None),
            ("missing-script", [sys.executable, "-B", str(scripts / "missing.py")], 2),
            ("clean-environment", [sys.executable, "-B", str(child), "env"], 0),
            ("timeout", [sys.executable, "-B", str(child), "sleep"], None),
            ("cancellation", [sys.executable, "-B", str(child), "sleep"], None)):
        cancel = threading.Event() if name == "cancellation" else None
        timer = threading.Timer(0.5, cancel.set) if cancel else None
        if timer:
            timer.start()
        try:
            result = launcher.run_child(args, cwd=ROOT, env=env,
                                        timeout=0.5 if name == "timeout" else 15, cancel=cancel)
        finally:
            if timer:
                timer.cancel()
                timer.join()
        stop = settled(result.get("pid"))
        if not result.get("settled") or not stop["verified"]:
            raise AssertionError("owned harmless child did not settle: " + name)
        if expected is not None and (result.get("exit_code") != expected or result.get("child_returncode") != expected):
            raise AssertionError("child status was not propagated: " + name)
        if name == "missing-executable" and (result.get("started") or result.get("exit_code") == 0):
            raise AssertionError("missing executable was masked")
        if name == "timeout" and not result.get("timed_out"):
            raise AssertionError("timeout missing")
        if name == "cancellation" and not result.get("cancelled"):
            raise AssertionError("cancellation missing")
        if name in {"success-argv", "clean-environment"}:
            received = json.loads(result["output"].splitlines()[-1])
            if received["argv"] != (arguments if name == "success-argv" else ["env"]):
                raise AssertionError("argument values/count changed")
            if received["forbidden_sentinel_present"] or not all(received["required_env"].values()):
                raise AssertionError("clean environment contract failed")
        observations.append({"case": name, "result": result, "owned_child": stop})
        save(output / (name + ".json"), observations[-1])
    from unittest.mock import patch
    for name in ("changed-source", "missing-review", "foreign-review", "manifest"):
        fixture = output / ("auth-" + name)
        fixture.mkdir()
        source = fixture / "harmless source ü.py"
        source.write_text("# standalone authentication fixture, never executed\n", encoding="utf-8")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate = {"source_sha256": "a" * 64,
                     "candidate_sha256": {source.name: "0" * 64 if name == "manifest" else source_sha}}
        candidate_path, review_path = fixture / "candidate.json", fixture / "review.json"
        save(candidate_path, candidate)
        if name != "missing-review":
            save(review_path, {"passed": True,
                "reviewer": "/root/foreign" if name == "foreign-review" else "/root/s2_a1_source_review",
                "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                "source_sha256": candidate["source_sha256"]})
        if name == "changed-source":
            source.write_text("# changed harmless fixture\n", encoding="utf-8")
        with patch.object(launcher, "run_child", side_effect=AssertionError("auth negative attempted child")) as denied:
            try:
                launcher.authenticate_candidate(fixture, candidate_path, review_path,
                                                reviewer="/root/s2_a1_source_review")
            except (ValueError, OSError) as exc:
                outcome = {"case": "auth-" + name, "expected_rejection": type(exc).__name__, "child_attempts": denied.call_count}
            else:
                raise AssertionError("authentication negative accepted: " + name)
            if denied.call_count:
                raise AssertionError("authentication negative started child")
        observations.append(outcome)
        save(output / ("auth-" + name + ".json"), outcome)
    result = {"kind": "phase3b-la1-launcher-probe-v1", "process_cases_completed": True,
        "authentication_cases_completed": True, "interpreter": sys.executable,
        "launcher_sha256": hashlib.sha256(LAUNCHER.read_bytes()).hexdigest(), "observations": observations,
        "provider_calls": 0, "Docker_calls": 0, "project_workflows": 0}
    save(output / "process-result.json", result)
    return result


def outer_status(output: Path) -> dict:
    """Harmless standalone wrapper propagates actual managed child status."""
    if os.name != "nt":
        raise ValueError("fresh ordinary LA1 output required")
    fresh_output(output)
    output.mkdir(parents=True)
    child = output / "status child ü.py"
    child.write_text("import sys\nraise SystemExit(int(sys.argv[1]))\n", encoding="utf-8")
    wrapper = output / "managed outer ü.py"
    wrapper.write_text("import importlib.util,json,sys\nfrom pathlib import Path\n" +
        "s=importlib.util.spec_from_file_location('la1'," + repr(str(LAUNCHER)) + ")\n" +
        "m=importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\n" +
        "r=m.run_child([sys.executable,'-B'," + repr(str(child)) + ",sys.argv[1]],cwd=Path(" +
        repr(str(ROOT)) + "),env=m.clean_environment(Path(" + repr(str(ROOT)) + ")),timeout=15)\n" +
        "print(json.dumps(r,ensure_ascii=True),flush=True)\nraise SystemExit(r['exit_code'])\n", encoding="utf-8")
    outcomes = []
    for expected in (0, 7):
        actual = subprocess.run([sys.executable, "-B", str(wrapper), str(expected)], cwd=ROOT,  # nosec B603
            env=clean_env(), shell=False, capture_output=True, timeout=20, check=False)
        managed = json.loads(actual.stdout.decode("utf-8").splitlines()[-1])
        if actual.returncode != expected or managed["exit_code"] != expected or managed["child_returncode"] != expected:
            raise AssertionError("outer wrapper masked real child status")
        owned = settled(managed["pid"])
        if not managed["settled"] or not owned["verified"]:
            raise AssertionError("outer wrapper left a harmless child")
        outcomes.append({"case": "outer-status-" + str(expected), "outer_returncode": actual.returncode,
            "managed": managed, "owned_child": owned, "error": actual.stderr.decode("utf-8", errors="replace")})
    result = {"kind": "phase3b-la1-outer-status-probe-v1", "passed": True,
        "launcher_sha256": hashlib.sha256(LAUNCHER.read_bytes()).hexdigest(), "outcomes": outcomes,
        "project_workflows": 0, "Docker_calls": 0, "provider_calls": 0}
    save(output / "outer-status-result.json", result)
    return result


def execve_minimal(output: Path) -> dict:
    """Historical argument shape, without quote/Unicode/script-space confounds."""
    if os.name != "nt":
        raise ValueError("fresh ordinary LA1 output required")
    fresh_output(output)
    output.mkdir(parents=True)
    child, outer = output / "simple_child.py", output / "simple_outer.py"
    child.write_text("import json,sys\nprint(json.dumps({'argv':sys.argv[1:]}),flush=True)\n", encoding="utf-8")
    args = [sys.executable, "-B", str(child), "boundary"]
    outer.write_text("import os,sys\nprint('OUTER_ENTERED',flush=True)\nos.execve(sys.executable," + repr(args) + ",dict(os.environ))\n", encoding="utf-8")
    actual = subprocess.run([sys.executable, "-B", str(outer)], cwd=ROOT, env=clean_env(),  # nosec B603
        shell=False, capture_output=True, timeout=15, check=False)
    result = {"kind": "phase3b-la1-execve-minimal-v1", "interpreter": sys.executable,
        "args": args, "outer_returncode": actual.returncode,
        "output": actual.stdout.decode("utf-8", errors="replace"),
        "error": actual.stderr.decode("utf-8", errors="replace"),
        "output_bytes_base64": base64.b64encode(actual.stdout).decode(),
        "error_bytes_base64": base64.b64encode(actual.stderr).decode(),
        "received_child_json": any(line.startswith(b'{"argv"') for line in actual.stdout.splitlines()),
        "provider_calls": 0, "Docker_calls": 0, "project_workflows": 0}
    save(output / "execve-minimal-result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outer-only", action="store_true")
    parser.add_argument("--execve-minimal", action="store_true")
    args = parser.parse_args()
    operation = execve_minimal if args.execve_minimal else outer_status if args.outer_only else run
    print(json.dumps(operation(args.output), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
