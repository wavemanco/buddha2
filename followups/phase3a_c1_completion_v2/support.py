"""Fresh R1 scope bound to preserved C1 and the closed 19-request attempt."""
from __future__ import annotations

import json
import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from followups.phase3a_c1_completion_v1 import support as parent
from followups.phase3a_compat_c1_v1 import support as c1

ROOT = c1.ROOT
DEFINITION = ROOT / "PHASE3A_C1_COMPLETION_R1_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-c1-completion-v2/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-c1-completion-v2/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-c1-completion-r1.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-c1-completion-v2"
NATIVE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-compat-c1-v1/completion-v2"
PARENT_SHA = "e2471ad9e38171cabc2d32615bac797739f378c3f6c7ebc64f8b95f8632d9d26"
PARENT_MANIFEST = "evidence/phase3a-c1-completion-v1/live-outcome-v2.manifest.json"
PARENT_MANIFEST_SHA = "6fd02cdfae24954bf9d881ecb23e81b6437d72c57e31e38d7602696f0972df66"
PARENT_ACCEPTANCE = "evidence/phase3a-c1-completion-v1/live-packet-acceptance.json"
PARENT_ACCEPTANCE_SHA = "de6d08cb1beb5046193038e9c60482a5b68f9946a16c71f3d8c90b14f9ae150e"

CLOSED_METADATA = {
    "evidence/phase3a-c1-completion-v1/live-outcome-v1.manifest.json": "72e52f3edb94fee536042071241c217f6c325c2164d496652c06a2497fec2d75",
    "evidence/phase3a-c1-completion-v1/offline-kit-v1.manifest.json": "c0595644ee1411c92825c7819faa3e786d2b30a3335699c2493c4f8ad2a24af1",
    "evidence/phase3a-c1-completion-v1/packet-acceptance.json": "15647a3578c9f7d6be876faf7f770988e243ef83ee835d16f51f8f8c4301f694"
}
CLOSED_ARCHIVES = {
    "evidence/phase3a-c1-completion-v1/live-outcome-v1.zip": "4dd8cd9ea050ef1115ea726e0bcbea44a6c165f8454687e3fa571bdf6a0156cc",
    "evidence/phase3a-c1-completion-v1/offline-kit-v1.zip": "1e53c490609e2c239c49c188b6fad127b5159bdfd3414061be431f3d715347be"
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read(path: Path) -> dict:
    require(path.is_absolute() and ".." not in path.parts
            and not any(part.casefold() in c1.PRIVATE for part in path.parts)
            and any(path.is_relative_to(root) for root in (ROOT, BASE, NATIVE)), "foreign/private R1 input")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (path, *path.parents)), "linked R1 artifact")
    require(path.is_file() and path.stat().st_size <= 32_000_000, "missing/oversized R1 artifact")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate R1 JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite R1 JSON")))
    require(isinstance(value, dict), "R1 artifact must be an object")
    return value


def path(value: Path) -> Path:
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts and
            not any(part.casefold() in c1.PRIVATE for part in value.parts) and
            any(value.is_relative_to(root) and value != root for root in (BASE, NATIVE)), "R1 output escaped scope")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (value, *value.parents)), "linked R1 output")
    return value


def _parent_manifest() -> dict:
    require(file_hash(ROOT / PARENT_MANIFEST) == PARENT_MANIFEST_SHA, "closed attempt manifest changed")
    require(file_hash(ROOT / PARENT_ACCEPTANCE) == PARENT_ACCEPTANCE_SHA, "closed attempt acceptance changed")
    require(all(c1.sha(name) == expected for name, expected in CLOSED_METADATA.items()),
            "closed attempt metadata changed")
    value = c1.read(PARENT_MANIFEST)
    require(value["passed"] is True and value["source_sha256"] == PARENT_SHA
            and value["all_member_SHA256_and_CRC_verified"] is True, "closed attempt packet is unaccepted")
    return value


def source_identity() -> dict:
    previous = parent.source_identity()
    require(previous["sha256"] == PARENT_SHA and len(previous["files"]) == 192, "closed attempt source changed")
    _parent_manifest()
    files = dict(previous["files"])
    names = list((ROOT / "followups/phase3a_c1_completion_v2").rglob("*.py"))
    names += [ROOT / name for name in CLOSED_METADATA]
    names += [DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER, ROOT / PARENT_MANIFEST,
              ROOT / PARENT_ACCEPTANCE, ROOT / "evidence/phase3a-c1-completion-v1/live-outcome.json"]
    require(all(p.is_file() for p in names), "R1 source package is not assembled")
    files.update({p.relative_to(ROOT).as_posix(): file_hash(p) for p in names})
    return {"kind": "phase3a-c1-completion-r1-source-v1", "parent_completion_source_sha256": PARENT_SHA,
            "files": files, "sha256": digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    require(value.get("authorized") is True and value.get("new_cap_micro_usd") == 205860000
            and value.get("first_cap_micro_usd") == 50860000
            and value.get("readiness_included_micro_usd") == 20000000
            and value.get("historical_known_micro_usd") == 11279643
            and value.get("historical_reserved_micro_usd") == 11440000
            and value.get("cumulative_max_exposure_micro_usd") == 228579643
            and value.get("cumulative_max_attempts") == 1636
            and value["cumulative_max_exposure_micro_usd"] < 250000000
            and value.get("definition_sha256") == file_hash(DEFINITION), "R1 authority differs")
    return value


def preserve() -> dict:
    previous = parent.preserve()
    require(all(c1.sha(name) == expected for name, expected in CLOSED_ARCHIVES.items()),
            "closed offline or incomplete attempt archive changed")
    manifest = _parent_manifest()
    for name, expected in manifest["member_sha256"].items():
        if name == manifest["manifest_member"]:
            continue
        require(c1.sha(name) == expected, "closed 19-request public artifact changed")
    require(c1.sha(manifest["archive"]) == manifest["archive_sha256"], "closed attempt archive changed")
    return {"kind": "phase3a-c1-completion-r1-preservation-v1", "passed": True,
            "closed_parents": previous, "parent_source_sha256": PARENT_SHA,
            "parent_archive_sha256": manifest["archive_sha256"]}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "R1 record seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
