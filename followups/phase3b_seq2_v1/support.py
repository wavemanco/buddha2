"""P3B-S2 identities and public paths; closed implementations stay immutable."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_readiness_recovery_v1 import support as frozen

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3b-seq2-v1"
DEFINITION = ROOT / "PHASE3B_DEFINITION.md"
AUTHORITY = ROOT / "evidence" / PREFIX / "authorization.json"
PROVIDERS = ROOT / "evidence" / PREFIX / "provider-documentation.json"
LAUNCHER = ROOT / "phase3b-seq2.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / PREFIX
NATIVE = BASE / "native"
IMAGE_ID = frozen.IMAGE_ID
PRIVATE = frozen.PRIVATE | frozenset({"__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
PARENT_SOURCE_SHA = "517b8efcdfc68bbb3e6ac6d260dc2e7e0541fdb02ea46784afc4ca5e2d300ed8"
PARENT_STUDY_SHA = "bc86391000266d413276de0f9ca8fb7f4f5b65632aa509d650f8236a48735be8"
PARENT_STUDY = "runs/phase3a-readiness-recovery-v1/verification-v3/release/study.json"
PARENT_HISTORY = "runs/phase3a-readiness-recovery-v1/verification-v3/preservation-before.json"
PARENT_PACKET = "evidence/phase3a-readiness-recovery-v1/live-outcome-v1.manifest.json"
PARENT_RECEIPT = "evidence/phase3a-readiness-recovery-v1/live-packet-acceptance-v1.json"
PARENT_RECEIPT_SHA = "1e897fc321aecaa868003edc4a2b643ba37f00d59268c67bdf429de1662c39ed"
README_AUTHORITY = "evidence/phase3b-seq2-v1/readme-refresh-authority-v1.json"
LEGACY_README_SHA = "59f21b6a7071aeaaf61a9760282621bc3aaa956677139e72fc49b698d9b40ae2"
OFFLINE_RECEIPT = "evidence/phase2-release-r018/independent-acceptance.json"
OFFLINE_RECEIPT_SHA = "f8c729dbbb23ab98efacb4a66e67a73189d830a3c837c6acf347a77036703ea7"
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
            and value.get("definition_sha256") == file_hash(DEFINITION)
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


SOURCE_INPUTS = (
    "specifications/amendments/phase3b-release-acceptance-1.0.md",
    "evidence/phase3b-ra1-v1/authority.json", "evidence/phase3b-ra1-v1/effort.py",
    "evidence/phase3b-ra1-v1/release-config.json", "evidence/phase3b-ra1-v1/ra1_operator.py",
    "evidence/phase3b-ra1-v1/unit_preflight.py", "evidence/phase3b-ra1-v1/run_units.py",
    "evidence/phase3b-ra1-v1/cases-v1.json", "evidence/phase3b-ra1-v1/cases-v2.json", "evidence/phase3b-ra1-v1/cases-v3.json", "evidence/phase3b-ra1-v1/cases-v4.json",
    "evidence/phase3b-bd1-v1/run_units.py",
    "evidence/phase3b-ra1-v1/reviews/packet-plan-static-review-v1.json",
    "evidence/phase3b-ra1-v1/component_checks.py", "evidence/phase3b-ra1-v1/check_effort.py",
    "evidence/phase3b-ra1-v1/packet-plan-v1/PLAN.md",
    "evidence/phase3b-ra1-v1/packet-plan-v1/plan.json",
    "evidence/phase3b-ra1-v1/packet-plan-v1/review_packet_ra1.py",
    "evidence/phase3b-ra1-v1/packet-plan-v1/cold_replay_ra1.py",
    "evidence/phase3b-ra1-v1/packet-plan-v1/cold_replay.py",
    "evidence/phase3b-ra1-v1/packet-plan-v1/parameterization.diff",
    "evidence/phase3b-ra1-v1/packet-plan-v2/PLAN.md",
    "evidence/phase3b-ra1-v1/packet-plan-v2/plan.json",
    "evidence/phase3b-ra1-v1/packet-plan-v2/review_packet_ra1.py",
    "evidence/phase3b-ra1-v1/packet-plan-v2/cold_replay_ra1.py",
    "evidence/phase3b-ra1-v1/packet-plan-v2/cold_replay.py",
    "evidence/phase3b-ra1-v1/packet-plan-v2/parameterization.diff",
    "evidence/phase3b-ra1-v1/packet-plan-v2/ast-delta-proof.json",
    "evidence/phase3b-ra1-v1/reviews/packet-plan-static-review-v2.json",
    "specifications/amendments/phase3b-bounded-offline-recovery-1.0.md",
    "evidence/phase3b-or1-v1/authority.json", "evidence/phase3b-or1-v1/effort.py",
    "evidence/phase3b-or1-v1/release-config.json",
    "evidence/phase3b-or1-v1/prior-source-la1/preservation-receipt.json",
    "evidence/phase3b-or1-v1/compatibility-plan-v3.json",
    "evidence/phase3b-or1-v1/compatibility-tests-v1.json",
    "evidence/phase3b-or1-v1/compatibility-independent-review-v1.json",
    "evidence/phase3b-or1-v1/initial-compatibility-source/test_boundary_compatibility_s2.py",
    "evidence/phase3b-or1-v1/operator-unit-checks-v1.json",
    "evidence/phase3b-or1-v1/operator-unit-checks-v2.json",
    "evidence/phase3b-or1-v1/windows-probes-v1/final-result.json",
    "evidence/phase3b-or1-v1/launcher_probe.py", "evidence/phase3b-or1-v1/probe_tree.py",
    "evidence/phase3b-or1-v1/campaign-cases-v1.json",
    "evidence/phase3b-or1-v1/campaign-cases-v2.json",
    "evidence/phase3b-or1-v1/campaign-cases-v3.json",
    "evidence/phase3b-or1-v1/candidate-2-main-failure.json",
    "evidence/phase3b-or1-v1/candidate-2-independent-classification.json",
    "evidence/phase3b-or1-v1/failed-candidate-2/preservation-receipt.json",
    "evidence/phase3b-or1-v1/path_domain_probe.py",
    "evidence/phase3b-or1-v1/path-repair-plan-v1.json",
    "evidence/phase3b-or1-v1/path-domain-prospective-review-v1.json",
    "evidence/phase3b-or1-v1/path-domain-operator-v1.json",
    "evidence/phase3b-or1-v1/path-domain-independent-outcome-v1.json",
    "runs/phase3b-seq2-v1/or1-path-domain-v1/create.json",
    "runs/phase3b-seq2-v1/or1-path-domain-v1/inspection.json",
    "runs/phase3b-seq2-v1/or1-path-domain-v1/execution.json",
    "runs/phase3b-seq2-v1/or1-path-domain-v1/cleanup.json",
    "runs/phase3b-seq2-v1/or1-path-domain-v1/result.json",
    "evidence/phase3b-or1-v1/candidate-1-entry-failure.json",
    "evidence/phase3b-or1-v1/candidate-1-independent-classification.json",
    "evidence/phase3b-or1-v1/failed-candidate-1/preservation-receipt.json",
    "evidence/phase3b-or1-v1/writer_domain_probe.py",
    "evidence/phase3b-or1-v1/writer-repair-plan-v1.json",
    "evidence/phase3b-or1-v1/writer-domain-prospective-review-v1.json",
    "evidence/phase3b-or1-v1/writer-host-tests-v1.json",
    "evidence/phase3b-or1-v1/writer-domain-operator-v1.json",
    "evidence/phase3b-or1-v1/writer-domain-independent-outcome-v1.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/create.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/inspection.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/execution.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/cleanup.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/result.json",
    "runs/phase3b-seq2-v1/or1-writer-domain-v1/allowed-runtime-marker.json",
    "evidence/phase3b-or1-v1/windows-probes-v1/managed/process-result.json",
    "evidence/phase3b-or1-v1/windows-probes-v1/outer/outer-status-result.json",
    "evidence/phase3b-or1-v1/windows-probes-v1/tree/tree-result.json",
    "runs/phase3b-or1-v1/packet-plan-v1/plan.json",
    "runs/phase3b-or1-v1/packet-plan-v1/parent-plan-review-v1.json",
    "README.md", "README_LEGACY.md", ".gitattributes", "docs/ATTRIBUTIONS.md", "docs/RESEARCH_METHOD.md",
    ".gitignore", "LICENSE", "NOTICE", "docs/PUBLICATION.md",
    "third_party_licenses/INSPECT_AI.txt", "third_party_licenses/NOVELTYBENCH.txt",
    "third_party_licenses/OPENCODE.txt",
    "evidence/phase1a-data-readiness-r07/references/assets/crpo-LICENSE.txt",
    "evidence/phase3b-seq2-v1/license-adoption-publication-authority-v1.json",
    README_AUTHORITY, "evidence/phase3b-seq2-v1/readme-provenance-cases-v1.json",
    PARENT_STUDY, PARENT_HISTORY,
    "PHASE3B_DEFINITION.md", "phase3b-seq2.ps1", "phase3b-seq2-core.ps1",
    "evidence/phase3b-seq2-v1/authorization.json",
    "evidence/phase3b-seq2-v1/acceptance-cases.json",
    "evidence/phase3b-seq2-v1/native-acceptance-cases.json",
    "evidence/phase3b-seq2-v1/workflow-acceptance-cases.json",
    "evidence/phase3b-seq2-v1/runtime-acceptance-cases.json",
    "evidence/phase3b-seq2-v1/runtime-information-supplement-cases-v1.json",
    "evidence/phase3b-seq2-v1/workflow-admission-correction-cases-v1.json",
    "evidence/phase3b-seq2-v1/capacity-acceptance-cases.json",
    "evidence/phase3b-seq2-v1/capacity-aggregate-cases-v1.json",
    "evidence/phase3b-seq2-v1/capacity-artifact-bound-clarification-v1.json",
    "evidence/phase3b-seq2-v1/runtime-read-footer-cases-v1.json",
    "evidence/phase3b-seq2-v1/required-checkpoint-economy-cases-v1.json",
    "evidence/phase3b-seq2-v1/packet-json-cases-v1.json",
    "evidence/phase3b-seq2-v1/provider-documentation.json",
    "evidence/phase3b-seq2-v1/public-billing-review-v1.json",
    "evidence/phase3b-seq2-v1/component-preparation-v1.json",
    "evidence/phase3b-seq2-v1/component-preparation-v2.json",
    "evidence/phase3b-seq2-v1/component-preparation-v3.json",
    "evidence/phase3b-seq2-v1/component-preparation-v4.json",
    "evidence/phase3b-seq2-v1/source-snapshot-correction-cases-v1.json",
    "evidence/phase3b-seq2-v1/unaccepted-candidate-v1.json",
    "runs/phase3b-seq2-v1/verification-v1/release/study.json",
    "evidence/phase3b-seq2-v1/preacceptance-review-v1.json",
    "evidence/phase3b-seq2-v1/preacceptance-review-v2.json",
    "evidence/phase3b-seq2-v1/preacceptance-review-v3.json",
    "evidence/phase3b-seq2-v1/package_public.py",
    "specifications/amendments/phase3b-export-contract-correction-1.0.md",
    "evidence/phase3b-seq2-c2-v1/authority.json",
    "evidence/phase3b-seq2-c2-v1/composed_acceptance.py",
    "evidence/phase3b-seq2-c2-v1/run_boundary.py",
    "evidence/phase3b-seq2-c2-v1/run_composed.py",
    "evidence/phase3b-seq2-c2-v1/launch_candidate.py",
    "specifications/amendments/phase3b-launcher-offline-acceptance-1.0.md",
    "evidence/phase3b-la1-v1/authority.json",
    "evidence/phase3b-la1-v1/effort.py",
    "evidence/phase3b-la1-v1/launcher_probe.py",
    "evidence/phase3b-la1-v1/probe_tree.py",
    "evidence/phase3b-la1-v1/probe-final-v2/final-result.json",
    "evidence/phase3b-la1-v1/probe-final-v2/managed/process-result.json",
    "evidence/phase3b-la1-v1/probe-final-v2/outer/outer-status-result.json",
    "evidence/phase3b-la1-v1/probe-final-v2/tree/tree-result.json",
    "evidence/phase3b-la1-v1/probe-final-v3/final-result.json",
    "evidence/phase3b-la1-v1/probe-final-v3/managed/process-result.json",
    "evidence/phase3b-la1-v1/probe-final-v3/outer/outer-status-result.json",
    "evidence/phase3b-la1-v1/probe-final-v3/tree/tree-result.json",
    "evidence/phase3b-la1-v1/campaign-cases.json",
    "evidence/phase3b-la1-v1/campaign-cases-v2.json",
    "evidence/phase3b-la1-v1/test_launcher_cleanup.py",
    "evidence/phase3b-la1-v1/cleanup-fault-result-v1.json",
    "evidence/phase3b-la1-v1/cleanup-fault-result-v2.json",
    "evidence/phase3b-la1-v1/sanitized-cli-readiness-v1.json",
    "runs/phase3b-la1-v1/packet-plan-v1/plan.json",
    "runs/phase3b-la1-v1/packet-plan-v1/parent-plan-review-v1.json",
    "evidence/phase3b-la1-v1/host_acceptance.py",
    "evidence/phase3b-la1-v1/launcher-probe-milestone-v1.json",
    "evidence/phase3b-la1-v1/initial-repair-independent-review-v1.json",
    "evidence/phase3b-la1-v1/prior-source-c2/preservation-receipt.json",
    "runs/phase3b-seq2-v1/verification-v2/external-reviews/recovery-review-v1/saved_only_worker_v2.py",
    "PHASE3A_RP2_LIVE_REPORT.md",
    "evidence/phase3a-readiness-recovery-v1/live-outcome-v1.json",
    "evidence/phase3a-readiness-recovery-v1/live-independent-review-v1.json",
    "evidence/phase3a-readiness-recovery-v1/live-outcome-v1.manifest.json",
    "evidence/phase3a-readiness-recovery-v1/live-packet-acceptance-v1.json",
)


def _parent_source() -> tuple[dict, dict]:
    """Authenticate the closed map without rerunning old current-README assumptions."""
    require(file_hash(ROOT / PARENT_RECEIPT) == PARENT_RECEIPT_SHA, "closed RP2 packet receipt changed")
    receipt = read(ROOT / PARENT_RECEIPT)
    require(receipt.get("passed") is True and receipt.get("source_sha256") == PARENT_SOURCE_SHA
        and receipt.get("study_sha256") == PARENT_STUDY_SHA
        and file_hash(ROOT / PARENT_PACKET) == receipt["manifest_sha256"], "closed RP2 packet binding differs")
    manifest = read(ROOT / PARENT_PACKET)
    require(manifest.get("archive") == receipt["archive"]
        and manifest.get("archive_sha256") == receipt["archive_sha256"], "closed RP2 archive binding differs")
    require(file_hash(ROOT / PARENT_STUDY) == manifest["member_sha256"][PARENT_STUDY], "closed RP2 study changed")
    study = read(ROOT / PARENT_STUDY)
    parent = study.get("source")
    if not isinstance(parent, dict):
        raise ContractError("closed RP2 source map is not an object")
    require(study.get("study_sha256") == PARENT_STUDY_SHA
        and digest({key: value for key, value in study.items() if key != "study_sha256"}) == PARENT_STUDY_SHA
        and isinstance(parent.get("files"), dict)
        and len(parent["files"]) == 549 and parent.get("sha256") == PARENT_SOURCE_SHA
        and digest(parent["files"]) == PARENT_SOURCE_SHA, "closed RP2 source map differs")
    return parent, manifest


def _readme_alias() -> dict:
    alias = {"README.md": {"retained_path": "README_LEGACY.md", "sha256": LEGACY_README_SHA}}
    authority = read(ROOT / README_AUTHORITY)
    require(authority.get("kind") == "buddha2-scientific-readme-refresh-authority-v1"
        and authority.get("historical_document_alias") == alias
        and authority.get("parent_source_sha256") == PARENT_SOURCE_SHA
        and authority.get("historical_manifests_rewritten") is False
        and authority.get("scientific_conditions_models_caps_and_repetitions_unchanged") is True
        and authority.get("new_source_identity_required") is True, "only the declared README alias is allowed")
    return alias


def _offline_streams(files: dict) -> dict:
    """Reuse the packet's exact pinned-receipt classification, before stream metadata."""
    name = OFFLINE_RECEIPT
    require(file_hash(ROOT / name) == OFFLINE_RECEIPT_SHA,
        "historical offline classification receipt changed")
    receipt = read(ROOT / name)
    names = {key for key in files if any("stdout" in part.casefold() or "stderr" in part.casefold()
        for part in PurePosixPath(key).parts)}
    require(len(names) == 14 and receipt["independent_checks"]["real_provider_calls"] == 0
        and all(receipt["evidence"].get(key) == files[key] for key in names), "only fourteen classified offline originals allowed")
    return {key: files[key] for key in names}


