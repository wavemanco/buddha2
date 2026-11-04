"""Bind the reviewed cold algorithm with static repairs to the extracted RA1 identity."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
from typing import Any

p = argparse.ArgumentParser(__doc__)
p.add_argument("--index-sha256", required=True)
p.add_argument("--source-sha256", required=True)
p.add_argument("--study-sha256", required=True)
p.add_argument("--candidate", type=int, choices=(1, 2), required=True)
a = p.parse_args()
for value in (a.index_sha256, a.source_sha256, a.study_sha256):
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid frozen cold identity")
path = Path(__file__).resolve().with_name("cold_replay.py")
if not path.is_relative_to(Path("/workspace")) or hashlib.sha256(path.read_bytes()).hexdigest() != "daab8abfa3797477ad8eb46cfcb030ab5b1cd5f02667f423929cff48c5ba5ae4":
    raise ValueError("extracted RA1 cold worker differs")
spec = importlib.util.spec_from_file_location("ra1_unchanged_cold", path)
if spec is None or spec.loader is None:
    raise ValueError("cold worker unavailable")
worker: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
worker.SOURCE = a.source_sha256
worker.STUDY = a.study_sha256
worker.VERIFICATION = Path("/results/phase3b-seq2-v1") / ("verification-ra1-v" + str(a.candidate))
worker.INDEX = Path("/workspace/evidence/phase3b-seq2-v1") / ("offline-kit-ra1-c" + str(a.candidate) + "-index.json")
worker.main(a.index_sha256)
