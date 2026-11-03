"""Bounded saved-rank derivation, explicit historical reuse and native judging."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from buddha2.artifacts import ContractError, write_bytes_once
from buddha2.phase2_am1_controls import (
    BILLING_PROFILE,
    CONTROL_POLICY,
    CONTROL_SHA256,
    canonical_live_journal,
    runtime_guard,
)
from buddha2.phase2_contracts import export_native, make_portfolio, slot_prefix, validate_portfolio
from buddha2.phase2_dispatch import (
    FROZEN_PROFILES,
    Dispatcher,
    _validate_auth,
    replay_dispatch,
    writer_lock,
)
from buddha2.phase2_native import GROUP_CONFIG, SCORE_CONFIG, NativeAssessment
from buddha2.phase2_release import load_execution

from . import support
from .normalizer import normalize_rank
from .support import (
    CAP,
    PARENT,
    POLICY,
    RESULTS,
    ROOT,
    checked_path,
    digest,
    file_hash,
    read_json,
    require,
    write_once,
)

PARENT_STUDY = "38132ee3a935af4ac975c3fda84154d1a85b1bcb510925f409993a15d3103d8b"
PARENT_DECISION = "6cc0d324f9be864a9747140c4d6bd41a42606f31e38ee772e5c35aac62e381fc"
PARENT_MANIFEST = "932e280b781edce72b3b73c6d7087ea5008fb65ee60c7e15ee370387a41f3fbb"
PARENT_CUTOFF = "2026-10-28T12:12:19Z"
METHODS = ("A", "B", "C-N")


def _native() -> NativeAssessment:
    return NativeAssessment(ROOT / ".upstream/novelty-bench")


def _seal(value: dict, field: str) -> dict:
    return value | {field: digest(value)}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def _exact(path: Path, expected: Any) -> None:
    require(checked_path(path).read_bytes() == _canonical(expected), "immutable artifact differs: " + path.name)


def _parent_file(relative: str, manifest: dict) -> Path:
    path = checked_path(PARENT / relative)
    require(manifest["files"].get(relative) == file_hash(path), "closed parent evidence differs")
    return path


def _definition() -> dict:
    runtime_guard()
    sources = support.source_identity()
    require(file_hash(PARENT / "manifest.json") == PARENT_MANIFEST, "closed parent manifest differs")
    manifest = read_json(PARENT / "manifest.json")
    old, saved = load_execution(ROOT / "runs/phase2-release-r018/release/study.json",
        RESULTS / "phase2-release-r018" / PARENT_STUDY / "live", cutoff=PARENT_CUTOFF)
    require(old["study_sha256"] == PARENT_STUDY and
            saved["bundle"]["decision"]["decision_sha256"] == PARENT_DECISION,
            "closed strict-study identity differs")
    require(saved["state"]["attempts"] == 991 and saved["state"]["reserved_micro_usd"] == 0,
            "parent liability or request population differs")
    journal = _parent_file("raw/run/journal/events.jsonl", manifest)
    canonical_parent = RESULTS / "phase2-release-r018" / PARENT_STUDY / "live/journal/events.jsonl"
    require(journal.read_bytes() == canonical_parent.read_bytes(), "canonical parent is no longer closed evidence")
    indexed = {row["order_id"]: row for row in old["worklist"]["outputs"]}
    portfolios = {slot_prefix(p["task"]["id"], p["provenance"]["method"], p["provenance"]["repeat"]): p
                  for p in saved["portfolios"]}
    require(Counter(p["provenance"]["method"] for p in portfolios.values()) == {"A": 24, "B": 24, "C": 20},
            "the closed reuse population differs")
    normalizations, derived = [], []
    for block in old["worklist"]["blocks"]:
        task_id, repeat = block["task_id"], block["repeat"]
        b = slot_prefix(task_id, "B", repeat)
        c = slot_prefix(task_id, "C", repeat)
        parent = portfolios[b]
        raw = saved["state"]["results"][c + ".rank"]
        require(raw["status"] == "response" and raw["role"] == "rank" and
                raw["response"]["stop_reason"] == "end_turn", "rank input is not a known finished response")
        # No task text, score, judge result or competing order enters N1.
        normalized = normalize_rank(raw["response"]["text"], [r["id"] for r in parent["responses"]])
        require(normalized["policy_id"] == POLICY["id"] and normalized["status"] == "accepted",
                "N1 rejected a saved input; stop offline without changing policy")
        order = normalized["order"]
        require(len(order) == 10 and set(order) == {r["id"] for r in parent["responses"]},
                "normalizer did not preserve the exact parent permutation")
        row = {"task_id": task_id, "repeat": repeat, "order_id": c,
               "parent_path": "raw/run/portfolios/" + b + ".json", "parent_sha256": digest(parent),
               "rank_slot": c + ".rank", "rank_result_sha256": digest(raw),
               "raw_text_sha256": hashlib.sha256(raw["response"]["text"].encode("utf-8")).hexdigest(),
               "original_strict_status": saved["coverage"]["slots"][c + ".rank"],
               "normalization": normalized, "normalized_order_sha256": digest(order),
               "reuse_original_C": c in portfolios}
        if c in portfolios:
            require(order == [r["id"] for r in portfolios[c]["responses"]], "N1 changed a valid original C order")
        else:
            require(row["original_strict_status"] == "invalid_rank", "new order was not an original strict failure")
            derived.append(copy.deepcopy(row))
        normalizations.append(row)
    require(len(normalizations) == 24 and len(derived) == 4, "normalization cohort differs")
    native = _native()
    reuse = []
    for prefix, portfolio in sorted(portfolios.items()):
        ppath = "raw/run/portfolios/" + prefix + ".json"
        apath = "raw/run/assessments/" + prefix + ".json"
        require(read_json(_parent_file(ppath, manifest)) == portfolio, "original portfolio no longer matches")
        assessment = read_json(_parent_file(apath, manifest))
        require(assessment["status"] == "scored" and assessment["evaluator"] == native.identity,
                "reused assessment is not scored under the pinned evaluator")
        for name in ("generations.jsonl", "identities.json"):
            _parent_file("raw/run/native/" + prefix + "/" + name, manifest)
        require(native.load_export(PARENT / "raw/run/native" / prefix) == portfolio,
                "reused native exchange differs")
        expected = native.finalize(portfolio, assessment["requests"][0], assessment["requests"][1:])
        require(assessment == expected, "original native assessment does not replay")
        definition = indexed[prefix]
        reuse.append({"task_id": definition["task_id"], "repeat": definition["repeat"],
                      "method": "C-N" if definition["method"] == "C" else definition["method"],
                      "origin_method": definition["method"], "portfolio_path": ppath,
                      "assessment_path": apath, "portfolio_sha256": digest(portfolio),
                      "assessment_sha256": digest(assessment), "portfolio_file_sha256": file_hash(PARENT / ppath),
                      "assessment_file_sha256": file_hash(PARENT / apath),
                      "native_input_sha256": digest(native._instance(portfolio)),
                      "native_replay_sha256": digest(expected), "reused_not_newly_judged": True})
    require(len(reuse) == 68, "reuse proof population differs")
    costs = saved["bundle"]["analysis"]["generation_ranking_cost_micro_usd_by_candidate"]
    rank_cost = sum(r["spent_micro_usd"] for r in saved["state"]["results"].values() if r["role"] == "rank")
    slots = {row["order_id"] + suffix: {"role": role, "checkpoint": "canary"}
             for row in derived for suffix, role in [(".group", "group"),
                 *[(f".quality.{i:02d}", "quality") for i in range(10)]]}
    body = {"kind": "p2bn-study-v1", "source_files": sources, "source_sha256": digest(sources),
            "policy": POLICY, "policy_sha256": digest(POLICY),
            "launcher_sha256": sources["rank-format.ps1"], "parent_study_sha256": PARENT_STUDY,
            "parent_decision_sha256": PARENT_DECISION, "parent_manifest_sha256": PARENT_MANIFEST,
            "tasks": old["tasks"], "profiles": FROZEN_PROFILES, "native_evaluator": native.identity,
            "shared_generator_settings_sha256": old["shared_generator_settings_sha256"],
            "control_policy_sha256": CONTROL_SHA256, "billing_profile": BILLING_PROFILE,
            "normalizations": normalizations, "reuse": reuse, "derived_orders": derived, "slots": slots,
            "procedure_sha256": digest({"policy": POLICY,
                "normalizer_source": sources["followups/rank_format_v1/normalizer.py"],
                "origin_procedure": old["procedure_hashes"]["C"]}),
            "candidate_costs": {"A": costs["A"], "B": costs["B"], "C-N": costs["B"] + rank_cost},
            "original_procedure_hashes": old["procedure_hashes"],
            "historical_shared_micro_usd": saved["state"]["spent_micro_usd"],
            "budget": {"cap_micro_usd": CAP, "canary_cap_micro_usd": CAP, "marginal_not_old_allowance": True},
            "decision_policy": {"id": "rank-format-development-v1", "track": "benchmark",
                "lineage": "posthoc-C-N-v1", "sort": ["highest exact mean utility", "lowest candidate cost", "A/B/C-N"]}}
    return _seal(body, "study_sha256")


def _parent_portfolio(row: dict) -> dict:
    parent = read_json(checked_path(PARENT / row["parent_path"]))
    require(digest(parent) == row["parent_sha256"], "derived order parent changed")
    return parent


def validate_derivation(study: dict, row: dict, child: dict, *, fixture: bool) -> None:
    parent = _parent_portfolio(row)
    validate_portfolio(child)
    p = child["provenance"]
    mapping = {r["id"]: r for r in parent["responses"]}
    require(child["task"] == parent["task"] and child["fixture"] is fixture and
            p["method"] == "C" and p["repeat"] == row["repeat"] and
            p["study_sha256"] == study["study_sha256"] and p["parent_sha256"] == digest(parent) and
            p["procedure_sha256"] == study["procedure_sha256"] and
            p["settings_sha256"] == parent["provenance"]["settings_sha256"] and
            p["model"] == parent["provenance"]["model"] and
            p["request_ids"] == parent["provenance"]["request_ids"] + [row["rank_slot"]] and
            child["responses"] == [mapping[i] for i in row["normalization"]["order"]],
            "cross-study derivation changed IDs, text, parent or declared provenance")


def _derived(study: dict, row: dict, *, fixture: bool) -> dict:
    parent = _parent_portfolio(row)
    mapping = {r["id"]: r for r in parent["responses"]}
    child = make_portfolio(parent["task"], [mapping[i] for i in row["normalization"]["order"]],
        method="C", repeat=row["repeat"], model=parent["provenance"]["model"],
        settings_sha256=parent["provenance"]["settings_sha256"], procedure_sha256=study["procedure_sha256"],
        request_ids=parent["provenance"]["request_ids"] + [row["rank_slot"]],
        study_sha256=study["study_sha256"], fixture=fixture, parent_sha256=digest(parent))
    validate_derivation(study, row, child, fixture=fixture)
    return child


def prepare(output: Path) -> dict:
    output = checked_path(output, output=True)
    study = _definition()
    write_once(output / "study.json", study)
    write_once(output / "normalizations.json", study["normalizations"])
    write_once(output / "reuse.json", study["reuse"])
    native = _native()
    for row in study["derived_orders"]:
        child = _derived(study, row, fixture=False)
        write_once(output / "derived" / f"{row['order_id']}.json", child)
        export_native(child, output / "derived-native" / row["order_id"])
        require(native.load_export(output / "derived-native" / row["order_id"]) == child,
                "new derived native exchange does not replay")
    for name in study["source_files"]:
        if name.startswith("followups/") or name in ("rank-format.ps1", support.DEFINITION):
            write_bytes_once(output / "source" / name, (ROOT / name).read_bytes())
    return {"status": "prepared-offline", "study_sha256": study["study_sha256"],
            "normalizations": 24, "reused_assessments": 68, "derived_unscored": 4,
            "request_slots": 44, "provider_calls": 0}


def load_preparation(study_path: Path) -> dict:
    path = checked_path(study_path)
    study = _definition()
    _exact(path, study)
    _exact(path.parent / "normalizations.json", study["normalizations"])
    _exact(path.parent / "reuse.json", study["reuse"])
    for row in study["derived_orders"]:
        _exact(path.parent / "derived" / f"{row['order_id']}.json", _derived(study, row, fixture=False))
    return study


def grant_template(study_path: Path, *, fixture: bool, authorized: bool) -> dict:
    study = load_preparation(study_path)
    require(type(fixture) is bool and type(authorized) is bool, "grant mode must be explicit")
    authorization = {"study_sha256": study["study_sha256"],
        "authorization_id": "p2bn-" + study["study_sha256"][:20] + ("-mock" if fixture else "-live"),
        "authorized": False if fixture else authorized, "cap_micro_usd": CAP,
        "canary_cap_micro_usd": CAP, "expansion_authorized": False,
        "control_policy_sha256": CONTROL_SHA256, "billing_profile": BILLING_PROFILE}
    return _seal({"kind": "p2bn-grant-v1", "fixture": fixture, "authorization": authorization,
                  **{k: study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")}},
                 "grant_sha256")


def _grant(study: dict, grant_path: Path, fixture: bool) -> dict:
    grant = read_json(checked_path(grant_path))
    body = {k: v for k, v in grant.items() if k != "grant_sha256"}
    require(grant.get("grant_sha256") == digest(body) and grant.get("kind") == "p2bn-grant-v1" and
            grant.get("fixture") is fixture, "grant identity or mode differs")
    require(set(grant) == {"kind", "fixture", "authorization", "study_sha256", "source_sha256",
                           "policy_sha256", "launcher_sha256", "grant_sha256"}, "unexpected grant fields")
    require(all(grant[k] == study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")),
            "grant belongs to another study/source/policy/launcher")
    auth = grant["authorization"]
    _validate_auth(auth, study["study_sha256"], CONTROL_POLICY)
    require(auth["authorized"] is (not fixture) and auth["expansion_authorized"] is False and
            auth["cap_micro_usd"] == auth["canary_cap_micro_usd"] == CAP,
            "authority does not cover exactly this marginal bounded stage")
    return grant


def _location(study: dict, fixture: bool) -> tuple[Path, Path]:
    journal = (RESULTS / "phase2b-rank-format-v1" / study["study_sha256"] / "mock/journal"
               if fixture else canonical_live_journal(study["study_sha256"]))
    return journal.parent, journal


def _manifest(study: dict, grant: dict) -> dict:
    inputs = {"study_sha256": study["study_sha256"], "slots": study["slots"],
              "profiles": FROZEN_PROFILES, "admission": CONTROL_POLICY,
              "authorization": {k: v for k, v in grant["authorization"].items() if k != "expansion_authorized"},
              "fixture": grant["fixture"], "control_policy": CONTROL_POLICY,
              "rates_thousandths_micro_usd": CONTROL_POLICY["maximum_rates_thousandths_micro_usd"]}
    return {"schema_version": 2, "run_id": digest(inputs), "inputs": inputs}


def _state(study: dict, grant: dict, journal: Path) -> dict:
    if (journal / "manifest.json").exists():
        _exact(journal / "manifest.json", _manifest(study, grant))
        return replay_dispatch(journal)
    require(not journal.exists() or not any(journal.iterdir()), "unrecognized journal contents")
    return {"run_id": _manifest(study, grant)["run_id"], "fixture": grant["fixture"], "status": "ready",
            "attempts": 0, "spent_micro_usd": 0, "reserved_micro_usd": 0,
            "canary_spent_micro_usd": 0, "canary_reserved_micro_usd": 0,
            "provider_calls": 0, "retries": 0, "results": {}}


def preflight(study_path: Path, grant_path: Path, fixture: bool) -> dict:
    require(type(fixture) is bool, "explicit fixture/live mode required")
    study = load_preparation(study_path)
    grant = _grant(study, grant_path, fixture)
    if not fixture:
        support.validate_gate(study_path, study)
    run, journal = _location(study, fixture)
    state = _state(study, grant, journal)
    require(state["status"] == "ready" and state["reserved_micro_usd"] == 0,
            "unresolved delivery/usage liability blocks further dispatch")
    with _reader(run):
        _saved(study, run, state, _native(), fixture)
    return {"kind": "p2bn-nonsending-preflight-v1",
            **{k: study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")},
            "grant_sha256": grant["grant_sha256"], "control_policy_sha256": CONTROL_SHA256,
            "billing_profile": BILLING_PROFILE, "fixture": fixture, "run": str(run), "journal": str(journal),
            "journal_id": _manifest(study, grant)["run_id"], "slot_count": 44,
            "role_counts": {"group": 4, "quality": 40}, "cap_micro_usd": CAP,
            "provider_calls": 0, "credentials_read": False}


@contextmanager
def _reader(run: Path) -> Iterator[None]:
    import fcntl
    lock = run / "owner/.writer.lock"
    if not lock.exists():
        yield
        return
    require(not lock.is_symlink(), "owner lock cannot be a link")
    with lock.open("rb") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another owner is executing this follow-up") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _validate_results(study: dict, state: dict, native: NativeAssessment, fixture: bool) -> None:
    """Check every accounted request before semantic output failures may be classified."""
    remaining = set(state["results"])
    for row in study["derived_orders"]:
        child = _derived(study, row, fixture=fixture)
        prefix = row["order_id"]
        group = state["results"].get(prefix + ".group")
        if group is None:
            continue
        request = native.group_request(child)
        def identity(result: dict, slot: str, role: str, expected: dict) -> None:
            require(result.get("slot_id") == slot and result.get("role") == role and
                    result.get("request_sha256") == digest(expected) and
                    isinstance(result.get("dispatch_id"), str) and result.get("fixture") is fixture and
                    result.get("study_sha256") == study["study_sha256"],
                    "saved native request identity differs from frozen derived portfolio")
            if result["status"] == "response":
                native._response(result, slot, role, expected, child)
            remaining.remove(slot)
        identity(group, prefix + ".group", "group", request)
        if group["status"] != "response":
            continue
        try:
            fields = native.fold_group(child, group)
        except ValueError:
            continue
        heads = native.modules["score"].heads(fields["partition"])
        for index, expected in zip(heads, native.quality_requests(child, fields["partition"]), strict=True):
            slot = f"{prefix}.quality.{index:02d}"
            if slot in state["results"]:
                identity(state["results"][slot], slot, "quality", expected)
    require(not remaining, "quality evidence lacks a valid group/head request or uses an undeclared slot")


def _saved(study: dict, run: Path, state: dict, native: NativeAssessment, fixture: bool) -> tuple[dict, dict]:
    require(not any(p.is_symlink() for p in (run, *run.rglob("*"))), "new run artifacts contain a link")
    _validate_results(study, state, native, fixture)
    portfolios, assessments = {}, {}
    allowed = {r["order_id"] for r in study["derived_orders"]}
    for folder in ("portfolios", "assessments", "native"):
        require(not any(p.is_symlink() for p in (run / folder).rglob("*")), "new artifact contains a link")
        require(all(p.stem in allowed for p in (run / folder).glob("*.json")), "undeclared new order artifact")
    require(all(p.is_dir() and p.name in allowed for p in (run / "native").glob("*")),
            "undeclared native exchange")
    for row in study["derived_orders"]:
        prefix = row["order_id"]
        child = _derived(study, row, fixture=fixture)
        portfolio_path, assessment_path = run / "portfolios" / f"{prefix}.json", run / "assessments" / f"{prefix}.json"
        if portfolio_path.exists():
            _exact(portfolio_path, child)
            require(native.load_export(run / "native" / prefix) == child, "new native exchange differs")
            portfolios[prefix] = child
        if assessment_path.exists():
            require(prefix in portfolios, "published assessment lacks its derived portfolio")
            assessment = read_json(assessment_path)
            requests = assessment.get("requests")
            require(isinstance(requests, list) and requests and all(
                result == state["results"].get(result.get("slot_id")) for result in requests),
                "new native evidence is not from this settled journal")
            expected = native.finalize(child, requests[0], requests[1:])
            _exact(assessment_path, expected)
            assessments[prefix] = expected
    return portfolios, assessments


def _coverage(study: dict, state: dict, portfolios: dict, assessments: dict, native: NativeAssessment) -> dict:
    slots = dict.fromkeys(study["slots"], "not_attempted")
    orders = dict.fromkeys((row["order_id"] for row in study["derived_orders"]), "not_attempted")
    for slot, result in state["results"].items():
        if result["status"] != "response":
            slots[slot] = "unknown_liability"
            continue
        response = result["response"]
        stop, text = response.get("stop_reason"), response.get("text", "")
        status = "refused" if response.get("refusal") or stop in ("refusal", "content_filter") else (
            "truncated" if stop in ("max_tokens", "length") else "empty" if not text.strip() else "ok")
        slots[slot] = status
    for row in study["derived_orders"]:
        prefix = row["order_id"]
        if prefix in assessments:
            orders[prefix] = assessments[prefix]["status"]
        elif any(slot.startswith(prefix + ".") for slot in state["results"]):
            orders[prefix] = "incomplete"
        grouped = state["results"].get(prefix + ".group")
        if not grouped or grouped["status"] != "response" or prefix not in portfolios:
            continue
        try:
            fields = native.fold_group(portfolios[prefix], grouped)
            head_list = native.modules["score"].heads(fields["partition"])
            heads = set(head_list)
            calls = native.modules["score"].score_calls({**native._instance(portfolios[prefix]), **fields}, SCORE_CONFIG)
            for i, call in zip(head_list, calls, strict=True):
                slot = f"{prefix}.quality.{i:02d}"
                result = state["results"].get(slot)
                if result and slots[slot] == "ok":
                    response = result["response"]
                    message = SimpleNamespace(stop_reason=response.get("stop_reason"), content=[
                        SimpleNamespace(type="text", text=response["text"])])
                    try:
                        native.modules["judge"].parse_message(message, call.schema)
                        native._strict_object(response["text"], call.schema)
                    except ValueError:
                        slots[slot] = "invalid_quality"
            for i in range(10):
                slot = f"{prefix}.quality.{i:02d}"
                if i not in heads:
                    require(slot not in state["results"], "nonhead quality slot was dispatched")
                    slots[slot] = "not_needed_nonhead"
        except ValueError:
            slots[prefix + ".group"] = "invalid_group" if slots[prefix + ".group"] == "ok" else slots[prefix + ".group"]
            for i in range(10):
                slot = f"{prefix}.quality.{i:02d}"
                require(slot not in state["results"], "quality followed an invalid group")
                slots[slot] = "skipped_invalid_group"
    return {"slots": slots, "orders": orders, "slot_counts": dict(Counter(slots.values())),
            "order_counts": dict(Counter(orders.values())), "scheduled_slots": 44}


def _time(cutoff: str | None) -> str:
    value = cutoff or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    require(isinstance(value, str) and dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime(
        "%Y-%m-%dT%H:%M:%SZ") == value, "cutoff requires canonical UTC")
    return value


def _snapshot(study: dict, grant: dict, run: Path, journal: Path, cutoff: str | None) -> dict:
    state = _state(study, grant, journal)
    native = _native()
    portfolios, assessments = _saved(study, run, state, native, grant["fixture"])
    coverage = _coverage(study, state, portfolios, assessments, native)
    rows = []
    for row in study["reuse"]:
        assessment = read_json(PARENT / row["assessment_path"])
        rows.append({"task_id": row["task_id"], "repeat": row["repeat"], "method": row["method"],
                     "status": "scored", "reused": True, "source_assessment_sha256": row["assessment_sha256"],
                     "metrics": assessment["metrics"]})
    for row in study["derived_orders"]:
        assessment = assessments.get(row["order_id"])
        rows.append({"task_id": row["task_id"], "repeat": row["repeat"], "method": "C-N", "reused": False,
                     "status": assessment["status"] if assessment else coverage["orders"][row["order_id"]],
                     "source_assessment_sha256": digest(assessment) if assessment else None,
                     "metrics": assessment["metrics"] if assessment else {"utility": None, "distinct": None}})
    require(len(rows) == 72 and len({(r["task_id"], r["repeat"], r["method"]) for r in rows}) == 72,
            "comparison row population differs")
    complete = all(r["status"] == "scored" and r["metrics"]["utility"] is not None for r in rows) and state["status"] == "ready" and state["reserved_micro_usd"] == 0
    paired = []
    for task in study["tasks"]:
        means = {}
        for method in METHODS:
            selected_rows = [r for r in rows if r["task_id"] == task["id"] and r["method"] == method]
            means[method] = sum(r["metrics"]["utility"] for r in selected_rows) / 2 if len(selected_rows) == 2 and all(
                r["status"] == "scored" and r["metrics"]["utility"] is not None for r in selected_rows) else None
        paired.append({"task_id": task["id"], "means": means,
                       "B_minus_A": means["B"] - means["A"] if means["B"] is not None and means["A"] is not None else None,
                       "C_N_minus_B": means["C-N"] - means["B"] if means["C-N"] is not None and means["B"] is not None else None})
    means = {m: sum(p["means"][m] for p in paired) / 12 if complete else None for m in METHODS}
    comparable: dict[str, float] = {}
    if complete:
        for method in METHODS:
            value = means[method]
            if value is None:
                raise ContractError("complete comparison lacks a method mean")
            comparable[method] = float(value)
    selected = min(METHODS, key=lambda m: (-comparable[m], study["candidate_costs"][m], METHODS.index(m))) if complete else None
    evidence_id = digest({"state": state, "assessments": assessments, "coverage": coverage})
    cutoff_path = run / "report-cutoffs" / f"{evidence_id}.json"
    if cutoff is None and cutoff_path.exists():
        cutoff = read_json(cutoff_path)["cutoff"]
    actual_cutoff = _time(cutoff)
    procedure = (study["procedure_sha256"] if selected == "C-N" else
                 study["original_procedure_hashes"].get(selected)) if selected else None
    decision = _seal({"kind": "rank-format-development-decision-v1", "study_sha256": study["study_sha256"],
        "policy": study["decision_policy"], "parent_decision_sha256": PARENT_DECISION, "cutoff": actual_cutoff,
        "fixture": grant["fixture"], "native_complete": complete, "status": "complete-development" if complete else "inconclusive",
        "selected_method": None if grant["fixture"] else selected,
        "synthetic_selected_method": selected if grant["fixture"] else None,
        "selected_procedure_sha256": None if grant["fixture"] else procedure,
        "synthetic_selected_procedure_sha256": procedure if grant["fixture"] else None,
        "mean_utility": means, "candidate_cost_micro_usd": study["candidate_costs"],
        "human_status": "not-required", "posthoc_not_independent_replication": True}, "decision_sha256")
    summary = {"status": "mock-complete" if complete and grant["fixture"] else "complete" if complete else "partial",
               "study_sha256": study["study_sha256"], "fixture": grant["fixture"], "attempts": state["attempts"],
               "new_assessments": len(assessments), "scored_new_assessments": sum(a["status"] == "scored" for a in assessments.values()),
               "reused_assessments": 68, "new_spent_micro_usd": state["spent_micro_usd"],
               "historical_shared_micro_usd": study["historical_shared_micro_usd"],
               "combined_micro_usd": study["historical_shared_micro_usd"] + state["spent_micro_usd"],
               "reserved_micro_usd": state["reserved_micro_usd"], "journal_status": state["status"],
               "provider_calls": state["provider_calls"], "retries": 0, "cutoff": actual_cutoff,
               "decision_status": decision["status"], "selected_method": decision["selected_method"],
               "synthetic_selected_method": decision["synthetic_selected_method"], "evidence_sha256": evidence_id}
    return {"study": study, "state": state, "coverage": coverage, "rows": rows,
            "analysis": {"paired_prompt_means": paired, "mean_utility": means,
                         "independent_prompt_units": 12, "posthoc": True},
            "decision": decision, "summary": summary}


def snapshot(study_path: Path, grant_path: Path, fixture: bool, cutoff: str | None = None) -> dict:
    study = load_preparation(study_path)
    grant = _grant(study, grant_path, fixture)
    run, journal = _location(study, fixture)
    with _reader(run):
        return _snapshot(study, grant, run, journal, cutoff)


def run(study_path: Path, grant_path: Path, transport: Any, cutoff: str | None = None) -> dict:
    if cutoff is not None:
        _time(cutoff)
    checked = preflight(study_path, grant_path, transport.fixture)
    study = load_preparation(study_path)
    grant = _grant(study, grant_path, transport.fixture)
    run_path, journal = Path(checked["run"]), Path(checked["journal"])
    native = _native()
    with writer_lock(run_path / "owner"):
        dispatcher = Dispatcher(journal, study_sha256=study["study_sha256"], slots=study["slots"],
                                authorization=grant["authorization"], transport=transport, control_policy=CONTROL_POLICY)
        state = _state(study, grant, journal)
        _, assessments = _saved(study, run_path, state, native, transport.fixture)
        for row in study["derived_orders"]:
            child = _derived(study, row, fixture=transport.fixture)
            prefix = row["order_id"]
            export_native(child, run_path / "native" / prefix)
            write_once(run_path / "portfolios" / f"{prefix}.json", child)
            if prefix in assessments:
                continue
            def dispatch(slot: str, role: str, request: dict, **kwargs: Any) -> dict:
                if hasattr(transport, "select"):
                    transport.select(role, slot)
                return dispatcher.dispatch(slot, role, request, **kwargs)
            try:
                assessment = native.assess(child, dispatch, checkpoint="canary")
                write_once(run_path / "assessments" / f"{prefix}.json", assessment)
            except ContractError as exc:
                current = replay_dispatch(journal)
                write_once(run_path / "halts" / f"{current['attempts']:04}.json", {
                    "kind": "p2bn-bounded-halt-v1", "order_id": prefix, "attempts": current["attempts"],
                    "state_sha256": digest(current), "reason": str(exc)})
                break
        saved = _snapshot(study, grant, run_path, journal, cutoff)
        write_once(run_path / "report-cutoffs" / f"{saved['summary']['evidence_sha256']}.json", {
            "evidence_sha256": saved["summary"]["evidence_sha256"], "cutoff": saved["summary"]["cutoff"]})
        return saved["summary"]


def report(study_path: Path, grant_path: Path, output: Path, fixture: bool,
           cutoff: str | None = None) -> dict:
    saved = snapshot(study_path, grant_path, fixture, cutoff)
    output = checked_path(output, output=True)
    for key in ("coverage", "rows", "analysis", "decision", "summary"):
        write_once(output / f"{key}.json", saved[key])
    study, state = saved["study"], saved["state"]
    request_index = []
    for slot, result in state["results"].items():
        response = result.get("response") or {}
        request_index.append({"slot_id": slot, "dispatch_id": result["dispatch_id"],
            "role": result["role"], "requested_model": FROZEN_PROFILES[result["role"]]["model"],
            "returned_model": response.get("model"), "status": result["status"],
            "outcome": saved["coverage"]["slots"][slot], "stop_reason": response.get("stop_reason"),
            "usage": response.get("usage"), "spent_micro_usd": result["spent_micro_usd"],
            "reserved_micro_usd": result["reserved_micro_usd"],
            "request_sha256": result["request_sha256"], "result_sha256": digest(result)})
    write_once(output / "protocol.json", {
        "kind": "p2bn-protocol-and-request-index-v1", "fixture": fixture,
        **{k: study[k] for k in ("study_sha256", "source_sha256", "policy_sha256", "native_evaluator",
                                "parent_study_sha256", "parent_decision_sha256", "procedure_sha256")},
        "journal_run_id": state["run_id"], "profiles": FROZEN_PROFILES,
        "native_group_config": GROUP_CONFIG, "native_score_config": SCORE_CONFIG,
        "sampling": {"prompt_units": 12, "repeats": 2, "tasks": [task["id"] for task in study["tasks"]],
                     "methods": list(METHODS), "no_new_generation_plan_or_rank_calls": True},
        "new_scope": {"orders": 4, "group_slots": 4, "quality_slots_max": 40, "slots_max": 44},
        "marginal_cap_micro_usd": CAP, "cost_basis": CONTROL_POLICY["cost_basis"],
        "historical_shared_micro_usd": study["historical_shared_micro_usd"],
        "reuse": study["reuse"], "request_index": request_index})
    summary, decision = saved["summary"], saved["decision"]
    text = ("# Saved-rank normalization development comparison\n\n"
            + ("Synthetic native judgments; no real seed selected.\n\n" if fixture else "Post-hoc development evidence; not held-out validation.\n\n")
            + f"Status: {decision['status']}. Original strict-C decision remains inconclusive.\n\n"
            + f"Reused assessments: 68; new scored: {summary['scored_new_assessments']}/4. "
            + f"New requests: {summary['attempts']}; marginal accounted micro-USD: {summary['new_spent_micro_usd']}; "
            + f"unresolved: {summary['reserved_micro_usd']}. Shared history: {summary['historical_shared_micro_usd']}; "
            + f"combined: {summary['combined_micro_usd']}. Costs are public-price upper bounds, not invoices.\n\n"
            + f"Mean utility: {json.dumps(decision['mean_utility'], sort_keys=True)}. "
            + f"Selected: {decision['synthetic_selected_method'] if fixture else decision['selected_method']}.\n\n"
            + "The 12 prompts receive equal weight after averaging two repeats. A/B/C-N ties use candidate "
            + "generation/ranking cost then A/B/C-N. Historical scores are shared evidence, not independent replication.\n")
    write_bytes_once(output / "PHASE2B_RANK_FORMAT_REPORT.md", text.encode("utf-8"))
    return {**summary, "report_output": str(output), "new_provider_calls_for_reporting": 0}
