"""Snapshot the AM-1 offline handoff; never edit retained parent evidence."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = Path(r"C:\Users\arvik\code\research\Buddha2")
EVIDENCE = ROOT / "evidence/phase2-am1-r016"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    if ROOT.resolve(strict=True) != EXPECTED or ROOT.is_symlink():
        raise RuntimeError("packaging is restricted to the new project")
    members: dict[str, bytes] = {}
    excluded = {"manifest.json", "am1-offline-kit.zip", "package-record.json", "package-review.json"}
    roots = (EVIDENCE, ROOT / "runs/phase2-am1-r016", ROOT / "tests")
    for folder in roots:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or (path.parent == EVIDENCE and path.name in excluded):
                continue
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(ROOT):
                raise RuntimeError("handoff source escapes the approved root")
            members[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("AGENTS.md", "README.md", "EXPERIMENT_PLAN.md", "PHASE_DEFINITIONS.md",
                 "PHASE2_AM1_REPORT.md", "DECISIONS.md", "requirements.lock",
                 "requirements-build.lock", "upstreams.lock.json", "phase0.ps1",
                 "specifications/archive/phase-definitions-0.15.md",
                 "specifications/archive/phase-definitions-0.16.md"):
        members[name] = (ROOT / name).read_bytes()
    manifest = {"kind": "am1-offline-handoff-manifest", "specification": "0.16",
                "closure_specification": "0.17", "files": {name: sha(raw) for name, raw in members.items()},
                "limitations": "Continuation snapshot for the existing project. Requires its retained "
                              "parent records, pinned upstream checkouts and immutable runtime image; "
                              "not a standalone install or provider-enabled launcher."}
    raw_manifest = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    manifest_path = EVIDENCE / "manifest.json"
    archive_path = EVIDENCE / "am1-offline-kit.zip"
    if manifest_path.exists() or archive_path.exists():
        raise RuntimeError("handoff already packaged; preserve it rather than overwrite")
    manifest_path.write_bytes(raw_manifest)
    members["evidence/phase2-am1-r016/manifest.json"] = raw_manifest
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(members):
            raise RuntimeError("handoff archive inventory/CRC differs")
        for name, raw in members.items():
            if archive.read(name) != raw:
                raise RuntimeError("handoff archive bytes differ")
    record = {"kind": "am1-offline-handoff-package", "entries": len(members),
              "archive_bytes": archive_path.stat().st_size,
              "archive_sha256": sha(archive_path.read_bytes()), "manifest_sha256": sha(raw_manifest),
              "all_members_verified": True, "provider_calls": 0,
              "api_spend_micro_usd": 0, "provider_enabled_launcher": False}
    (EVIDENCE / "package-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
