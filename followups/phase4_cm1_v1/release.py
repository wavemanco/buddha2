"""Metadata-only P4 freeze and grants on the retained inspected launcher path."""
from __future__ import annotations

import copy
from pathlib import Path

from buddha2.artifacts import digest, file_hash, read_json, write_once
from buddha2.phase2_dispatch import FROZEN_PROFILES
from followups.phase3b_seq2_v1 import accounting, editor, ledger_core, strategy, supervision
from followups.phase3b_seq2_v1.support import (
    BASE,
    LAUNCHER,
    NATIVE,
    READINESS_BINDINGS,
    ROOT,
    _source_inputs,
    _source_name,
    offline_readiness,
    require,
    runtime_guard,
    runtime_identity,
    safe,
)

from . import eligibility, policy

KIND = "buddha2-phase4-cm1-v1"
DEFINITION = "docs/phases/phase-4/PHASE4_COST_MATCHED_CONFIRMATION_DEFINITION.md"
RECORDS = {
    "authorization": "evidence/phase4-cm1-v1/authorization-v1.json",
    "exposure": "evidence/phase4-cm1-v1/exposure-audit-v1.json",
    "exposure_review": "evidence/phase4-cm1-v1/exposure-coverage-review-v1.json",
    "pricing": "evidence/phase4-cm1-v1/public-billing-v1.json",
}
PARENT_POLICY = {
    "id": "phase4-cm1-parent-budget-v1", "phase_micro_usd": 1_200_000_000,
    "first_micro_usd": 1_200_000_000,
    "allocations_micro_usd": {"development": 100_000_000, "inference": 850_000_000, "assessment": 250_000_000},
    "cell_micro_usd": 75_000_000, "maximum_admitted_attempts": 40914,
}
OLD_STUDY_SHA = "1846b3656b125866f02b88cc1cd6a2a9e9624d5c7189512c3f37abfec2f09ebe"
DEVELOPMENT = "configs/phase4-development.json"
DEVELOPMENT_SHA256 = "a62253693aa6da22c0e4a088f7c318e4521835c79667090a7e3736d600b17bd6"


def path(value: Path) -> Path:
    value = Path(value)
    require(value.is_absolute() and value != BASE and value.is_relative_to(BASE)
        and ".." not in value.parts, "P4 parent metadata must remain in the controlled scope")
    return safe(value)


def source_identity() -> dict:
    names = set(_source_inputs()) | {DEFINITION, DEVELOPMENT, *RECORDS.values()}
    for pattern in ("followups/phase4_cm1_v1/*.py", "tests/test_phase4*.py"):
        for item in ROOT.glob(pattern):
            names.add(item.relative_to(ROOT).as_posix())
    files = {name: file_hash(safe(ROOT / _source_name(name))) for name in sorted(names)}
    body = {"kind": "buddha2-effective-source-v2", "schema_version": 2, "files": files}
    return {**body, "sha256": digest(body)}


def _records() -> tuple[dict, dict]:
    authority = read_json(ROOT / RECORDS["authorization"])
    policy._authority(file_hash(ROOT / RECORDS["authorization"]))
    require(file_hash(ROOT / DEFINITION) == authority["definition_sha256"], "P4 definition changed")
    audit = read_json(ROOT / RECORDS["exposure"])
    review = read_json(ROOT / RECORDS["exposure_review"])
    require(audit.get("kind") == "phase4-cm1-exposure-audit-v1"
        and review.get("kind") == "phase4-cm1-exposure-coverage-review-v1"
        and review.get("passed") is True and review.get("independent") is True
        and review.get("provider_calls") == 0 and review.get("real_credentials_used") is False
        and review.get("exposure_inventory_sha256") == file_hash(ROOT / RECORDS["exposure"])
        and review.get("sha256") == digest({k: v for k, v in review.items() if k != "sha256"}),
        "P4 exposure inventory has no matching independent coverage review")
    pricing = read_json(ROOT / RECORDS["pricing"])
    require(pricing.get("kind") == "phase4-cm1-public-billing-v1"
        and pricing.get("model_substitution") is False and pricing.get("provider_calls") == 0
        and set(pricing.get("model_ids", [])) == {"claude-sonnet-5-5", "claude-opus-5", "gpt-5.6-luna"}
        and pricing.get("retained_next_request_reservation_micro_usd") == {
            "sonnet": ledger_core._reservation("plan")["micro_usd"],
            "opus": ledger_core._reservation("editor")["micro_usd"],
            "group": ledger_core._reservation("group")["micro_usd"]},
        "P4 prices/models differ from the accepted reservation basis")
    return review, pricing


