"""Authenticate one reviewed C2 candidate, then replace this clean host process."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("boundary", "main", "replay"))
    phase = parser.parse_args().phase
    if Path.cwd().resolve() != ROOT:
        raise ValueError("exact C2 working root required")
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT") if k in os.environ}
    env.update(PYTHONPATH=os.pathsep.join(str(p) for p in (ROOT, ROOT / "src", ROOT / ".upstream/harness2")),
               BUDDHA2_OUTPUT_ROOT=str(ROOT / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    os.environ.clear()
    os.environ.update(env)
    sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / ".upstream/harness2")]
    from followups.phase3b_seq2_v1.support import file_hash, read, require, safe, source_identity

    candidate_path = HERE / "candidate-v3.json"
    candidate = read(candidate_path)
    review = read(HERE / "prospective-acceptance-v3.json")
    require(review.get("passed") is True and review.get("reviewer") == "/root/s2_a1_source_review"
            and review.get("candidate_sha256") == file_hash(candidate_path)
            and review.get("source_sha256") == candidate["source_sha256"], "unreviewed C2 candidate")
    for name, expected in candidate["candidate_sha256"].items():
        require(file_hash(safe(ROOT / name)) == expected, "reviewed C2 file changed")
    require(source_identity()["sha256"] == candidate["source_sha256"], "current C2 source changed")
    driver = HERE / ("run_boundary.py" if phase == "boundary" else "run_composed.py")
    args = [sys.executable, "-B", str(driver)] + ([] if phase == "boundary" else [phase])
    # Exact interpreter and reviewed local driver; no shell or inherited keys.
    os.execve(sys.executable, args, env)  # nosec B606: exact interpreter and reviewed local driver


if __name__ == "__main__":
    main()
