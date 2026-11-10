"""Metadata-only P4 freeze and grants on the retained inspected launcher path."""
from __future__ import annotations

import copy
from pathlib import Path

from buddha2.artifacts import digest, file_hash, read_json, write_bytes_once, write_once
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
    checked,
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


def prepare(output: Path, *, continuation: dict | None = None) -> dict:
    runtime_guard()
    output = path(output)
    require(not output.exists(), "P4 preparation requires a fresh output directory")
    review, pricing = _records()
    source, runtime = source_identity(), runtime_identity()
    method = _method(source, pricing)
    if continuation is not None:
        _validate_continuation(continuation, source)
        method = _amended_method(method, continuation)
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
    if continuation is not None:
        body["continuation"] = continuation
        body["execution_tag"] = continuation["logical_execution_tag"]
        if continuation.get("required_artifact_recovery"):
            body["potential_slot_count"] = 46098
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
    continuation = value.get("continuation")
    if continuation is not None:
        _validate_continuation(continuation, source)
        method = _amended_method(method, continuation)
    expected_tag = (continuation["logical_execution_tag"] if continuation is not None
                    else "p4-cm1-" + digest(str(study_path.parent.relative_to(BASE)))[:16])
    require(value["source"] == source and value["source_sha256"] == source["sha256"]
        and value["runtime"] == runtime and value["runtime_sha256"] == digest(runtime)
        and value["launcher_sha256"] == file_hash(LAUNCHER)
        and value["policy"] == PARENT_POLICY and value["policy_sha256"] == digest(PARENT_POLICY)
        and value["authorization_sha256"] == file_hash(ROOT / RECORDS["authorization"])
        and value["pricing_sha256"] == file_hash(ROOT / RECORDS["pricing"])
        and value["method"] == method and value["method_sha256"] == digest(method)
        and value["execution_tag"] == expected_tag
        and value["development"] == _development() and value["seed_tree"] == strategy.seed_tree()
        and value["development_study_sha256"] == OLD_STUDY_SHA
        and value["editor_tools"] == read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
        and value["exposure_inventory_sha256"] == file_hash(ROOT / RECORDS["exposure"])
        and value["eligibility_proof"] == review and value["eligibility_proof_sha256"] == digest(review)
        and value["confirmation_source_sha256"] == eligibility.SOURCE_SHA256
        and value["confirmation_tasks_opened"] is False
        and value["maximum_admitted_attempts"] == 40914
        and value["potential_slot_count"] == (46098 if continuation and continuation.get("required_artifact_recovery") else 40914)
        and value["fixture_supervision_rehearsal"] is False,
        "P4 current method/source/runtime/authority changed")
    require(strategy.validate_harness(study_path.parent / "seed")["tree"] == value["seed_tree"],
            "P4 seed directory changed")
    return value




def _amended_method(method: dict, continuation: dict) -> dict:
    # Spending approval is a separate receipt; excluding it avoids circular seals.
    plan = {key: value for key, value in continuation.items() if key not in {"sha256", "spending_authorization"}}
    return {**method, "id": "phase4-cm1-amended-resumed-method-v1",
        "original_method_sha256": continuation["original_method_sha256"],
        "continuation_plan_sha256": digest(plan),
        "required_artifact_recovery": continuation.get("required_artifact_recovery")}