def _development() -> list[dict]:
    record = safe(ROOT / DEVELOPMENT)
    require(file_hash(record) == DEVELOPMENT_SHA256, "P4 exposed task record changed")
    value = read_json(record)
    require(set(value) == {"kind", "source_study_sha256", "source_study_file_sha256", "development"}
        and value["kind"] == "phase4-cm1-development-inputs-v1"
        and value["source_study_sha256"] == OLD_STUDY_SHA
        and value["source_study_file_sha256"] == "38a6413ba02200c22e26025865c0133535679fc07df64f9d75eff964bae77a0d"
        and [(row["pilot_id"], row["source_pilot_id"], row["target_micro_usd"]) for row in value["development"]]
            == [("dev02", "p3b-02", 6_016_759), ("dev04", "p3b-04", 5_402_521)],
        "P4 exposed development record scope differs")
    return copy.deepcopy(value["development"])


def _method(source: dict, pricing: dict) -> dict:
    locks = read_json(ROOT / "upstreams.lock.json")["upstreams"]
    require(locks["harness2"]["commit"] == "1cfe254e8d25b15f37048c3730134686abe60335"
        and locks["novelty-bench"]["commit"] == "64a23be6b18ec1dacc298830aab276061b6e143c",
        "P4 upstream pins differ")
    return {
        "id": "phase4-cm1-method-v1", "source_sha256": source["sha256"],
        "definition_sha256": file_hash(ROOT / DEFINITION),
        "pricing_sha256": file_hash(ROOT / RECORDS["pricing"]),
        "model_ids": pricing["model_ids"],
        "role_profiles": {role: {key: value for key, value in controls.items()
            if key not in {"input_limit", "reserved_output"}} for role, controls in FROZEN_PROFILES.items()},
        "author_selector": {"model": "claude-opus-5", "thinking": "adaptive", "effort": "high",
            "max_tokens": 16000, "service_tier": "standard_only", "inference_geo": "global"},
        "upstream_commits": {name: locks[name]["commit"] for name in ("harness2", "novelty-bench")},
        "seed_procedure_sha256": "16cd0c8b829c7147b51ff76bd38a350686ca1b3bf53e308cc4b76acbf0747de0",
        "seed_tree_sha256": digest(strategy.seed_tree()), "editor_profile": editor.profile(),
        "inference_policy": copy.deepcopy(PARENT_POLICY), "role_payload_bytes": policy.payload_limits(),
        "reservation_policy_sha256": ledger_core.am1.CONTROL_SHA256,
        "adaptive": {"mode": "seq", "k": 2, "solver_portfolios": 8, "author_stages": 6, "turns": 24},
        "fixed": {"maximum_pools": 8, "candidates_per_pool": 12, "stop_fraction": [90, 100],
            "one_final_selection_if_multiple_pools": True},
        "scoring": {"version": "1.1", "answers": 10, "patience": 0.8, "generation_replicates": 1,
            "seed": None, "generation_before_grading": True, "fallback": None,
            "supplemental_group_orders": [list(reversed(range(10))), list(range(5, 10)) + list(range(5))],
            "complete_quality": True},
    }


