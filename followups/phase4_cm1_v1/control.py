"""Cost-only allocation across complete, unchanged twelve-candidate pools."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from buddha2.artifacts import digest
from followups.phase3b_seq2_v1 import ledger_core, strategy
from followups.phase3b_seq2_v1.support import require


def fixed_run_ids(run_id: str) -> list[str]:
    require(isinstance(run_id, str) and bool(run_id.strip()), "fixed hierarchy requires its run identity")
    return [f"{run_id}/pool-{i:02d}" for i in range(1, 9)]


def run_fixed(task: dict, harness_dir: Path, *, study_sha256: str, run_id: str,
              target_micro_usd: int, dispatch: Callable, spent: Callable[[], int],
              fixture: bool, request_policy: dict, recovery_policy: str | None = None) -> dict:
    """Spend toward the native bill; only settled cost controls pool count."""
    require(type(target_micro_usd) is int and target_micro_usd > 0,
            "complete native inference with a positive settled bill is required")
    require(callable(dispatch) and callable(spent), "controlled dispatch and accounting are required")
    pools: list[dict] = []
    visited: dict[str, dict] = {}
    prior = 0
    base = {"kind": "phase4-cm1-hierarchical-fixed-v1", "study_sha256": study_sha256,
            "task_id": task["id"], "run_id": run_id, "fixture": fixture,
            "target_micro_usd": target_micro_usd, "request_policy_sha256": digest(request_policy)}

    def prefix_cost():
        return sum(row["spent_micro_usd"] for row in visited.values())

    def call(slot, role, request):
        result = dispatch(slot, role, request)
        if result.get("status") == "unknown":
            raise ledger_core.LiabilityStop("unresolved fixed request prevents further allocation")
        require(result.get("status") == "response" and type(result.get("spent_micro_usd")) is int
                and result["spent_micro_usd"] >= 0, "fixed request lacks settled usage accounting")
        require(slot not in visited or visited[slot] == result, "fixed replay changed a settled result")
        visited[slot] = result
        return result

    def outcome(status, reason, *, portfolio=None, chosen=None, selection=None):
        actual = spent()
        require(type(actual) is int and actual >= prior, "fixed settled accounting moved backwards")
        require(actual == prefix_cost(), "fixed accounting contains unreachable or missing requests")
        return {**base, "status": status, "reason": reason, "pools": pools,
                "spent_micro_usd": actual, "selected_run_id": chosen,
                "portfolio": portfolio, "selection": selection,
                "pool_ceiling_reached": len(pools) == 8}

    for pool_id in fixed_run_ids(run_id):
        # Hash ordering is fixed before outcomes; no scores enter the allocation.
        order = sorted([f"{pool_id}/candidate-{i:02d}" for i in range(1, 13)],
                       key=lambda candidate: digest({"task_id": task["id"],
                           "run_id": pool_id, "candidate_run_id": candidate}))
        record = strategy.fixed_best12(task, harness_dir, study_sha256=study_sha256,
            run_id=pool_id, dispatch=call, fixture=fixture, candidate_order=order,
            request_policy=request_policy, recovery_policy=recovery_policy)
        pools.append(record)
        # Replays see the original settled prefix, not the later full journal total.
        current = prefix_cost()
        require(type(current) is int and current >= prior, "fixed settled accounting moved backwards")
        prior = current
        if record.get("status") != "complete" or record.get("portfolio") is None:
            return outcome("incomplete", "required_pool_incomplete")
        if 10 * current >= 9 * target_micro_usd:
            break
    if len(pools) == 1:
        return outcome("complete", None, portfolio=pools[0]["portfolio"],
                       chosen=pools[0]["selected_run_id"])
    ordered = sorted(pools, key=lambda row: digest({"task_id": task["id"],
                                                  "run_id": row["run_id"]}))
    mapping = {f"candidate-{i:02d}": row for i, row in enumerate(ordered, 1)}
    request = strategy.fixed_selection_request(task, mapping)
    ledger_core.validate_request("fixed_selector", request, policy=request_policy)
    slot = strategy.slot_ids(run_id)["selector"]
    try:
        result = call(slot, "fixed_selector", request)
    except ledger_core.CellBudgetStop:
        return outcome("incomplete", "final_selection_budget_stop")
    raw = strategy.verified_response(result, study_sha256=study_sha256, fixture=fixture,
                                    slot_id=slot, role="fixed_selector", request=request)
    selection = {"slot_id": slot, "request": request, "result": result,
                 "candidate_map": {key: row["selected_run_id"] for key, row in mapping.items()}}
    try:
        chosen = strategy.strict_object(raw["text"])
    except ledger_core.ContractError:
        return outcome("incomplete", "invalid_final_selection", selection=selection)
    if (raw["stop_reason"] != "end_turn" or set(chosen) != {"candidate_id"}
            or type(chosen["candidate_id"]) is not str or chosen["candidate_id"] not in mapping):
        return outcome("incomplete", "invalid_final_selection", selection=selection)
    winner = mapping[chosen["candidate_id"]]
    return outcome("complete", None, portfolio=winner["portfolio"],
                   chosen=winner["selected_run_id"], selection=selection)
