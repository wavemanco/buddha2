"""Fetch/verify only the two public pinned sources inside the new project."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "harness2": (
        "https://github.com/google-research/harness2.git",
        "1cfe254e8d25b15f37048c3730134686abe60335",
    ),
    "novelty-bench": (
        "https://github.com/novelty-bench/novelty-bench.git",
        "64a23be6b18ec1dacc298830aab276061b6e143c",
    ),
}


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *arguments],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    arguments = parser.parse_args()
    if ROOT.name != "Buddha2" or ROOT.parent.name != "research":
        raise SystemExit("source setup must run from the new research/Buddha2 checkout")
    upstreams = {}
    for name, (url, commit) in PINS.items():
        checkout = ROOT / ".upstream" / name
        for path in (ROOT / ".upstream", checkout):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise SystemExit("source paths must not be links/junctions")
        if not checkout.exists():
            if not arguments.fetch:
                raise SystemExit(f"missing source: {name}; run setup first")
            git("clone", "--depth", "1", "--no-checkout", url, str(checkout))
            git("-C", str(checkout), "fetch", "--depth", "1", "origin", commit)
            git("-C", str(checkout), "checkout", "--detach", commit)
        if git("-C", str(checkout), "rev-parse", "HEAD") != commit:
            raise SystemExit(f"wrong source revision: {name}")
        if git("-C", str(checkout), "status", "--porcelain"):
            raise SystemExit(f"upstream source is modified: {name}")
        files = {}
        for relative in git("-C", str(checkout), "ls-files").splitlines():
            path = checkout / relative
            if path.is_symlink() or not path.resolve().is_relative_to(checkout.resolve()):
                raise SystemExit("upstream contains an unsupported linked source")
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        upstreams[name] = {"url": url, "commit": commit, "files": files}
    record = {"schema_version": 1, "upstreams": upstreams}
    target = ROOT / "upstreams.lock.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != record:
            raise SystemExit("source content differs from the recorded pins; refusing to replace lock")
    else:
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({name: data["commit"] for name, data in upstreams.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
