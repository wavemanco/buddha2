"""Read-only transcript evidence for the counted native readiness path.

The proof establishes mechanical delivery, lineage and normal completion.  It
does not grade the ideas in an edit or the substantive reasons for KEEP_BASE.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from buddha2.artifacts import ContractError, digest
from followups.phase3a_compat_c1_v1.mocks import verify_delivery
from followups.phase3a_compat_c1_v1.support import OPENCODE_FILES, PRIVATE

from . import contract
from . import transport as bounded
from .support import NATIVE, ROOT


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sealed(value: dict) -> None:
    _require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "readiness record seal differs")


def _file(root: Path, name: str, hashes: dict[str, str]) -> bytes:
    rel = PurePosixPath(name)
    _require(bool(rel.parts) and not rel.is_absolute() and ".." not in rel.parts and ":" not in name
             and "\\" not in name and not any(part.lower() in PRIVATE for part in rel.parts), "unsafe readiness evidence path")
    path = root.joinpath(*rel.parts)
    _require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)),
             "linked readiness evidence")
    _require(path.is_file() and path.stat().st_size <= 2_000_000, "missing/oversized readiness evidence")
    data = path.read_bytes()
    data.decode("utf-8", errors="strict")
    hashes[name] = _sha(data)
    return data


def _read(root: Path, name: str, hashes: dict[str, str]) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate readiness JSON key")
            result[key] = value
        return result
    value = json.loads(_file(root, name, hashes), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite readiness JSON")))
    _require(type(value) is dict, "readiness artifact must be an object")
    return value


def _body(body: dict, normalized: set[str]) -> dict:
    """Permit absent direct-caller metadata only in a proof-parser copy."""
    result = copy.deepcopy(body)
    for message in result["messages"]:
        if message.get("role") != "assistant" or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if block.get("type") != "tool_use":
                continue
            if "caller" not in block:
                normalized.add(block["id"])
                block["caller"] = {"type": "direct"}
            _require(block["caller"] == {"type": "direct"}, "unsupported actual tool caller")
    return result


def _system(body: dict, configured: str, cwd: str | None) -> str:
    parts = body.get("system")
    if not isinstance(parts, list) or not parts or not all(isinstance(p, dict) and p.get("type") == "text"
             and isinstance(p.get("text"), str) for p in parts):
        raise ContractError("actual authoring SYSTEM is missing")
    text = "\n".join(p["text"] for p in parts)
    _require(text.startswith(configured), "actual authoring SYSTEM does not start with its configured profile")
    tail = text[len(configured):]
    match = re.fullmatch(
        r"\nYou are powered by the model named claude-opus-5\. The exact model ID is anthropic/claude-opus-5\n"
        r"Here is some useful information about the environment you are running in:\n<env>\n"
        r"  Working directory: (?P<cwd>/tmp/harness2-prop-[A-Za-z0-9_-]+)\n"
        r"  Workspace root folder: (?P<workspace>/[^\r\n<>]*)\n"
        r"  Is directory a git repo: no\n  Platform: linux\n"
        r"  Today's date: [A-Za-z]{3} [A-Za-z]{3} [ 0-9][0-9]? [0-9]{4}\n</env>", tail)
    if match is None:
        raise ContractError("actual SYSTEM has an unexpected instruction layer/environment")
    actual = match["cwd"]
    _require(cwd is None or actual == cwd, "editor conversation changed its working directory")
    _require(".." not in PurePosixPath(match["workspace"]).parts, "unexpected authoring workspace")
    return actual


def _without_cache(value: Any) -> Any:
    if isinstance(value, dict):
        result = {k: _without_cache(v) for k, v in value.items() if k != "cache_control"}
        if result.get("type") == "tool_use" and "caller" not in result:
            result["caller"] = {"type": "direct"}
        return result
    return [_without_cache(v) for v in value] if isinstance(value, list) else value


def _after_mutation(body: dict, identity: str) -> dict:
    found = []
    for index, message in enumerate(body["messages"]):
        blocks = message.get("content")
        if message.get("role") == "assistant" and isinstance(blocks, list) and any(
                b.get("type") == "tool_use" and b.get("id") == identity for b in blocks):
            found.append(index)
    _require(len(found) == 1, "mutation lacks its exact actual assistant history")
    suffix = body["messages"][found[0] + 1:]
    acknowledgments = [b for m in suffix if m.get("role") == "user" and isinstance(m.get("content"), list)
                        for b in m["content"] if b.get("type") == "tool_result" and b.get("tool_use_id") == identity]
    _require(len(acknowledgments) == 1 and not acknowledgments[0].get("is_error"), "mutation failed or lacks its tool result")
    return {"messages": suffix}


def _sources(search: Path, prefix: str, manifest: dict, hashes: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    original, views = {}, {}
    for entry in manifest["required_evidence"]:
        joined, cursor = [], 0
        _require(isinstance(entry.get("chunks"), list) and entry["chunks"], "required evidence has no lossless views")
        for chunk in entry["chunks"]:
            name = prefix + "/context-view/" + chunk["path"]
            raw = _file(search, name, hashes)
            _require(len(raw) == chunk["bytes"] and _sha(raw) == chunk["sha256"] and chunk["offset"] == 1
                     and chunk["limit"] == len(raw.decode().splitlines()), "lossless evidence chunk changed")
            view = json.loads(raw)
            _require(view["source_path"] == entry["path"] and view["source_sha256"] == entry["sha256"]
                     and view["char_start"] == chunk["char_start"] == cursor and view["char_end"] == chunk["char_end"]
                     and type(view["text"]) is list and all(type(t) is str for t in view["text"]), "lossless view identity changed")
            text = "".join(view["text"])
            _require(cursor + len(text) == view["char_end"], "lossless evidence range is incomplete")
            joined.append(text)
            cursor = view["char_end"]
            _require(chunk["path"] not in views, "duplicate lossless evidence view")
            views[chunk["path"]] = raw.decode("utf-8")
        data = "".join(joined).encode("utf-8")
        _require(len(data) == entry["bytes"] and _sha(data) == entry["sha256"]
                 and manifest["context_inventory"][entry["path"]] == {"bytes": len(data), "sha256": _sha(data)},
                 "lossless views omit/rewrite original evidence")
        _require(entry["path"] not in original, "duplicate required source")
        original[entry["path"]] = data.decode("utf-8")
    expected = contract._layout(manifest["role"])[1]
    _require([(e["path"], e["kind"]) for e in manifest["required_evidence"]] == expected,
             "role-specific required evidence was omitted or reordered")
    return original, views


def verify_readiness(study: dict, run: Path, state: dict, branch: dict, fixture: bool) -> dict:
    """Validate normal native completion and delivered evidence without any calls/writes."""
    try:
        return _verify(study, run, state, branch, fixture)
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("counted readiness evidence is incomplete or invalid") from error


def _verify(study: dict, run: Path, state: dict, branch: dict, fixture: bool) -> dict:
    _require(type(fixture) is bool and state["fixture"] is fixture and state["study_sha256"] == study["study_sha256"]
             and state["status"] == "ready" and all(state[k] == 0 for k in (
                 "reserved_micro_usd", "reserved_input_tokens", "reserved_output_tokens")), "readiness accounting has a hold/liability")
    _require(set(state["intents"]) == set(state["results"]) and all(
        r["status"] == "response" and r.get("failure") is None and r["reserved_micro_usd"] == 0
        for r in state["results"].values()), "readiness accounting is not fully known")
    _sealed(branch)
    _require(branch["study_sha256"] == study["study_sha256"] and branch["fixture"] is fixture
             and branch["pilot"] == "p3a-01" and branch["arm"] == "adaptive" and branch["failure"] is None,
             "foreign/incomplete readiness branch")
    result, c1 = branch["result"], branch["c1_evidence"]
    _require(result["status"] == "complete" and result["fixture"] is fixture
             and result["study_sha256"] == study["study_sha256"] and result["authentic"] is (not fixture)
             and branch["portfolio_sha256"] == digest(result["portfolio"]), "native readiness completion/authenticity differs")
    _require(c1["fixture"] is fixture and c1["study_sha256"] == study["study_sha256"]
             and c1["source_sha256"] == study["source_sha256"], "C1 readiness source identity differs")
    mode = result["native"]["modes"]["agg"]
    ledger = mode["ledger"]
    _require(mode["ok"] and ledger["P"] == ledger["expected_P"] == 3 and ledger["R"] == ledger["expected_R"] == 4
             and set(result["rollouts"]) == {"base1", "inv1", "dom1", "agg1"}, "native readiness path lacks its four executions")
    selection = result["native"]["selections"]["agg"]
    _require(selection["ok"] and selection["trivial"] and selection["chosen_label"] == "agg1" and not selection["fallback"],
             "native k1 readiness selection changed")
    stages = {s["label"]: s for s in result["stage_dispositions"]}
    _require(set(stages) == {"inv1", "dom1", "agg1"} and all(s["authentic_eligible"] and s["model_backed"]
             and not s["fell_back"] and not s["terminal_note_used"] and not s["cap_limited_unchanged"]
             for s in stages.values()), "readiness requires three normal eligible native stages")
    search = Path(run) / "search/p3a-01/adaptive"
    _require(search.is_absolute() and ".." not in search.parts and Path(run).is_relative_to(NATIVE), "invalid readiness run path")
    hashes: dict[str, str] = {}
    scoped = {slot for slot, row in state["intents"].items() if row["cell"] == "p3a-01:adaptive"}
    for rollout in result["rollouts"].values():
        _require(rollout["status"] == "complete" and len(rollout["requests"]) == 12, "readiness solver rollout incomplete")
        for response in rollout["requests"]:
            _require(response == state["results"][response["slot_id"]] and response["slot_id"] in scoped,
                     "solver execution differs from authoritative readiness results")
    expected_binding = {key: _sha((ROOT / name).read_bytes()) for key, name in {
        "adapter_sha256": "followups/phase3a_c1_completion_v3/adapter.py",
        "contract_sha256": "followups/phase3a_c1_completion_v2/contract.py",
        "definition_sha256": "PHASE3A_C1_COMPLETION_R2_DEFINITION.md",
        "parent_boundary_sha256": "followups/phase3a_v1/editor.py"}.items()}
    _require(c1["binding"] == expected_binding, "frozen C1 adapter/profile binding differs")
    upstream = contract._upstream()
    sessions = []
    for stage_name in ("inv1", "dom1", "agg1"):
        accepted = stages[stage_name]["accepted_editor_sessions"]
        _require(len(accepted) == 1 and re.fullmatch(stage_name + r"\.a[12]", accepted[0]), "native accepted session identity differs")
        label = accepted[0]
        prefix = "editor-audit/c1-contracts/" + label
        record = _read(search, prefix + "/result.json", hashes)
        _sealed(record)
        _require(record == c1["sessions"][label] and record["fixture"] is fixture and record["status"] == "returned"
                 and record["native_reply_ok"] and record["auxiliary_removed"] and record["binding"] == expected_binding
                 and record["study_sha256"] == study["study_sha256"] and record["source_sha256"] == study["source_sha256"],
                 "saved C1 session differs from its source-bound branch")
        manifest = _read(search, prefix + "/manifest.json", hashes)
        _sealed(manifest)
        role = {"inv1": "INV", "dom1": "DOM", "agg1": "AGG"}[stage_name]
        _require(manifest["label"] == label and manifest["role"] == role and manifest["sha256"] == record["manifest_sha256"]
                 and manifest["policy_id"] == contract.POLICY_ID and manifest["upstream_commit"] == contract.UPSTREAM_COMMIT
                 and manifest["upstream_files"] == upstream
                 and manifest["contract_source_sha256"] == expected_binding["contract_sha256"]
                 and manifest["base_policy_id"] == contract.frozen.POLICY_ID
                 and manifest["base_contract_source_sha256"] == _sha(Path(contract.frozen.__file__).read_bytes())
                 and manifest["final_response_rule_sha256"] == _sha(contract.FINAL_RULE.encode())
                 and digest(manifest["context_inventory"]) == manifest["context_inventory_sha256"] == record["context_inventory_sha256"],
                 "readiness evidence manifest identity differs")
        effective = _file(search, prefix + "/effective-mission.md", hashes).decode()
        _require(effective == contract._render(role, label, manifest["native_repair_diagnostic"])
                 and _sha(effective.encode()) == manifest["effective_mission_sha256"] == record["effective_mission_sha256"],
                 "effective native role contract changed")
        native_mission = _file(search, prefix + "/native-mission.md", hashes).decode()
        _require(contract._mission(native_mission, label)[0] == role
                 and _sha(native_mission.encode()) == manifest["raw_mission_sha256"] == record["raw_mission_sha256"], "raw native mission changed")
        original, views = _sources(search, prefix, manifest, hashes)
        index = _file(search, prefix + "/context-view/C1_INDEX.md", hashes).decode()
        canonical_index = (f"# {role} evidence index — {contract.POLICY_ID}\n\n"
            f"Stage: {label}; manifest identity: {manifest['sha256']}.\n"
            "Read all ordered lossless views below; original files remain available unchanged.\n"
            "Compatibility stubs are inert. Solver delivery and editor completion are separate.\n\n")
        for entry in manifest["required_evidence"]:
            canonical_index += f"- {entry['kind']}: context/{entry['path']} ({entry['bytes']} UTF-8 bytes).\n"
            canonical_index += "".join(f"  - context/{chunk['path']} (read offset=1, limit={chunk['limit']}).\n"
                                       for chunk in entry["chunks"])
        _require(index == canonical_index, "factual evidence index differs from the sealed manifest")
        manifest_text = _file(search, prefix + "/context-view/C1_MANIFEST.json", hashes).decode()
        _require(json.loads(manifest_text) == manifest, "model-visible manifest differs")
        configured = _file(search, prefix + "/configured-agent-prompt.md", hashes).decode()
        _require(configured == contract.authoring_system(effective, index),
                 "configured authoring SYSTEM changed its declared composition")
        profile = _read(search, prefix + "/system-profile.json", hashes)
        _require(profile["profile"] == contract.SYSTEM_ID and profile["sources"] == OPENCODE_FILES
                 and profile["steps"] == 8 and profile["permissions"] == {"*": "deny", "read": "allow", "write": "allow", "edit": "allow"}
                 and profile["configured_agent_prompt_sha256"] == record["authoring_system_sha256"] == _sha(configured.encode())
                 and profile["default_provider_prompt_sha256"] == record["default_provider_prompt_sha256"] == OPENCODE_FILES["session/prompt/anthropic.txt"],
                 "OpenCode supported system override/runtime identity differs")
        session = result["editor_evidence"]["sessions"][label]
        settled = _read(search, "editor-audit/phase3a-sessions/" + label + ".settled.json", hashes)
        _sealed(settled)
        _require(settled["label"] == label and settled["session"] == session and settled["binding"] == {
            "study_sha256": study["study_sha256"], "source_sha256": expected_binding["parent_boundary_sha256"],
            "pilot": "p3a-01", "fixture": fixture}, "accepted native session differs from its saved audit")
        _require(session["status"] == "valid" and session["model_backed"] and session["authentic_eligible"]
                 and not session["terminal_note_used"] and 1 <= len(session["requests"]) <= 7,
                 "accepted editor did not finish normally before terminal control")
        rows = session["requests"]
        _require(session["result_slots"] == [q["slot_id"] for q in rows], "editor result coverage differs")
        normalized: set[str] = set()
        bodies: list[dict] = []
        contents: list[list[dict]] = []
        cwd = None
        seen_ids: set[str] = set()
        strategy_mutations: list[str] = []
        notes_mutations: list[str] = []
        decision = None
        for turn, row in enumerate(rows, 1):
            slot = f"p3a-01.adaptive.editor.{label}.t{turn:02}"
            _require(row["slot_id"] == slot and slot in scoped and row["role_translation"] is None,
                     "normal editor turn/translation differs")
            intent, response = state["intents"][slot], state["results"][slot]
            request = intent["request"]
            _require(intent["role"] == response["role"] == "editor" and intent["study_sha256"] == response["study_sha256"] == study["study_sha256"]
                     and intent["fixture"] is response["fixture"] is fixture and intent["request_sha256"] == response["request_sha256"] == digest(request)
                     and response["intent_sha256"] == digest(intent) and row["effective_sha256"] == digest(request)
                     and row["result_sha256"] == digest(response), "authoritative editor request/result binding differs")
            cwd = _system(request, configured, cwd)
            body = _body(request, normalized)
            present = [_without_cache(b) for m in body["messages"] if m.get("role") == "assistant"
                       and isinstance(m.get("content"), list) for b in m["content"]]
            for blocks in contents:
                for block in blocks:
                    if block.get("type") in {"tool_use", "thinking", "redacted_thinking"}:
                        _require(_without_cache(block) in present, "actual provider tool/thinking history was changed or omitted")
            actual_prior = {b["id"]: _without_cache(b) for blocks in contents for b in blocks if b.get("type") == "tool_use"}
            historical_calls = [b for b in present if b.get("type") == "tool_use"]
            _require(historical_calls == list(actual_prior.values()),
                "actual editor history has extra, duplicate or changed tool calls")
            user_results = [b for m in body["messages"] if m.get("role") == "user" and isinstance(m.get("content"), list)
                            for b in m["content"] if b.get("type") == "tool_result"]
            _require(len(user_results) == len(actual_prior) and {b["tool_use_id"] for b in user_results} == set(actual_prior),
                "actual editor history lacks exact prior tool-result coverage")
            content = response["response"]["provider_response"]["content"]
            calls = [b for b in content if b.get("type") == "tool_use"]
            if turn == 1:
                _require(len(calls) == 1 and calls[0]["name"] == "read" and calls[0]["input"]["filePath"] == cwd + "/MISSION.md",
                         "first model tool response must read only MISSION.md")
            for call in calls:
                _require(call["id"] not in seen_ids, "duplicate actual tool-use identity")
                seen_ids.add(call["id"])
                if call["name"] in {"write", "edit"}:
                    path = call["input"]["filePath"]
                    _require(path in {cwd + "/context/harness/systemprompt.md", cwd + "/output/answer.md"}, "editor mutated an unsupported path")
                    (strategy_mutations if path.endswith("systemprompt.md") else notes_mutations).append(call["id"])
                    if decision is None:
                        decision = body
            if turn == len(rows):
                _require(not calls and response["response"]["stop_reason"] == "end_turn", "editor has no normal final response")
                if decision is None:
                    decision = body
            else:
                _require(response["response"]["stop_reason"] == "tool_use", "editor ended before its final recorded turn")
            bodies.append(body)
            contents.append(content)
        if cwd is None or decision is None:
            raise ContractError("accepted editor lacks its actual decision context")
        expected = {cwd + "/MISSION.md": effective, cwd + "/context/C1_MANIFEST.json": manifest_text,
                    cwd + "/context/C1_INDEX.md": index,
                    cwd + "/context/harness/systemprompt.md": original["harness/systemprompt.md"]}
        expected.update({cwd + "/context/" + path: text for path, text in views.items()})
        delivery = verify_delivery(decision, expected)
        final = state["results"][rows[-1]["slot_id"]]["response"]["text"]
        _require(isinstance(final, str) and final.count("<notes>") == final.count("</notes>") == 1
                 and re.fullmatch(r"\s*<notes>\s*\S[\s\S]*</notes>\s*", final), "normal final is not one complete notes block")
        _require(notes_mutations, "normal editor did not write its final notes")
        verify_delivery(_after_mutation(bodies[-1], notes_mutations[-1]), {cwd + "/output/answer.md": final})
        harvested = _file(search, "rollouts/" + stage_name + "/harness/systemprompt.md", hashes).decode()
        contract._strategy(harvested.encode())
        if strategy_mutations:
            verify_delivery(_after_mutation(bodies[-1], strategy_mutations[-1]), {cwd + "/context/harness/systemprompt.md": harvested})
        else:
            _require(contract._strategy(harvested.encode()) == contract._strategy(original["harness/systemprompt.md"].encode())
                     and not stages[stage_name]["effective_changed"], "changed strategy lacks an actual write/edit")
        sessions.append({"label": label, "ordinary_http_calls": len(rows), "mission_first": True,
            "complete_evidence_before_decision": True, "source_files": len(original), "lossless_views": len(views),
            "delivered_file_sha256": {name.removeprefix(cwd + "/"): value["sha256"] for name, value in delivery.items()},
            "strategy_mutations": len(strategy_mutations), "notes_mutations": len(notes_mutations),
            "normal_final_notes_sha256": _sha(final.encode()), "post_write_verification": True,
            "absent_caller_ids_normalized_in_parser_copy_only": sorted(normalized),
            "effective_changed": stages[stage_name]["effective_changed"]})
    transport_audits = {}
    clock_records = {}
    bindings = {key: study[key] for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")}
    for stage_name in ("inv1", "dom1", "agg1"):
        label = stages[stage_name]["accepted_editor_sessions"][0]
        clock = _read(search, "editor-audit/conversation-deadlines/" + label + ".json", hashes)
        _sealed(clock)
        _require(clock["study_sha256"] == study["study_sha256"] and clock["source_sha256"] == study["source_sha256"]
                 and clock["fixture"] is fixture and clock["label"] == label and clock["pilot"] == "p3a-01"
                 and clock["conversation_id"] == "p3a-01:adaptive:" + label and clock["seconds"] == 600
                 and clock["deadline_monotonic"] == clock["started_monotonic"] + 600
                 and clock["native_subprocess_cap_seconds"] == 600 and clock["OpenCode_fetch_cap_seconds"] == 590
                 and clock["renewable"] is False, "absolute conversation admission clock differs")
        clock_records[label] = clock
    for slot in sorted(scoped):
        audit = bounded.read_audit(study["study_sha256"], fixture, slot, intent=state["intents"][slot],
                                   result=state["results"][slot], bindings=bindings)
        _require(audit["sdk_invoked"] is True and audit["worker_stopped"] is True and not any(
            audit[key] for key in ("late_known", "deadline_expired", "cleanup_failed", "owner_stop_required")),
            "readiness cannot use a stopped, late or uninvoked provider result")
        if audit["role"] == "editor":
            label = slot.split(".editor.", 1)[1].rsplit(".t", 1)[0]
            clock = clock_records[label]
            _require(audit["budget"]["conversation_deadline"] == clock["deadline_monotonic"]
                     and audit["budget"]["started_monotonic"] >= clock["started_monotonic"],
                     "editor budget changed or renewed its registered conversation deadline")
        transport_audits[slot] = audit["sha256"]
    return {"kind": "phase3a-c1-counted-readiness-evidence-v1", "passed": True, "fixture": fixture,
        "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"], "branch_sha256": branch["sha256"],
        "readiness_adaptive_requests": len(scoped), "role_counts": dict(Counter(state["results"][s]["role"] for s in scoped)),
        "scoped_intents_sha256": digest({s: state["intents"][s] for s in sorted(scoped)}),
        "scoped_results_sha256": digest({s: state["results"][s] for s in sorted(scoped)}),
        "artifact_sha256": hashes, "sessions": sessions,
        "scoped_transport_audit_sha256": transport_audits,
        "conversation_admission_clock_sha256": {label: clock["sha256"] for label, clock in clock_records.items()},
        "mechanical_readiness_only": True, "semantic_grounding_review_required": True,
        "favorable_utility_required": False}
