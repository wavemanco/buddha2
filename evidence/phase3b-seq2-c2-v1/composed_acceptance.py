"""C2 main acceptance and separately guarded, generation-free saved replay."""
from __future__ import annotations

import argparse
import importlib.util
import os
import stat
from pathlib import Path

from buddha2.artifacts import file_hash
from followups.phase3b_seq2_v1 import verify, workflow
from followups.phase3b_seq2_v1.support import PRIVATE, checked, read, require, safe, source_identity

ROOT = Path(__file__).resolve().parents[2]
SAVED_WORKER = ROOT / (
    "runs/phase3b-seq2-v1/verification-v2/external-reviews/"
    "recovery-review-v1/saved_only_worker_v2.py"
)
SAVED_WORKER_SHA = "99b2f90abf62b9de4999b8a461c7b5fc9b9c57c569a79e5c64dda427f64f5bb5"


def ordinary_inventory(directory: Path) -> dict:
    """Add the new capacity root to the unchanged R1 worker's input coverage."""
    result = {}

    def walk(parent: Path) -> None:
        for name in sorted(os.listdir(parent)):
            if name.casefold() in PRIVATE or "stdout" in name.casefold() or "stderr" in name.casefold():
                continue
            target = safe(parent / name)
            info = target.lstat()
            if stat.S_ISDIR(info.st_mode):
                walk(target)
            elif stat.S_ISREG(info.st_mode):
                result[target.relative_to(directory).as_posix()] = {
                    "sha256": file_hash(target), "bytes": info.st_size,
                    "mode": stat.S_IMODE(info.st_mode),
                }
            else:
                raise ValueError("nonordinary current capacity input")

    walk(safe(directory))
    return result


def saved_replay(output: Path) -> int:
    """Parameterize the already reviewed R1 worker; retain its real run/guards."""
    require({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "network-none required")
    study_path = output / "release/study.json"
    study = workflow.load_study(study_path)
    source = source_identity()
    require(study["source_sha256"] == source["sha256"], "current source differs")
    matrix = checked(read(output / "matrix.json"))
    require(matrix["passed"] is True and all(matrix[key] == study[key] for key in verify.BINDINGS),
            "current complete matrix required")
    require(file_hash(SAVED_WORKER) == SAVED_WORKER_SHA, "reviewed saved-only worker changed")
    replay_output = output / "external-reviews/c2-saved-replay"
    replay_output.mkdir(parents=True, exist_ok=False)
    module_spec = importlib.util.spec_from_file_location("c2_reviewed_saved_worker", SAVED_WORKER)
    if module_spec is None or module_spec.loader is None:
        raise ValueError("saved worker cannot load")
    worker = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(worker)
    # Bind the immutable algorithm to this fresh identity and destination. Its
    # original source/history, physical journal, report and fail-before-call
    # checks remain in perform(), including the real workflow.run invocation.
    worker.ROOT = ROOT
    worker.BASE = workflow.BASE
    worker.VERIFY = output
    worker.REVIEW = replay_output
    worker.OUTPUT = replay_output
    worker.SOURCE = study["source_sha256"]
    worker.STUDY = study["study_sha256"]
    worker.NATIVE, worker.JOURNAL = workflow.paths(study, True)
    capacity = workflow.NATIVE / ("capacity-" + output.name)
    capacity_before = ordinary_inventory(capacity)
    verify.save(replay_output / "capacity-before.json", capacity_before)
    details = worker.perform({"worker_sha256": SAVED_WORKER_SHA,
                              "source_sha256": worker.SOURCE, "study_sha256": worker.STUDY})
    capacity_after = ordinary_inventory(capacity)
    verify.save(replay_output / "capacity-after.json", capacity_after)
    require(capacity_before == capacity_after and not any(worker.COUNTS.values()),
            "current capacity input changed or forbidden activity attempted")
    verify.save(replay_output / "result.json", {
        **details, "reused_worker_sha256": SAVED_WORKER_SHA,
        "new_capacity_inputs_unchanged": True, "forbidden_attempts": worker.COUNTS,
    })
    verify.record(output, "replay", study, {
        **details, "SDK_and_sockets_blocked": True,
        "new_capacity_inputs_unchanged": True, "reused_worker_sha256": SAVED_WORKER_SHA,
    })
    return 0 if details["passed"] is True else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("main", "replay"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = verify.output_path(args.output, existing=True)
    require(output.name == "verification-v3", "C2 requires its fresh verification root")
    if args.phase == "replay":
        return saved_replay(output)
    require(not (output / "source-before.json").exists(), "main acceptance already attempted")
    return verify.inside(output, saved_replay=False)


if __name__ == "__main__":
    raise SystemExit(main())
