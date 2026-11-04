"""Harmless actual driver+grandchild cancellation/timeout; no campaign imports."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(output: Path) -> dict:
    spec = importlib.util.spec_from_file_location("la1_probe_helpers", HERE / "launcher_probe.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    helpers.fresh_output(output)
    output.mkdir(parents=True)
    launcher = helpers.import_launcher()
    source_sha = hashlib.sha256(helpers.LAUNCHER.read_bytes()).hexdigest()
    script = output / "harmless tree driver.py"
    script.write_text("import json,os,subprocess,sys,time\n" +
        "p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],env=dict(os.environ))\n" +
        "print(json.dumps({'driver_pid':os.getpid(),'grandchild_pid':p.pid}),flush=True)\n" +
        "time.sleep(60)\n", encoding="utf-8")
    outcomes = []
    for name in ("timeout", "cancellation"):
        cancel = threading.Event() if name == "cancellation" else None
        timer = threading.Timer(1, cancel.set) if cancel else None
        if timer:
            timer.start()
        try:
            result = launcher.run_child([sys.executable, "-B", str(script)], cwd=helpers.ROOT,
                env=launcher.clean_environment(helpers.ROOT), timeout=1.5 if name == "timeout" else 5,
                cancel=cancel, driver=True)
        finally:
            if timer:
                timer.cancel()
                timer.join()
        pids = json.loads(result["output"].splitlines()[0])
        owners = {key: {"pid": pid, **helpers.settled(pid)} for key, pid in pids.items()}
        if (result["pid"] != pids["driver_pid"] or result.get("tree_stop_exit_code") != 0
                or not result["settled"] or not all(row["verified"] for row in owners.values())
                or result["exit_code"] != (124 if name == "timeout" else 130)
                or not result["timed_out" if name == "timeout" else "cancelled"]):
            helpers.save(output / (name + "-failure.json"), {"result": result, "owners": owners})
            raise AssertionError("actual harmless driver tree did not settle: " + name)
        outcomes.append({"case": name, "passed": True, "result": result, "owners": owners})
        helpers.save(output / (name + ".json"), outcomes[-1])
    if hashlib.sha256(helpers.LAUNCHER.read_bytes()).hexdigest() != source_sha:
        raise AssertionError("operator changed during harmless tree probes")
    receipt = {"kind": "phase3b-la1-tree-probe-v1", "passed": True,
        "launcher_sha256": source_sha, "outcomes": outcomes,
        "provider_calls": 0, "Docker_calls": 0, "project_workflows": 0}
    helpers.save(output / "tree-result.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output), ensure_ascii=True, sort_keys=True))
