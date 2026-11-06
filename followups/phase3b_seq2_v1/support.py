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
AUTHORITY = ROOT / "evidence" / PREFIX / "timing-continuation-authorization-v1.json"
READ_CONSUMPTION_POLICY = "read-consumption-diagnostic-v1"
PRIOR_CLOSED_ATTEMPT = {
    "study_sha256": "ed17a788fdd61b203cf7d5c856b635430e824ea254e31cdf215eea76f7d12b5c",
    "known_spent_micro_usd": 12528747,
    "reserved_micro_usd": 0,
    "provider_calls": 122,
    "known_requests": 122,
    "unknown_requests": 0,
}
PRIOR_CLOSED_REPEAT = {
    "study_sha256": "102140079517281714d49e90fde70702551e672ad24877422b5b48dd36ab2d67",
    "known_spent_micro_usd": 1063902,
    "reserved_micro_usd": 0,
    "provider_calls": 35,
    "known_requests": 35,
    "unknown_requests": 0,
}
PRIOR_CLOSED_ARTIFACT_ATTEMPT = {
    "study_sha256": "0e55a3316b31f093b10d6c6f1ac7e4c72087d716d081184cdff02a2844eaf08b",
    "known_spent_micro_usd": 14094285,
    "reserved_micro_usd": 0,
    "provider_calls": 513,
    "known_requests": 513,
    "unknown_requests": 0,
    "first_pair_spent_micro_usd": 9435450,
}
PRIOR_CLOSED_CONTINUATION = {
    "study_sha256": "90e0562959a2ba5a03411a45aa86be5ed77b6f9115fe0791ee5811f91e94a838",
    "known_spent_micro_usd": 5877824,
    "reserved_micro_usd": 0,
    "provider_calls": 161,
    "known_requests": 161,
    "unknown_requests": 0,
    "first_pair_spent_micro_usd": 5877824,
}
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
    from .deadline import CONVERSATION_POLICY

    value = read(AUTHORITY)
    expected = {
        "new_cap_micro_usd": 146435242, "first_cap_micro_usd": 26094077,
        "first_assessment_sublimit_micro_usd": 25000000, "readiness_included_micro_usd": 35000000,
        "inference_cell_micro_usd": 35000000, "assessment_pool_micro_usd": 70000000,
        "historical_known_micro_usd": 79609123, "historical_reserved_micro_usd": 22880000,
        "historical_attempts": 2828, "new_max_attempts": 1513, "potential_request_slots": 2344,
        "closed_parent_spent_micro_usd": 12528747, "closed_parent_reserved_micro_usd": 0,
        "closed_parent_attempts": 122,
        "closed_repeat_spent_micro_usd": 1063902, "closed_repeat_reserved_micro_usd": 0,
        "closed_repeat_attempts": 35,
        "closed_artifact_attempt_spent_micro_usd": 14094285,
        "closed_artifact_attempt_reserved_micro_usd": 0,
        "closed_artifact_attempts": 513,
        "closed_artifact_attempt_first_pair_spent_micro_usd": 9435450,
        "closed_continuation_spent_micro_usd": 5877824,
        "closed_continuation_reserved_micro_usd": 0, "closed_continuation_attempts": 161,
        "closed_continuation_first_pair_spent_micro_usd": 5877824,
        "cumulative_max_exposure_micro_usd": 248924365, "cumulative_max_attempts": 4341,
    }
    require(value.get("kind") == "phase3b-s2-timing-continuation-authority-v1" and value.get("authorized") is True
            and value.get("definition_sha256") == DECLARED_DEFINITION_SHA256
        and value.get("amendment_id") == "phase3b-timing-continuation-v1"
        and value.get("parent_authority_file_sha256")
            == "6c61ee2a2301c12989f74fdd1fdea61995394bc3228e57316ab0dbf153df8cfb"
        and value.get("conversation_timing_policy") == CONVERSATION_POLICY
        and value.get("user_answer") == "proceed"
        and value.get("annotation_selected_text") == "Next is existing current-source acceptance for the separately authorized four-prompt comparison, followed by fresh keys and execution."
        and value.get("annotation_source_assistant_message_id") == "msg_0d7d9d4b735ca8b9016aed1dffc2e087d0b3218b34b8dfa8ac"
        and value.get("approval_timestamp_provided") is False
        and value.get("created_at_utc_is_approval_timestamp") is False
        and value.get("continuation_proposal_file_sha256")
            == "8e36a5b46d62ae98511031bfe4ab00d51d436faa8279f52380101cba64d35ccd"
        and value.get("continuation_proposal_commit") == "db6956c"
        and value.get("read_consumption_policy") == READ_CONSUMPTION_POLICY
        and value.get("authorized_repeat") is True
        and value.get("closed_parent_study") == PRIOR_CLOSED_ATTEMPT["study_sha256"]
        and value.get("closed_parent_summary_file_sha256")
            == "6b302d23860fc2e77bf42921116f25612f3ae5ae94600ed93a4d8d178ca749a2"
        and value.get("closed_repeat_study") == PRIOR_CLOSED_REPEAT["study_sha256"]
        and value.get("closed_repeat_summary_file_sha256")
            == "48641fff45cc15d84369c677dfd05f94d21d0a0e7e822e8b17cb2c2dc108df7d"
        and value.get("closed_artifact_attempt_study") == PRIOR_CLOSED_ARTIFACT_ATTEMPT["study_sha256"]
        and value.get("closed_artifact_attempt_summary_file_sha256")
            == "7b96fb7364d63e4aaa902f8f90c6b23530b7f09a6c3a05fc9c539b568e3a2c17"
        and value.get("closed_artifact_attempt_first_pair_summary_file_sha256")
            == "cf8bd5b73a46bf42ffd5aeb5d31c2ed7ee1bf86eec009d7fc7671fb00566b079"
        and value.get("closed_continuation_study") == PRIOR_CLOSED_CONTINUATION["study_sha256"]
        and value.get("closed_continuation_outcome_file_sha256")
            == "8f0427b49b740be19d37d57bef806fec7b0e0d24c18cf73599856b4ff6c486cf"
            and all(type(value.get(key)) is int and value[key] == n for key, n in expected.items())
            and value.get("historical_liability_release_authorized") is False
            and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("original_folder_access_authorized") is False
            and value.get("one_fresh_pilot_only") is True
            and value.get("rollover_only_no_additional_funds") is True
            and value.get("subsequent_paid_repetition_authorized") is False
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
REQUIRED_REGRESSION_TESTS = frozenset({
    # Representation changes must preserve the actual native artifact and tool payloads.
    "followups.phase3b_seq2_v1.test_information_s2.InformationGuardTests.test_earlier_completion_witness_accepts_only_block_cache_changes",
    "followups.phase3b_seq2_v1.test_information_s2.InformationGuardTests.test_saved_selector_replays_actual_written_output_with_different_final_prose",
    "followups.phase3b_seq2_v1.test_native_s2.NativeS2Tests.test_native_relay_binds_consumed_file_or_stdout_after_different_final_prose",
    # Pinned read rendering and incomplete coverage must remain diagnostic.
    "followups.phase3b_seq2_v1.test_delivery_s2.PagedReadTests.test_actual_footer_excludes_metadata_and_accepts_later_offset",
    "followups.phase3b_seq2_v1.test_read_audit_reporting_s2.ReadAuditReportingCases.test_incomplete_audit_is_retained_without_blocking_completed_fixture",
    # A soft timing pause must preserve both continuation and hard financial limits.
    "followups.phase3b_seq2_v1.test_runtime_s2.SoftConversationTimingTests.test_saved_543_second_shortfall_keeps_full_request_budget_in_new_mode",
    "followups.phase3b_seq2_v1.test_runtime_s2.SoftConversationTimingTests.test_review_pauses_before_admission_and_continue_excludes_waiting_time",
    "followups.phase3b_seq2_v1.test_runtime_s2.SoftConversationTimingTests.test_hard_money_token_and_request_caps_precede_any_timing_pause",
    # Signed history and actual owned SDK response handling stay binding.
    "followups.phase3b_seq2_v1.test_information_s2.HistoryGuardTests.test_signed_normal_history_passes_but_prefix_or_signature_tamper_stops_before_dispatch",
    "followups.phase3b_seq2_v1.test_runtime_s2.SelectorOwnedWorkerTests.test_actual_pinned_selector_sdk_response_has_bound_native_role_audit",
    "followups.phase3b_seq2_v1.test_workflow_s2.WorklistCases.test_unknown_liability_and_remaining_gate",
    "followups.phase3b_seq2_v1.test_capacity_s2.EvaluatorAdmissionTests.test_evaluator_reservations_and_legacy_limits_are_unchanged",
    # The consumer must accept the whole producer contract, including future limit changes.
    "followups.phase3b_seq2_v1.test_capacity_s2.EvaluatorAdmissionTests.test_quality_request_at_saved_failure_size_is_admitted",
    "followups.phase3b_seq2_v1.test_capacity_s2.EvaluatorAdmissionTests.test_native_requests_cover_entire_allowed_portfolio_text_envelope",
    "followups.phase3b_seq2_v1.test_capacity_s2.EvaluatorAdmissionTests.test_evaluator_size_boundaries_and_frozen_profiles",
    "followups.phase3b_seq2_v1.test_capacity_s2.EvaluatorAdmissionTests.test_preflight_rejects_changed_producer_limit_without_consumer_change",
})


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
    observed_tests: set[str] = set()
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
        observed_tests.update(record["test_ids"])
    require(REQUIRED_REGRESSION_TESTS.issubset(observed_tests),
        "current offline checks omit required historical regressions")
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