def continuation_scope(study: dict) -> dict:
    """Exact metadata-only review scope; no unopened prompt content is needed."""
    from .workflow import worklist

    value = study["continuation"]
    manifest = read_json(_referenced(value["confirmation_manifest"])) if value.get("confirmation_manifest") else None
    require(manifest is not None or value["fixture"], "live continuation requires the original 24-task manifest")
    ids = [row["source_task_id"] for row in manifest["selected"]] if manifest else [f"synthetic-p4-{i:02d}" for i in range(1, 25)]
    require(len(ids) == 24 and len(set(ids)) == 24, "continuation must retain the exact 24 original task IDs")
    spent, held = dict.fromkeys(policy.ALLOCATIONS, 0), dict.fromkeys(policy.ALLOCATIONS, 0)
    attempts = 0
    known: dict[tuple[str, str], set[str]] = {}
    latest: dict[tuple[str, str], dict] = {}
    for entry in value["children"]:
        unit = (entry["kind"], entry["pair"])
        state, _ = accounting.read_reference(entry["journal"])
        spent[unit[0]] += state["spent_micro_usd"]
        held[unit[0]] += state["reserved_micro_usd"]
        attempts += state["attempts"]
        known.setdefault(unit, set()).update(state["intents"])
        if entry.get("result"):
            latest[unit] = read_json(_referenced(entry["result"]), max_bytes=policy.artifact_limits()["saved_artifact_bytes"])
    future = {}
    for entry in study["development"]:
        pair = entry["pilot_id"]
        if (latest.get(("dev", pair)) or {}).get("status") != "complete":
            future["dev/" + pair] = {slot: meta for slot, meta in worklist(study, "dev", pair, entry["task"]).items()
                                      if slot not in known.get(("dev", pair), set())}
    for index, task_id in enumerate(ids, 1):
        pair = f"p4-{index:02d}"
        generation = latest.get(("inference", pair), {})
        adaptive_complete = (generation.get("adaptive") or {}).get("status") == "complete"
        fixed_complete = (generation.get("fixed") or {}).get("status") == "complete"
        if not (adaptive_complete and fixed_complete):
            slots = worklist(study, "inference", pair, {"id": task_id})
            future["inference/" + pair] = {slot: meta for slot, meta in slots.items()
                if slot not in known.get(("inference", pair), set())
                and not (adaptive_complete and meta["cell"] == pair + ":adaptive")
                and not (fixed_complete and meta["cell"] == pair + ":fixed")}
        future["assessment/" + pair] = {slot: meta for slot, meta in worklist(study, "assessment", pair, {"id": task_id}).items()
            if slot not in known.get(("assessment", pair), set())}
    return {"kind": "phase4-cm1-continuation-spending-scope-v1", "method_sha256": study["method_sha256"],
        "source_sha256": study["source_sha256"], "original_prompt_ids": ids,
        "confirmation_manifest_sha256": value["confirmation_manifest"]["file_sha256"] if manifest else None,
        "required_artifact_recovery": value.get("required_artifact_recovery"),
        "future_worklist_sha256": digest(future), "future_potential_slots": sum(len(slots) for slots in future.values()),
        "remaining_admissions": 40914 - attempts, "maximum_cumulative_admissions": 40914,
        "known_spent_micro_usd": sum(spent.values()), "held_micro_usd": sum(held.values()),
        "remaining_total_micro_usd": 1_200_000_000 - sum(spent.values()) - sum(held.values()),
        "remaining_allocations_micro_usd": {key: policy.ALLOCATIONS[key] - spent[key] - held[key] for key in spent},
        "historical_held_micro_usd": 22_880_000, "historical_hold_available_for_spending": False}


def _sealed_reference(target: Path) -> dict:
    target = safe(target)
    return {"path": str(target), "file_sha256": file_hash(target)}


def _referenced(value: dict) -> Path:
    require(isinstance(value, dict) and set(value) == {"path", "file_sha256"}
        and ledger_core._hash(value["file_sha256"]), "invalid artifact origin reference")
    target = safe(Path(value["path"]))
    require(file_hash(target) == value["file_sha256"], "immutable continuation origin changed")
    return target



