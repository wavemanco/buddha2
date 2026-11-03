"""Reuse frozen analysis and disclose R2 deadline accounting without restoring outputs."""
from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from buddha2.artifacts import ContractError, digest, write_bytes_once, write_once
from followups.phase3a_c1_completion_v1.report import ARMS as ARMS
from followups.phase3a_c1_completion_v1.report import build as frozen_build
from followups.phase3a_c1_completion_v1.report import parent as parent

ROOT = Path(__file__).resolve().parents[2]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def build(study: dict, state: dict, saved: dict, fixture: bool) -> dict:
    """Project validated deadline evidence; no clock, SDK or filesystem work occurs here."""
    stop = state.get("deadline_stop")
    if stop is None:
        stop = saved.get("deadline_stop")
    _require(stop is None or isinstance(stop, dict) and bool(stop), "deadline stop metadata must be a nonempty object")
    if state.get("deadline_stop") is not None and saved.get("deadline_stop") is not None:
        _require(state["deadline_stop"] == saved["deadline_stop"], "deadline stop projections differ")
    validation = saved.get("validation_failure")
    known_validation_stop = isinstance(validation, dict) and validation.get("classification") == "known_deadline_stop"
    _require(not known_validation_stop or stop is not None, "known deadline classification lacks its durable latch")
    if stop is not None:
        _require(state["status"] in {"stopped-known-deadline", "blocked-unknown"}, "deadline stop cannot expose a ready ledger")
    audits = state.get("transport_audit_summary")
    _require(audits is None or isinstance(audits, dict), "transport audit summary must be an object or unknown")
    data = frozen_build(study, state, saved, fixture)
    projected_unknown = data["summary"]["unknown_results"]
    active = state.get("active_unsettled_intents")
    durable_unknown = state.get("durable_unknown_results")
    if active is not None or durable_unknown is not None:
        if (not isinstance(active, list) or not all(isinstance(slot, str) and slot in state["intents"] for slot in active)
                or len(active) != len(set(active)) or type(durable_unknown) is not int or durable_unknown < 0):
            raise ContractError("durable journal counters are invalid")
        _require(durable_unknown + len(active) == projected_unknown,
                 "durable and active unknown counters differ from conservative replay")
        for request in data["protocol"]["requests"]:
            if request["slot_id"] in active:
                request["conservative_replay_projection"] = {
                    "result_sha256": request["result_sha256"], "status": request["status"], "failure": request["failure"]}
                request.update(status="pending", result_sha256=None, returned_model=None, failure=None, spent_micro_usd=None)
                data["coverage"]["slots"][request["slot_id"]] = "pending_active_intent"
        for section in ("summary", "accounting"):
            data[section].update(unknown_results=durable_unknown, pending_intents=len(active))
    for section in ("summary", "accounting", "protocol"):
        data[section].update(durable_unknown_results=durable_unknown,
            active_unsettled_intents=copy.deepcopy(active), projected_unknown_results=projected_unknown,
            unknown_results_semantics=("Durable unknown result events only; conservative active-intent projections are separate."
                if active is not None else "Legacy conservative replay counter; durable/active distinction was not supplied."))
    disposition = ("known_deadline_stop" if state["status"] == "stopped-known-deadline" else "unknown_deadline_hold") if stop else None
    if known_validation_stop:
        if disposition is None:
            raise ContractError("known deadline validation lacks a stopped disposition")
        for row in data["rows"]:
            if row["status"] == "unvalidated_integrity_hold":
                row["status"] = "unvalidated_" + disposition
                row["branch_status"] = row["status"]
    for section in ("summary", "accounting", "analysis", "protocol"):
        data[section]["deadline_stop"] = copy.deepcopy(stop)
        data[section]["deadline_disposition"] = disposition
        data[section]["transport_audit_summary"] = copy.deepcopy(audits)
    data["summary"].update(admitted_attempts=state["attempts"],
        provider_calls_semantics="Legacy live admitted-attempt counter; not SDK invocation or provider-egress proof.",
        core_journal_status=state.get("core_status", state["status"]))
    data["protocol"]["provider_calls_semantics"] = data["summary"]["provider_calls_semantics"]
    if stop is not None:
        if disposition is None:
            raise ContractError("deadline stop lacks its stopped disposition")
        data["summary"].update(status="incomplete", complete_primary=False, scientific_complete=False)
        data["analysis"].update(complete_primary=False, scientific_complete=False,
            mean_adaptive_minus_fixed=None, selected_method=None, descriptive_direction=None)
        for slot, status in data["coverage"]["slots"].items():
            if status in {"not_attempted", "not_attempted_readiness_gate", "not_attempted_engineering_review"}:
                data["coverage"]["slots"][slot] = "not_attempted_" + disposition
        if disposition == "known_deadline_stop":
            for request in data["protocol"]["requests"]:
                if request["slot_id"] == stop.get("slot_id"):
                    request["deadline_output_eligible"] = False
    data["coverage"]["slot_counts"] = dict(Counter(data["coverage"]["slots"].values()))
    data["summary"].pop("evidence_sha256", None)
    data["summary"]["evidence_sha256"] = digest(data)
    return data


