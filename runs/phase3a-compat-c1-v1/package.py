"""Assemble and verify the public C1 closure packet after all acceptance gates."""
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/phase3a-compat-c1-v1"
VERIFY = ROOT / "runs/phase3a-compat-c1-v1/verification-v7"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}


def safe(name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or any(p in PRIVATE for p in rel.parts):
        raise ValueError("unsafe/private packet input")
    path = ROOT.joinpath(*rel.parts)
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
        raise ValueError("linked packet input")
    return path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def publish(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    result = read(VERIFY / "result.json")
    if not result["passed"] or read(VERIFY / "host-execution.json")["exit_code"] != 0:
        raise ValueError("complete contained verification required before packaging")
    source = read(VERIFY / "source-before.json")
    if source != read(VERIFY / "source-after.json"):
        raise ValueError("source changed during verification")
    names = set(source["files"])
    names.update({"CURRENT_SPEC.md", "PHASE3A_C1_REPORT.md", "C1_OFFLINE_RUNBOOK.md",
        "PHASE3A_POST_C1_LIVE_READINESS_DEFINITION.md", "runs/phase3a-compat-c1-v1/package.py"})
    for directory in (VERIFY, ROOT / "runs/phase3a-compat-c1-v1/verification-v1",
                      ROOT / "runs/phase3a-compat-c1-v1/verification-v2",
                      ROOT / "runs/phase3a-compat-c1-v1/verification-v3",
                      ROOT / "runs/phase3a-compat-c1-v1/verification-v4",
                      ROOT / "runs/phase3a-compat-c1-v1/verification-v5",
                      ROOT / "runs/phase3a-compat-c1-v1/verification-v6", OUT):
        for parent, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = [n for n in dirs if n not in PRIVATE and n != "__pycache__"]
            for n in files:
                if n in PRIVATE or (Path(parent) == OUT and n in {"offline-kit-v1.zip", "manifest.json", "closeout.json"}):
                    continue
                names.add((Path(parent) / n).relative_to(ROOT).as_posix())
    members = {name: sha(safe(name)) for name in sorted(names)}
    if any(members[name] != value for name, value in source["files"].items()):
        raise ValueError("candidate source changed before packaging")
    packet = {"kind": "phase3a-c1-public-packet-v1", "source_sha256": source["sha256"],
        "member_sha256": members, "real_provider_calls": 0, "real_spent_micro_usd": 0,
        "private_names_excluded_before_stat_read": sorted(PRIVATE),
        "runtime_prerequisite": "existing pinned Docker image and upstream checkouts; no downloads bundled"}
    archive = OUT / "offline-kit-v1.zip"
    if archive.exists():
        raise ValueError("closure archive already exists")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, expected in members.items():
            path = safe(name)
            if sha(path) != expected:
                raise ValueError("packet input changed during assembly")
            zipped.write(path, name)
        raw = (json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
        zipped.writestr("C1_PACKET_MANIFEST.json", raw)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("archive CRC failed")
        for name, expected in members.items():
            if hashlib.sha256(zipped.read(name)).hexdigest() != expected:
                raise ValueError("archive member checksum failed")
        if zipped.read("C1_PACKET_MANIFEST.json") != raw:
            raise ValueError("packet metadata changed")
    manifest = {**packet, "created_utc": datetime.now(timezone.utc).isoformat(),
        "member_sha256": {**members, "C1_PACKET_MANIFEST.json": hashlib.sha256(raw).hexdigest()},
        "archive_sha256": sha(archive), "archive_bytes": archive.stat().st_size,
        "CRC_and_all_member_SHA256_verified": True,
        "verification_result_sha256": sha(VERIFY / "result.json"),
        "study_sha256": result["demo"]["study_sha256"], "status": "offline-compatible",
        "live_readiness_established": False, "scientific_effectiveness_established": False}
    publish(OUT / "manifest.json", manifest)
    publish(OUT / "closeout.json", {"kind": "phase3a-c1-closeout-v1", "status": "offline-compatible",
        "source_sha256": source["sha256"], "manifest_sha256": sha(OUT / "manifest.json"),
        "archive_sha256": manifest["archive_sha256"], "provider_calls": 0, "spend_micro_usd": 0,
        "original_folder_accessed": False, "automatic_live_launch_authorized": False})
    print(json.dumps({k: manifest[k] for k in ("status", "source_sha256", "archive_sha256", "archive_bytes")}))


if __name__ == "__main__":
    main()