def prepare(output: Path) -> dict:
    runtime_guard()
    output = path(output)
    require(not output.exists(), "P4 preparation requires a fresh output directory")
    review, pricing = _records()
    source, runtime = source_identity(), runtime_identity()
    method = _method(source, pricing)
    body = {"kind": KIND, "source": source, "source_sha256": source["sha256"],
        "runtime": runtime, "runtime_sha256": digest(runtime),
        "policy": copy.deepcopy(PARENT_POLICY), "policy_sha256": digest(PARENT_POLICY),
        "launcher_sha256": file_hash(LAUNCHER),
        "authorization_sha256": file_hash(ROOT / RECORDS["authorization"]),
        "pricing_sha256": file_hash(ROOT / RECORDS["pricing"]),
        "method": method, "method_sha256": digest(method),
        "execution_tag": "p4-cm1-" + digest(str(output.relative_to(BASE)))[:16],
        "development": _development(), "seed_tree": strategy.seed_tree(),
        "development_study_sha256": OLD_STUDY_SHA,
        "editor_tools": read_json(ROOT / "followups/phase3a_v1/editor-tools.json"),
        "maximum_admitted_attempts": 40914, "potential_slot_count": 40914,
        "exposure_inventory_sha256": file_hash(ROOT / RECORDS["exposure"]),
        "eligibility_proof": review, "eligibility_proof_sha256": digest(review),
        "confirmation_source_sha256": eligibility.SOURCE_SHA256,
        "confirmation_tasks_opened": False, "fixture_supervision_rehearsal": False}
    value = {**body, "study_sha256": digest(body)}
    require(source_identity() == source, "P4 source changed during preparation")
    output.mkdir(parents=True)
    write_once(output / "study.json", value)
    strategy.materialize_seed(output / "seed")
    return value


def load_study(study_path: Path) -> dict:
    runtime_guard()
    study_path = path(study_path)
    value = read_json(study_path)
    require(isinstance(value, dict) and value.get("kind") == KIND
        and value.get("study_sha256") == digest({k: v for k, v in value.items() if k != "study_sha256"}),
        "P4 parent study seal differs")
    review, pricing = _records()
    source, runtime = source_identity(), runtime_identity()
    method = _method(source, pricing)
    require(value["source"] == source and value["source_sha256"] == source["sha256"]
        and value["runtime"] == runtime and value["runtime_sha256"] == digest(runtime)
        and value["launcher_sha256"] == file_hash(LAUNCHER)
        and value["policy"] == PARENT_POLICY and value["policy_sha256"] == digest(PARENT_POLICY)
        and value["authorization_sha256"] == file_hash(ROOT / RECORDS["authorization"])
        and value["pricing_sha256"] == file_hash(ROOT / RECORDS["pricing"])
        and value["method"] == method and value["method_sha256"] == digest(method)
        and value["execution_tag"] == "p4-cm1-" + digest(str(study_path.parent.relative_to(BASE)))[:16]
        and value["development"] == _development() and value["seed_tree"] == strategy.seed_tree()
        and value["development_study_sha256"] == OLD_STUDY_SHA
        and value["editor_tools"] == read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
        and value["exposure_inventory_sha256"] == file_hash(ROOT / RECORDS["exposure"])
        and value["eligibility_proof"] == review and value["eligibility_proof_sha256"] == digest(review)
        and value["confirmation_source_sha256"] == eligibility.SOURCE_SHA256
        and value["confirmation_tasks_opened"] is False
        and value["maximum_admitted_attempts"] == value["potential_slot_count"] == 40914
        and value["fixture_supervision_rehearsal"] is False,
        "P4 current method/source/runtime/authority changed")
    require(strategy.validate_harness(study_path.parent / "seed")["tree"] == value["seed_tree"],
            "P4 seed directory changed")
    return value


def make_grant(study_path: Path, fixture: bool) -> dict:
    study = load_study(study_path)
    require(type(fixture) is bool, "P4 grant mode must be explicit")
    body = {"kind": "phase4-cm1-parent-grant-v1", "fixture": fixture,
        **{key: study[key] for key in READINESS_BINDINGS},
        "authority": {"study_sha256": study["study_sha256"], "authorization_id": "phase4-cm1-user-approval",
            "authorized": not fixture, "cap_micro_usd": PARENT_POLICY["phase_micro_usd"],
            "canary_cap_micro_usd": PARENT_POLICY["first_micro_usd"], "expansion_authorized": False,
            "control_policy_sha256": ledger_core.am1.CONTROL_SHA256,
            "billing_profile": ledger_core.am1.BILLING_PROFILE}}
    return {**body, "grant_sha256": digest(body)}


