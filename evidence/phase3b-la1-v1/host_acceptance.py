"""Invoke unchanged Windows and genuinely supervised host checks for LA1."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from followups.phase3b_seq2_v1 import verify
from followups.phase3b_seq2_v1.support import recovery_config

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "runs/phase3b-seq2-v1" / recovery_config()["verification"]


def emergency_cleanup() -> dict:
    """Settle only new inspected launcher owners and exact named create receipts."""
    from followups.phase3b_seq2_v1.support import read
    launcher = ROOT / "runs/phase3b-seq2-v1/launcher"
    errors = []
    def load(record_path):
        try:
            return read(record_path)
        except Exception as exc:
            errors.append({"receipt": str(record_path), "type": type(exc).__name__, "message": str(exc)})
            return None
    baseline = load(OUTPUT / "host-launcher-before.json")
    before = set(baseline["names"]) if baseline else None
    receipts, owners, allowed_studies = [], [], set()
    for study_path in (OUTPUT / "release/study.json", OUTPUT / "operational-rehearsal/release/study.json"):
        record = load(study_path)
        identity = record.get("study_sha256", "") if record else ""
        if len(identity) == 64 and all(c in "0123456789abcdef" for c in identity):
            allowed_studies.add(identity)
        else:
            errors.append({"receipt": str(study_path), "message": "invalid cleanup study identity"})
    for name in sorted(set(os.listdir(launcher)) - before) if before is not None else []:
        if not any(name.endswith(suffix) for suffix in (".inspection.json", ".preflight-container.json")):
            continue
        try:
            nonce = name.split(".")[0]
            if len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
                raise ValueError("unknown new launcher inspection name")
            record = load(launcher / name)
            if record is None:
                continue
            item = record["container"] if name.endswith(".inspection.json") else record
            if name.endswith(".inspection.json") and record["preflight"]["study_sha256"] not in allowed_studies:
                raise ValueError("foreign new launcher study")
            command = item["command"]
            study_argument = command[command.index("--study") + 1]
            prefix = "/results/" + OUTPUT.relative_to(ROOT / "runs").as_posix()
            if study_argument not in {prefix + "/release/study.json",
                                      prefix + "/operational-rehearsal/release/study.json"}:
                raise ValueError("foreign inspected launcher input")
            owners.append((item["container_id"], item["image"], name))
        except Exception as exc:
            errors.append({"receipt": name, "type": type(exc).__name__, "message": str(exc)})
    receipts += [OUTPUT / "native-fixtures" / mode / "create.json"
                 for mode in ("terminal-readiness", "terminal-later")]
    for study in allowed_studies:
        for point in ("first-pair", "closure"):
            for label in ("supervised", "replay-1", "replay-2"):
                receipts.append(ROOT / "runs/phase3b-seq2-v1/visibility-exports" / study / "mock" / point / label / "create.json")
    for receipt in receipts:
        if receipt.is_file():
            record = load(receipt)
            if record is None:
                continue
            try:
                if record.get("exit_code") != 0:
                    continue
                image = "sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d" if "visibility-exports" in receipt.parts else verify.IMAGE
                owners.append((record["stdout"].strip(), image, receipt.relative_to(ROOT).as_posix()))
            except Exception as exc:
                errors.append({"receipt": str(receipt), "type": type(exc).__name__, "message": str(exc)})
    results = []
    for owner, image, evidence_name in sorted(set(owners)):
        row = {"owner": owner, "receipt": evidence_name, "passed": False}
        try:
            if len(owner) != 64 or any(c not in "0123456789abcdef" for c in owner):
                raise ValueError("invalid inspected owner")
            actual = verify.execute(["docker", "inspect", "--format", "{{json .Image}}", owner], timeout=15)
            row["inspection"] = actual
            if actual["exit_code"] == 0:
                if actual["stdout"].strip('\"\r\n') != image:
                    raise ValueError("exact receipt owner image differs")
                row["stop"] = verify.execute(["docker", "stop", "--time", "10", owner], timeout=30)
                row["remove"] = verify.execute(["docker", "rm", owner], timeout=30)
            absent = verify.execute(["docker", "inspect", "--format", "{{json .State.Running}}", owner], timeout=15)
            row["absence"] = absent
            row["passed"] = absent["exit_code"] != 0 and "no such object" in absent["stderr"].casefold()
        except Exception as exc:
            row.update(error_type=type(exc).__name__, error_message=str(exc))
        results.append(row)
    return {"passed": not errors and all(row["passed"] for row in results), "owners": results, "discovery_errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("windows", "host"))
    parser.add_argument("--supervisor-agent")
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise ValueError("exact LA1 working root required")
    if args.phase == "windows":
        return verify.windows(verify.output_path(str(OUTPUT), existing=True))
    from followups.phase3b_seq2_v1.host_checks import complete_host_checks
    from followups.phase3b_seq2_v1.supervision import agent_name

    launcher = ROOT / "runs/phase3b-seq2-v1/launcher"
    verify.save(OUTPUT / "host-launcher-before.json", {"names": os.listdir(launcher)})
    complete_host_checks(OUTPUT, supervisor_agent=agent_name(args.supervisor_agent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