def write_report(data: dict, output: Path) -> dict:
    """Write immutable public report files; the caller owns snapshot validation."""
    output = Path(output)
    roots = (ROOT / "runs/phase3a-compat-c1-v1/completion-v3",
             ROOT / "runs/phase3a-c1-completion-v3",
             ROOT / "evidence/phase3a-c1-completion-v3",
             Path("/results/phase3a-compat-c1-v1/completion-v3"),
             Path("/results/phase3a-c1-completion-v3"))
    _require(output.is_absolute() and ".." not in output.parts
             and not any(part.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
                         for part in output.parts)
             and any(output.is_relative_to(p) and output != p for p in roots),
             "report output is outside the new completion namespace")
    _require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                     for p in (output, *output.parents)), "report output traverses a link")
    names = ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")
    if output.exists():
        allowed = {name + ".json" for name in names} | {"PHASE3A_REPORT.md"}
        _require(output.is_dir() and all(p.name in allowed for p in output.iterdir()),
                 "report output contains artifacts owned by another operation")
    for name in names:
        write_once(output / f"{name}.json", data[name])
    summary, analysis = data["summary"], data["analysis"]
    text = ("# Phase 3A C1-backed paired development pilot\n\n"
        + ("Synthetic evidence only; no live readiness or effectiveness conclusion.\n\n" if summary["fixture"] else
           "Four exposed paired development units; no held-out, population or equal-realized-compute causal claim.\n\n")
        + f"Status: {summary['status']}. Primary scores: {summary['primary_scored']}/8. "
        + f"Readiness passed: {summary['readiness_passed']}. Authentic live path: {summary['authentic_live_path']}.\n\n"
        + f"Admitted attempts: {summary['attempts']}; accounted micro-USD: {summary['spent_micro_usd']}; "
        + f"new unresolved reservation: {summary['reserved_micro_usd']}.\n\n"
        + "The legacy provider_calls field counts admitted live attempts; it is not proof of SDK invocation or provider egress. "
        + f"Validated transport-audit counts: {json.dumps(summary.get('transport_audit_summary'), sort_keys=True)}. "
        + f"Deadline disposition: {summary.get('deadline_disposition')}.\n\n"
        + f"Durable unknown results: {summary.get('durable_unknown_results')}; "
        + f"active unsettled intents: {summary['pending_intents']}; "
        + f"conservative replay unknown projections: {summary.get('projected_unknown_results')}. "
        + "An active intent is not a durable unknown outcome; its full conservative reservation remains held.\n\n"
        + f"Complete-primary mean adaptive-minus-fixed: {analysis['mean_adaptive_minus_fixed']}. "
        + "Missing readiness, primary coverage, known accounting or authentic live execution keeps the aggregate unset. "
        + "Native fallback outcomes remain included and classified.\n\n"
        + f"Historical known accounting: {summary['prior_real_phase3a_spent_micro_usd']} micro-USD; "
        + f"historical unresolved reservation: {summary['prior_real_phase3a_reserved_micro_usd']} micro-USD, retained in full. "
        + ("Fixture costs are separate; no cumulative real total is inferred.\n\n" if summary["fixture"] else
           f"Cumulative known accounting: {summary['cumulative_real_phase3a_spent_micro_usd']} micro-USD.\n\n")
        + "The fixed first-prompt duplicate is diagnostic only and never replaces the primary. "
        + "Readiness is counted once in adaptive01; equal ceilings are allowances, not invoices or equal realized compute.\n")
    write_bytes_once(output / "PHASE3A_REPORT.md", text.encode("utf-8"))
    return {**summary, "report_output": str(output), "reporting_provider_calls": 0}