def validate_origin_entry(entry: dict) -> None:
    opened = checked(read_json(_referenced(entry["open"])))
    require(opened["child_sha256"] == entry["journal"]["execution_study_sha256"]
        and opened["allocation"]["child_kind"] == entry["kind"]
        and opened["allocation"]["pair"] == entry["pair"], "origin open identity differs")
    if entry.get("result") is not None:
        require(entry.get("closure") is not None, "published origin result lacks its committed closure")
        result = read_json(_referenced(entry["result"]), max_bytes=policy.artifact_limits()["saved_artifact_bytes"])
        closure = checked(read_json(_referenced(entry["closure"])))
        require(closure["open_sha256"] == opened["sha256"]
            and closure["child_sha256"] == entry["journal"]["execution_study_sha256"]
            and closure["result_sha256"] == digest(result), "origin result differs from its committed closure")

def _validate_continuation(value: dict, current_source: dict) -> None:
    require(isinstance(value, dict) and value.get("kind") == "phase4-cm1-continuation-v1"
        and value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}),
        "continuation seal differs")
    original = read_json(_referenced(value["original_study"]))
    require(original.get("study_sha256") == digest({k: v for k, v in original.items() if k != "study_sha256"})
        and value["logical_execution_tag"] == original["execution_tag"]
        and value["original_method_sha256"] == original["method_sha256"]
        and type(value["fixture"]) is bool
        and value.get("required_artifact_recovery") in (None, "required-plan-rank-once-v1"),
        "continuation logical lineage differs")
    previous_path = _referenced(value["previous_study"])
    previous = read_json(previous_path)
    require(value["children"] == continuation_children(previous_path, value["fixture"]),
            "continuation omitted or changed a physical origin execution")
    require(previous.get("study_sha256") == value["previous_study_sha256"], "previous study identity differs")
    if value.get("previous_outcome") is not None:
        outcome = read_json(_referenced(value["previous_outcome"]))
        require(outcome.get("study_sha256") == value["previous_study_sha256"]
            and outcome.get("fixture") is value["fixture"], "closed predecessor outcome differs")
    else:
        require(value.get("owner_closure") is not None, "crashed predecessor needs verified owner closure")
    if value.get("owner_closure") is not None:
        closure = read_json(_referenced(value["owner_closure"]))
        require(closure.get("kind") == "phase4-cm1-owner-closure-v1"
            and closure.get("sha256") == digest({k: v for k, v in closure.items() if k != "sha256"})
            and closure.get("study_sha256") == value["previous_study_sha256"]
            and closure.get("owner_stopped") is True, "predecessor owner is not verified stopped")
    for child in value["children"]:
        require(child["journal"].get("fixture") is value["fixture"], "continuation mixes live and fixture origins")
        accounting.read_reference(child["journal"])
        validate_origin_entry(child)
    proof = read_json(_referenced(value["compatibility"]), max_bytes=policy.artifact_limits()["saved_artifact_bytes"])
    require(proof.get("kind") == "phase4-cm1-continuation-compatibility-v1"
        and proof.get("sha256") == digest({k: v for k, v in proof.items() if k != "sha256"})
        and proof.get("passed") is True and proof.get("provider_calls") == 0
        and proof.get("previous_source_sha256") == previous["source_sha256"]
        and proof.get("current_source_sha256") == current_source["sha256"]
        and proof.get("origins_sha256") == digest([child["journal"] for child in value["children"]])
        and isinstance(proof.get("validated_segments"), list)
        and proof.get("origin_source") == previous["source"],
        "offline source/prefix compatibility proof required before continuation")
    for entry in value["children"]:
        if entry["kind"] != "inference" or entry.get("result") is None:
            continue
        generation = read_json(_referenced(entry["result"]), max_bytes=policy.artifact_limits()["saved_artifact_bytes"])
        adaptive = generation.get("adaptive") or {}
        if adaptive.get("status") == "complete":
            require(any(segment.get("kind") == "native-adaptation-v1"
                and segment.get("record_sha256") == digest(adaptive)
                for segment in proof["validated_segments"]),
                "published native selection lacks its fully verified origin aggregate")
    if value.get("confirmation_manifest") is not None:
        _referenced(value["confirmation_manifest"])


