"""Reuse the frozen pure analysis; admit report writes only in the new V2 scope."""
from __future__ import annotations

from pathlib import Path

from buddha2.artifacts import ContractError, write_bytes_once, write_once
from followups.phase3a_c1_completion_v1.report import ARMS as ARMS
from followups.phase3a_c1_completion_v1.report import build as build
from followups.phase3a_c1_completion_v1.report import parent as parent

ROOT = Path(__file__).resolve().parents[2]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def write_report(data: dict, output: Path) -> dict:
    """Write immutable public report files; the caller owns snapshot validation."""
    output = Path(output)
    roots = (ROOT / "runs/phase3a-compat-c1-v1/completion-v2",
             ROOT / "runs/phase3a-c1-completion-v2",
             ROOT / "evidence/phase3a-c1-completion-v2",
             Path("/results/phase3a-compat-c1-v1/completion-v2"),
             Path("/results/phase3a-c1-completion-v2"))
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
        + f"Attempts: {summary['attempts']}; accounted micro-USD: {summary['spent_micro_usd']}; "
        + f"new unresolved reservation: {summary['reserved_micro_usd']}.\n\n"
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
