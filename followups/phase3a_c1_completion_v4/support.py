"""Fresh R3 identity bound to the closed 254-file R2 source and held outcomes."""
from __future__ import annotations

import json
import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from followups.phase3a_c1_completion_v3 import support as parent
from followups.phase3a_compat_c1_v1 import support as c1

ROOT = c1.ROOT
DEFINITION = ROOT / "PHASE3A_C1_COMPLETION_R3_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-c1-completion-v4/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-c1-completion-v4/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-c1-completion-r3.ps1"
PROPOSAL_PATH = "specifications/archive/phase3a-c1-completion-r3-proposal-1.0.md"
PROPOSAL_SHA = "5363abb3b7a2bb741158bc60d67f56779330f3397c428efbd3c2920cb407d380"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-c1-completion-v4"
NATIVE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-compat-c1-v1/completion-v4"
PARENT_SHA = "b17f977af8c893989870216aa8e92e09a4538f7d63555cceae73095998b37e9d"
PARENT_MANIFEST = "evidence/phase3a-c1-completion-v3/live-outcome-v1.manifest.json"
PARENT_MANIFEST_SHA = "0a59e2e9b51ea7992eaa732a11fddfd3c2ec15a798b2d2b012a2251c0ee64129"
PARENT_ACCEPTANCE = "evidence/phase3a-c1-completion-v3/live-packet-acceptance.json"
PARENT_ACCEPTANCE_SHA = "b11b6d09c856c277ce0866121c51c21634a1bdc71fe47d0b6fb0932be531195b"
PARENT_ARCHIVE_SHA = "7b026fbe76282269149e34e507651dbd6da3693a68ce261e943ec2689952dd05"

CLOSED_METADATA = {
    "evidence/phase3a-c1-completion-v3/offline-kit-v1.manifest.json": "d620609be3c74696c413e672d2f899a7f56ae73abfb4396d4436dfb7baa1bb05",
    "evidence/phase3a-c1-completion-v3/packet-acceptance.json": "e111d9d673df47a434d9945c9ae245b9561ecbb1950d779f7327e0f2545f3062"
}
CLOSED_ARCHIVES = {
    "evidence/phase3a-c1-completion-v3/offline-kit-v1.zip": "076749622f4f421fb447a1055bd51220fca536775537ad855a58e5377eb1c11d"
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read(path: Path) -> dict:
    require(path.is_absolute() and ".." not in path.parts
            and not any(part.casefold() in c1.PRIVATE for part in path.parts)
            and any(path.is_relative_to(root) for root in (ROOT, BASE, NATIVE)), "foreign/private R3 input")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (path, *path.parents)), "linked R3 artifact")
    require(path.is_file() and path.stat().st_size <= 32_000_000, "missing/oversized R3 artifact")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate R3 JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite R3 JSON")))
    require(isinstance(value, dict), "R3 artifact must be an object")
    return value


def path(value: Path) -> Path:
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts and
            not any(part.casefold() in c1.PRIVATE for part in value.parts) and
            any(value.is_relative_to(root) and value != root for root in (BASE, NATIVE)), "R3 output escaped scope")
    require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                    for p in (value, *value.parents)), "linked R3 output")
    return value


def _parent_manifest() -> dict:
    require(c1.sha(PARENT_MANIFEST) == PARENT_MANIFEST_SHA, "closed attempt manifest changed")
    require(c1.sha(PARENT_ACCEPTANCE) == PARENT_ACCEPTANCE_SHA, "closed attempt acceptance changed")
    require(all(c1.sha(name) == expected for name, expected in CLOSED_METADATA.items()),
            "closed attempt metadata changed")
    value = c1.read(PARENT_MANIFEST)
    require(value["passed"] is True and value["source_sha256"] == PARENT_SHA
            and value["archive_sha256"] == PARENT_ARCHIVE_SHA
            and value["all_member_SHA256_and_CRC_verified"] is True, "closed attempt packet is unaccepted")
    return value


def source_identity() -> dict:
    previous = parent.source_identity()
    require(previous["sha256"] == PARENT_SHA and len(previous["files"]) == 254, "closed attempt source changed")
    _parent_manifest()
    files = dict(previous["files"])
    names = list((ROOT / "followups/phase3a_c1_completion_v4").rglob("*.py"))
    names += [ROOT / name for name in CLOSED_METADATA]
    names += [DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER, ROOT / PROPOSAL_PATH, ROOT / PARENT_MANIFEST,
              ROOT / PARENT_ACCEPTANCE, ROOT / "evidence/phase3a-c1-completion-v3/live-outcome.json"]
    names += [ROOT / "evidence/phase3a-c1-completion-v4/package_public.py",
              ROOT / "specifications/archive/phase3a-c1-completion-r3-definition-1.0.md"]
    require(not any(part.casefold() in c1.PRIVATE for p in names for part in p.parts),
            "private path cannot enter R3 source identity")
    require(all(p.is_relative_to(ROOT) for p in names) and not any(
        ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction())
        for p in names for ancestor in (p, *p.parents)), "linked/foreign R3 source")
    require(all(p.is_file() for p in names), "R3 source package is not assembled")
    files.update({p.relative_to(ROOT).as_posix(): file_hash(p) for p in names})
    return {"kind": "phase3a-c1-completion-r3-source-v1", "parent_completion_source_sha256": PARENT_SHA,
            "files": files, "sha256": digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {"new_cap_micro_usd": 205860000, "first_cap_micro_usd": 50860000,
        "first_assessment_sublimit_micro_usd": 23700000, "readiness_included_micro_usd": 20000000,
        "historical_known_micro_usd": 13101271, "historical_reserved_micro_usd": 22880000,
        "historical_attempts": 904,
        "new_max_attempts": 775, "potential_request_slots": 967, "cumulative_max_exposure_micro_usd": 241841271, "cumulative_max_attempts": 1679}
    require(value.get("kind") == "phase3a-c1-completion-r3-authority-v1"
            and value.get("authorized") is True
            and all(type(value.get(key)) is int and value[key] == number for key, number in expected.items())
            and value.get("historical_liability_release_authorized") is False and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("accepted_proposal_path") == PROPOSAL_PATH
            and value.get("accepted_proposal_sha256") == PROPOSAL_SHA == c1.sha(PROPOSAL_PATH)
            and value["cumulative_max_exposure_micro_usd"] < 250000000
            and value.get("definition_sha256") == c1.sha(DEFINITION.relative_to(ROOT).as_posix()),
            "R3 authority differs")
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
    return {"kind": "phase3a-c1-completion-r3-preservation-v1", "passed": True,
            "closed_parents": previous, "parent_source_sha256": PARENT_SHA,
            "parent_archive_sha256": manifest["archive_sha256"]}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "R3 record seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
