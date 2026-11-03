"""Freeze the P2-R continuation kit with verified member bytes; never overwrite."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/phase2-release-r018"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    if ROOT != Path(r"C:\Users\arvik\code\research\Buddha2") or ROOT.is_symlink():
        raise RuntimeError("packaging requires the new project")
    members = {}
    excluded = {"manifest.json", "p2r-execution-kit.zip", "package-record.json", "package-review.json"}
    for folder in (EVIDENCE, ROOT / "runs/phase2-release-r018", ROOT / "src", ROOT / "tests"):
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or (path.parent == EVIDENCE and path.name in excluded):
                continue
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(ROOT):
                raise RuntimeError("package member escapes project")
            members[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("AGENTS.md", "README.md", "EXPERIMENT_PLAN.md", "PHASE_DEFINITIONS.md",
                 "PRE_PHASE2B_BLOCK.md", "PHASE2B_EXECUTION_KIT_REPORT.md", "PHASE2B_RUNBOOK.md",
                 "DECISIONS.md", "requirements.lock", "requirements-build.lock", "upstreams.lock.json",
                 "phase0.ps1", "phase2-release.ps1", "specifications/archive/phase-definitions-0.18.md"):
        members[name] = (ROOT / name).read_bytes()
    study = json.loads((ROOT / "runs/phase2-release-r018/release/study.json").read_text(encoding="utf-8"))
    manifest = {"kind": "p2r-complete-execution-kit-manifest", "specification": "0.18", "closure": "0.19",
                "study_sha256": study["study_sha256"], "files": {name: sha(raw) for name, raw in members.items()},
                "limitations": "Continuation snapshot requiring this project's preserved parent studies, pinned upstreams and installed immutable image. No paid authority or credentials included."}
    raw_manifest = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    with (EVIDENCE / "manifest.json").open("xb") as stream:
        stream.write(raw_manifest)
    members["evidence/phase2-release-r018/manifest.json"] = raw_manifest
    target = EVIDENCE / "p2r-execution-kit.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(members):
            raise RuntimeError("archive inventory/CRC mismatch")
        if any(archive.read(name) != raw for name, raw in members.items()):
            raise RuntimeError("archive bytes mismatch")
    record = {"kind": "p2r-execution-kit-package", "entries": len(members), "bytes": target.stat().st_size,
              "archive_sha256": sha(target.read_bytes()), "manifest_sha256": sha(raw_manifest),
              "all_members_verified": True, "provider_calls": 0, "api_spend_micro_usd": 0,
              "actual_credentials_supplied": False, "paid_authority_included": False}
    with (EVIDENCE / "package-record.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
