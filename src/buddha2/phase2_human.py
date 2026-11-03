"""Append-only optional human assessments of unchanged Phase 2 outputs.

This module prepares or validates local records only. It neither contacts readers
nor gives synthetic forms the status of actual human evidence.
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

from .artifacts import ContractError, digest, file_hash
from .phase2_analysis import build_human_packets, validate_human_evidence

_KIND = "phase2-human-assessment-v1"
_POLICY = {
    "version": "phase2-optional-human-0.12-v1",
    "sample": "first two frozen tasks; repeat 1; all A/B/C; two independent readers",
    "eligibility": "original packet instructions and eligibility at first exposure",
    "missingness": "missing, compromised, cannot judge or missing context is inconclusive",
    "concerns": "exclude a candidate with either reader's substantive concern",
    "late": "append a newly received reader only; preserve first submissions and predecessor",
}


def timestamp(value: str) -> dt.datetime:
    """Require an unambiguous, canonical UTC timestamp at the input boundary."""
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ContractError("timestamps require UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    except ValueError as exc:
        raise ContractError("invalid UTC timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ContractError("timestamp is not canonical UTC")
    return parsed


def implementation_identity() -> dict:
    """Bind assessment code separately from the historical execution identity."""
    root = Path(__file__).parent
    files = {name: file_hash(root / name) for name in (
        "phase2_human.py", "phase2_analysis.py", "phase2_contracts.py", "artifacts.py",
    )}
    return {"version": 1, "files": files, "sha256": digest(files)}


def make_human_assessment(
    study: dict, portfolios: list[dict], submissions: list[dict], *, cutoff: str,
    previous: dict | None = None, window: dict | None = None, fixture: bool = False,
) -> dict:
    """Record received original forms, optionally supplementing an earlier snapshot.

    Each submission contains ``form``, ``delivered_at``, ``first_exposed_at`` and
    ``received_at``. These are operator-recorded metadata, not proof of reader
    honesty. Delivery/eligibility must be bound before first exposure. A late
    original form enters a supplement after the agreed window has been closed;
    an existing reader can never be replaced or rerated.
    """
    return _make(study, portfolios, submissions, cutoff=cutoff, previous=previous, window=window,
                 fixture=fixture, depth=0)


def _make(study: dict, portfolios: list[dict], submissions: list[dict], *, cutoff: str,
          previous: dict | None, window: dict | None, fixture: bool, depth: int) -> dict:
    if depth > 32:
        raise ContractError("human supplement chain exceeds the bounded profile")
    cut = timestamp(cutoff)
    if type(fixture) is not bool or not isinstance(submissions, list) or len(submissions) > 2:
        raise ContractError("explicit fixture mode and at most two original submissions required")
    # This also validates the frozen study, exact ordered portfolios and sample.
    checked_empty = validate_human_evidence(study, [], portfolios, fixture=fixture)
    prior: list[dict] = []
    version = 1
    previous_cut = None
    if previous is not None:
        _validate(study, portfolios, previous, fixture=fixture, depth=depth + 1)
        previous_cut = timestamp(previous["cutoff"])
        if cut < previous_cut:
            raise ContractError("a supplement cannot move its evidence cutoff backwards")
        prior = copy.deepcopy(previous["submissions"])
        version = previous["version"] + 1
        if previous["window"] is not None and window is not None and window != previous["window"]:
            raise ContractError("a supplement cannot revise the original agreed collection window")
        if previous["window"] is not None:
            window = previous["window"]
    readers = ("fixture-R1", "fixture-R2") if fixture else ("R1", "R2")
    closed = {}
    if window is not None:
        if not isinstance(window, dict) or set(window) != set(readers):
            raise ContractError("collection window must bind both declared readers")
        for reader, schedule in window.items():
            if not isinstance(schedule, dict) or set(schedule) != {"delivered_at", "due_date"}:
                raise ContractError("each reader window requires its delivery timestamp and agreed due date")
            delivered = timestamp(schedule["delivered_at"])
            try:
                due = dt.date.fromisoformat(schedule["due_date"])
            except (TypeError, ValueError) as exc:
                raise ContractError("invalid agreed due date") from exc
            if not 0 <= (due - delivered.date()).days <= 7 or delivered > cut:
                raise ContractError("collection window is outside delivery/cutoff or seven-day limit")
            if (previous is not None and previous["window"] is None
                    and previous_cut is not None and delivered <= previous_cut):
                raise ContractError("newly activated collection must follow the prior unactivated snapshot")
            closed[reader] = cut >= dt.datetime.combine(due, dt.time(23, 59, 59), dt.UTC)
    all_submissions = prior + copy.deepcopy(submissions)
    if len(all_submissions) > 2:
        raise ContractError("only two original reader submissions are permitted")
    reader_ids, late = set(), []
    for index, submission in enumerate(all_submissions):
        if not isinstance(submission, dict) or set(submission) != {
            "form", "delivered_at", "first_exposed_at", "received_at",
        } or not isinstance(submission["form"], dict):
            raise ContractError("submission requires its original form and delivery/exposure/receipt times")
        form = submission["form"]
        reader = form.get("reader_id")
        if not isinstance(reader, str) or reader in reader_ids:
            raise ContractError("preserve each reader's first submission; rerating is forbidden")
        reader_ids.add(reader)
        if window is None or reader not in window:
            raise ContractError("submitted forms require their originally agreed collection window")
        if (submission["delivered_at"] != window[reader]["delivered_at"]
                or form.get("due_date") != window[reader]["due_date"]):
            raise ContractError("submission differs from its original delivery/window record")
        delivered = timestamp(submission["delivered_at"])
        exposed = timestamp(submission["first_exposed_at"])
        received = timestamp(submission["received_at"])
        try:
            form_delivery = dt.date.fromisoformat(form["delivered_on"])
            due = dt.date.fromisoformat(form["due_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("original form must bind its agreed delivery/due dates") from exc
        if (delivered.date() != form_delivery or not delivered <= exposed <= received <= cut
                or not 0 <= (due - form_delivery).days <= 7):
            raise ContractError("delivery, first exposure, receipt, cutoff or agreed window is inconsistent")
        is_new = index >= len(prior)
        if is_new and previous_cut is not None and received <= previous_cut:
            raise ContractError("a supplement must not introduce evidence already received by its predecessor cutoff")
        if received.date() > due:
            late.append(reader)
            deadline = dt.datetime.combine(due, dt.time(23, 59, 59), dt.UTC)
            if is_new and (previous_cut is None or previous_cut < deadline):
                raise ContractError("late forms require a versioned supplement after closing the agreed window")
    checked = validate_human_evidence(
        study, [row["form"] for row in all_submissions], portfolios, fixture=fixture,
    ) if all_submissions else checked_empty
    missing_context = any(row.get("missing_context") is True for row in checked["records"])
    inconclusive = checked["selection_inconclusive"] or missing_context
    eligible = [] if inconclusive else [method for method in ("A", "B", "C") if all(
        row["status"] == "acceptable" for row in checked["records"] if row["method"] == method
    )]
    body = {
        "schema_version": 1, "kind": _KIND, "fixture": fixture, "version": version,
        "study_sha256": study["study_sha256"], "cutoff": cutoff,
        "policy": copy.deepcopy(_POLICY), "policy_sha256": digest(_POLICY),
        "implementation": implementation_identity(),
        "portfolio_sha256s": sorted(digest(portfolio) for portfolio in portfolios),
        "previous_assessment_sha256": previous["assessment_sha256"] if previous else None,
        "previous": copy.deepcopy(previous), "added_submissions": copy.deepcopy(submissions),
        "window": copy.deepcopy(window), "window_closed_by_reader": closed,
        "submissions": all_submissions, "late_reader_ids": sorted(late),
        "complete": checked["complete"] and not missing_context,
        "selection_inconclusive": inconclusive, "compromised": checked["compromised"],
        "cannot_judge": checked["cannot_judge"], "missing_context": missing_context,
        "records": checked["records"], "eligible_methods": eligible,
        "missing_judgments": checked["missing_judgments"],
        "missing_readers": sorted(set(readers) - reader_ids),
        "collection_started_by_this_operation": False,
        "limitations": [
            "Receipt/exposure metadata and eligibility are recorded attestations, not independent proof.",
            "Missing readers are absent evidence, never acceptance; an absent window means collection is unactivated.",
            "No native scores or prior decisions are edited; this small diagnostic is not broad human validation.",
        ],
    }
    return body | {"assessment_sha256": digest(body)}


def validate_human_assessment(study: dict, portfolios: list[dict], assessment: dict,
                              *, fixture: bool = False) -> dict:
    """Rebuild the entire append-only chain and reject changed evidence or policy."""
    return _validate(study, portfolios, assessment, fixture=fixture, depth=0)


def _validate(study: dict, portfolios: list[dict], assessment: dict, *, fixture: bool,
              depth: int) -> dict:
    if depth > 32 or not isinstance(assessment, dict) or assessment.get("kind") != _KIND:
        raise ContractError("invalid or excessive human assessment chain")
    if assessment.get("assessment_sha256") != digest({
        key: value for key, value in assessment.items() if key != "assessment_sha256"
    }):
        raise ContractError("human assessment content identity changed")
    try:
        expected = _make(study, portfolios, assessment["added_submissions"], cutoff=assessment["cutoff"],
                         previous=assessment["previous"], window=assessment["window"],
                         fixture=fixture, depth=depth)
    except KeyError as exc:
        raise ContractError("human assessment is missing a required field") from exc
    if assessment != expected:
        raise ContractError("human assessment differs from original forms, chronology or frozen policy")
    return assessment


def prepare_reader_packets(study: dict, portfolios: list[dict], *, fixture: bool = False) -> dict:
    """Prepare local blinded packets only; collection still needs explicit activation."""
    return build_human_packets(study, portfolios, fixture=fixture)