def _continuation_authority(study: dict, reference: dict | None = None) -> None:
    value, source_sha256 = study["continuation"], study["source_sha256"]
    reference = reference or value.get("spending_authorization")
    require(reference is not None, "continuation needs explicit amended spending authorization")
    authority = read_json(_referenced(reference))
    require(authority.get("kind") == "phase4-cm1-continuation-authorization-v1"
        and authority.get("sha256") == digest({k: v for k, v in authority.items() if k != "sha256"})
        and authority.get("authorized") is True and authority.get("previous_owner_stopped") is True
        and authority.get("previous_study_sha256") == value["previous_study_sha256"]
        and authority.get("source_sha256") == source_sha256
        and authority.get("compatibility_sha256") == read_json(_referenced(value["compatibility"]),
            max_bytes=policy.artifact_limits()["saved_artifact_bytes"])["sha256"]
        and authority.get("total_cap_micro_usd") == 1_200_000_000
        and authority.get("maximum_admissions") == 40914
        and authority.get("required_artifact_recovery") == value.get("required_artifact_recovery")
        and authority.get("scope") == continuation_scope(study),
        "amended spending authority does not cover this exact continuation")



def continuation_children(previous_study_path: Path, fixture: bool) -> list[dict]:
    previous_study_path = path(previous_study_path)
    previous = read_json(previous_study_path)
    previous_run, _ = paths(previous, fixture)
    children = []
    for directory in sorted((previous_run / "children").glob("*")):
        opened = read_json(directory / "open.json")
        reference = accounting.journal_reference(accounting.canonical_journal(opened["child_sha256"], fixture))
        entry = {"kind": opened["allocation"]["child_kind"], "pair": opened["allocation"]["pair"],
            "journal": reference, "open": _sealed_reference(directory / "open.json"),
            "result": _sealed_reference(directory / "result.json") if (directory / "result.json").is_file() else None,
            "closure": _sealed_reference(directory / "closure.json") if (directory / "closure.json").is_file() else None}
        children.append(entry)
    prior = previous.get("continuation")
    if prior is not None:
        inherited = {row["journal"]["execution_study_sha256"]: row for row in prior["children"]}
        inherited.update({row["journal"]["execution_study_sha256"]: row for row in children})
        children = list(inherited.values())
    return children


def prepare_continuation(previous_study_path: Path, output: Path, *, fixture: bool,
                         compatibility_path: Path, spending_authorization_path: Path | None = None,
                         recovery_policy: str | None = None, owner_closure_path: Path | None = None) -> dict:
    """A new execution of the same logical cases; original artifacts remain read-only."""
    previous_study_path = path(previous_study_path)
    previous = read_json(previous_study_path)
    require(type(fixture) is bool and previous.get("study_sha256") == digest({k: v for k, v in previous.items()
        if k != "study_sha256"}), "previous study is not sealed")
    previous_run, _ = paths(previous, fixture)
    if previous.get("continuation", {}).get("required_artifact_recovery") is not None:
        inherited = previous["continuation"]["required_artifact_recovery"]
        require(recovery_policy is None or recovery_policy == inherited, "required recovery policy changed after exposure")
        recovery_policy = inherited
    require((previous_run / "outcome.json").is_file() or owner_closure_path is not None,
            "crashed predecessor requires explicit owner-closure evidence")
    children = continuation_children(previous_study_path, fixture)
    prior = previous.get("continuation")
    manifest = (prior.get("confirmation_manifest") if prior else None)
    if manifest is None and (previous_study_path.parent / "confirmation-manifest.json").is_file():
        manifest = _sealed_reference(previous_study_path.parent / "confirmation-manifest.json")
    original_reference = prior["original_study"] if prior else _sealed_reference(previous_study_path)
    original = read_json(_referenced(original_reference))
    body = {"kind": "phase4-cm1-continuation-v1", "fixture": fixture,
        "previous_study": _sealed_reference(previous_study_path), "previous_study_sha256": previous["study_sha256"],
        "previous_outcome": _sealed_reference(previous_run / "outcome.json") if (previous_run / "outcome.json").is_file() else None,
        "owner_closure": _sealed_reference(owner_closure_path) if owner_closure_path else None,
        "original_study": original_reference,
        "funding_origin_study_sha256": prior["funding_origin_study_sha256"] if prior else previous["study_sha256"],
        "original_method_sha256": original["method_sha256"], "logical_execution_tag": original["execution_tag"],
        "children": children, "confirmation_manifest": manifest,
        "compatibility": _sealed_reference(compatibility_path),
        "spending_authorization": _sealed_reference(spending_authorization_path) if spending_authorization_path else None,
        "required_artifact_recovery": recovery_policy}
    body["sha256"] = digest(body)
    result = prepare(output, continuation=body)
    if manifest is not None:
        write_bytes_once(path(output) / "confirmation-manifest.json", _referenced(manifest).read_bytes())
    return result


