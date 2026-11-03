"""C1-only identities and public preservation; no live authority or clients."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from buddha2.artifacts import ContractError, digest

ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "PHASE3A_COMPATIBILITY_CHECKPOINT_DEFINITION.md"
OLD_STUDY = "runs/phase3a-r2-v1/release-v1/study.json"
OLD_SHA = "a3b9403d6bc0a144d0bb74e74a330ccf057850da0d23dcb2d9059d94a20883e3"
PRIVATE = frozenset({"credential-binding.json", ".writer.lock", ".env", "credentials.json", "auth.json"})
OPENCODE_FILES = {
    "session/llm.ts": "c55d98991e8eb18f5cfeb1126934a825b3a5d046500e6ce9e59628ab4728301c",
    "agent/agent.ts": "210323495e9bc2be5f200ed9ed747a90c6336b77d2abc1b030f3dc11f18b5195",
    "session/system.ts": "0f8374707f7de40c1910af0aa83fc894184ce59c2fae30b6c38cadbc0d10fb1a",
    "session/prompt/anthropic.txt": "88b202adbeb683e942e6cb45a7d24ed453c71cc48648eff8f170e7bd21f8b4c7",
}


def opencode_profile_sources() -> dict:
    root = Path("/opt/phase3a-opencode/packages/opencode/src")
    require(all(hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
                for name, expected in OPENCODE_FILES.items()), "OpenCode prompt configuration source drift")
    return dict(OPENCODE_FILES)


def runtime_identity() -> dict:
    from followups.phase3a_v1.support import runtime_identity as parent_runtime
    return {**parent_runtime(), "c1_agent_prompt_sources": opencode_profile_sources(),
            "c1_agent_prompt_seam": "agent.build.prompt replaces provider default; environment remains appended"}
# Accepted pre-C1 Git 55cb07b metadata and its authenticated packet member maps.
# Pin the reference records before trusting their maps, not only their self seals.
CLOSED = {
    "evidence/phase3a-definition-v1/preservation-before.json": "a1595667b2235905a0d711999a2468e9f3c3691b2886c28edfcaca68111fb884",
    "evidence/phase3a-r2-v1/offline-execution-kit-v1.manifest.json": "86660f8dbc64d67a73f1495e72bc5ecf41070ea1929e0c6ff70afb6e8ed1e76a",
    "evidence/phase3a-r2-v1/first-pair-v1/manifest.json": "8fb3ea516f6da4dcfc7034e49bf6deca1ace41bc5ec3a1b4a177458a4dc7cda7",
    "evidence/phase3a-r2-v1/live-outcome-v1/manifest.json": "a5072fa016f090a5d42ea7ab41fa2e8d3d3b2b60acf8b3ec2b9f318d0da8562b",
    "runs/phase3a-r2-v1/release-v1/study.json": "117e2d5a2782c14206cbff2fbb9be6b3266eedcc7016bb934bb178d899ba4fbf",
    "runs/phase3a-r2-v1/preservation.json": "9c23f6337d850f745d521f427169e64b79190d7fa9d716eda8d266baefe62ef3",
    "runs/phase3a-r1-v1/release-v1/study.json": "579b09ec89e96d51237430d08ab357e942cb76a0b41efa93bc291166a89f83ab",
    "runs/phase3a-v1/release-v3/study.json": "7203f29ed9acd7f124400702ef8ee545bbbcd324a9d2c31790aaef41bd44b9f5",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def safe(relative: str) -> Path:
    """Exclude private names before filesystem access, including ancestor checks."""
    name = PurePosixPath(relative)
    require(bool(name.parts) and not name.is_absolute() and ".." not in name.parts
            and ":" not in relative and "\\" not in relative
            and not any(part in PRIVATE for part in name.parts), "unsafe/private C1 source path")
    path = ROOT.joinpath(*name.parts)
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (path, *path.parents)), "linked C1 source path")
    return path


def sha(relative: str) -> str:
    with safe(relative).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(relative: str) -> dict:
    value = json.loads(safe(relative).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "C1 reference must be a JSON object")
    return value


def read_closed(relative: str) -> dict:
    require(relative in CLOSED and sha(relative) == CLOSED[relative], "closed reference bytes differ")
    return read(relative)


def parent_source() -> dict:
    study = read_closed(OLD_STUDY)
    source = study["source"]
    require(len(source["files"]) == 157 and digest(source["files"]) == source["sha256"]
            == study["source_sha256"] == OLD_SHA, "frozen R2 source identity differs")
    require(all(sha(name) == expected for name, expected in source["files"].items()),
            "frozen R2 current source changed")
    return source


def source_identity() -> dict:
    """Bind all new executable/test files and the unchanged parent sources."""
    parent = parent_source()
    names = [p.relative_to(ROOT).as_posix() for p in
             (ROOT / "followups/phase3a_compat_c1_v1").rglob("*.py")]
    names += [DEFINITION.relative_to(ROOT).as_posix(), OLD_STUDY]
    files = dict(parent["files"])
    files.update({name: sha(name) for name in sorted(names)})
    return {"kind": "phase3a-c1-source-v1", "parent_source_sha256": OLD_SHA,
            "files": files, "sha256": digest(files)}


def preservation() -> dict:
    """Recheck public closed bytes; private worktree contents are never accessed."""
    parent = parent_source()
    expected = dict(parent["files"])
    for release, count in (("runs/phase3a-v1/release-v3", 142),
                           ("runs/phase3a-r1-v1/release-v1", 149),
                           ("runs/phase3a-r2-v1/release-v1", 157)):
        frozen = read_closed(release + "/study.json")["source"]
        require(len(frozen["files"]) == count and digest(frozen["files"]) == frozen["sha256"],
                "retained source identity differs")
        expected.update({release + "/source/" + name: value for name, value in frozen["files"].items()})
    oldproof = read_closed("runs/phase3a-r2-v1/preservation.json")
    private = set(oldproof["historical_private_fingerprint_Git_identity_only"])
    baseline = read_closed("evidence/phase3a-definition-v1/preservation-before.json")["files"]
    expected.update({name: value for name, value in baseline.items() if name not in private})
    for key in ("committed_prior_reports_unchanged", "historical_archives_and_metadata_unchanged"):
        expected.update(oldproof[key])
    for name in ("evidence/phase3a-r2-v1/offline-execution-kit-v1.manifest.json",
                 "evidence/phase3a-r2-v1/first-pair-v1/manifest.json",
                 "evidence/phase3a-r2-v1/live-outcome-v1/manifest.json"):
        manifest = read_closed(name)
        expected.update({path: value for path, value in manifest["member_sha256"].items()
                         if path != "OFFLINE_PACKET_MANIFEST.json"})
        archive = name.replace(".manifest.json", ".zip") if ".manifest.json" in name else name.replace("manifest.json", "archive.zip")
        expected[archive] = manifest["archive_sha256"]
        expected[name] = sha(name)
    # Only the four exact authenticated public native summary locks are readable.
    empty = hashlib.sha256(b"").hexdigest()
    lock_names = {name for name in expected if PurePosixPath(name).name == "summary.lock"}
    for name in lock_names:
        require(expected[name] == empty and safe(name).stat().st_size == 0,
                "authenticated public summary lock is not empty")
    actual = {name: sha(name) for name in sorted(expected)}
    require(actual == expected, "closed public source/evidence bytes changed")
    return {"kind": "phase3a-c1-preservation-v1", "passed": True,
            "parent_source_sha256": parent["sha256"], "parent_files": 157,
            "public_files": actual, "public_inventory_sha256": digest(actual),
            "trusted_closed_reference_sha256": CLOSED,
            "private_paths_excluded_before_stat_read": sorted(private),
            "private_worktree_accessed": False, "protected_original_accessed": False}