def grant_for(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    value = read_json(path(grant_path))
    require(type(fixture) is bool and value == make_grant(study_path, fixture), "P4 parent grant differs")
    return value


def paths(study: dict, fixture: bool) -> tuple[Path, Path]:
    require(ledger_core._hash(study.get("study_sha256")) and type(fixture) is bool, "P4 path identity differs")
    return (NATIVE / study["study_sha256"] / ("mock" if fixture else "live"),
            accounting.canonical_journal(study["study_sha256"], fixture))


def _claim_record(checked: dict) -> dict:
    require(checked.get("mode") == "provider" and checked.get("fixture") is False
        and all(ledger_core._hash(checked.get(key)) for key in (*READINESS_BINDINGS, "grant_sha256"))
        and checked.get("cap_micro_usd") == checked.get("first_pair_cap_micro_usd") == 1_200_000_000
        and checked.get("maximum_admitted_attempts") == checked.get("slot_count") == 40914
        and checked.get("readiness_included_micro_usd") == 0, "P4 claim scope differs")
    return {"kind": "phase4-cm1-parent-allowance-claim-v1",
        **{key: checked[key] for key in (*READINESS_BINDINGS, "grant_sha256")},
        "run": checked["run"], "journal": checked["journal"], "cap_micro_usd": 1_200_000_000,
        "allocations_micro_usd": copy.deepcopy(PARENT_POLICY["allocations_micro_usd"]),
        "cell_micro_usd": 75_000_000, "maximum_admitted_attempts": 40914}


def preflight(study_path: Path, grant_path: Path, stage: str, mode: str, *, supervisor_agent=None, host=None) -> dict:
    require(stage == "all" and mode in {"preflight", "mock", "provider-config", "provider"}
        and host is None, "unknown P4 launch stage/mode/host override")
    study = load_study(study_path)
    proposed = read_json(path(grant_path))
    fixture = proposed.get("fixture") if mode in {"preflight", "provider-config"} else mode == "mock"
    require(type(fixture) is bool, "P4 grant must declare its mode")
    grant = grant_for(study_path, grant_path, fixture)
    if mode in {"provider", "mock"} or supervisor_agent is not None:
        supervisor_agent = supervision.agent_name(supervisor_agent)
    run, journal = paths(study, fixture)
    require(not (journal / "manifest.json").exists(), "P4 parent must never admit a ledger request")
    require(not (run / "outcome.json").exists(), "closed P4 parent cannot start another execution")
    require(mode not in {"provider", "mock"} or not (run / "started.json").exists(),
            "started P4 parent cannot request a fresh execution")
    checked = {"kind": "phase4-cm1-launch-preflight-v1", "phase4_cm1": True,
        **{key: study[key] for key in READINESS_BINDINGS}, "grant_sha256": grant["grant_sha256"],
        "fixture": fixture, "provider_calls": 0, "credentials_read": False,
        "study_path": str(path(study_path)), "grant_path": str(path(grant_path)),
        "run": str(run), "journal": str(journal), "mode": mode, "stage": stage,
        "journal_id": digest({"study_sha256": study["study_sha256"], "grant_sha256": grant["grant_sha256"],
            "parent_has_no_model_ledger": True}),
        "control_policy_sha256": ledger_core.am1.CONTROL_SHA256, "billing_profile": ledger_core.am1.BILLING_PROFILE,
        "cap_micro_usd": 1_200_000_000, "first_pair_cap_micro_usd": 1_200_000_000,
        "readiness_included_micro_usd": 0, "slot_count": 40914, "maximum_admitted_attempts": 40914,
        "configuration_only": mode == "provider-config", "supervisor_agent": supervisor_agent,
        "fixture_supervision_rehearsal": False}
    if not fixture and mode != "provider-config":
        checked["offline_readiness"] = offline_readiness(path(study_path),
            {key: study[key] for key in READINESS_BINDINGS})
    if mode == "provider":
        record = _claim_record(checked)
        target = path(BASE / "live-study-phase4-cm1-v1.json")
        if target.exists():
            require(read_json(target) == record, "another P4 parent already claims this allowance")
    return checked


def claim(checked: dict) -> dict:
    require(preflight(Path(checked["study_path"]), Path(checked["grant_path"]), checked["stage"],
        checked["mode"], supervisor_agent=checked.get("supervisor_agent")) == checked,
        "P4 claim no longer matches accepted preflight")
    record = _claim_record(checked)
    write_once(path(BASE / "live-study-phase4-cm1-v1.json"), record)
    return record
