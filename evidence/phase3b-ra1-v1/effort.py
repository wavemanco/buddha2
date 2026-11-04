"""Append-only per-actor focused effort; overlapping active intervals are summed."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
LOGS = BASE / "effort"
TARGET = 14400

def now():
    return datetime.now(timezone.utc)

def records(target, observed):
    if target.is_symlink() or not target.is_file():
        raise ValueError("effort log must be an ordinary file")
    result: list[tuple[datetime, dict[str, Any]]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if set(row) != {"at_utc", "actor", "mode", "note"} or row["mode"] not in {"active", "wait", "done"}:
            raise ValueError("invalid effort record")
        stamp = datetime.fromisoformat(row["at_utc"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > observed:
            raise ValueError("future or naive effort timestamp")
        if not isinstance(row["actor"], str) or not row["actor"] or not isinstance(row["note"], str):
            raise ValueError("invalid effort actor/note")
        if result and (stamp < result[-1][0] or row["actor"] != result[0][1]["actor"]):
            raise ValueError("effort log reordered or actor changed")
        result.append((stamp, row))
    if not result or result[0][1]["mode"] != "active":
        raise ValueError("effort actor must register with active")
    return result

def status(observed=None):
    observed = observed or now()
    authority = json.loads((BASE / "authority.json").read_text(encoding="utf-8"))
    if (authority["aggregate_focused_engineering_target_seconds"] != TARGET
            or authority.get("target_is_hard_abort") is not False):
        raise ValueError("effort authority changed")
    since = datetime.fromisoformat(authority["recorded_at_utc"])
    actors = []
    for name in sorted(os.listdir(LOGS)):
        if name.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json", "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache"} or "stdout" in name.casefold() or "stderr" in name.casefold():
            raise ValueError("private/cache/stream name rejected before effort metadata")
        if not re.fullmatch(r"[a-z0-9_-]+\.jsonl", name):
            raise ValueError("invalid effort filename")
        target = LOGS / name
        items = records(target, observed)
        if items[0][0] < since:
            raise ValueError("effort predates this authority")
        total = 0.0
        for index, (start, row) in enumerate(items):
            end = items[index+1][0] if index+1 < len(items) else observed
            if row["mode"] == "active":
                total += (end-start).total_seconds()
        actors.append({"file": target.name, "actor": items[0][1]["actor"], "mode": items[-1][1]["mode"],
                       "active_seconds": round(total, 6), "records": len(items)})
    if not actors or not (LOGS / "root.jsonl").is_file():
        raise ValueError("root effort registration required")
    measured = sum(row["active_seconds"] for row in actors)
    charge = authority["preledger_bootstrap_charge_seconds"]
    if not isinstance(charge, int) or charge < 0:
        raise ValueError("invalid conservative bootstrap charge")
    additional = 0
    for name in sorted(os.listdir(BASE / "charges")):
        if (name.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json",
                "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
                or "stdout" in name.casefold() or "stderr" in name.casefold()):
            raise ValueError("private/cache/stream charge name rejected before metadata")
        if not re.fullmatch(r"[a-z0-9_-]+\.json", name):
            raise ValueError("invalid effort charge filename")
        target = BASE / "charges" / name
        if target.is_symlink() or not target.is_file():
            raise ValueError("effort charge must be an ordinary file")
        item = json.loads(target.read_text(encoding="utf-8"))
        if (set(item) != {"kind", "seconds", "recorded_at_utc", "basis"}
                or item["kind"] != "phase3b-ra1-conservative-effort-charge-v1"
                or type(item["seconds"]) is not int or item["seconds"] <= 0
                or not isinstance(item["basis"], str) or not item["basis"]):
            raise ValueError("invalid conservative effort charge")
        stamp = datetime.fromisoformat(item["recorded_at_utc"])
        if stamp.tzinfo is None or not since <= stamp <= observed:
            raise ValueError("effort charge outside authority interval")
        additional += item["seconds"]
    total = measured + charge + additional
    return {"observed_at_utc": observed.isoformat(), "target_seconds": TARGET, "target_is_hard_abort": False,
            "measured_seconds": round(measured, 6), "conservative_charge_seconds": charge + additional,
            "bootstrap_charge_seconds": charge, "additional_charge_seconds": additional,
            "active_seconds": round(total, 6), "remaining_to_target_seconds": round(TARGET-total, 6),
            "review_due": total >= TARGET,
            "review_milestones_reached": [n for n in (7200, 10800, TARGET) if total >= n], "actors": actors}

def mark(filename, actor, mode, note):
    if not re.fullmatch(r"[a-z0-9_-]+", filename) or not actor or not note:
        raise ValueError("invalid effort mark")
    target = LOGS / (filename + ".jsonl")
    observed = now()
    if target.exists():
        prior = records(target, observed)
        if prior[0][1]["actor"] != actor:
            raise ValueError("effort actor/file ownership mismatch")
    elif mode != "active":
        raise ValueError("new actor must begin active")
    with target.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"at_utc": observed.isoformat(), "actor": actor, "mode": mode, "note": note}, sort_keys=True)+"\n")
    return status()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file")
    p.add_argument("--actor")
    p.add_argument("--mark", choices=("active", "wait", "done"))
    p.add_argument("--note")
    a=p.parse_args()
    if a.mark:
        if not all((a.file,a.actor,a.note)):
            p.error("mark requires file/actor/note")
        result=mark(a.file,a.actor,a.mark,a.note)
    else:
        result=status()
    print(json.dumps(result, sort_keys=True))
    return 0  # Planning-target crossings require review, never a seconds-level abort.

if __name__ == "__main__":
    raise SystemExit(main())
