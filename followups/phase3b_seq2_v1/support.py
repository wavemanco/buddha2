"""P3B-S2 identities and public paths; closed implementations stay immutable."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

from buddha2.artifacts import ContractError, digest, public_path_parts, write_once
from followups.phase3a_readiness_recovery_v1 import support as frozen

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3b-seq2-v1"
DECLARED_DEFINITION_SHA256 = "84cc77fd0c98b3b3dcb4d299a649b38953b66ed41b117e11a9ef2306cd08bf2e"
AUTHORITY = ROOT / "evidence" / PREFIX / "authorization.json"
PROVIDERS = ROOT / "evidence" / PREFIX / "provider-documentation.json"
LAUNCHER = ROOT / "phase3b-seq2.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / PREFIX
NATIVE = BASE / "native"
IMAGE_ID = frozen.IMAGE_ID
PRIVATE = frozen.PRIVATE | frozenset({"__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
PARENT_STUDY_SHA = "bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8"
require = frozen.require
runtime_guard = frozen.runtime_guard
runtime_identity = frozen.runtime_identity
seal, checked = frozen.seal, frozen.checked


def safe(value: Path, *, roots: tuple[Path, ...] | None = None) -> Path:
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts and not any(
        part.casefold() in PRIVATE or "stdout" in part.casefold() or "stderr" in part.casefold()
        for part in value.parts), "private, cached or relative S2 path")
    roots = roots or (ROOT, BASE)
    require(any(value == root or value.is_relative_to(root) for root in roots), "S2 path outside explicit roots")
    current = Path(value.anchor)
    for part in value.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "linked S2 input/output")
    return value


def read(value: Path) -> dict:
    target = safe(value)
    require(target.is_file() and target.stat().st_size <= 32_000_000, "missing/oversized S2 artifact")

    def pairs(items):
        result = {}
        for key, item in items:
            require(key not in result, "duplicate S2 JSON key")
            result[key] = item
        return result

    def nonfinite(_):
        raise ContractError("nonfinite S2 JSON")

    result = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    require(isinstance(result, dict), "S2 artifact must be an object")
    return result


def file_hash(value: Path) -> str:
    return hashlib.sha256(safe(value).read_bytes()).hexdigest()


def path(value: Path) -> Path:
    roots = (BASE, ROOT / "runs" / PREFIX)
    target = safe(value, roots=roots)
    require(target not in roots, "S2 output requires a child namespace")
    return target


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {
        "new_cap_micro_usd": 180000000, "first_cap_micro_usd": 55000000,
        "first_assessment_sublimit_micro_usd": 25000000, "readiness_included_micro_usd": 35000000,
        "inference_cell_micro_usd": 35000000, "assessment_pool_micro_usd": 70000000,
        "historical_known_micro_usd": 46044365, "historical_reserved_micro_usd": 22880000,
        "historical_attempts": 1997, "new_max_attempts": 2344, "potential_request_slots": 2344,
        "cumulative_max_exposure_micro_usd": 248924365, "cumulative_max_attempts": 4341,
    }
    require(value.get("kind") == "phase3b-s2-authority-v1" and value.get("authorized") is True
            and value.get("definition_sha256") == DECLARED_DEFINITION_SHA256
            and all(type(value.get(key)) is int and value[key] == n for key, n in expected.items())
            and value.get("historical_liability_release_authorized") is False
            and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("original_folder_access_authorized") is False
            and value.get("one_fresh_pilot_only") is True
            and value.get("whole_block_internal_reviews_and_closure_authorized") is True,
            "P3B-S2 authority differs")
    return value


SOURCE_KIND = "buddha2-effective-source-v2"
SOURCE_MANIFEST = "followups/phase3b_seq2_v1/source-inputs.json"


def _source_name(name: str) -> str:
    require(isinstance(name, str), "source input name must be text")
    relative = PurePosixPath(name)
    require(bool(relative.parts) and not relative.is_absolute() and relative.as_posix() == name
        and "\\" not in name and ":" not in name
        and all(part not in {"", ".", ".."}
            and part.casefold() not in PRIVATE | {"runs", "source"} for part in relative.parts),
        "private, captured or nonrelative source input")
    public_path_parts(relative.parts)
    return name


def _source_inputs() -> list[str]:
    manifest = read(ROOT / SOURCE_MANIFEST)
    require(set(manifest) == {"kind", "files"}
        and manifest.get("kind") == "buddha2-effective-source-inputs-v2"
        and isinstance(manifest.get("files"), list) and bool(manifest["files"]),
        "effective source manifest differs")
    names = [_source_name(name) for name in manifest["files"]]
    require(names == sorted(set(names)) and SOURCE_MANIFEST not in names,
        "effective source inputs must be unique and sorted")
    return [SOURCE_MANIFEST, *names]


def source_snapshot_policy(files: dict) -> dict:
    """Only ordinary effective inputs may be copied; historical streams have no exemption."""
    require(isinstance(files, dict) and bool(files), "missing source snapshot files")
    for name, expected in files.items():
        _source_name(name)
        require(isinstance(expected, str) and len(expected) == 64
            and all(char in "0123456789abcdef" for char in expected), "invalid source snapshot hash")
    return {"kind": "buddha2-effective-source-snapshot-v2", "canonical_originals": {},
        "files_sha256": digest(files)}


def recovery_config() -> dict:
    value = read(ROOT / "evidence/phase3b-ra1-v1/release-config.json")
    number = value.get("candidate")
    require(set(value) == {"kind", "candidate", "verification", "authority"}
        and value.get("kind") == "phase3b-ra1-release-config-v1"
        and type(number) is int and number in (1, 2)
        and value.get("verification") == "verification-ra1-v" + str(number)
        and value.get("authority") == "evidence/phase3b-ra1-v1/authority.json",
        "RA1 release configuration differs")
    return value


def release_authority() -> dict:
    config = recovery_config()
    value = read(ROOT / config["authority"])
    definition = "specifications/amendments/phase3b-release-acceptance-1.0.md"
    expected = {"aggregate_focused_engineering_target_seconds": 14400,
        "minimum_closure_reserve_seconds": 2700, "max_preflight_sets": 3,
        "max_candidates": 2, "max_main_entries": 2, "max_S13_starts": 2,
        "max_saved_replays": 2, "max_cold_replays": 2, "real_API_cap_usd": 0}
    require(value.get("kind") == "phase3b-ra1-direct-authority-v1"
        and value.get("instruction") == "complete P3B-RA1"
        and value.get("definition") == definition
        and value.get("definition_sha256") == "377b6dfdf4b3192a834f5fedfc0df7400f5f27128012ac6a245ef1b00925027d"
        and file_hash(ROOT / definition) == value["definition_sha256"]
        and all(type(value.get(k)) is int and value[k] == v for k, v in expected.items())
        and all(value.get(k) is False for k in ("target_is_hard_abort", "keys_authorized",
            "original_folder_access_authorized", "frozen_control_edits_authorized", "old_ledgers_reopened")),
        "RA1 direct offline authority differs")
    amendment = "specifications/amendments/phase3b-release-acceptance-am1-1.0.md"
    approval_path = ROOT / "evidence/phase3b-ra1-v1/am1-authority.json"
    approval = read(approval_path)
    require(file_hash(approval_path) == "35cee7563a5cf38f856e9ce6a318b8a95d5d447b547272be35d79a650ac5b0a6"
        and approval.get("amendment") == amendment
        and approval.get("amendment_sha256") == "5dfad6322a72f029cbbcd17824a384774a6787fa9ced969e6cc04b4b134ea1e1"
        and file_hash(ROOT / amendment) == approval["amendment_sha256"]
        and approval.get("original_authority_sha256") == file_hash(ROOT / config["authority"])
        and approval.get("instruction") == "Approve complete RA1-AM1 (Recommended)"
        and approval.get("approved_full_remaining_RA1_block") is True
        and type(approval.get("positive_bootstrap_test_total_seconds")) is int
        and approval["positive_bootstrap_test_total_seconds"] == 30
        and type(approval.get("positive_bootstrap_test_cleanup_seconds")) is int
        and approval["positive_bootstrap_test_cleanup_seconds"] == 1
        and approval.get("no_new_repetition_allowance") is True
        and approval.get("production_or_frozen_A0_control_edits_authorized") is False
        and type(approval.get("real_API_cap_usd")) is int and approval["real_API_cap_usd"] == 0
        and approval.get("keys_authorized") is False,
        "approved RA1-AM1 requirement or offline scope differs")
    return value


def bootstrap_capture_path(raw: str) -> Path:
    """A new post-collector sink, separate from the closed BD1 namespace."""
    release_authority()
    target = safe(Path(raw))
    preflight = BASE / "ra1-unit-preflight-v1"
    allowed_unit = target.parent == preflight and target.name in {"suite-1", "suite-2", "suite-3"}
    require((allowed_unit or target == BASE / recovery_config()["verification"]) and target.is_dir(),
        "RA1 diagnostic output escaped its admitted namespace")
    return target


def source_identity() -> dict:
    """Bind the current implementation and effective inputs, independently of old campaigns."""
    names = _source_inputs()
    files = {name: file_hash(ROOT / name) for name in names}
    source_snapshot_policy(files)
    body = {"kind": SOURCE_KIND, "schema_version": 2, "files": files}
    return {**body, "sha256": digest(body)}


def preserve() -> dict:
    source = source_identity()
    return {"kind": "buddha2-effective-source-preservation-v2", "passed": True,
        "source_sha256": source["sha256"], "source_files": len(source["files"]),
        "historical_artifacts_rewritten": False, "protected_original_accessed": False,
        "private_worktree_accessed": False}


READINESS_BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
READINESS_CHECKS = frozenset({"financial", "transport", "message_history", "strategy", "native_contract", "source_coverage"})


def offline_readiness(study_path: Path, bindings: dict) -> dict:
    """Require current offline receipts and a separate review before live admission."""
    require(isinstance(bindings, dict) and set(bindings) == set(READINESS_BINDINGS)
        and all(isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value) for value in bindings.values()),
        "incomplete current readiness binding")
    directory = safe(study_path).parent

    def load(name: str, kind: str) -> dict:
        record = checked(read(safe(directory / name)))
        require(record.get("kind") == kind and record.get("passed") is True
            and type(record.get("provider_calls")) is int and record["provider_calls"] == 0
            and record.get("real_credentials_used") is False
            and all(record.get(key) == value for key, value in bindings.items()),
            "current offline readiness evidence is failed, stale or foreign")
        return record

    common = {"kind", "passed", "provider_calls", "real_credentials_used", "sha256", *READINESS_BINDINGS}
    manifest = load("offline-readiness.json", "buddha2-offline-readiness-v2")
    require(set(manifest) == common | {"checked_by", "checks"}
        and isinstance(manifest.get("checked_by"), str) and bool(manifest["checked_by"].strip())
        and isinstance(manifest.get("checks"), dict) and set(manifest["checks"]) == READINESS_CHECKS,
        "current offline readiness checks are incomplete")
    for name in sorted(READINESS_CHECKS):
        reference = manifest["checks"][name]
        filename = f"offline-checks/{name}.json"
        require(isinstance(reference, dict) and set(reference) == {"path", "sha256"}
            and reference["path"] == filename, "foreign readiness receipt path")
        record = load(filename, "buddha2-offline-check-v2")
        require(file_hash(directory / filename) == reference["sha256"]
            and set(record) == common | {"check", "command", "exit_code", "tests_run", "test_ids", "failures", "errors", "skipped"}
            and record.get("check") == name
            and isinstance(record.get("command"), list) and bool(record["command"])
            and all(isinstance(arg, str) and bool(arg.strip()) for arg in record["command"])
            and type(record.get("tests_run")) is int and record["tests_run"] > 0
            and isinstance(record.get("test_ids"), list)
            and all(isinstance(identity, str) and bool(identity.strip()) for identity in record["test_ids"])
            and len(record["test_ids"]) == len(set(record["test_ids"])) == record["tests_run"]
            and all(type(record.get(key)) is int and record[key] == 0
                for key in ("exit_code", "failures", "errors", "skipped")),
            "current offline check receipt is incomplete or changed")
    manifest_hash = file_hash(directory / "offline-readiness.json")
    review = load("independent-review.json", "buddha2-offline-independent-review-v2")
    require(set(review) == common | {"manifest_file_sha256", "manifest_sha256", "reviewer", "independent", "notes"}
        and review.get("manifest_file_sha256") == manifest_hash
        and review.get("manifest_sha256") == manifest["sha256"]
        and review.get("independent") is True
        and isinstance(review.get("reviewer"), str) and bool(review["reviewer"].strip())
        and review["reviewer"].strip().casefold() != manifest["checked_by"].strip().casefold()
        and isinstance(review.get("notes"), str) and bool(review["notes"].strip()),
        "current independent readiness review is missing, stale or not independent")
    return {"profile": "buddha2-offline-readiness-v2", "manifest_sha256": manifest["sha256"],
        "manifest_file_sha256": manifest_hash, "independent_review_sha256": file_hash(directory / "independent-review.json")}
