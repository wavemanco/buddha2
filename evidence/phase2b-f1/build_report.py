"""Publish a first-block descriptive appendix and verified, credential-free archive.

Use only in the pinned network-none image. Saved native evidence is replayed by
the frozen public loader; no generation, SDK construction or key lookup occurs.
This separate reporting tool does not alter the frozen execution kit or decision.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import anthropic
import openai

from buddha2.artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    write_bytes_once,
    write_once,
)
from buddha2.phase2_am1_controls import runtime_guard
from buddha2.phase2_release import load_execution
from buddha2.phase2_release_journal import _events
from buddha2.phase2_release_runner import _reader_lock

PUBLIC_FILES = ("summary.json", "coverage.json", "analysis.json", "decision.json", "execution.json",
                "native_assessment.json", "PHASE2_REPORT.md")
CHECKED_CONTROLS = ("temperature", "top_p", "top_k", "seed", "max_tokens", "max_completion_tokens",
                    "reasoning_effort", "service_tier", "inference_geo", "thinking", "output_config")


def require(condition, message):
    if not condition:
        raise ContractError(message)


def bounded(path: Path, *, exists=True) -> Path:
    require(path.is_absolute() and ".." not in path.parts and path.is_relative_to(Path("/results")),
            "report paths must remain canonically under /results")
    require(not any(item.is_symlink() for item in (path, *path.parents)), "report paths cannot traverse links")
    require(path.resolve(strict=exists).is_relative_to(Path("/results")), "resolved report path escapes /results")
    if exists:
        require(path.exists(), "required report input is missing: " + str(path))
    return path


def fence(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    runs = [len(match.group()) for match in re.finditer(r"`+", text)]
    marker = "`" * max(3, max(runs, default=0) + 1)
    return marker + "\n" + text + "\n" + marker + "\n"


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ") if value is not None else "—"


def money(amount):
    return f"${amount / 1_000_000:.6f}"


def credential_free(value):
    if isinstance(value, dict):
        require(not set(value).intersection({"api_key", "anthropic_api_key", "openai_api_key",
                                            "authorization", "Authorization"}),
                "credential field is outside the reporting whitelist")
        for item in value.values():
            credential_free(item)
    elif isinstance(value, list):
        for item in value:
            credential_free(item)


def collect(study, saved, run):
    state = saved["state"]
    definitions = [row for row in study["worklist"]["outputs"] if row["checkpoint"] == "canary"]
    require(len(definitions) == 3 and {row["method"] for row in definitions} == {"A", "B", "C"},
            "first-block definition differs")
    prefixes = {row["method"]: row["order_id"] for row in definitions}
    canary = {slot for slot, row in study["worklist"]["slots"].items() if row["checkpoint"] == "canary"}
    require(set(state["results"]).issubset(canary) and state["attempts"] <= 55,
            "this report accepts first-block evidence only; expansion has already begun")
    require(all(row["task"]["id"] == definitions[0]["task_id"] and row["provenance"]["repeat"] == 1
                for row in saved["portfolios"]), "foreign task/repeat in first-block evidence")
    events, tail = _events(run / "journal")
    intents = {row["record"]["slot_id"]: (index, row["record"]) for index, row in enumerate(
        [event for event in events if event["kind"] == "intent"], 1)}
    slots = [f"{prefixes['A']}.answer.{i:02d}" for i in range(10)] + [prefixes["B"] + ".plan"]
    slots += [f"{prefixes['B']}.answer.{i:02d}" for i in range(10)] + [prefixes["C"] + ".rank"]
    for method in ("A", "B", "C"):
        slots += [prefixes[method] + ".group"] + [f"{prefixes[method]}.quality.{i:02d}" for i in range(10)]
    require(set(slots) == canary and len(slots) == 55, "logical first-block slot inventory differs")
    outcomes, settings = [], {}
    for position, slot in enumerate(slots, 1):
        attempt, intent = intents.get(slot, (None, None))
        result = state["results"].get(slot)
        response = result.get("response") if result else None
        request = intent["request"] if intent else None
        role = study["worklist"]["slots"][slot]["role"]
        controls = {key: value for key, value in request.items() if key not in {"messages", "system"}} if request else None
        outcomes.append({"planned_position": position, "slot_id": slot, "role": role,
                         "attempt": attempt, "coverage": saved["coverage"]["slots"][slot],
                         "intent": intent, "result": result, "requested_settings": controls,
                         "omitted_controls": [key for key in CHECKED_CONTROLS if key not in request] if request else None,
                         "returned_model": response.get("model") if response else None})
        if request:
            key = digest({"role": role, "settings": controls})
            group = settings.setdefault(key, {"role": role, "requested_settings": controls,
                "omitted_controls": [name for name in CHECKED_CONTROLS if name not in request],
                "attempts": 0, "returned_models": []})
            group["attempts"] += 1
            if response and response.get("model") not in group["returned_models"]:
                group["returned_models"].append(response.get("model"))
    indexed = {row["provenance"]["method"]: row for row in saved["portfolios"]}
    assessments = {row["method"]: row for row in saved["assessments"]}
    b_positions = {row["id"]: index for index, row in enumerate(indexed.get("B", {}).get("responses", []), 1)}
    orders = []
    for definition in definitions:
        method = definition["method"]
        portfolio, assessment = indexed.get(method), assessments.get(method)
        native = assessment.get("native", {}) if assessment else {}
        partition = (native.get("partition_fields") or {}).get("partition")
        scores = native.get("fields", {}).get("generation_scores", [])
        responses = portfolio["responses"] if portfolio else []
        rows = []
        for index in range(10):
            response = responses[index] if index < len(responses) else None
            group = partition[index] if partition else None
            head = group not in partition[:index] if partition else None
            quality_slot = f"{definition['order_id']}.quality.{index:02d}"
            rows.append({"position": index + 1, "response": response,
                         "original_B_position": b_positions.get(response["id"]) if response and method == "C" else None,
                         "group": group, "is_head": head,
                         "quality": scores[index] if index < len(scores) else None,
                         "quality_slot": quality_slot, "quality_coverage": saved["coverage"]["slots"][quality_slot]})
        request_ids = set(portfolio["provenance"]["request_ids"]) if portfolio else set()
        candidate_cost = sum(state["results"][slot]["spent_micro_usd"] or 0 for slot in request_ids) if portfolio else None
        orders.append({"definition": definition, "portfolio": portfolio, "assessment": assessment,
                       "status": saved["coverage"]["orders"][definition["order_id"]], "responses": rows,
                       "candidate_generation_ranking_cost_micro_usd": candidate_cost})
    by_role = Counter()
    for result in state["results"].values():
        by_role[result["role"]] += result["spent_micro_usd"] or 0
    return {"orders": orders, "outcomes": outcomes, "settings": list(settings.values()),
            "first_slot_coverage": dict(Counter(row["coverage"] for row in outcomes)),
            "actual_request_counts": dict(Counter(row["role"] for row in state["results"].values())),
            "unique_cost_micro_usd_by_role": dict(by_role), "truncated_event_tail_bytes": len(tail)}


def markdown(data):
    state, summary = data["state"], data["summary"]
    complete = summary["first_block_ready_for_review"]
    parts = ["# Phase 2B first-block report\n\n",
             "**SYNTHETIC OFFLINE FIXTURE — no live model or provider outcome.**\n\n" if state["fixture"] else "Counted live first-block evidence.\n\n",
             f"**{'First block complete' if complete else 'First block incomplete'}; HOLD expansion.** "
             "A successful technical review and a separately applicable cumulative grant remain required. "
             "This report creates no spending authority.\n\n",
             f"Study `{data['study_sha256']}`. Task `{data['task']['id']}`, repeat 1.\n\n",
             fence(data["task"]["prompt"]), "\nSource:\n" + fence(data["task"]["source_context"]),
             f"\nRequests attempted: **{state['attempts']}/55**; native orders present: **{summary['orders']}/3** "
             f"(**{summary['missing_assessments']} missing in the full 72-order study**). "
             f"Usage-based public-price upper bound: **{money(state['spent_micro_usd'])}**; "
             f"unresolved reservation: **{money(state['reserved_micro_usd'])}**. "
             "These amounts are not provider invoice certification.\n\n",
             "One prompt and one repeat do not establish a strategy winner. The unchanged whole-study "
             "benchmark decision is inconclusive, with null aggregate contrasts and no selected seed. "
             "No human, CrPO or recursive-adaptation result is inferred.\n\n",
             "## Procedure and context\n\nIn the user's regenerate/in-context terms: **A independently regenerates "
             "each answer in a fresh context** containing the original prompt and fixed answer instruction. "
             "**B regenerates each answer in a fresh context conditioned on one planning angle**: it makes "
             "one ten-angle plan, then ten fresh answer requests, each receiving the original prompt plus its "
             "assigned angle. That angle is in-context guidance; the answer itself is newly generated. "
             "A/B answer calls do not see sibling answers. **C performs an in-context permutation, not answer "
             "resampling**: it sees the original prompt and ten saved B answers and returns only their order. "
             "For example, C may move saved B07 to position 1 without rewriting B07; an A or B regeneration "
             "creates a new answer text through a separate request. Thirty complete ordered "
             "presentations would therefore contain twenty generated texts. Each native grouping sees one "
             "whole portfolio; each quality head is judged alone against the original prompt.\n\n",
             "Patience is 0.8. Later duplicates receive no quality call and contribute zero credited utility; "
             "their missing quality is not a fabricated zero score. Native saved metrics below are replayed "
             "unchanged. No fallback, repair, retry or replacement is performed.\n\n",
             "## Actual request settings and returned models\n\nOmitted parameters remain omitted; provider "
             "defaults are not reconstructed as observations. Exact contexts and canonical response records "
             "are included in first-block-data.json and the whitelisted raw archive.\n\n"]
    for group in data["settings"]:
        parts += [f"### {group['role']} — {group['attempts']} attempted requests\n\n", fence(group)]
    if not data["settings"]:
        parts.append("No model request was attempted.\n\n")
    parts += ["## Accounting\n\n", fence({"request_counts": data["actual_request_counts"],
        "unique_role_cost_micro_usd": data["unique_cost_micro_usd_by_role"],
        "first_slot_coverage": data["first_slot_coverage"], "journal_status": state["status"],
        "active_cumulative_cap_micro_usd": state.get("authorized_cap_micro_usd"),
        "reserved_micro_usd": state["reserved_micro_usd"]}),
        "\nCandidate C's attributed generation cost includes its B parent plus ranking; the unique phase "
        "ledger charges those requests once. Missing portfolios keep candidate costs missing.\n\n",
        "## Planner and reranker visible outputs\n\n"]
    for role in ("plan", "rank"):
        outcome = next(row for row in data["outcomes"] if row["role"] == role)
        response = (outcome["result"] or {}).get("response")
        parts += [f"### {role}: {outcome['coverage']}\n\n", fence(response["text"] if response else "No visible output saved.")]
    for order in data["orders"]:
        method, assessment = order["definition"]["method"], order["assessment"]
        parts += [f"\n## Order {method} — {order['status']}\n\n", fence({
            "metrics": assessment.get("metrics") if assessment else None,
            "failure": assessment.get("failure") if assessment else "missing assessment",
            "candidate_generation_ranking_cost_micro_usd": order["candidate_generation_ranking_cost_micro_usd"]}),
            "\n| Position | Response ID | Original B position | Status | Group | Head | Quality | Quality coverage |\n"
            "|---:|---|---:|---|---:|---|---:|---|\n"]
        for row in order["responses"]:
            response = row["response"] or {}
            parts.append("| " + " | ".join(cell(value) for value in (
                row["position"], response.get("id"), row["original_B_position"], response.get("status", "missing"),
                row["group"], row["is_head"], row["quality"], row["quality_coverage"])) + " |\n")
        parts.append("\nAll visible answer texts, in this order; C repeats its unchanged B texts.\n\n")
        for row in order["responses"]:
            response = row["response"]
            parts += [f"### {method}{row['position']:02d}" + (f" — {response['id']}" if response else " — missing") + "\n\n",
                      fence(response["text"] if response else "No answer saved for this position.")]
    parts += ["\n## All 55 planned request outcomes\n\n"
              "| Planned | Attempt | Role | Coverage | Returned model | Settled µUSD | Reserved µUSD | Slot |\n"
              "|---:|---:|---|---|---|---:|---:|---|\n"]
    for row in data["outcomes"]:
        result = row["result"] or {}
        parts.append("| " + " | ".join(cell(value) for value in (
            row["planned_position"], row["attempt"], row["role"], row["coverage"], row["returned_model"],
            result.get("spent_micro_usd"), result.get("reserved_micro_usd"), row["slot_id"])) + " |\n")
    parts += ["\n## Failures, liabilities and decision limits\n\n", fence(data["failures"]),
              "\nCanonical records contain saved visible text, model IDs, stop reasons and usage; they are "
              "not complete SDK/API objects. Anthropic thinking blocks were not retained. Native quality "
              "outputs contain scores, not saved explanatory rationales. Missing or refused outcomes remain "
              "missing/refused. No automatic expansion or favorable-score requirement follows this report.\n\n"]
    if data.get("operator_review") is not None:
        parts += ["Operator-supplied review, separately attributed; not a journal grant:\n\n", fence(data["operator_review"])]
    if data.get("terminal_status") is not None:
        parts += ["Operator-supplied terminal status:\n\n", fence(data["terminal_status"])]
    return "".join(parts)


def build(args):
    runtime_guard()
    require({path.name for path in Path("/sys/class/net").iterdir()} == {"lo"}, "reporting requires network none")
    for path in (args.study, args.run, args.public_report):
        bounded(path)
    bounded(args.output, exists=False)
    require(not args.output.exists() and all(not args.output.is_relative_to(path) for path in (
        args.run, args.public_report, args.study.parent)), "output must be a new separate directory")
    public = {name: (args.public_report / name).read_bytes() for name in PUBLIC_FILES}
    summary = json.loads(public["summary.json"])
    guards = []
    with ExitStack() as stack:
        stack.enter_context(_reader_lock(args.run))
        for target in ("socket.socket", "socket.socketpair", "socket.create_connection",
                       "buddha2.phase2_dispatch.DirectSDKTransport", "buddha2.phase2_release_runner.ReleaseDispatcher"):
            guards.append(stack.enter_context(patch(target, side_effect=AssertionError("reporting attempted execution"))))
        for module, names in ((anthropic, ("Anthropic", "AsyncAnthropic", "AnthropicBedrock", "AsyncAnthropicBedrock")),
                              (openai, ("OpenAI", "AsyncOpenAI", "AzureOpenAI", "AsyncAzureOpenAI"))):
            for name in names:
                guards.append(stack.enter_context(patch.object(module, name, side_effect=AssertionError("reporting constructed SDK"))))
        study, saved = load_execution(args.study, args.run, cutoff=summary["cutoff"])
        require(args.allow_fixture or saved["state"]["fixture"] is False, "fixture requires explicit --allow-fixture")
        require(saved["summary"] == summary and saved["coverage"] == json.loads(public["coverage.json"]),
                "public report does not match current saved evidence")
        for name, value in saved["bundle"].items():
            require(value == json.loads(public[name + ".json"]), "public report failed exact native/analysis/decision replay")
        require(saved["bundle"]["decision"]["status"] == "inconclusive"
                and saved["bundle"]["decision"]["selected_method"] is None
                and saved["bundle"]["decision"]["synthetic_selected_method"] is None
                and all(value is None for value in saved["bundle"]["analysis"]["contrasts"].values()),
                "first-block report must preserve the inconclusive whole-study decision")
        extracted = collect(study, saved, args.run)
        data = {"kind": "phase2b-first-block-descriptive-report-v1", "study_sha256": study["study_sha256"],
                "task": study["tasks"][0], "repeat": 1, "fixture": saved["state"]["fixture"],
                "summary": summary, "state": saved["state"], "failures": saved["failures"],
                "whole_study_bundle": saved["bundle"], **extracted,
                "sampling_procedure": {
                    "A": {"operation": "independent regenerate", "context": "fresh original prompt and fixed answer instruction per answer",
                          "sees_sibling_answers": False, "creates_new_answer_text": True},
                    "B": {"operation": "regenerate conditioned on one angle", "context": "fresh original prompt, fixed answer instruction and assigned planning angle per answer",
                          "sees_sibling_answers": False, "creates_new_answer_text": True},
                    "C": {"operation": "in-context permutation", "context": "original prompt and ten saved B answers",
                          "sees_sibling_answers": True, "creates_new_answer_text": False,
                          "example": "move saved B07 to position1 without changing B07's text"},
                },
                "reporting_provider_calls": 0, "reporting_sdk_constructions": 0,
                "hold_expansion": True, "operator_review": None, "terminal_status": None}
        raw = {"raw/study.json": args.study.read_bytes(), **{"public-report/" + name: value for name, value in public.items()}}
        selected = [args.run / "journal" / name for name in ("manifest.json", "study.json", "events.jsonl")]
        selected += sorted((args.run / "journal/authority").glob("*.grant.json"))
        selected += sorted((args.run / "journal/reviews").glob("*.json"))
        selected += sorted((args.run / "failures").glob("*.json"))
        for order in extracted["orders"]:
            definition = order["definition"]
            selected += [args.run / definition[key] for key in ("portfolio_path", "assessment_path")]
            selected += [args.run / "native" / definition["order_id"] / name for name in ("generations.jsonl", "identities.json")]
        snapshot = args.run / "snapshots" / summary["snapshot_sha256"]
        if snapshot.exists():
            selected += [snapshot / (name + ".json") for name in (
                "coverage", "state", "failures", "recoverable_exports", "summary", "execution",
                "native_assessment", "analysis", "decision", "complete")]
        originals = {}
        for path in selected:
            if path.exists():
                bounded(path)
                value = path.read_bytes()
                raw["raw/run/" + path.relative_to(args.run).as_posix()] = value
                originals[path] = value
        for option in ("operator_review", "terminal_status"):
            path = getattr(args, option)
            if path is not None:
                bounded(path)
                data[option] = read_json(path)
                raw["operator/" + option + ".json"] = path.read_bytes()
        credential_free(data)
        for name, value in raw.items():
            require(re.search(rb"(?<![A-Za-z0-9_])sk-(?:ant-)?[A-Za-z0-9_-]{20,}", value) is None,
                    "recognizable credential pattern outside archive whitelist")
            if name.endswith(".json"):
                credential_free(json.loads(value))
        require(all(not guard.called for guard in guards), "reporting touched SDK/socket/dispatcher")
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in raw.items():
            write_bytes_once(args.output / name, value)
        write_once(args.output / "first-block-data.json", data)
        write_bytes_once(args.output / "PHASE2B_F1_REPORT.md", markdown(data).encode("utf-8"))
        files = {path.relative_to(args.output).as_posix(): file_hash(path) for path in args.output.rglob("*") if path.is_file()}
        manifest = {"kind": "phase2b-first-block-report-manifest-v1", "study_sha256": study["study_sha256"],
                    "fixture": data["fixture"], "files": files, "reporting_tool_sha256": file_hash(Path(__file__)),
                    "raw_scope": "whitelisted saved visible canonical evidence; excludes credential material and host environment",
                    "limitation": "First-block evidence; no whole-pilot seed, model effectiveness or complete raw API/thinking claim.",
                    "new_provider_calls": 0, "new_sdk_constructions": 0}
        write_once(args.output / "manifest.json", manifest)
        members = {name: (args.output / name).read_bytes() for name in (*files, "manifest.json")}
        target = args.output / "phase2b-f1-report.zip"
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, value in sorted(members.items()):
                archive.writestr(name, value)
        with zipfile.ZipFile(target) as archive:
            require(archive.testzip() is None and len(archive.namelist()) == len(members)
                    and set(archive.namelist()) == set(members)
                    and all(archive.read(name) == value for name, value in members.items()), "report archive verification failed")
        require(all(path.read_bytes() == value for path, value in originals.items())
                and all((args.public_report / name).read_bytes() == value for name, value in public.items()),
                "existing evidence changed during reporting")
        result = {"kind": "phase2b-first-block-report-package-check", "status": "pass", "fixture": data["fixture"],
                  "members": len(members), "archive_sha256": file_hash(target), "manifest_sha256": file_hash(args.output / "manifest.json"),
                  "native_analysis_decision_replay_exact": True, "source_evidence_unchanged": True,
                  "new_provider_calls": 0, "new_sdk_constructions": 0, "new_credential_reads": 0,
                  "bounded_secret_check": "structured credential fields and recognizable token prefixes only; unknown strings are not certified",
                  "first_block_complete": summary["first_block_ready_for_review"], "hold_expansion": True,
                  "output": str(args.output)}
        write_once(args.output / "package-check.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "run", "public-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("operator-review", "terminal-status"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args), sort_keys=True))


if __name__ == "__main__":
    main()