def make_grant(study_path: Path, fixture: bool, *, continuation_authorization_path: Path | None = None) -> dict:
    study = load_study(study_path)
    require(type(fixture) is bool, "P4 grant mode must be explicit")
    if study.get("continuation") is not None:
        require(study["continuation"].get("fixture") is fixture, "continuation grant mode differs from its origins")
    authorization = _sealed_reference(continuation_authorization_path) if continuation_authorization_path else None
    require(authorization is None or study.get("continuation") is not None,
            "continuation authority cannot alter an original study")
    if not fixture and study.get("continuation") is not None:
        _continuation_authority(study, authorization)
    body = {"kind": "phase4-cm1-parent-grant-v1", "fixture": fixture,
        **{key: study[key] for key in READINESS_BINDINGS},
        "authority": {"study_sha256": study["study_sha256"], "authorization_id": "phase4-cm1-user-approval",
            "authorized": not fixture, "cap_micro_usd": PARENT_POLICY["phase_micro_usd"],
            "canary_cap_micro_usd": PARENT_POLICY["first_micro_usd"], "expansion_authorized": False,
            "control_policy_sha256": ledger_core.am1.CONTROL_SHA256,
            "billing_profile": ledger_core.am1.BILLING_PROFILE}}
    if study.get("continuation") is not None:
        body["continuation_scope"] = continuation_scope(study)
        body["continuation_authorization"] = authorization or study["continuation"].get("spending_authorization")
    return {**body, "grant_sha256": digest(body)}


def grant_for(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    value = read_json(path(grant_path))
    authorization = _referenced(value["continuation_authorization"]) if value.get("continuation_authorization") else None
    require(type(fixture) is bool and value == make_grant(study_path, fixture,
        continuation_authorization_path=authorization), "P4 parent grant differs")
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
        if study.get("continuation") is not None:
            previous = study["continuation"]["funding_origin_study_sha256"]
            require(target.exists() and read_json(target).get("study_sha256") == previous,
                    "continuation has no original allowance claim")
        elif target.exists():
            require(read_json(target) == record, "another P4 parent already claims this allowance")
    return checked


def claim(checked: dict) -> dict:
    require(preflight(Path(checked["study_path"]), Path(checked["grant_path"]), checked["stage"],
        checked["mode"], supervisor_agent=checked.get("supervisor_agent")) == checked,
        "P4 claim no longer matches accepted preflight")
    record = _claim_record(checked)
    study = load_study(Path(checked["study_path"]))
    if study.get("continuation") is None:
        write_once(path(BASE / "live-study-phase4-cm1-v1.json"), record)
    else:
        # The original allowance claim remains immutable. Each successor has one claim.
        write_once(path(Path(checked["run"]) / "continuation-allowance-claim.json"), record)
    return record
