"""Phase 2A's offline study kit; no live-call command is exposed here."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import (
    ContractError,
    digest,
    file_hash,
    read_json,
    tree_hashes,
    write_bytes_once,
    write_once,
)
from .pairs import _prompt_hash
from .phase2_contracts import (
    export_native,
    import_native,
    make_portfolio,
    permute_portfolio,
    slot_prefix,
)
from .phase2_coverage import slot_coverage
from .phase2_dispatch import (
    ADMISSION_POLICY,
    FROZEN_PROFILES,
    Dispatcher,
    build_request,
    input_bound,
    replay_dispatch,
    reservation,
)

PROJECT = Path(__file__).resolve().parents[2]
NB_COMMIT = "64a23be6b18ec1dacc298830aab276061b6e143c"
CURATED_SHA256 = "ca9b6f470e5d7f7e34a281e2fdaa6f6e51c38bdae075ea580d184139ec391fa7"
IMAGE_ID = "sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366"
SELECTION: dict[str, Any] = {"namespace": "phase2-development-v1", "seed": 20261025, "count": 12,
             "repeats": 2, "normalized_aliases": "NFKC-casefold-whitespace",
             "canonical_rank_input": "JSON array [namespace, seed, source_task_id, normalized_prompt]"}


def _normalize(text: str) -> str:
    import unicodedata

    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _output(path: Path) -> Path:
    root = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")).resolve(strict=True)
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ContractError("Phase 2 outputs cannot traverse links")
    path = path.resolve()
    if path == root or not path.is_relative_to(root):
        raise ContractError("Phase 2 outputs must be children of the approved run root")
    return path


def _templates() -> dict:
    value = read_json(PROJECT / "strategies/fixed/phase2.json")
    expected = {"revision", "answer_system", "plan_system", "angle_note", "rank_system",
                "angle_schema", "permutation_schema"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError("invalid fixed strategy package")
    for key in ("revision", "answer_system", "plan_system", "angle_note", "rank_system"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ContractError("fixed strategy instruction is missing")
    return value


def select_tasks(rows: list[dict], source_sha256: str, excluded_aliases: set[str]) -> dict:
    """Apply the predeclared source/alias/rank policy, without observing outputs."""
    if not isinstance(rows, list) or not rows or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ContractError("invalid curated source identity")
    seen_ids: set[str] = set()
    candidates, exclusions = [], []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "category", "prompt", "prompt_paraphrases"}
                or any(not isinstance(row[k], str) or not row[k].strip() or "\x00" in row[k]
                       for k in ("id", "category", "prompt"))
                or len(row["id"]) > 256 or len(row["prompt"]) > 100_000
                or not isinstance(row["prompt_paraphrases"], list)
                or any(not isinstance(v, str) for v in row["prompt_paraphrases"])):
            raise ContractError("invalid curated source row")
        if row["id"] in seen_ids:
            raise ContractError("duplicate curated source ID")
        seen_ids.add(row["id"])
        normalized = _normalize(row["prompt"])
        record = {"source_task_id": row["id"], "category": row["category"],
                  "prompt_sha256": digest(row["prompt"]), "normalized_prompt_sha256": digest(normalized)}
        if _prompt_hash(row["prompt"]) in excluded_aliases:
            exclusions.append(record | {"reason": "previously exposed alias"})
            continue
        rank = digest([SELECTION["namespace"], SELECTION["seed"], row["id"], normalized])
        candidates.append((rank, row["id"], normalized, row, record))
    chosen: list[dict] = []
    aliases: set[str] = set()
    duplicate_aliases = 0
    inventory = []
    for rank, _, normalized, row, record in sorted(candidates):
        if normalized in aliases:
            duplicate_aliases += 1
            inventory.append(record | {"rank": rank, "status": "duplicate_alias"})
            continue
        aliases.add(normalized)
        selected = len(chosen) < SELECTION["count"]
        inventory.append(record | {"rank": rank, "status": "selected" if selected else "unused_development"})
        if selected:
            chosen.append({"id": "nb-curated-" + digest(row["id"])[:20], "prompt": row["prompt"],
                           "domain": "nb-curated-development", "source_context": {
                               "dataset": "NoveltyBench/curated", "revision": NB_COMMIT,
                               "source_sha256": source_sha256, "source_task_id": row["id"]}})
    if len(chosen) != SELECTION["count"]:
        raise ContractError(f"Phase 2 development selection shortfall: {len(chosen)}/12")
    return {"tasks": chosen, "inventory": inventory, "exclusions": sorted(exclusions, key=lambda r: r["source_task_id"]),
            "duplicate_aliases": duplicate_aliases, "source_rows": len(rows),
            "language_and_modality": "English text-only pinned curated source; analyst-reviewed inventory",
            "limitations": "Development only; normalized aliases are not a proof of semantic independence."}


def make_worklist(tasks: list[dict]) -> dict:
    if len(tasks) != 12 or len({t["id"] for t in tasks}) != 12:
        raise ContractError("worklist requires twelve unique development tasks")
    blocks, slots, outputs = [], {}, []
    for task_index, task in enumerate(tasks):
        for repeat in (1, 2):
            checkpoint = "canary" if task_index == 0 and repeat == 1 else "expansion"
            generation_order = ["A", "B"] if (task_index * 2 + repeat - 1) % 2 == 0 else ["B", "A"]
            blocks.append({"task_id": task["id"], "repeat": repeat, "checkpoint": checkpoint,
                           "generation_order": generation_order})
            for method in ("A", "B", "C"):
                prefix = slot_prefix(task["id"], method, repeat)
                outputs.append({"order_id": prefix, "task_id": task["id"], "method": method,
                                "repeat": repeat, "checkpoint": checkpoint,
                                "portfolio_path": f"portfolios/{prefix}.json",
                                "assessment_path": f"assessments/{prefix}.json"})
                roles = {prefix + ".group": "group"}
                roles.update({f"{prefix}.quality.{i:02d}": "quality" for i in range(10)})
                if method in ("A", "B"):
                    roles.update({f"{prefix}.answer.{i:02d}": "answer" for i in range(10)})
                if method == "B":
                    roles[prefix + ".plan"] = "plan"
                if method == "C":
                    roles[prefix + ".rank"] = "rank"
                slots.update({key: {"role": role, "checkpoint": checkpoint} for key, role in roles.items()})
    return {"blocks": blocks, "slots": slots, "outputs": outputs}


def parse_angles(value: Any) -> list[dict]:
    if not isinstance(value, dict) or set(value) != {"angles"} or not isinstance(value["angles"], list) or len(value["angles"]) != 10:
        raise ContractError("a plan must contain exactly ten angle records")
    seen = set()
    for index, angle in enumerate(value["angles"], 1):
        if (not isinstance(angle, dict) or set(angle) != {"id", "angle"}
                or angle["id"] != f"angle-{index:02d}" or not isinstance(angle["angle"], str)
                or not angle["angle"].strip() or len(angle["angle"]) > 2000 or "\x00" in angle["angle"]):
            raise ContractError("invalid ordered angle record")
        normalized = _normalize(angle["angle"])
        if normalized in seen:
            raise ContractError("a plan repeats the same normalized angle")
        seen.add(normalized)
    return copy.deepcopy(value["angles"])


def parse_order(value: Any, response_ids: list[str]) -> list[str]:
    if (not isinstance(value, dict) or set(value) != {"order"} or not isinstance(value["order"], list)
            or len(value["order"]) != 10 or any(not isinstance(v, str) for v in value["order"])
            or len(set(value["order"])) != 10 or set(value["order"]) != set(response_ids)):
        raise ContractError("ranker must return a permutation of exactly the supplied response IDs")
    return value["order"][:]


def render_request(role: str, task: dict, *, angle: dict | None = None,
                   responses: list[dict] | None = None, templates: dict | None = None) -> dict:
    templates = templates or _templates()
    if role == "answer":
        text = task["prompt"]
        if angle is not None:
            text += "\n\n" + templates["angle_note"] + "\n" + json.dumps(angle, ensure_ascii=False)
        system = templates["answer_system"]
    elif role == "plan":
        text, system = task["prompt"], templates["plan_system"]
    elif role == "rank":
        if responses is None or len(responses) != 10:
            raise ContractError("ranker requires ten saved responses")
        text = json.dumps({"prompt": task["prompt"], "responses": [
            {"id": r["id"], "text": r["text"]} for r in responses]}, ensure_ascii=False)
        system = templates["rank_system"]
    else:
        raise ContractError("strategy only renders answer, plan and rank roles")
    return build_request(role, messages=[{"role": "user", "content": text}], system=system)


def _exposed_aliases() -> tuple[set[str], dict]:
    """Read prior exposed inputs, not ratings, unused answers or held-out rows."""
    aliases = {_prompt_hash(read_json(PROJECT / "fixtures/task.json")["prompt"])}
    ledger = read_json(PROJECT / "evidence/phase1a-data-readiness-r07/exposure-ledger.json")
    # Every exposed source group ID is already a digest of the normalized raw alias.
    aliases.update(g["group_id"].removeprefix("muce-prompt-") for g in ledger["groups"])
    aliases.update(g.removeprefix("muce-prompt-") for g in ledger["published_example_groups"])
    exposed = set(aliases)
    pairs = read_json(PROJECT / "runs/phase1-prepared/pairs.json")
    if not isinstance(pairs, list) or len(pairs) != 24:
        raise ContractError("historical exposed public pair inputs are unavailable")
    for pair in pairs:
        if pair.get("kind") != "creativity-pair" or not isinstance(pair.get("prompt"), str):
            raise ContractError("invalid historical exposed prompt")
        aliases.add(_prompt_hash(pair["prompt"]))
    return aliases, {"source_group_aliases": sorted(exposed), "all_exclusion_aliases": sorted(aliases),
                     "basis": "Phase0 synthetic prompt and previously exposed Phase1/MuCE group/effective prompts"}


def _study_inputs() -> dict:
    if os.getenv("BUDDHA2_IMAGE_ID") != IMAGE_ID:
        raise ContractError("preparation requires the retained pinned runtime image")
    if tuple(sys.version_info[:3]) != (3, 12, 15):
        raise ContractError("preparation requires Python 3.12.15 in the pinned runtime")
    source = PROJECT / ".upstream/novelty-bench/data/curated.jsonl"
    if file_hash(source) != CURATED_SHA256:
        raise ContractError("pinned curated source differs")
    excluded, exposure = _exposed_aliases()
    try:
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    except (ValueError, UnicodeError) as exc:
        raise ContractError("curated source is not valid JSONL") from exc
    selection = select_tasks(rows, file_hash(source), excluded)
    selection["eligibility_review"] = {
        "reviewer": "preparation analyst", "reviewed_records": 100,
        "eligible_english_text_only": 100,
        "notes": ["All 100 prompts were inspected without outcomes or scores.",
                  "curated-19 requests sound effects expressible as text; no audio input is needed.",
                  "curated-54 includes accented Unicode text; preserve exact UTF-8 source text."],
        "exposure": "All inspected curated prompts are development material, never fresh confirmation.",
        "confirmation_rows_opened": 0,
    }
    tasks = selection["tasks"]
    work = make_worklist(tasks)
    from .phase2_native import NativeAssessment

    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    source_files = tree_hashes(PROJECT / "src/buddha2")
    templates = _templates()
    return {"schema_version": 2, "kind": "phase2-study-preparation-v2", "specification": "0.10",
            "specification_sha256": file_hash(PROJECT / "evidence/phase2-r010/specification-0.10.md"),
            "preparation_start_sha256": file_hash(PROJECT / "evidence/phase2-r010/execution-start.json"),
            "runtime_image_id": IMAGE_ID,
            "runtime_python": "3.12.15",
            "upstream_pins": {"harness2": "1cfe254e8d25b15f37048c3730134686abe60335",
                              "novelty-bench": NB_COMMIT},
            "fixture": False, "execution_authorized": False, "tasks": tasks,
            "selection_policy": SELECTION, "source_audit": selection, "exposure": exposure,
            "worklist": work, "templates": templates, "profiles": FROZEN_PROFILES,
            "static_input_candidates": [{"task_id": task["id"], "role": role,
                                         **input_bound(render_request(role, task, templates=templates))}
                                        for task in tasks for role in ("answer", "plan")],
            "procedure_hashes": {m: digest({"templates": templates, "method": m}) for m in ("A", "B", "C")},
            "shared_generator_settings_sha256": digest({k: v for k, v in FROZEN_PROFILES["answer"].items()
                                                       if k not in {"input_limit", "reserved_output", "provider"}}),
            "native_evaluator": native.identity, "package_files": source_files,
            "lockfiles": {n: file_hash(PROJECT / n) for n in ("requirements.lock", "requirements-build.lock")},
            "human_check": {"task_ids": [t["id"] for t in tasks[:2]], "repeat": 1,
                            "readers": 2, "portfolios_per_reader": 6, "reader_time_minutes_max": 60,
                            "administration_minutes_max": 90, "reader_identities_bound": False,
                            "statuses": ["acceptable", "substantive concern", "cannot judge"]},
            "caps": {"proposed_micro_usd": 125_000_000, "canary_micro_usd": 5_000_000,
                     "generation_requests_max": 528, "group_requests_max": 72,
                     "quality_requests_max": 720, "total_requests_max": 1320, "retries": 0},
            "admission": ADMISSION_POLICY, "route_h_required": False, "crpo_activated": False,
            "failure_policy": {"attempts_per_slot_max": 1, "retries": 0, "replacements": 0,
                               "invalid_plan": "skip dependent B generation/assessment and C slots",
                               "invalid_rank": "skip C assessment; preserve B unchanged",
                               "refused_answer": "preserve [refused] text with refused status",
                               "empty_answer": "preserve [empty] text with empty status",
                               "truncated_answer": "preserve text with truncated status",
                               "unknown_delivery_or_usage": "retain reservation and halt phase",
                               "over_limit_input": "reject visibly without truncation or replacement",
                               "assessment": "fresh grouping per order; strict fold; no fallback or repair",
                               "expansion": "stop and review first counted canary before expansion"},
            "selection_rule": {"unit": "twelve equally weighted prompt means of two repeats",
                               "contrasts": ["B_minus_A", "C_minus_same_B"],
                               "requires": ["complete comparable native coverage", "two eligible independent readers",
                                            "no unresolved substantive concern for the candidate"],
                               "inconclusive_if": ["cannot judge", "compromised review", "differential missingness",
                                                   "unknown accounting"],
                               "sort": ["highest mean utility", "lowest actual generation/ranking cost", "A then B then C"],
                               "fixtures_select_real_seed": False},
            "remaining_live_prerequisites": ["verified provider input-admission bound",
                                             "applicable spending authorization",
                                             "provider credentials/account/model access",
                                             "two eligible pilot-output readers and availability",
                                             "confirm grouping cache-write billing before final reservation review"]}


def validate_study(study: dict, *, current_sources: bool = True) -> None:
    if (not isinstance(study, dict) or study.get("kind") != "phase2-study-preparation-v2"
            or study.get("study_sha256") != digest({k: v for k, v in study.items() if k != "study_sha256"})
            or study.get("profiles") != FROZEN_PROFILES or study.get("selection_policy") != SELECTION
            or study.get("worklist") != make_worklist(study["tasks"])):
        raise ContractError("stale or invalid frozen Phase 2 study")
    if current_sources and study["package_files"] != tree_hashes(PROJECT / "src/buddha2"):
        raise ContractError("package differs from the frozen study; use a new preparation identity")
    if current_sources and study["templates"] != _templates():
        raise ContractError("fixed templates differ from the frozen study")
    if current_sources:
        from .phase2_native import NativeAssessment

        if study["native_evaluator"] != NativeAssessment(PROJECT / ".upstream/novelty-bench").identity:
            raise ContractError("native evaluator differs from the frozen study")
        if study["lockfiles"] != {n: file_hash(PROJECT / n) for n in study["lockfiles"]}:
            raise ContractError("dependency lock differs from the frozen study")
        if study["specification_sha256"] != file_hash(PROJECT / "evidence/phase2-r010/specification-0.10.md"):
            raise ContractError("frozen preparation specification differs")
        source = PROJECT / ".upstream/novelty-bench/data/curated.jsonl"
        if file_hash(source) != CURATED_SHA256:
            raise ContractError("frozen task source differs")
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        tasks = select_tasks(rows, CURATED_SHA256, set(study["exposure"]["all_exclusion_aliases"]))["tasks"]
        if tasks != study["tasks"]:
            raise ContractError("frozen tasks differ from the declared source selection")
        if study["exposure"] != _exposed_aliases()[1]:
            raise ContractError("historical exposure exclusions differ")
    if study["procedure_hashes"] != {m: digest({"templates": study["templates"], "method": m}) for m in ("A", "B", "C")}:
        raise ContractError("procedure identity differs from its exact templates")


def prepare(output: Path) -> dict:
    output = _output(output)
    study = _study_inputs()
    study["study_sha256"] = digest(study)
    validate_study(study)
    write_once(output / "study.json", study)
    write_once(output / "worklist.json", study["worklist"])
    write_once(output / "templates.json", study["templates"])
    write_once(output / "source-inventory.json", study["source_audit"])
    write_once(output / "cost-sheet.json", cost_sheet(study))
    write_once(output / "authorization-request.json", {
        "study_sha256": study["study_sha256"], "authorized": False,
        "proposed_total_micro_usd": 125_000_000, "proposed_canary_micro_usd": 5_000_000,
        "live_admission_verified": False, "note": "Proposal only; not a dispatch grant."})
    from .phase2_analysis import build_human_packets

    human = build_human_packets(study, [], fixture=False)
    for reader, packet in human["packets"].items():
        write_once(output / "human" / f"{reader}-blank.json", packet)
    write_once(output / "human" / "private" / "unit-mapping.json", human["private_mapping"])
    write_bytes_once(output / "PREPARATION.md", (
        "# Phase 2A preparation\n\n"
        "Twelve development prompts, 24 blocks, 48 generated portfolios, 24 permutations and 72 assessment orders are frozen.\n\n"
        "No model calls have been made. The study is not spending authorization. Real dispatch is disabled because provider input admission is unverified.\n\n"
        "Inspect study.json, worklist.json, source-inventory.json, cost-sheet.json and templates.json. Blank human planning forms are not reader-facing packets or completed ratings.\n"
    ).encode())
    return {"status": "prepared-with-live-prerequisites", "study_sha256": study["study_sha256"],
            "tasks": 12, "blocks": 24, "request_slots_max": 1320, "provider_calls": 0,
            "live_ready": False, "output": str(output)}


def cost_sheet(study: dict) -> dict:
    counts = Counter(v["role"] for v in study["worklist"]["slots"].values())
    amounts = {role: counts[role] * reservation(role) for role in counts}
    canary = sum(reservation(v["role"]) for v in study["worklist"]["slots"].values()
                 if v["checkpoint"] == "canary")
    return {"study_sha256": study["study_sha256"], "price_date_local": "2026-10-25",
            "currency": "USD", "counts": dict(counts), "reservation_micro_usd_by_role": amounts,
            "full_declared_max_micro_usd": sum(amounts.values()), "canary_declared_max_micro_usd": canary,
            "proposed_cap_micro_usd": 125_000_000, "proposed_canary_micro_usd": 5_000_000,
            "scenarios_usd": {"working": 21.6792, "higher_reasoning": 106.3584},
            "authorized": False, "live_cap_certified": False,
            "limitation": "Frozen price/model envelope only; input admission and grouping cache-write assumptions need review before live use."}


def _object(text: str) -> dict:
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise ContractError("strategy response is not a complete JSON object") from exc
    if not isinstance(value, dict):
        raise ContractError("strategy response must be a JSON object")
    return value


class WalkthroughTransport:
    """A deterministic software fixture; native judge texts are never model scores."""

    fixture = True

    def __init__(self):
        self.calls = 0
        self.slot = ""

    def create(self, role: str, request: dict) -> dict:
        self.calls += 1
        payload: Any
        if role == "plan":
            payload = {"angles": [{"id": f"angle-{i:02d}", "angle": f"Synthetic content direction {i}"}
                                  for i in range(1, 11)]}
        elif role == "rank":
            supplied = _object(request["messages"][0]["content"])
            payload = {"order": [row["id"] for row in reversed(supplied["responses"])]}
        elif role == "group":
            payload = {"groups": [[i, i + 1] for i in range(0, 10, 2)]}
        elif role == "quality":
            match = re.search(r"Fixture group (\d)", request["messages"][0]["content"])
            payload = {"score": 9 - int(match[1]) if match else 5}
        else:
            index = int(self.slot.rsplit(".", 1)[-1])
            payload = f"Fixture group {index // 2}: explicitly synthetic example."
        return {"model": request["model"], "text": payload if isinstance(payload, str) else json.dumps(payload),
                "stop_reason": "stop" if role == "group" else "end_turn",
                "request_id": "fixture-provider-" + digest({"slot": self.slot, "request": request})[:20],
                "message_id": "fixture-message-" + digest({"slot": self.slot, "request": request})[:20],
                "latency_seconds": 0.001,
                "usage": {"input_tokens": 100, "output_tokens": 40,
                          "service_tier": "default" if role == "group" else "standard"}}


def _response(result: dict, *, study_sha256: str, fixture: bool,
              slot_id: str, role: str, request: dict) -> dict:
    if (not isinstance(result, dict) or result.get("status") != "response"
            or result.get("fixture") is not fixture or result.get("study_sha256") != study_sha256
            or result.get("slot_id") != slot_id or result.get("role") != role
            or result.get("request_sha256") != digest(request)
            or not isinstance(result.get("dispatch_id"), str) or not result["dispatch_id"]
            or type(result.get("spent_micro_usd")) is not int or result["spent_micro_usd"] < 0
            or type(result.get("reserved_micro_usd")) is not int or result["reserved_micro_usd"] != 0):
        raise ContractError("unresolved dispatch; no dependent request may proceed")
    raw = result.get("response")
    if (not isinstance(raw, dict) or not isinstance(raw.get("model"), str)
            or re.fullmatch(re.escape(request["model"]) + r"(?:-\d{8})?", raw["model"]) is None
            or not isinstance(raw.get("text"), str) or not isinstance(raw.get("usage"), dict)
            or raw.get("stop_reason") not in ("end_turn", "refusal", "max_tokens")):
        raise ContractError("unsupported generation identity, response or stop reason")
    return copy.deepcopy(raw)


def generate_order(study: dict, task: dict, repeat: int, method: str,
                   dispatch: Any, *, checkpoint: str, fixture: bool) -> dict:
    """One fixed procedure; no adaptive proposal, score access or hidden retries."""
    if method not in ("A", "B") or type(fixture) is not bool:
        raise ContractError("generation condition must be A or B with explicit fixture identity")
    if not isinstance(study.get("tasks"), list) or task not in study["tasks"]:
        raise ContractError("generation requires the unchanged selected study task")
    prefix = slot_prefix(task["id"], method, repeat)
    ids, angles, returned = [], None, []
    if method == "B":
        slot = prefix + ".plan"
        request = render_request("plan", task, templates=study["templates"])
        result = dispatch(slot, "plan", request, checkpoint=checkpoint)
        raw = _response(result, study_sha256=study["study_sha256"], fixture=fixture,
                        slot_id=slot, role="plan", request=request)
        if raw["stop_reason"] != "end_turn":
            raise ContractError("planner did not finish normally; dependent slots are skipped")
        angles = parse_angles(_object(raw["text"]))
        ids.append(slot)
        returned.append(raw["model"])
    responses = []
    for index in range(10):
        slot = f"{prefix}.answer.{index:02d}"
        request = render_request("answer", task, angle=angles[index] if angles else None,
                                 templates=study["templates"])
        result = dispatch(slot, "answer", request, checkpoint=checkpoint)
        raw = _response(result, study_sha256=study["study_sha256"], fixture=fixture,
                        slot_id=slot, role="answer", request=request)
        if returned and raw["model"] != returned[0]:
            raise ContractError("returned generator model changed within a portfolio")
        status = ("refused" if raw["stop_reason"] == "refusal" else "truncated"
                  if raw["stop_reason"] == "max_tokens" else "empty" if not raw["text"].strip() else "ok")
        text = "[refused]" if status == "refused" else raw["text"] if raw["text"].strip() else f"[{status}]"
        responses.append({"id": "response-" + digest({"study": study["study_sha256"], "slot": slot,
                          "text": text, "status": status})[:24], "text": text, "status": status, "request_id": slot})
        ids.append(slot)
        returned.append(raw["model"])
    if len(set(returned)) != 1:
        raise ContractError("returned generator model changed within a portfolio")
    model = {"requested": "fixture-no-model" if fixture else FROZEN_PROFILES["answer"]["model"],
             "returned": "fixture-no-model" if fixture else returned[0]}
    return make_portfolio(task, responses, method=method, repeat=repeat, model=model,
                          study_sha256=study["study_sha256"],
                          settings_sha256=study["shared_generator_settings_sha256"],
                          procedure_sha256=study["procedure_hashes"][method], request_ids=ids, fixture=fixture)


def rank_order(study: dict, parent: dict, dispatch: Any, *, checkpoint: str) -> dict:
    from .phase2_contracts import validate_portfolio

    validate_portfolio(parent)
    provenance = parent["provenance"]
    parent_prefix = slot_prefix(parent["task"]["id"], "B", provenance["repeat"])
    expected_requests = [parent_prefix + ".plan"] + [f"{parent_prefix}.answer.{i:02d}" for i in range(10)]
    requested_model = "fixture-no-model" if parent["fixture"] else FROZEN_PROFILES["answer"]["model"]
    if (provenance["method"] != "B" or provenance["study_sha256"] != study["study_sha256"]
            or parent["task"] not in study["tasks"]
            or provenance["settings_sha256"] != study["shared_generator_settings_sha256"]
            or provenance["procedure_sha256"] != study["procedure_hashes"]["B"]
            or provenance["request_ids"] != expected_requests
            or provenance["model"]["requested"] != requested_model
            or re.fullmatch(re.escape(requested_model) + ("" if parent["fixture"] else r"(?:-\d{8})?"),
                            provenance["model"]["returned"]) is None):
        raise ContractError("ranker requires an unchanged B parent from this study and procedure")
    slot = slot_prefix(parent["task"]["id"], "C", parent["provenance"]["repeat"]) + ".rank"
    request = render_request("rank", parent["task"], responses=parent["responses"], templates=study["templates"])
    result = dispatch(slot, "rank", request, checkpoint=checkpoint)
    raw = _response(result, study_sha256=study["study_sha256"], fixture=parent["fixture"],
                    slot_id=slot, role="rank", request=request)
    if raw["stop_reason"] != "end_turn":
        raise ContractError("ranker did not finish normally")
    if not parent["fixture"] and raw["model"] != provenance["model"]["returned"]:
        raise ContractError("reranker returned a different actual generator model from its B parent")
    order = parse_order(_object(raw["text"]), [r["id"] for r in parent["responses"]])
    return permute_portfolio(parent, order, request_id=slot,
                             model={"requested": "fixture-no-model" if parent["fixture"] else FROZEN_PROFILES["rank"]["model"],
                                    "returned": "fixture-no-model" if parent["fixture"] else raw["model"]},
                             settings_sha256=study["shared_generator_settings_sha256"],
                             procedure_sha256=study["procedure_hashes"]["C"])


def analyze(study: dict, assessments: list[dict], human: list[dict], costs: dict,
            *, fixture: bool, portfolios: list[dict] | None = None,
            state: dict | None = None, native: Any = None) -> dict:
    """Twelve prompt-level descriptive comparisons; never turn missingness into success."""
    compromised = False
    if not fixture or portfolios is not None:
        from .phase2_analysis import validate_analysis_evidence, validate_human_evidence

        if portfolios is None or state is None or native is None:
            raise ContractError("analysis needs bound portfolios, journal and native evaluator")
        evidence = validate_analysis_evidence(study, assessments, portfolios, state, native, fixture=fixture)
        compromised = evidence["selection_inconclusive"]
        if costs != evidence["generation_costs_by_method"]:
            raise ContractError("analysis costs differ from the accounted generation/ranking records")
        checked_human = validate_human_evidence(study, human, portfolios, fixture=fixture)
        human = checked_human["records"]
        compromised = compromised or checked_human["selection_inconclusive"]
    expected = {(t["id"], repeat, method) for t in study["tasks"]
                for repeat in (1, 2) for method in ("A", "B", "C")}
    indexed = {}
    for row in assessments:
        key = (row.get("task_id"), row.get("repeat"), row.get("method"))
        if key not in expected or key in indexed or row.get("fixture") is not fixture:
            raise ContractError("duplicate, mixed or unexpected assessment")
        for metric in ("utility", "distinct"):
            value = row.get("metrics", {}).get(metric)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                      or not 0 <= value <= 10):
                raise ContractError("invalid assessment metric")
        indexed[key] = row
    human_expected = {(tid, m, reader) for tid in study["human_check"]["task_ids"]
                      for m in ("A", "B", "C") for reader in (
                          ("fixture-R1", "fixture-R2") if fixture else ("R1", "R2"))}
    human_index = {}
    for row in human:
        key = (row.get("task_id"), row.get("method"), row.get("reader_id"))
        if (key not in human_expected or key in human_index or row.get("fixture") is not fixture
                or row.get("repeat") != 1 or row.get("status") not in ("acceptable", "substantive concern", "cannot judge")
                or not isinstance(row.get("reason"), str) or not row["reason"].strip()):
            raise ContractError("invalid or duplicate human diagnostic record")
        human_index[key] = row
    complete = len(indexed) == 72 and all(r.get("status") in ("ok", "scored")
        and r.get("metrics", {}).get("utility") is not None for r in indexed.values())
    means, paired = {}, []
    for task in study["tasks"]:
        tid = task["id"]
        values = {}
        for method in ("A", "B", "C"):
            rows = [indexed.get((tid, rep, method)) for rep in (1, 2)]
            values[method] = sum(r["metrics"]["utility"] for r in rows if r is not None) / 2 if all(
                r is not None and r.get("status") in ("ok", "scored") and r["metrics"]["utility"] is not None for r in rows) else None
        paired.append({"task_id": tid, "means": values,
                       "B_minus_A": values["B"] - values["A"] if values["A"] is not None and values["B"] is not None else None,
                       "C_minus_B": values["C"] - values["B"] if values["B"] is not None and values["C"] is not None else None})
    for method in ("A", "B", "C"):
        means[method] = sum(r["means"][method] for r in paired) / 12 if complete else None
    eligible = []
    human_complete = len(human_index) == 12
    compromised = compromised or any(r["status"] == "cannot judge" or r.get("recognition") is True
                                     or r.get("missing_context") is True for r in human)
    if complete and human_complete and not compromised:
        for method in ("A", "B", "C"):
            if all(row["status"] == "acceptable" for key, row in human_index.items() if key[1] == method):
                eligible.append(method)
    if any(type(costs.get(m)) is not int or costs[m] < 0 for m in eligible):
        raise ContractError("selection needs known integer generation/ranking costs")
    def selection_key(method: str) -> tuple[float, int, int]:
        mean = means[method]
        if mean is None:
            raise ContractError("selection requires complete prompt means")
        return -mean, costs[method], ("A", "B", "C").index(method)

    selected = sorted(eligible, key=selection_key)[0] if eligible else None

    def difference(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None
    def method_summary(metric: str) -> tuple[dict, dict, dict]:
        averages, ranges, coverage = {}, {}, {}
        for method in ("A", "B", "C"):
            prompt_values = []
            coverage[method] = 0
            for task in study["tasks"]:
                vals = []
                for repeat in (1, 2):
                    row = indexed.get((task["id"], repeat, method), {})
                    if metric != "distinct" and row.get("status") not in ("ok", "scored"):
                        continue
                    if metric in ("utility", "distinct"):
                        value = row.get("metrics", {}).get(metric)
                    else:
                        scores = row.get("native", {}).get("fields", {}).get("generation_scores", [])
                        heads = [v for v in scores if v is not None]
                        value = scores[0] if scores and metric == "first_answer_quality" else sum(heads) / len(heads) if heads else None
                    if value is not None:
                        vals.append(value)
                        coverage[method] += 1
                if len(vals) == 2:
                    prompt_values.append(sum(vals) / 2)
            averages[method] = sum(prompt_values) / 12 if len(prompt_values) == 12 else None
            ranges[method] = {"minimum": min(prompt_values), "maximum": max(prompt_values)} if prompt_values else None
        return averages, ranges, coverage

    _, utility_ranges, utility_coverage = method_summary("utility")
    distinct_means, distinct_ranges, distinct_coverage = method_summary("distinct")
    head_means, head_ranges, head_coverage = method_summary("head_quality")
    first_means, first_ranges, first_coverage = method_summary("first_answer_quality")
    response_counts: dict = {}
    for method in ("A", "B", "C"):
        ps = [p for p in portfolios or [] if p["provenance"]["method"] == method]
        statuses = Counter(r["status"] for p in ps for r in p["responses"])
        response_counts[method] = {"scheduled_presentations": 240, "recorded": sum(statuses.values()),
                                   "missing": 240 - sum(statuses.values()), "statuses": dict(statuses)}
    ledger = state or {"results": {}, "reserved_micro_usd": 0, "spent_micro_usd": 0}
    role_costs: Counter = Counter()
    role_latency: dict[str, list[float]] = {}
    for result in ledger["results"].values():
        role_costs[result["role"]] += result.get("spent_micro_usd") or 0
        latency = (result.get("response") or {}).get("latency_seconds")
        if latency is not None and type(latency) in (int, float) and math.isfinite(latency) and latency >= 0:
            role_latency.setdefault(result["role"], []).append(latency)
    return {"kind": "phase2-walkthrough-analysis" if fixture else "phase2-development-analysis",
            "fixture": fixture, "status": "complete-development" if selected else "inconclusive",
            "independent_prompts": 12, "scheduled_order_assessments": 72,
            "assessment_records": len(indexed), "scored_orders": sum(r.get("metrics", {}).get("utility") is not None for r in indexed.values()),
            "missing_orders": len(expected - set(indexed)), "human_records": len(human_index),
            "missing_human_judgments": len(human_expected - set(human_index)),
            "paired_prompt_means": paired, "mean_utility": means,
            "utility_range": utility_ranges, "utility_scored_order_coverage": utility_coverage,
            "mean_distinct": distinct_means, "distinct_range": distinct_ranges,
            "distinct_scored_order_coverage": distinct_coverage,
            "head_quality": {"mean_of_prompt_means": head_means, "prompt_mean_range": head_ranges,
                             "orders_with_head_scores": head_coverage},
            "first_answer_quality": {"mean_of_prompt_means": first_means, "prompt_mean_range": first_ranges,
                                     "scored_order_coverage": first_coverage},
            "response_presentations": response_counts,
            "order_statuses": dict(Counter(r.get("status", "missing") for r in indexed.values())),
            "human_statuses": dict(Counter(r["status"] for r in human)),
            "human_compromised_or_cannot_judge": compromised,
            "generation_ranking_cost_micro_usd_by_candidate": costs,
            "unique_request_cost_micro_usd_by_role": dict(role_costs),
            "accounted_total_micro_usd": ledger.get("spent_micro_usd"),
            "unresolved_reservation_micro_usd": ledger.get("reserved_micro_usd"),
            "latency_seconds_by_role": {role: {"measured_requests": len(vals), "total": sum(vals),
                                               "minimum": min(vals), "maximum": max(vals)} for role, vals in role_latency.items()},
            "contrasts": {"B_minus_A": difference(means["B"], means["A"]),
                          "C_minus_B": difference(means["C"], means["B"])},
            "selected_method": None if fixture else selected, "synthetic_selected_method": selected if fixture else None,
            "limitations": ["Development only; fixtures never establish model effectiveness or select a real seed.",
                            "Ranges describe the twelve within-prompt repeat means; missing metrics stay missing.",
                            "C includes its B parent generation cost for candidate comparison; total ledger cost counts every request once.",
                            "B/C presentations share texts; counts are not independent tasks or additional generated answers.",
                            "Head-quality averages weight orders/prompts, not pooled heads; first answer is the first native group head."]}


def walkthrough(study: dict, output: Path) -> dict:
    validate_study(study)
    output = _output(output)
    transport = WalkthroughTransport()
    grant = {"study_sha256": study["study_sha256"], "authorization_id": "synthetic-walkthrough-only",
             "authorized": False, "cap_micro_usd": 125_000_000,
             "canary_cap_micro_usd": 5_000_000, "expansion_authorized": True}
    dispatcher = Dispatcher(output / "journal", study_sha256=study["study_sha256"],
                            slots=study["worklist"]["slots"], authorization=grant, transport=transport)
    from .phase2_native import NativeAssessment

    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    def dispatch(slot, role, request, **kwargs):
        # Fixture-only logical IDs never alter the provider request body.
        transport.slot = slot
        return dispatcher.dispatch(slot, role, request, **kwargs)
    tasks = {t["id"]: t for t in study["tasks"]}
    assessments, portfolios = [], []
    for block in study["worklist"]["blocks"]:
        task, repeat, checkpoint = tasks[block["task_id"]], block["repeat"], block["checkpoint"]
        saved = {}
        for method in block["generation_order"]:
            saved[method] = generate_order(study, task, repeat, method, dispatch,
                                           checkpoint=checkpoint, fixture=True)
        saved["C"] = rank_order(study, saved["B"], dispatch, checkpoint=checkpoint)
        for method in ("A", "B", "C"):
            portfolio = saved[method]
            prefix = slot_prefix(task["id"], method, repeat)
            write_once(output / "portfolios" / f"{prefix}.json", portfolio)
            export_native(portfolio, output / "native" / prefix)
            restored = native.load_export(output / "native" / prefix)
            if restored != portfolio:
                raise ContractError("native exchange changed the portfolio")
            assessment = native.assess(restored, dispatch, checkpoint=checkpoint)
            write_once(output / "assessments" / f"{prefix}.json", assessment)
            assessments.append({**assessment, "method": method, "repeat": repeat, "order_id": prefix,
                                "study_sha256": study["study_sha256"]})
            portfolios.append(portfolio)
    from .phase2_analysis import build_human_packets

    packet_set = build_human_packets(study, portfolios, fixture=True)
    human = list(packet_set["packets"].values())
    for form in human:
        form["reader_reference"] = "synthetic-" + form["reader_id"]
        form["due_date"] = "2026-10-25"
        form["delivered_on"] = "2026-10-25"
        form["eligibility"] = {key: key != "actual_human" for key in form["eligibility"]}
        for judgment in form["judgments"]:
            judgment.update({"status": "acceptable", "reason": "Synthetic human-form fixture; no person rated this.",
                             "recognition": False, "missing_context": False,
                             "task_fitness_notes": "Synthetic software fixture only.",
                             "variety_notes": "Synthetic software fixture only.",
                             "duplication_notes": "Synthetic software fixture only."})
        write_once(output / "human" / f"{form['reader_id']}-fixture.json", form)
    write_once(output / "human" / "private" / "unit-mapping.json", packet_set["private_mapping"])
    state = replay_dispatch(output / "journal")
    costs = _generation_costs(portfolios, state)
    report = analyze(study, assessments, human, costs, fixture=True,
                     portfolios=portfolios, state=state, native=native)
    report.update({"provider_calls": state["provider_calls"], "synthetic_dispatches": state["attempts"],
                   "new_fixture_transport_calls": transport.calls, "experiment_api_spend_usd": 0,
                   "synthetic_accounting_micro_usd": state["spent_micro_usd"], "real_human_ratings": 0})
    # Per-call replay can be checked without changing the immutable final report.
    report.pop("new_fixture_transport_calls")
    write_once(output / "human-fixtures.json", human)
    write_once(output / "coverage.json", slot_coverage(study, state["results"], portfolios, assessments))
    write_once(output / "analysis.json", report)
    write_bytes_once(output / "report.md", ("# Synthetic Phase 2 walkthrough\n\n"
        "All answers, plans, rankings, judge outputs, usage, latency and reader forms are deterministic fixtures. No provider or human was called.\n\n"
        f"48 generated fixture portfolios, 24 permutations, 72 native assessment instances. Synthetic dispatches: {state['attempts']}.\n\n"
        f"Synthetic contrasts: {json.dumps(report['contrasts'])}. No real strategy has been selected.\n\n"
        "The native import/call construction/strict folding/utility and separate export identities were exercised. Live admission remains blocked; consult the preparation report.\n").encode())
    return {"status": "synthetic-walkthrough-complete", "orders": 72, "provider_calls": 0,
            "new_fixture_dispatches": transport.calls, "synthetic_dispatches": state["attempts"],
            "output": str(output)}


def _generation_costs(portfolios: list[dict], state: dict) -> dict:
    costs = {}
    for method in ("A", "B", "C"):
        selected = [p for p in portfolios if p["provenance"]["method"] == method]
        slots = {slot for p in selected for slot in p["provenance"]["request_ids"]}
        costs[method] = sum(state["results"][slot]["spent_micro_usd"] for slot in slots) if len(selected) == 24 else None
    return costs


def replay_assessments(study: dict, output: Path) -> dict:
    validate_study(study)
    output = _output(output)
    state = replay_dispatch(output / "journal")
    from .phase2_native import NativeAssessment

    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    def saved(slot, role, request, **_):
        result = state["results"].get(slot)
        if not result or result["role"] != role or result["request_sha256"] != digest(request):
            raise ContractError("saved request does not match reassessment")
        return result
    count, portfolios, assessments = 0, [], []
    for path in sorted((output / "portfolios").glob("*.json")):
        portfolio = read_json(path)
        prefix = slot_prefix(portfolio["task"]["id"], portfolio["provenance"]["method"], portfolio["provenance"]["repeat"])
        assessment = read_json(output / "assessments" / f"{prefix}.json")
        if native.assess(portfolio, saved) != assessment:
            raise ContractError("saved native assessment failed exact replay")
        portfolios.append(portfolio)
        assessments.append({**assessment, "method": portfolio["provenance"]["method"],
                            "repeat": portfolio["provenance"]["repeat"], "order_id": prefix,
                            "study_sha256": study["study_sha256"]})
        count += 1
    if count != 72:
        raise ContractError("walkthrough reassessment coverage is incomplete")
    if not state["fixture"]:
        raise ContractError("this offline walkthrough replay requires explicitly synthetic evidence")
    analysis = analyze(study, assessments, read_json(output / "human-fixtures.json"),
                       _generation_costs(portfolios, state), fixture=True,
                       portfolios=portfolios, state=state, native=native)
    final = read_json(output / "analysis.json")
    if any(final.get(key) != value for key, value in analysis.items()):
        raise ContractError("saved analysis failed exact replay")
    if slot_coverage(study, state["results"], portfolios, assessments) != read_json(output / "coverage.json"):
        raise ContractError("saved coverage failed exact replay")
    return {"status": "replayed", "native_assessments": count, "provider_calls": 0,
            "analysis_identical": True, "coverage_identical": True,
            "generation_requests": 0, "journal_attempts_unchanged": state["attempts"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    for name in ("walkthrough", "replay"):
        p = commands.add_parser(name)
        p.add_argument("--study", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--study", type=Path, required=True)
    exp = commands.add_parser("export")
    exp.add_argument("--portfolio", type=Path, required=True)
    exp.add_argument("--output", type=Path, required=True)
    imp = commands.add_parser("import")
    imp.add_argument("--source", type=Path, required=True)
    imp.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from .__main__ import _offline, _upstreams

        _offline()
        _upstreams()
        if args.command == "prepare":
            result = prepare(args.output)
        elif args.command in ("walkthrough", "replay"):
            study = read_json(args.study)
            result = walkthrough(study, args.output) if args.command == "walkthrough" else replay_assessments(study, args.output)
        elif args.command == "inspect":
            study = read_json(args.study)
            validate_study(study)
            result = {"study_sha256": study["study_sha256"], "tasks": study["tasks"],
                      "counts": cost_sheet(study), "live_ready": False,
                      "remaining_live_prerequisites": study["remaining_live_prerequisites"]}
        elif args.command == "export":
            export_native(read_json(args.portfolio), _output(args.output))
            result = {"status": "exported", "provider_calls": 0}
        else:
            portfolio = import_native(args.source)
            write_once(_output(args.output) / "portfolio.json", portfolio)
            result = {"status": "imported", "portfolio_sha256": digest(portfolio), "provider_calls": 0}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ContractError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
