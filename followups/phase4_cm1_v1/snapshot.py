"""Read-only P4 native snapshot writer; never opens the benchmark corpus."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, file_hash, write_once
from buddha2.phase2_contracts import validate_portfolio

from .inspect_export import OPTIONAL_TOKENS, TOKEN_FIELDS, _utc, validate_snapshot

PARAMETERS = ("model", "max_tokens", "thinking", "output_config", "reasoning_effort",
              "service_tier", "inference_geo", "temperature", "top_p", "seed", "response_format")


def _require(value, message):
    if not value:
        raise ContractError(message)


def _read(path: Path, observed: dict) -> dict:
    from .workflow import _report_read

    return _report_read(path, observed)


def _sealed(value: dict) -> dict:
    _require(isinstance(value, dict) and value.get("sha256")
             == digest({k: v for k, v in value.items() if k != "sha256"}), "saved artifact seal differs")
    return value


def _remember(path: Path, observed: dict) -> None:
    from .release import path as scoped

    path = scoped(path)
    observed[path] = file_hash(path) if path.exists() else None


def _ledger(opened: dict, fixture: bool, observed: dict):
    from followups.phase3b_seq2_v1 import accounting, transport

    child = opened["child_sha256"]
    journal = accounting.canonical_journal(child, fixture)
    for name in ("manifest.json", "events.jsonl", "deadline-stop.json", "transport-audit-failure.json"):
        _remember(journal / name, observed)
    state, manifest = accounting.replay(journal), accounting._manifest(journal)
    audits = {}
    for slot, intent in state["intents"].items():
        result = state["results"].get(slot)
        audit_path = transport.audit_path(child, fixture, slot)
        _remember(audit_path, observed)
        audits[slot] = (transport.read_audit(child, fixture, slot, intent=intent, result=result,
            bindings=accounting._bindings(manifest)) if result is not None and audit_path.exists() else None)
    return journal, state, manifest, audits


def project_requests(state: dict, audits: dict) -> tuple[list, dict, list]:
    """Actual source timestamps and uncached input usage; no raw request/response bodies."""
    events, usages, undated = [], {}, []
    for slot, intent in state["intents"].items():
        result = state["results"].get(slot)
        response = (result or {}).get("response") or {}
        known = result is not None and result.get("status") == "response"
        usage = response.get("usage") if known else None
        request = intent["request"]
        data = {"slot_id": slot, "role": intent["role"], "child_sha256": state["study_sha256"],
            "request_study_sha256": intent["study_sha256"],
            **{key: intent[key] for key in ("cell", "pair") if key in intent},
            "requested_model": request.get("model"), "returned_model": response.get("model"),
            "status": result.get("status") if result else "unsettled",
            "request_sha256": intent["request_sha256"], "result_sha256": digest(result) if result else None,
            "usage": copy.deepcopy(usage), "spent_micro_usd": (result or {}).get("spent_micro_usd"),
            "reserved_micro_usd": (result or {}).get("reserved_micro_usd", intent["reservation"]["micro_usd"]),
            "requested_parameters": {key: copy.deepcopy(request[key]) for key in PARAMETERS if key in request}}
        audit = audits.get(slot)
        if audit is not None:
            start, end = audit["budget"]["started_utc"], audit["finished_utc"]
            _require(_utc(start) <= _utc(end), "source API interval is reversed")
            data.update(started_at=start, completed_at=end, elapsed_seconds=audit["elapsed_seconds"],
                        interval_basis="observed admission through cleanup; not provider-server latency")
            events.append({"timestamp": start, "source": "IMPORTED native ledger/transport interval", "data": data})
        else:
            undated.append(data)
        if result is None or result.get("status") != "response":
            continue
        if not isinstance(usage, dict) or not all(type(usage.get(k)) is int and usage[k] >= 0
                                               for k in ("input_tokens", "output_tokens")):
            raise ContractError("known result lacks normalized usage")
        model = response.get("model")
        if not isinstance(model, str) or not model:
            raise ContractError("known result lacks its returned model")
        total = result["input_tokens"] + result["output_tokens"]
        details = usage.get("output_tokens_details") or {}
        row = {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
            "total_tokens": total, "input_tokens_cache_write": usage.get("cache_creation_input_tokens"),
            "input_tokens_cache_read": usage.get("cache_read_input_tokens"),
            "reasoning_tokens": details.get("thinking_tokens", details.get("reasoning_tokens")),
            "cost_micro_usd": result["spent_micro_usd"]}
        if model not in usages:
            usages[model] = row
        else:
            target = usages[model]
            for key in TOKEN_FIELDS + ("cost_micro_usd",):
                target[key] += row[key]
            for key in OPTIONAL_TOKENS:
                target[key] = target[key] + row[key] if target[key] is not None and row[key] is not None else None
    for row in usages.values():
        row["total_cost"] = row.pop("cost_micro_usd") / 1_000_000
    return events, usages, undated


def _targets(value: dict, outputs: dict | None, task: dict, fixture: bool) -> dict:
    result: dict[str, dict[str, Any] | None] = {}
    for target, bundle in value["targets"].items():
        _require(target in {"fixed", "c1", "c2"}, "foreign assessment target")
        if bundle is None:
            result[target] = None
            continue
        _sealed(bundle)
        official = bundle["official"]
        _require(bundle.get("kind") == "phase4-cm1-target-assessment-v1"
            and bundle.get("fixture") is fixture and official.get("fixture") is fixture
            and official.get("task_id") == task["id"] and isinstance(outputs, dict) and outputs.get(target) is not None
            and bundle["portfolio_sha256"] == official["portfolio_sha256"] == digest(outputs[target]),
            "assessment does not belong to its saved portfolio")
        result[target] = {"sha256": bundle["sha256"], "portfolio_sha256": bundle["portfolio_sha256"],
            "official": {key: copy.deepcopy(official[key]) for key in ("status", "failure", "metrics") if key in official},
            "native_fields": copy.deepcopy(official.get("native", {}).get("fields")),
            "quality_scores": copy.deepcopy(bundle["quality_scores"]),
            "quality_failures": copy.deepcopy(bundle["quality_failures"]),
            "sensitivity": copy.deepcopy(bundle["sensitivity"]), "complete": bundle["complete"]}
    _require(set(result) == {"fixed", "c1", "c2"}, "assessment target inventory differs")
    return result


def build_snapshot(study: dict, run_path: Path, *, fixture: bool, status: str) -> dict:
    from . import release

    _require(study.get("kind") == release.KIND and study.get("study_sha256")
             == digest({k: v for k, v in study.items() if k != "study_sha256"})
             and study.get("source_sha256") == study.get("source", {}).get("sha256")
             and type(fixture) is bool, "saved parent identity/mode differs")
    _require(release.source_identity() == study["source"], "accepted source changed before projection")
    run_path = release.path(run_path)
    observed: dict[Path, str | None] = {}
    records: list[tuple[str, str, dict, dict, str, tuple[list, dict, list]]] = []
    closed_refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    generation_children: dict[str, str] = {}
    children = run_path / "children"
    folders = sorted(children.iterdir()) if children.exists() else []
    confirmation = any(re.fullmatch(r"\d{3}-(?:inference|assessment)-p4-\d{2}", p.name) for p in folders)
    for folder in folders:
        match = re.fullmatch(r"(\d{3})-(dev|inference|assessment)-([A-Za-z0-9-]+)", folder.name)
        if match is None or not folder.is_dir():
            raise ContractError("unknown child artifact directory")
        if not (folder / "closure.json").exists():
            continue  # Active work is never projected as a completed source record.
        ordinal, kind, pair = int(match[1]), match[2], match[3]
        _require(ordinal == len(records) + 1 and (kind, pair) not in seen,
                 "closed children are repeated or skip an ordinal")
        seen.add((kind, pair))
        opened = _sealed(_read(folder / "open.json", observed))
        closure = _sealed(_read(folder / "closure.json", observed))
        value = _read(folder / "result.json", observed)
        allocation, profile, task = _sealed(opened["allocation"]), opened["profile"], opened["task"]
        child = digest({"parent": study["study_sha256"], "allocation": allocation,
                        "profile": profile, "task_sha256": digest(task)})
        bindings = {"source_sha256": study["source_sha256"], "policy_sha256": digest(profile),
                    "launcher_sha256": study["launcher_sha256"]}
        _require(opened.get("kind") == "phase4-cm1-child-open-v1" and opened["child_sha256"] == child
            and allocation["parent_sha256"] == study["study_sha256"] and allocation["ordinal"] == ordinal
            and allocation["child_kind"] == kind and allocation["pair"] == pair
            and allocation["task_sha256"] == digest(task) and opened["bindings"] == bindings
            and profile["phase4_child"]["parent_sha256"] == study["study_sha256"]
            and profile["phase4_child"]["kind"] == kind and profile["phase4_child"]["pair"] == pair,
            "child open record belongs to another parent/source/task")
        if kind == "inference":
            generation_children[pair] = child
        if kind == "assessment":
            _require(pair in generation_children and opened.get("generation_study_sha256")
                     == profile["phase4_child"].get("generation_study_sha256") == generation_children[pair],
                     "assessment child refers to another generation")
        journal, state, manifest, audits = _ledger(opened, fixture, observed)
        _require(manifest["inputs"] == {"study_sha256": child, "slots": opened["slots"],
            "authority": opened["authority"], "fixture": fixture, "bindings": bindings,
            "policy": profile, "editor_tools": study["editor_tools"]}, "journal identity differs from saved child")
        _require(closure.get("kind") == "phase4-cm1-child-close-v1"
            and closure["parent_sha256"] == study["study_sha256"] and closure["child_sha256"] == child
            and closure["child_kind"] == kind and closure["pair"] == pair
            and closure["open_sha256"] == opened["sha256"] and closure["journal"] == str(journal)
            and closure["result_sha256"] == digest(value) and closure["status"] == state["status"]
            and all(closure[key] == state[key] for key in ("attempts", "spent_micro_usd", "reserved_micro_usd"))
            and closure["transport_audit_summary"] == state["transport_audit_summary"], "closed result/accounting binding differs")
        records.append((kind, pair, task, value, child, project_requests(state, audits)))
        closed_refs.append({"kind": kind, "pair": pair, "sha256": closure["sha256"], "path": str(folder)})
    outcome_path = run_path / "outcome.json"
    if outcome_path.exists():
        outcome = _sealed(_read(outcome_path, observed))
        _require(outcome["study_sha256"] == study["study_sha256"] and outcome["fixture"] is fixture
                 and outcome["status"] == status and outcome["closed_children"] == closed_refs,
                 "parent outcome status/mode/closed inventory differs")
    cases = {}
    if confirmation and not fixture:
        started = _read(run_path / "started.json", observed)
        manifest_path = run_path / "confirmation-manifest.json"
        manifest = _read(manifest_path, observed)
        _require(started["study_sha256"] == study["study_sha256"]
            and started["confirmation_manifest_sha256"] == observed[manifest_path]
            and manifest["manifest_sha256"] == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
            and manifest["frozen_method_sha256"] == study["method_sha256"]
            and manifest["source_sha256"] == study["confirmation_source_sha256"]
            and manifest["exposure_inventory_sha256"] == study["exposure_inventory_sha256"]
            and manifest["eligibility_passed"] is True and len(manifest["selected"]) == 24,
            "saved confirmation manifest belongs to another frozen method/frame")
        declarations = [(f"p4-{i:02d}", row["source_task_id"], "", row["prompt_sha256"])
                        for i, row in enumerate(manifest["selected"], 1)]
        scope = "confirmation_24_prompt_units"
    elif confirmation:
        declared = {pair: task for kind, pair, task, *_ in records if kind == "inference"}
        declarations = [(pair, task["id"], task["prompt"], digest(task["prompt"])) for pair, task in sorted(declared.items())]
        scope = "synthetic_fixture_actual_prompt_units"
    else:
        declarations = [(row["pilot_id"], row["task"]["id"], row["task"]["prompt"], digest(row["task"]["prompt"]))
                        for row in study["development"]]
        scope = "qualification_only"
    expected_hashes = {}
    for pair, task_id, prompt, prompt_hash in declarations:
        expected_hashes[pair] = prompt_hash
        cases[pair] = {"id": task_id, "prompt": prompt, "metrics": None, "outputs": None,
            "events": [], "model_usage": {}, "started_at": None, "completed_at": None,
            "undated_requests": [], "pair": pair, "usage_scope": "known settled native requests only; unknown is not zero"}
    for kind, pair, task, value, child, projected in records:
        if confirmation and kind == "dev":
            continue
        _require(pair in cases and task["id"] == cases[pair]["id"]
                 and digest(task["prompt"]) == expected_hashes[pair], "closed child task differs from declared sample")
        case = cases[pair]
        case["prompt"] = task["prompt"]
        events, usage, undated = projected
        case["events"].extend(events)
        case["undated_requests"].extend(undated)
        for model, row in usage.items():
            if model not in case["model_usage"]:
                case["model_usage"][model] = row
            else:
                target = case["model_usage"][model]
                for key in TOKEN_FIELDS:
                    target[key] += row[key]
                for key in OPTIONAL_TOKENS + ("total_cost",):
                    target[key] = target[key] + row[key] if target.get(key) is not None and row.get(key) is not None else None
        if kind in {"dev", "inference"}:
            _require(kind == "dev" or value.get("kind") == "phase4-cm1-generation-v1"
                     and value["task"] == task and value["pair"] == pair
                     and value["generation_study_sha256"] == child, "saved generation identity differs")
            adaptive = value.get("adaptive") or {} if kind == "inference" else {}
            fixed = value.get("fixed") or {} if kind == "inference" else value
            outputs = {"fixed": fixed.get("portfolio"), "c1": adaptive.get("checkpoints", {}).get("c1"),
                       "c2": adaptive.get("checkpoints", {}).get("c2"), "selected_checkpoint": adaptive.get("selected_checkpoint")}
            _require(outputs["selected_checkpoint"] in (None, "c1", "c2"), "foreign native checkpoint choice")
            for portfolio in (outputs[key] for key in ("fixed", "c1", "c2")):
                if portfolio is not None:
                    validate_portfolio(portfolio)
                    _require(portfolio["fixture"] is fixture and portfolio["task"] == task
                             and portfolio["provenance"]["study_sha256"] == child, "portfolio provenance differs")
            choice = outputs["selected_checkpoint"]
            if choice is not None:
                _require(outputs[choice] is not None and adaptive.get("portfolio") == outputs[choice], "native selected portfolio differs")
            case["outputs"] = outputs if any(outputs[key] is not None for key in ("fixed", "c1", "c2")) else None
        else:
            choice = case["outputs"]["selected_checkpoint"] if case["outputs"] is not None else None
            _require(value["prompt_id"] == task["id"] and value["pair"] == pair
                     and value["selected_checkpoint"] == choice, "assessment row has another task/choice")
            case["metrics"] = {"targets": _targets(value, case["outputs"], task, fixture),
                               "selected_checkpoint": value["selected_checkpoint"]}
    analysis = None
    if (run_path / "analysis.json").exists():
        analysis = _read(run_path / "analysis.json", observed)
        _require(analysis.get("kind") == "phase4-cm1-saved-analysis-v1", "foreign saved analysis")
        panels = {row["prompt_id"]: row for row in analysis["pairs"]}
        for case in cases.values():
            if case["id"] in panels:
                case["metrics"] = {**(case["metrics"] or {}), "analysis_panel": panels[case["id"]]}
    for case in cases.values():
        case["events"].sort(key=lambda row: (_utc(row["timestamp"]), row["data"]["slot_id"]))
        if case["events"]:
            case["started_at"] = min(_utc(row["data"]["started_at"]) for row in case["events"]).isoformat()
            case["completed_at"] = max(_utc(row["data"]["completed_at"]) for row in case["events"]).isoformat()
    _require(release.source_identity() == study["source"]
             and all((file_hash(path) if path.exists() else None) == expected for path, expected in observed.items()),
             "snapshot source artifacts changed during read-only projection")
    payload = {"kind": "phase4-cm1-snapshot-v1", "study_sha256": study["study_sha256"],
        "source_sha256": study["source_sha256"], "definition_sha256": study["method"]["definition_sha256"],
        "fixture": fixture, "status": status, "scope": scope, "analysis": analysis,
        "read_only_sources_unchanged": True,
        "cases": sorted(cases.values(), key=lambda row: row["id"]),
        "source_artifacts": [{"path": str(path), "sha256": value} for path, value in sorted(observed.items()) if value is not None]}
    validate_snapshot(payload)
    return payload


def publish_snapshot(study: dict, run_path: Path, output: Path, *, fixture: bool, status: str) -> dict:
    from .release import path

    payload = build_snapshot(study, run_path, fixture=fixture, status=status)
    write_once(path(output), payload)
    return payload