def _parent_file_hash(name: str, expected: str, streams: dict) -> str:
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and relative.as_posix() == name and "\\" not in name and ":" not in name
        and all(part not in {"", ".", ".."} and part.casefold() not in PRIVATE for part in relative.parts),
        "private/cached/nonrelative parent path")
    if not any("stdout" in part.casefold() or "stderr" in part.casefold() for part in relative.parts):
        return file_hash(ROOT / name)
    require(name in streams and streams[name] == expected, "unclassified stream forbidden before metadata")
    target = ROOT
    for index, part in enumerate(relative.parts):
        target /= part
        info = target.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
            and (stat.S_ISREG(info.st_mode) if index == len(relative.parts)-1 else stat.S_ISDIR(info.st_mode)),
            "classified offline original traverses a link or nonordinary entry")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def source_snapshot_policy(files: dict) -> dict:
    """Authenticate canonical originals; never authorize a retained stream copy."""
    require(isinstance(files, dict) and bool(files), "missing source snapshot files")
    for name, expected in files.items():
        require(isinstance(name, str), "source snapshot name must be text")
        relative = PurePosixPath(name)
        require(bool(relative.parts) and not relative.is_absolute() and relative.as_posix() == name and "\\" not in name
            and ":" not in name and all(part not in {"", ".", ".."}
                and part.casefold() not in PRIVATE for part in relative.parts),
            "private/cached/nonrelative source snapshot name")
        require(isinstance(expected, str) and len(expected) == 64
            and all(char in "0123456789abcdef" for char in expected), "invalid source snapshot hash")
    streams = _offline_streams(files)
    require(all(_parent_file_hash(name, expected, streams) == expected
        for name, expected in streams.items()), "canonical offline source changed")
    return {"kind": "phase3b-s2-originals-only-source-snapshot-v1",
            "canonical_originals": streams,
            "offline_classification_receipt": {"path": OFFLINE_RECEIPT, "sha256": OFFLINE_RECEIPT_SHA}}


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
    release_authority()
    or1_definition = "specifications/amendments/phase3b-bounded-offline-recovery-1.0.md"
    or1 = read(ROOT / "evidence/phase3b-or1-v1/authority.json")
    require(or1.get("definition") == or1_definition
        and or1.get("definition_sha256") == file_hash(ROOT / or1_definition)
        and or1.get("reply") == "Approve full OR1 execution (Recommended)"
        and or1.get("aggregate_focused_engineering_limit_seconds") == 10800
        and or1.get("initial_compatibility_limit_seconds") == 1800
        and or1.get("minimum_closure_reserve_seconds") == 1800
        and or1.get("maximum_frozen_candidates") == 3
        and or1.get("maximum_main_matrix_starts") == 2
        and or1.get("maximum_positive_S13_starts") == 2
        and or1.get("maximum_saved_replays") == 2
        and or1.get("maximum_extracted_cold_replays") == 2
        and or1.get("prior_ledgers_reopened") is False
        and or1.get("real_API_cost_usd_ceiling") == 0
        and or1.get("real_keys_authorized") is False
        and or1.get("paid_pilot_authorized") is False,
        "OR1 bounded offline authority differs")
    la1_definition = "specifications/amendments/phase3b-launcher-offline-acceptance-1.0.md"
    la1 = read(ROOT / "evidence/phase3b-la1-v1/authority.json")
    require(la1.get("definition") == la1_definition
        and la1.get("definition_sha256") == file_hash(ROOT / la1_definition)
        and la1.get("reply") == "complete P3B-LA1"
        and la1.get("aggregate_focused_engineering_limit_seconds") == 7200
        and la1.get("initial_repair_limit_seconds") == 1800
        and la1.get("minimum_closure_reserve_seconds") == 1200
        and la1.get("one_frozen_offline_campaign") is True
        and la1.get("closed_prior_ledger_reopened") is False
        and la1.get("offline_API_cost_usd") == 0
        and la1.get("paid_calls_authorized") is False
        and la1.get("real_keys_authorized") is False, "LA1 offline execution authority differs")
    amendment = "specifications/amendments/phase3b-export-contract-correction-1.0.md"
    authority = read(ROOT / "evidence/phase3b-seq2-c2-v1/authority.json")
    require(authority.get("kind") == "phase3b-s2-c2-direct-authority-v1"
        and authority.get("reply") == "C2 is approved"
        and authority.get("definition") == amendment
        and authority.get("definition_sha256") == file_hash(ROOT / amendment)
        and authority.get("prior_source_sha256") == "0b154f40fd0418b5d86a218abf23050d9b0db26a2195dbad828a6c6a3f4073aa"
        and authority.get("prior_study_sha256") == "160fa663c793f3ac0878031f3ffaa9d6db57b4349069bc9460756e147b2b68ee"
        and authority.get("aggregate_focused_engineering_limit_seconds") == 10800
        and authority.get("effort_limit_reset") is False
        and authority.get("additional_focused_engineering_seconds") == 0
        and authority.get("additional_api_funding_usd") == 0
        and authority.get("existing_live_usd_ceiling") == 180
        and authority.get("minimum_supported_live_reserve_seconds") == 1800
        and authority.get("extra_paid_repetition_authorized") is False
        and authority.get("fresh_keys_only_after_complete_acceptance") is True
        and authority.get("scientific_protocol_and_stop_rules_unchanged") is True,
        "C2 amendment or bounded direct authority differs")
    parent, _ = _parent_source()
    aliases = _readme_alias()
    streams = _offline_streams(parent["files"])
    files = {}
    for name, expected in parent["files"].items():
        retained = aliases[name]["retained_path"] if name in aliases else name
        require(name != "README.md" or expected == LEGACY_README_SHA, "historical README expectation changed")
        require(_parent_file_hash(retained, expected, streams) == expected, "closed parent source changed: " + name)
        files[retained] = expected
    directory = safe(ROOT / "followups/phase3b_seq2_v1")
    for name in sorted(os.listdir(directory)):
        if name.casefold() in PRIVATE or "stdout" in name.casefold() or "stderr" in name.casefold():
            continue
        target = safe(directory / name)
        info = target.lstat()
        require(stat.S_ISREG(info.st_mode), "unexpected S2 source directory/type")
        if target.suffix in {".py", ".json", ".md", ".ps1"}:
            files[target.relative_to(ROOT).as_posix()] = file_hash(target)
    for name in SOURCE_INPUTS:
        files[name] = file_hash(ROOT / name)
    config = recovery_config()
    copied = f"runs/{PREFIX}/{config['verification']}/external-reviews/packet-review-ra1-c{config['candidate']}-v2"
    masters = {name: "evidence/phase3b-ra1-v1/packet-plan-v2/" + name for name in
        ("PLAN.md", "plan.json", "review_packet_ra1.py", "cold_replay_ra1.py", "cold_replay.py", "parameterization.diff", "ast-delta-proof.json")}
    masters["packet-plan-static-review-v2.json"] = "evidence/phase3b-ra1-v1/reviews/packet-plan-static-review-v2.json"
    for name, master in masters.items():
        expected = file_hash(ROOT / master)
        retained = copied + "/" + name
        require(file_hash(ROOT / retained) == expected, "current candidate packet reviewer copy differs")
        files[retained] = expected
    return {"kind": "phase3b-s2-source-v1", "parent_source_sha256": parent["sha256"],
            "H1_source_sha256": parent["H1_source_sha256"], "I1_source_sha256": parent["I1_source_sha256"],
            "historical_document_alias": aliases,
            "files": files, "sha256": digest(files)}


