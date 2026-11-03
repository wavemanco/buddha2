"""Retained synthetic verification in bounded tmpfs, preserving failures too."""

import json
import os
import shutil
from pathlib import Path

from buddha2.__main__ import _offline, _upstreams
from buddha2.artifacts import read_json, tree_hashes, write_once
from buddha2.phase2 import replay_assessments, walkthrough

_offline()
_upstreams()
root = Path("/tmp/phase2a")
root.mkdir()
os.environ["BUDDHA2_OUTPUT_ROOT"] = str(root)
study = read_json(Path("/results/phase2-r010/prepared-final/study.json"))
staged = root / "walkthrough"
destination = Path("/results/phase2-r010/walkthrough-final")
if destination.exists():
    raise RuntimeError("verification destination already exists; preserve it")
evidence = {"study_sha256": study["study_sha256"], "status": "started",
            "provider_calls": 0, "experiment_api_spend_usd": 0,
            "storage_note": "Bounded container tmpfs; exact files preserved in the approved run root."}
try:
    evidence["first"] = walkthrough(study, staged)
    before = tree_hashes(staged)
    evidence["replay"] = replay_assessments(study, staged)
    evidence["resumed"] = walkthrough(study, staged)
    if evidence["resumed"]["new_fixture_dispatches"] != 0 or tree_hashes(staged) != before:
        raise RuntimeError("replay or resume changed immutable artifacts or dispatched again")
    evidence["status"] = "passed"
finally:
    if staged.exists():
        evidence["files"] = tree_hashes(staged)
        shutil.copytree(staged, destination)
        if tree_hashes(destination) != evidence["files"]:
            raise RuntimeError("preserved walkthrough files differ from tmpfs verification")
    write_once(Path("/results/phase2-r010/walkthrough-execution-final.json"), evidence)
print(json.dumps({key: value for key, value in evidence.items() if key != "files"}))
