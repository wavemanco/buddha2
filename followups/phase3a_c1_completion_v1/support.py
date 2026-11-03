"""Source/authority bindings for the prospectively combined Phase 3A run."""
from __future__ import annotations

import json
import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from followups.phase3a_compat_c1_v1 import support as c1

ROOT = c1.ROOT
DEFINITION = ROOT / "PHASE3A_C1_COMPLETION_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-c1-completion-v1/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-c1-completion-v1/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-c1-completion.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-c1-completion-v1"
NATIVE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-compat-c1-v1/completion-v1"
PARENT_SHA = "e138a2eb07e537bfbf047dd451f487f96424abfdce9080968e3e8ad7637570d4"
PARENT_MANIFEST = "evidence/phase3a-compat-c1-v1/manifest.json"
PARENT_MANIFEST_SHA = "ef2a6979bb8b7d05295deec1043cf1d62202c6029fa75500095deefacb93a0d4"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read(path: Path) -> dict:
    require(path.is_absolute() and ".." not in path.parts
            and not any(part in c1.PRIVATE for part in path.parts)
            and any(path.is_relative_to(root) for root in (ROOT, BASE, NATIVE)), "foreign/private completion input")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (path, *path.parents)), "linked completion artifact")
    require(path.is_file() and path.stat().st_size <= 32_000_000, "missing/oversized completion artifact")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate completion JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite completion JSON")))
    require(isinstance(value, dict), "completion artifact must be an object")
    return value


def path(value: Path) -> Path:
    value = Path(value)
    roots = (BASE, NATIVE)
    require(value.is_absolute() and ".." not in value.parts and
            not any(part in c1.PRIVATE for part in value.parts) and
            any(value.is_relative_to(root) and value != root for root in roots), "completion output escaped its scope")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (value, *value.parents)), "linked completion output")
    return value


def source_identity() -> dict:
    parent = c1.source_identity()
    require(parent["sha256"] == PARENT_SHA and len(parent["files"]) == 171,
            "accepted C1 source changed")
    require(file_hash(ROOT / PARENT_MANIFEST) == PARENT_MANIFEST_SHA, "C1 manifest changed")
    manifest = c1.read(PARENT_MANIFEST)
    require(manifest.get("source_sha256") == PARENT_SHA, "C1 packet source differs")
    files = dict(parent["files"])
    names = [p for p in (ROOT / "followups/phase3a_c1_completion_v1").rglob("*.py")]
    names += [DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER,
              ROOT / PARENT_MANIFEST, ROOT / "evidence/phase3a-compat-c1-v1/independent-acceptance.json"]
    require(all(p.is_file() for p in names), "completion source package is not yet assembled")
    files.update({p.relative_to(ROOT).as_posix(): file_hash(p) for p in names})
    return {"kind": "phase3a-c1-completion-source-v1", "parent_c1_source_sha256": PARENT_SHA,
            "files": files, "sha256": digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    require(value.get("authorized") is True and value.get("new_cap_micro_usd") == 205860000
            and value.get("first_cap_micro_usd") == 50860000
            and value.get("readiness_included_micro_usd") == 20000000
            and value.get("historical_known_micro_usd") == 10487885
            and value.get("historical_reserved_micro_usd") == 11440000
            and value.get("cumulative_max_exposure_micro_usd") == 227787885
            and value["cumulative_max_exposure_micro_usd"] < 250000000
            and value.get("definition_sha256") == file_hash(DEFINITION), "combined Phase 3A authority differs")
    return value


def preserve() -> dict:
    result = c1.preservation()
    require(file_hash(ROOT / PARENT_MANIFEST) == PARENT_MANIFEST_SHA, "closed C1 manifest changed")
    manifest = c1.read(PARENT_MANIFEST)
    require(manifest["source_sha256"] == PARENT_SHA, "C1 packet changed identity")
    for name, sha in manifest["member_sha256"].items():
        if name == "C1_PACKET_MANIFEST.json" or name == "CURRENT_SPEC.md":
            continue
        require(c1.sha(name) == sha, "closed C1 public artifact changed")
    require(file_hash(ROOT / "evidence/phase3a-compat-c1-v1/offline-kit-v1.zip") == manifest["archive_sha256"],
            "closed C1 archive changed")
    return {"kind": "phase3a-c1-completion-preservation-v1", "passed": True,
            "closed_r2": result, "c1_archive_sha256": manifest["archive_sha256"],
            "c1_source_sha256": PARENT_SHA}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "completion record seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
