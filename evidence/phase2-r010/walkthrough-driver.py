"""Retained Phase 2A verification driver: bounded tmpfs, then preserve exact files.

This is software evidence only. Run inside the pinned, network-disabled image
with the new project read-only and its run directory as /results. It does not
construct provider transports, load credentials, or authorize live work.
"""

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
study = read_json(Path("/results/phase2-r010/prepared/study.json"))
staged = root / "walkthrough"
first = walkthrough(study, staged)
before = tree_hashes(staged)
replayed = replay_assessments(study, staged)
resumed = walkthrough(study, staged)
if resumed["new_fixture_dispatches"] != 0 or tree_hashes(staged) != before:
    raise RuntimeError("replay or resume changed immutable artifacts or dispatched again")
destination = Path("/results/phase2-r010/walkthrough-final")
shutil.copytree(staged, destination)
if tree_hashes(destination) != before:
    raise RuntimeError("preserved walkthrough files differ from tmpfs verification")
evidence = {"study_sha256": study["study_sha256"], "first": first,
            "replay": replayed, "resumed": resumed, "files": before,
            "provider_calls": 0, "experiment_api_spend_usd": 0,
            "storage_note": "Executed in bounded container tmpfs; files copied byte-for-byte to the approved run root."}
write_once(Path("/results/phase2-r010/walkthrough-execution.json"), evidence)
print(json.dumps({"first": first, "replay": replayed, "resumed": resumed,
                  "preserved_files": len(before), "provider_calls": 0}))