def preserve() -> dict:
    source_identity()
    parent_source, manifest = _parent_source()
    require(file_hash(ROOT / PARENT_HISTORY) == manifest["member_sha256"][PARENT_HISTORY], "closed preservation inventory changed")
    parent = read(ROOT / PARENT_HISTORY)
    rp1, hi = parent["RP1_preservation"], parent["RP1_preservation"]["HI_preservation"]
    require(parent.get("passed") is True and rp1.get("passed") is True and hi.get("passed") is True,
        "closed parent preservation was not accepted")
    for inventory in (parent["accepted_checkpoints"], rp1["accepted_checkpoints"], hi["closed_public_metadata"]):
        require(all(parent_source["files"].get(name) == expected for name, expected in inventory.items()),
            "closed checkpoint preservation inventory differs from authenticated source")
    archives = dict(parent["closed_RP1_archives"])
    require(set(archives) == {f"evidence/phase3a-rc1-pilot-v1/{stem}.zip" for stem in ("offline-kit-v1", "live-outcome-v1")},
        "closed RP1 archive inventory differs")
    archives["evidence/phase3a-c1-completion-v4/live-outcome-v1.zip"] = hi["closed_R3_archive_sha256"]
    archive_name = "evidence/phase3a-readiness-recovery-v1/live-outcome-v1.zip"
    require(manifest["archive"] == archive_name, "closed Phase3A archive path differs")
    archives[archive_name] = manifest["archive_sha256"]
    require(all(file_hash(ROOT / name) == expected for name, expected in archives.items()), "closed ancestor archive changed")
    return {"kind": "phase3b-s2-preservation-v1", "passed": True, "parent": parent,
            "parent_source_sha256": PARENT_SOURCE_SHA, "closed_phase3a_archive_sha256": manifest["archive_sha256"],
            "historical_document_alias": _readme_alias(), "closed_ancestor_archives": archives,
            "protected_original_accessed": False, "private_worktree_accessed": False}
