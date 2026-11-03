"""Reuse the frozen scientific fold and disclose HI inventory versus authority."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from buddha2.artifacts import ContractError, digest, write_bytes_once, write_once
from followups.phase3a_c1_completion_v3 import report as frozen

from .support import safe

ARMS, parent = frozen.ARMS, frozen.parent
ROOT = Path(__file__).resolve().parents[2]
NAMES = ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def build(study: dict, state: dict, saved: dict, fixture: bool) -> dict:
    """Project validated records without changing scoring, missingness or eligibility."""
    counts = Counter(row["cell"] for row in study["slots"].values())
    pilots = {task["pilot_id"] for task in study["tasks"]}
    expected = {pilot + ":" + arm: 144 if arm == "adaptive" else 73
                for pilot in pilots for arm in ARMS} | {"assessment": 99}
    _require(counts == expected and len(study["slots"]) == 967
             and study["policy"]["editor_turns"] == 16 and study["policy"]["cell_http"] == 96,
             "HI report inventory/profile differs")
    maximum = sum(min(96, count) if cell != "assessment" else count for cell, count in counts.items())
    _require(maximum == 775 and state["attempts"] <= maximum, "HI report exceeds admitted authority")
    data = frozen.build(study, state, saved, fixture)
    limits = {"potential_request_slots": 967, "maximum_new_admitted_attempts": maximum,
        "editor_max_requests": 16, "editor_max_ordinary_requests": 15,
        "inventory_is_authorization": False, "shape_attempts_share_cell_allowance": True}
    for name in ("coverage", "summary", "protocol"):
        data[name].update(limits)
    data["accounting"]["resource_report"].update(limits)
    data["accounting"]["resource_report"]["current_study_cap_micro_usd"] = study["policy"]["phase_micro_usd"]
    data["protocol"]["rank_io_profile"] = study["rank_io_profile"]
    data["protocol"]["authoring_intervention"] = (
        "RP1 retains sixteen maximum editor requests, fifteen ordinary and a terminal sixteenth. "
        "Initial readiness cannot use terminal control. Shared RC1 rank-only labels preserve canonical answers, "
        "N1, seed strings and model settings. This contract is fixed engineering, not learned adaptation. "
        "The global $200 ceiling overlaps the unchanged local pools; potential slots do not grant admissions.")
    for name, value in data.items():
        if isinstance(value, dict) and "kind" in value:
            value["kind"] = "phase3a-rp1-" + name + "-v1"
    data["summary"].pop("evidence_sha256", None)
    data["summary"]["evidence_sha256"] = digest(data)
    return data


def write_report(data: dict, output: Path) -> dict:
    """Write the same eight immutable files, only below the new HI scopes."""
    output = Path(output)
    roots = tuple(base / suffix for base in (ROOT / "runs", Path("/results"))
                  for suffix in ("phase3a-rc1-pilot-v1/native", "phase3a-rc1-pilot-v1"))
    roots += (ROOT / "evidence/phase3a-rc1-pilot-v1",)
    _require(output.is_absolute() and any(output != root and output.is_relative_to(root) for root in roots),
             "report output is outside the HI namespace")
    output = safe(output, roots=roots)
    allowed = {name + ".json" for name in NAMES} | {"PHASE3A_REPORT.md"}
    if output.exists():
        _require(output.is_dir() and all(path.name in allowed for path in output.iterdir()),
                 "report output contains foreign artifacts")
    for name in NAMES:
        write_once(output / (name + ".json"), data[name])
    s, a = data["summary"], data["analysis"]
    text = ("# Phase 3A RP1 paired development pilot\n\n"
        + ("Synthetic evidence only; no live readiness or effectiveness conclusion.\n\n" if s["fixture"] else
           "Four exposed paired development units; no held-out or population claim.\n\n")
        + f"Status: {s['status']}. Primary scores: {s['primary_scored']}/8. Readiness passed: {s['readiness_passed']}. "
        + f"Authentic live path: {s['authentic_live_path']}.\n\n"
        + "The967 potential request slots are an inventory; at most775 requests may be admitted, "
        + "subject to every shared cell, token, dollar, time and reservation guard. Editor requests1–15 are ordinary; "
        + "request16 carries terminal control. Shape attempts share resources.\n\n"
        + f"Admitted attempts: {s['attempts']}; accounted micro-USD: {s['spent_micro_usd']}; "
        + f"new reserved micro-USD: {s['reserved_micro_usd']}. Durable unknowns: {s.get('durable_unknown_results')}; "
        + f"active unsettled intents: {s['pending_intents']}.\n\n"
        + "The legacy provider_calls field counts admitted live attempts, not proved SDK invocations or egress. "
        + "An active-intent recovery projection is not a durable unknown result.\n\n"
        + f"Complete-primary mean adaptive-minus-fixed: {a['mean_adaptive_minus_fixed']}. "
        + "Missing readiness, coverage, known accounting or authentic execution keeps the aggregate unset. "
        + "Native failures and fallback outcomes remain classified.\n\n"
        + f"Historical known micro-USD: {s['prior_real_phase3a_spent_micro_usd']}; historical held micro-USD: "
        + f"{s['prior_real_phase3a_reserved_micro_usd']}, retained in full. "
        + ("Fixture accounting never becomes cumulative real spending.\n\n" if s["fixture"] else
           f"Cumulative known micro-USD: {s['cumulative_real_phase3a_spent_micro_usd']}.\n\n")
        + "Readiness is counted once in adaptive01. The fixed duplicate is diagnostic only. "
        + "Equal ceilings are allowances, not equal actual expenditure or a completion promise.\n")
    write_bytes_once(output / "PHASE3A_REPORT.md", text.encode("utf-8"))
    return {**s, "report_output": str(output), "reporting_provider_calls": 0}
