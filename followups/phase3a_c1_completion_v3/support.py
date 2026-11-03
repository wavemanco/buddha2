"""Fresh R2 scope bound to the closed 221-file R1 source and held outcome."""
from __future__ import annotations

import json
import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from followups.phase3a_c1_completion_v2 import support as parent
from followups.phase3a_compat_c1_v1 import support as c1

ROOT = c1.ROOT
DEFINITION = ROOT / "PHASE3A_C1_COMPLETION_R2_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-c1-completion-v3/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-c1-completion-v3/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-c1-completion-r2.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-c1-completion-v3"
NATIVE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-compat-c1-v1/completion-v3"
PARENT_SHA = "33cc36cb56fa75b6b427add09934a943515dd40e57cccfb4d4cfcb92a8b4bc1c"
PARENT_MANIFEST = "evidence/phase3a-c1-completion-v2/live-outcome-v1.manifest.json"
PARENT_MANIFEST_SHA = "2681b60e90ff1fe1638429687f8f125f090aab29a6d2d395b7660306c8c0b271"
PARENT_ACCEPTANCE = "evidence/phase3a-c1-completion-v2/live-packet-acceptance.json"
PARENT_ACCEPTANCE_SHA = "26774f595761211862830b0763af0383785bb1e80c8b348055e8694c5d5b9777"
PARENT_ARCHIVE_SHA = "baf5b8413e5f45305c6e1df306542e04a314039312de3ed66b138284b2798527"

CLOSED_METADATA = {
    "evidence/phase3a-c1-completion-v2/offline-kit-v1.manifest.json": "aa6427180dbe8305e2fc6f18ae74fce068a97519ad4d240352a587b8c0697793",
    "evidence/phase3a-c1-completion-v2/packet-acceptance.json": "ffc6b2bc199f087e1c00ad172fb8dfa5330370132117c8ba9f6b2c20ad693f1f"
}
CLOSED_ARCHIVES = {
    "evidence/phase3a-c1-completion-v2/offline-kit-v1.zip": "fadb7cf8609ff3a7d074b5349f03d6a57285a4046f5bdfd9364dba17032ed39c"
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read(path: Path) -> dict:
    require(path.is_absolute() and ".." not in path.parts
            and not any(part.casefold() in c1.PRIVATE for part in path.parts)
            and any(path.is_relative_to(root) for root in (ROOT, BASE, NATIVE)), "foreign/private R2 input")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (path, *path.parents)), "linked R2 artifact")
    require(path.is_file() and path.stat().st_size <= 32_000_000, "missing/oversized R2 artifact")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate R2 JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite R2 JSON")))
    require(isinstance(value, dict), "R2 artifact must be an object")
    return value


def path(value: Path) -> Path:
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts and
            not any(part.casefold() in c1.PRIVATE for part in value.parts) and
            any(value.is_relative_to(root) and value != root for root in (BASE, NATIVE)), "R2 output escaped scope")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (value, *value.parents)), "linked R2 output")
    return value


def _parent_manifest() -> dict:
    require(file_hash(ROOT / PARENT_MANIFEST) == PARENT_MANIFEST_SHA, "closed attempt manifest changed")
    require(file_hash(ROOT / PARENT_ACCEPTANCE) == PARENT_ACCEPTANCE_SHA, "closed attempt acceptance changed")
    require(all(c1.sha(name) == expected for name, expected in CLOSED_METADATA.items()),
            "closed attempt metadata changed")
    value = c1.read(PARENT_MANIFEST)
    require(value["passed"] is True and value["source_sha256"] == PARENT_SHA
            and value["archive_sha256"] == PARENT_ARCHIVE_SHA
            and value["all_member_SHA256_and_CRC_verified"] is True, "closed attempt packet is unaccepted")
    return value


def source_identity() -> dict:
    previous = parent.source_identity()
    require(previous["sha256"] == PARENT_SHA and len(previous["files"]) == 221, "closed attempt source changed")
    _parent_manifest()
    files = dict(previous["files"])
    names = list((ROOT / "followups/phase3a_c1_completion_v3").rglob("*.py"))
    names += [ROOT / name for name in CLOSED_METADATA]
    names += [DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER, ROOT / PARENT_MANIFEST,
              ROOT / PARENT_ACCEPTANCE, ROOT / "evidence/phase3a-c1-completion-v2/live-outcome.json"]
    require(all(p.is_file() for p in names), "R2 source package is not assembled")
    files.update({p.relative_to(ROOT).as_posix(): file_hash(p) for p in names})
    return {"kind": "phase3a-c1-completion-r2-source-v1", "parent_completion_source_sha256": PARENT_SHA,
            "files": files, "sha256": digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {"new_cap_micro_usd": 205860000, "first_cap_micro_usd": 50860000,
        "first_assessment_sublimit_micro_usd": 23700000, "readiness_included_micro_usd": 20000000,
        "historical_known_micro_usd": 12231444, "historical_reserved_micro_usd": 22880000,
        "new_max_attempts": 775, "cumulative_max_exposure_micro_usd": 240971444, "cumulative_max_attempts": 1660}
    require(value.get("authorized") is True
            and all(type(value.get(key)) is int and value[key] == number for key, number in expected.items())
            and value.get("historical_liability_release_authorized") is False and value.get("old_results_reused") is False
            and value["cumulative_max_exposure_micro_usd"] < 250000000
            and value.get("definition_sha256") == file_hash(DEFINITION), "R2 authority differs")
    return value


def preserve() -> dict:
    previous = parent.preserve()
    require(all(c1.sha(name) == expected for name, expected in CLOSED_ARCHIVES.items()),
            "closed offline or incomplete attempt archive changed")
    manifest = _parent_manifest()
    for name, expected in manifest["member_sha256"].items():
        if name == manifest["manifest_member"]:
            continue
        require(c1.sha(name) == expected, "closed 24-request public artifact changed")
    require(c1.sha(manifest["archive"]) == manifest["archive_sha256"], "closed attempt archive changed")
    return {"kind": "phase3a-c1-completion-r2-preservation-v1", "passed": True,
            "closed_parents": previous, "parent_source_sha256": PARENT_SHA,
            "parent_archive_sha256": manifest["archive_sha256"]}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "R2 record seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
