"""The approved, finite three-pair continuation profile; legacy defaults stay intact."""
from __future__ import annotations

import copy

from buddha2.artifacts import digest

from . import ledger_core
from .support import ROOT, read, require

PILOTS = ("p3b-02", "p3b-03", "p3b-04")
DEFINITION_SHA256 = "cff2c3447c4bf761bc8d5f9c86f4ba083bd742a1423e3858aa73f891fc1d17b5"
AUTHORITY = ROOT / "evidence/phase3b-seq2-v1/remaining-pairs-authorization-v1.json"
POLICY = copy.deepcopy(ledger_core.POLICY)
POLICY.update(id="phase3b-remaining-pairs-accounting-v1", phase_micro_usd=350_000_000,
    first_micro_usd=350_000_000, cell_micro_usd=50_000_000,
    assessment_micro_usd=100_000_000, first_assessment_micro_usd=100_000_000,
    execution_pairs=list(PILOTS), maximum_admitted_attempts=1758,
    cell_bounds={
        "adaptive": {"http": 408, "input": 408_000_000, "output": 5_385_216},
        "fixed": {"http": 145, "input": 145_000_000, "output": 605_824},
    })


def authority() -> dict:
    value = read(AUTHORITY)
    require(value.get("kind") == "phase3b-remaining-pairs-authority-v1"
        and value.get("authorized") is True and value.get("definition_sha256") == DEFINITION_SHA256
        and value.get("execution_pilots") == list(PILOTS)
        and value.get("new_cap_micro_usd") == POLICY["phase_micro_usd"]
        and value.get("inference_cell_micro_usd") == POLICY["cell_micro_usd"]
        and value.get("assessment_pool_micro_usd") == POLICY["assessment_micro_usd"]
        and value.get("potential_request_slots") == value.get("maximum_admitted_attempts") == 1758
        and value.get("completed_pair_new_calls") == 0
        and value.get("fresh_keys_only_after_independent_acceptance") is True
        and value.get("whole_block_includes_reviews_exports_and_closure") is True
        and value.get("automatic_paid_repeat_authorized") is False
        and value.get("historical_hold_release_authorized") is False,
        "remaining-pairs authority differs from approved scope")
    return value


def enabled(study: dict) -> bool:
    return "execution_pilots" in study


def execution_tasks(study: dict) -> list[dict]:
    if not enabled(study):
        return study["tasks"]
    require(study["execution_pilots"] == list(PILOTS), "remaining execution scope changed")
    tasks = [row for row in study["tasks"] if row["pilot_id"] in PILOTS]
    require([row["pilot_id"] for row in tasks] == list(PILOTS), "remaining task order changed")
    return tasks


def first(study: dict) -> str:
    return execution_tasks(study)[0]["pilot_id"]


def policy_for(slots: dict) -> dict | None:
    if len(slots) != 1758:
        return None
    require({row.get("pair") for row in slots.values()} == set(PILOTS),
        "remaining slots contain a foreign pair")
    validate_bounds(slots)
    return copy.deepcopy(POLICY)


def validate_bounds(slots: dict) -> None:
    """A producer role change must be detected before any journal or SDK opens."""
    totals: dict[str, dict[str, int]] = {}
    for row in slots.values():
        require(row.get("role") in ledger_core.ROLES and isinstance(row.get("cell"), str),
            "remaining role/cell contract is incomplete")
        reserve = ledger_core._reservation(row["role"])
        cell = totals.setdefault(row["cell"], {"http": 0, "input": 0, "output": 0})
        cell["http"] += 1
        cell["input"] += reserve["input"]
        cell["output"] += reserve["output"]
    expected = {pilot + ":" + arm: bounds for pilot in PILOTS
        for arm, bounds in POLICY["cell_bounds"].items()}
    expected["assessment"] = {"http": 99, "input": 99_450_000, "output": 2_592_000}
    require(totals == expected and sum(row["http"] for row in totals.values()) == 1758
        and sum(row["input"] for row in totals.values()) == 1_758_450_000
        and sum(row["output"] for row in totals.values()) == 20_565_120,
        "remaining producer reservations no longer match the approved worklist bounds")


def policy_by_hash(value: object) -> dict | None:
    return copy.deepcopy(POLICY) if value == digest(POLICY) else None
