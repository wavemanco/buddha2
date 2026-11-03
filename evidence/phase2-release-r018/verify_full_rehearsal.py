"""Independent offline acceptance checks over a completed ten-head P2-R rehearsal.

Run inside the pinned network-none image. Only --output and a temporary report
directory are written; all supplied evidence trees must remain byte-identical.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import anthropic
import openai

from buddha2.artifacts import digest, tree_hashes, write_once
from buddha2.phase2_am1_controls import runtime_guard
from buddha2.phase2_release import load_execution, report

EXPECTED_ROLES = {"answer": 480, "plan": 24, "rank": 24, "group": 72, "quality": 720}
PREFIX_FIELDS = (
    "run_id", "fixture", "status", "attempts", "spent_micro_usd", "reserved_micro_usd",
    "canary_spent_micro_usd", "canary_reserved_micro_usd", "provider_calls", "retries", "results",
)


def load(path: Path):
    # Full saved states exceed the ordinary per-artifact 2 MB JSON ceiling.
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def settlement(result: dict) -> int:
    """Independent integer/Fraction public-price arithmetic, not account()."""
    usage = result["response"]["usage"]
    base, output, write, read = (usage.get(key, 0) for key in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    require(all(type(value) is int and value >= 0 for value in (base, output, write, read)),
            "invalid saved token category")
    if result["role"] == "group":
        incoming, outgoing = base * 200 + write * 250 + read * 20, output * 1200
        if base + write + read > 272000:
            incoming *= 2
            outgoing = outgoing * 3 // 2
        amount = Fraction(incoming + outgoing) * Fraction(11, 10) * {
            "default": Fraction(1), "flex": Fraction(1, 2), "priority": Fraction(2),
        }[usage["service_tier"]]
    else:
        cache = usage.get("cache_creation") or {}
        five, hour = cache.get("ephemeral_5m_input_tokens", 0), cache.get("ephemeral_1h_input_tokens", 0)
        require(five + hour == write, "cache creation categories do not reconcile")
        amount = Fraction(base * 5500 + five * 6875 + hour * 11000 + read * 550 + output * 27500
                          if result["role"] == "quality"
                          else base * 2000 + five * 2500 + read * 100 + output * 10000)
    return (amount.numerator + amount.denominator * 1000 - 1) // (amount.denominator * 1000)


def verify(args) -> dict:
    runtime_guard()
    require({path.name for path in Path("/sys/class/net").iterdir()} == {"lo"}, "external network interface present")
    paths = (args.run, args.first_report, args.full_report, args.replay_report)
    for path in (args.study, *paths, args.output):
        require(path.is_absolute() and path.is_relative_to(Path("/results")), "paths must remain under /results")
    require(not args.output.exists() and all(not args.output.is_relative_to(path) for path in paths),
            "verification output must be new and outside supplied evidence trees")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    before = {str(path): tree_hashes(path) for path in paths}
    full_summary = load(args.full_report / "summary.json")
    guards = []
    with ExitStack() as stack:
        for target in ("socket.socket", "socket.create_connection", "socket.socketpair",
                       "buddha2.phase2_dispatch.DirectSDKTransport",
                       "buddha2.phase2_release_runner.ReleaseDispatcher"):
            guards.append(stack.enter_context(patch(target, side_effect=AssertionError("offline replay boundary"))))
        for module, names in ((anthropic, ("Anthropic", "AsyncAnthropic", "AnthropicBedrock", "AsyncAnthropicBedrock")),
                              (openai, ("OpenAI", "AsyncOpenAI", "AzureOpenAI", "AsyncAzureOpenAI"))):
            for name in names:
                guards.append(stack.enter_context(patch.object(module, name,
                    side_effect=AssertionError("SDK construction forbidden during replay"))))
        study, saved = load_execution(args.study, args.run, cutoff=full_summary["cutoff"])
        with tempfile.TemporaryDirectory(prefix="p2r-verify-replay-", dir=args.output.parent) as temporary:
            generated = Path(temporary)
            result = report(args.study, args.run, generated, cutoff=full_summary["cutoff"])
            require(result["provider_calls"] == result["new_generation_requests"] == 0, "report dispatched work")
            require(tree_hashes(generated) == tree_hashes(args.full_report) == tree_hashes(args.replay_report),
                    "public report replay differs from saved full/replay reports")
        require(all(not guard.called for guard in guards), "replay attempted SDK, socket or dispatcher construction")
    state, coverage, bundle = saved["state"], saved["coverage"], saved["bundle"]
    require(state["fixture"] is True and state["status"] == "ready", "requires complete synthetic fixture")
    require(saved["summary"] == full_summary and saved["summary"]["status"] == "mock-pilot-complete",
            "full summary differs from public saved-evidence replay")
    require(not saved["failures"] and not saved["recoverable_exports"], "full rehearsal has failed/pending artifacts")
    results = list(state["results"].values())
    counts = dict(Counter(row["role"] for row in results))
    require(counts == EXPECTED_ROLES and len(results) == state["attempts"] == 1320, "actual role/attempt matrix differs")
    require(len({row["slot_id"] for row in results}) == 1320, "repeated request slot")
    require(all(row["status"] == "response" and row["reserved_micro_usd"] == 0 for row in results),
            "unsettled result in complete rehearsal")
    independently_priced = {row["slot_id"]: settlement(row) for row in results}
    require(all(row["spent_micro_usd"] == independently_priced[row["slot_id"]] for row in results),
            "per-request settlement differs from independent pricing")
    spent = sum(independently_priced.values())
    require(spent == state["spent_micro_usd"] and state["reserved_micro_usd"] == 0,
            "phase-wide money does not sum once")
    require(state["authorized_cap_micro_usd"] == 125_000_000 and spent <= 125_000_000,
            "cumulative authority or spend differs")
    require(state["provider_calls"] == state["retries"] == 0, "fixture claims paid requests/retries")
    require(coverage["scheduled_request_slots"] == coverage["recorded_request_results"] == 1320
            and coverage["slot_status_counts"] == {"ok": 1320}
            and coverage["order_status_counts"] == {"scored": 72}, "full denominator coverage differs")
    require(len(saved["portfolios"]) == len(saved["assessments"]) == 72, "missing native artifacts")
    blocks = Counter((row["task"]["id"], row["provenance"]["repeat"]) for row in saved["portfolios"])
    require(len(blocks) == 24 and set(blocks.values()) == {3}, "24 paired A/B/C blocks not preserved")
    require(Counter(row["provenance"]["method"] for row in saved["portfolios"]) == {"A": 24, "B": 24, "C": 24},
            "procedure portfolio counts differ")
    require(len(list((args.run / "portfolios").glob("*.json"))) == 72
            and len(list((args.run / "assessments").glob("*.json"))) == 72, "disk native counts differ")
    journal = args.run / "journal"
    require(list(args.run.rglob("manifest.json")) == [journal / "manifest.json"], "multiple ledgers under run")
    manifest = load(journal / "manifest.json")
    require(len(manifest["inputs"]["slots"]) == 1320, "first authority did not freeze whole worklist")
    events = [json.loads(line) for line in (journal / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(events) == 2640, "journal does not contain exactly one intent/result pair per attempt")
    intents, event_results = [row["record"] for row in events[::2]], [row["record"] for row in events[1::2]]
    require(event_results == results and len({row["dispatch_id"] for row in intents}) == 1320,
            "journal order or unique dispatch accounting differs")
    first_summary = load(args.first_report / "summary.json")
    first_state = load(Path(first_summary["snapshot"]) / "state.json")
    # Saved JSON sorts object keys; reconstruct chronology from the actual
    # event stream instead of treating serialization order as dispatch order.
    first_slots = [row["slot_id"] for row in results[:55]]
    require(set(first_state["results"]) == set(first_slots), "first snapshot has missing/foreign request slots")
    first_results = [first_state["results"][slot] for slot in first_slots]
    require(first_summary["attempts"] == len(first_results) == 55 and first_summary["orders"] == 3
            and first_summary["missing_assessments"] == 69 and first_results == results[:55],
            "first55 evidence changed during expansion")
    require(first_state["spent_micro_usd"] == sum(settlement(row) for row in first_results)
            and load(args.first_report / "native_assessment.json")["journal_state_sha256"] == digest(first_state),
            "first report lost its exact native/accounting prefix")
    require({study["worklist"]["slots"][row["slot_id"]]["checkpoint"] for row in first_results} == {"canary"}
            and {study["worklist"]["slots"][row["slot_id"]]["checkpoint"] for row in results[55:]} == {"expansion"},
            "stage worklists overlap or first block regenerated")
    grants = [load(path) for path in sorted((journal / "authority").glob("*.grant.json"))]
    require(len(grants) == 2 and [row["attempts_at_grant"] for row in grants] == [0, 55]
            and [row["grant"]["stage"] for row in grants] == ["first", "expansion"]
            and [row["grant"]["cumulative_cap_micro_usd"] for row in grants] == [20_000_000, 125_000_000],
            "staged cumulative authority differs")
    prefix = digest({key: first_state[key] for key in PREFIX_FIELDS})
    review = load(journal / "reviews/first.json")
    require(grants[1]["prefix_sha256"] == review["prefix_sha256"] == prefix
            and review["prefix_attempts"] == 55
            and grants[1]["grant"]["previous_authority_sha256"] == grants[0]["authority_sha256"]
            and grants[1]["grant"]["review_sha256"] == review["review_sha256"], "expansion lost first accounting/review")
    require(all(row["authority_sha256"] == grants[0 if index < 55 else 1]["authority_sha256"]
                for index, row in enumerate(intents)), "request authority differs from staged grant")
    for name, value in bundle.items():
        require(load(args.full_report / f"{name}.json") == value, f"saved {name} does not replay")
    first_decision = load(args.first_report / "decision.json")
    decision, analysis = bundle["decision"], bundle["analysis"]
    require(first_decision["status"] == "inconclusive" and first_decision["selected_method"] is None
            and first_decision["synthetic_selected_method"] is None, "partial first block selected a seed")
    require(decision["native_complete"] and decision["selected_method"] is None
            and decision["synthetic_selected_method"] in ("A", "B", "C"), "full fixture decision not synthetic")
    require(decision["policy"]["human_required"] is False and decision["human_assessment_sha256"] is None,
            "benchmark decision depends on human evidence")
    require(analysis["accounted_total_micro_usd"] == spent
            and sum(analysis["unique_request_cost_micro_usd_by_role"].values()) == spent,
            "analysis double-counts request costs")
    costs = analysis["generation_ranking_cost_micro_usd_by_candidate"]
    require(costs["C"] == costs["B"] + sum(row["spent_micro_usd"] for row in results if row["role"] == "rank"),
            "C attribution does not include its unchanged B generation once")
    require(set(analysis["contrasts"]) == {"B_minus_A", "C_minus_B"}
            and all(value is not None for value in analysis["contrasts"].values()), "primary contrasts missing")
    require(all(tree_hashes(path) == before[str(path)] for path in paths), "verification changed existing evidence")
    return {"kind": "p2r-full-rehearsal-independent-verification", "status": "PASS",
            "study_sha256": study["study_sha256"], "actual_role_counts": counts,
            "attempts": 1320, "blocks": 24, "portfolios": 72, "native_assessments": 72,
            "first_prefix_attempts": 55, "first_prefix_preserved": True, "one_cumulative_journal": True,
            "independent_settlement_micro_usd": spent, "cumulative_cap_micro_usd": 125_000_000,
            "reserved_micro_usd": 0, "all_slots_ok": True, "native_analysis_decision_replay_exact": True,
            "public_report_replay_byte_identical": True, "existing_evidence_unchanged": True,
            "sdk_constructions": 0, "socket_attempts": 0, "provider_calls": 0, "api_spend_micro_usd": 0,
            "human_required": False, "real_seed_selected": False,
            "report_hashes": tree_hashes(args.full_report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "run", "first-report", "full-report", "replay-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args)
    write_once(args.output, result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
