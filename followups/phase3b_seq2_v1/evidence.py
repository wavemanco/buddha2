"""Read-only HI readiness proof; six native stages plus normal checkpoint selection."""
from __future__ import annotations

import json
import posixpath
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3.evidence import (
    _body,
    _file,
    _read,
    _require,
    _sealed,
    _sha,
    _system,
    _without_cache,
)
from followups.phase3a_compat_c1_v1.support import OPENCODE_FILES

from . import contract, editor
from . import transport as bounded
from .delivery import _history, verify_delivery, verify_original_strategy
from .support import NATIVE, ROOT


@dataclass(frozen=True)
class _ValidationProfile:
    namespace: str
    definition: str
    native_root: Path
    contract: ModuleType
    editor: ModuleType
    transport: ModuleType


def _live_profile() -> _ValidationProfile:
    return _ValidationProfile("phase3b_seq2_v1", "PHASE3B_DEFINITION.md",
                              NATIVE, contract, editor, bounded)


def _sources(search: Path, prefix: str, manifest: dict, hashes: dict[str, str], *,
             supplied: dict[str, str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    # Verify the new round-specific source set; the old reader binds a k1 layout.
    for entry in manifest["required_evidence"]:
        for name in [entry["path"], *(chunk["path"] for chunk in entry["chunks"])]:
            parts = PurePosixPath(name).parts
            _require(isinstance(name, str) and parts and not PurePosixPath(name).is_absolute()
                and ".." not in parts and ":" not in name and "\\" not in name and not any(
                p.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
                or "stdout" in p.casefold() or "stderr" in p.casefold() or "cache" in p.casefold() for p in parts),
                "private/stream readiness view forbidden")
    original, views = {}, {}
    for entry in manifest["required_evidence"]:
        joined, cursor = [], 0
        _require(isinstance(entry.get("chunks"), list) and entry["chunks"], "required evidence has no lossless views")
        for chunk in entry["chunks"]:
            if supplied is None:
                raw = _file(search, prefix + "/context-view/" + chunk["path"], hashes)
            else:
                _require(isinstance(supplied.get(chunk["path"]), str), "required prepared evidence view is absent")
                raw = supplied[chunk["path"]].encode("utf-8")
            _require(len(raw) == chunk["bytes"] and _sha(raw) == chunk["sha256"] and chunk["offset"] == 1
                     and chunk["limit"] == len(raw.decode().splitlines()), "lossless evidence chunk changed")
            view = json.loads(raw)
            _require(view["source_path"] == entry["path"] and view["source_sha256"] == entry["sha256"]
                     and view["char_start"] == chunk["char_start"] == cursor and view["char_end"] == chunk["char_end"]
                     and type(view["text"]) is list and all(type(t) is str for t in view["text"]),
                     "lossless view identity changed")
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
    if manifest["role"] == "SELECT":
        candidates = sorted(name for name in manifest["context_inventory"] if name.startswith("candidates/"))
        _require(1 <= len(candidates) <= 2
                 and set(manifest["context_inventory"]) == {"task.md", *candidates}
                 and all(re.fullmatch(r"candidates/[A-Za-z0-9_-]+\.md", name) for name in candidates),
                 "native selector source set contains noncandidate evidence")
        expected = [("task.md", "task_contract"), *[(name, "selection_candidate") for name in candidates]]
    else:
        expected = contract._layout(manifest["role"], manifest["label"])[1]
    _require([(entry["path"], entry["kind"]) for entry in manifest["required_evidence"]] == expected,
             "round-specific required evidence was omitted or reordered")
    return original, views

def verify_readiness(study: dict, run: Path, state: dict, branch: dict, fixture: bool) -> dict:
    """Verify saved delivery/normal completion, never model quality or efficacy."""
    try:
        return _verify(study, run, state, branch, fixture, _live_profile())
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("counted readiness evidence is incomplete or invalid") from error


def verify_native_path(study: dict, run: Path, state: dict, branch: dict, fixture: bool) -> dict:
    """Same full normal-path proof for any declared development pilot."""
    pilot = branch.get("pilot")
    if not isinstance(pilot, str):
        raise ContractError("native proof pilot is absent")
    _require(pilot in {entry["pilot_id"] for entry in study["tasks"]}, "foreign native proof pilot")
    result = _verify(study, run, state, branch, fixture, _live_profile(), pilot=pilot)
    return {**result, "kind": "phase3b-s2-normal-native-path-evidence-v1", "pilot": pilot}



def _verify(study: dict, run: Path, state: dict, branch: dict, fixture: bool,
            validation: _ValidationProfile, *, pilot: str = "p3b-01") -> dict:
    contract, editor, bounded = validation.contract, validation.editor, validation.transport
    _require(type(fixture) is bool and state["fixture"] is fixture and state["study_sha256"] == study["study_sha256"]
             and state["status"] == "ready" and all(state[k] == 0 for k in (
                 "reserved_micro_usd", "reserved_input_tokens", "reserved_output_tokens")), "readiness accounting has a hold/liability")
    _require(set(state["intents"]) == set(state["results"]) and all(
        r["status"] == "response" and r.get("failure") is None and r["reserved_micro_usd"] == 0
        for r in state["results"].values()), "readiness accounting is not fully known")
    _sealed(branch)
    _require(branch["study_sha256"] == study["study_sha256"] and branch["fixture"] is fixture
             and branch["pilot"] == pilot and branch["arm"] == "adaptive" and branch["failure"] is None,
             "foreign/incomplete readiness branch")
    result, c1 = branch["result"], branch["c1_evidence"]
    _require(result["status"] == "complete" and result["fixture"] is fixture
             and result["study_sha256"] == study["study_sha256"] and result["authentic"] is (not fixture)
             and branch["portfolio_sha256"] == digest(result["portfolio"]), "native readiness completion/authenticity differs")
    _require(c1["fixture"] is fixture and c1["study_sha256"] == study["study_sha256"]
             and c1["source_sha256"] == study["source_sha256"], "C1 readiness source identity differs")
    mode = result["native"]["modes"]["seq"]
    ledger = mode["ledger"]
    _require(mode["ok"] and ledger["P"] == ledger["expected_P"] == 6 and ledger["R"] == ledger["expected_R"] == 8
             and set(result["rollouts"]) == {"base1", "base2", "inv1", "dom1", "c1", "inv2", "dom2", "c2"}, "native readiness path lacks its eight executions")
    selection = result["native"]["selections"]["seq"]
    from harness2.core.selection import assign_ids
    task_id = next(entry["parent_task_id"] for entry in study["tasks"] if entry["pilot_id"] == pilot)
    _require(selection["task_id"] == task_id and selection["mode"] == "seq" and selection["k"] == 2
             and selection["id_map"] == assign_ids(("c1", "c2"), task_id=task_id, k=2, mode="seq")
             and selection["id_map"].get(selection["chosen_id"]) == selection["chosen_label"],
             "native selection task/round/id-to-checkpoint identity differs")
    _require(selection["ok"] and not selection.get("trivial", False) and selection["chosen_label"] in {"c1", "c2"} and not selection["fallback"],
             "native seq2 readiness selection is absent, trivial or failed")
    _require(result["selected_checkpoint"] == selection["chosen_label"]
             and set(result["checkpoints"]) == {"c1", "c2"}
             and set(selection["id_map"].values()) == {"c1", "c2"}
             and result["portfolio"] == result["checkpoints"][result["selected_checkpoint"]],
             "native selected output is not its existing checkpoint")
    stages = {s["label"]: s for s in result["stage_dispositions"]}
    _require(set(stages) == {"inv1", "dom1", "c1", "inv2", "dom2", "c2"} and all(s["authentic_eligible"] and s["model_backed"]
             and not s["fell_back"] and not s["terminal_note_used"] and not s["cap_limited_unchanged"]
             for s in stages.values()), "readiness requires six normal eligible native stages")
    search = Path(run) / "search" / pilot / "adaptive"
    _require(search.is_absolute() and ".." not in search.parts and Path(run).is_relative_to(validation.native_root), "invalid readiness run path")
    hashes: dict[str, str] = {}
    scoped = {slot for slot, row in state["intents"].items() if row["cell"] == pilot + ":adaptive"}
    for rollout in result["rollouts"].values():
        _require(rollout["status"] == "complete" and len(rollout["requests"]) == 12, "readiness solver rollout incomplete")
        for response in rollout["requests"]:
            _require(response == state["results"][response["slot_id"]] and response["slot_id"] in scoped,
                     "solver execution differs from authoritative readiness results")
    expected_binding = {key: _sha((ROOT / name).read_bytes()) for key, name in {
        "adapter_sha256": f"followups/{validation.namespace}/adapter.py",
        "contract_sha256": f"followups/{validation.namespace}/contract.py",
        "definition_sha256": validation.definition,
        "parent_boundary_sha256": "followups/phase3a_v1/editor.py",
        "editor_sha256": f"followups/{validation.namespace}/editor.py"}.items()}
    _require(c1["binding"] == expected_binding, "frozen C1 adapter/profile binding differs")
    upstream = contract._upstream()
    sessions = []
    for stage_name in ("inv1", "dom1", "c1", "inv2", "dom2", "c2"):
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
        role = {"inv1": "INV", "dom1": "DOM", "c1": "AGG", "inv2": "INV", "dom2": "DOM", "c2": "AGG"}[stage_name]
        _require(manifest["label"] == label and manifest["role"] == role and manifest["sha256"] == record["manifest_sha256"]
                 and manifest["policy_id"] == contract.POLICY_ID and manifest["upstream_commit"] == contract.UPSTREAM_COMMIT
                 and manifest["upstream_files"] == upstream
                 and manifest["contract_source_sha256"] == expected_binding["contract_sha256"]
                 and manifest["editor_profile_sha256"] == digest(editor.profile())
                 and manifest["prior_policy_id"] == contract.final_contract.POLICY_ID
                 and manifest["prior_contract_source_sha256"] == _sha(Path(contract.final_contract.__file__).read_bytes())
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
        canonical_index = (f"# {role} evidence index \u2014 {contract.POLICY_ID}\n\n"
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
                 and profile["steps"] == editor.MAX_STEPS and profile["editor_profile_sha256"] == digest(editor.profile()) and profile["permissions"] == {"*": "deny", "read": "allow", "write": "allow", "edit": "allow"}
                 and profile["configured_agent_prompt_sha256"] == record["authoring_system_sha256"] == _sha(configured.encode())
                 and profile["default_provider_prompt_sha256"] == record["default_provider_prompt_sha256"] == OPENCODE_FILES["session/prompt/anthropic.txt"],
                 "OpenCode supported system override/runtime identity differs")
        session = result["editor_evidence"]["sessions"][label]
        settled = _read(search, "editor-audit/phase3a-sessions/" + label + ".settled.json", hashes)
        _sealed(settled)
        _require(settled["label"] == label and settled["session"] == session and settled["binding"] == {
            "study_sha256": study["study_sha256"], "source_sha256": expected_binding["editor_sha256"],
            "editor_profile_sha256": digest(editor.profile()),
            "pilot": pilot, "fixture": fixture}, "accepted native session differs from its saved audit")
        _require(session["status"] == "valid" and session["model_backed"] and session["authentic_eligible"]
                 and not session["terminal_note_used"] and 1 <= len(session["requests"]) <= editor.NORMAL_STEPS,
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
            slot = f"{pilot}.adaptive.editor.{label}.t{turn:02}"
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
        delivery, original_delivery = verify_original_strategy(decision, expected, cwd=cwd,
            manifest=manifest, original=original, views=views)
        final = state["results"][rows[-1]["slot_id"]]["response"]["text"]
        _require(isinstance(final, str) and final.count("<notes>") == final.count("</notes>") == 1
                 and re.fullmatch(r"\s*<notes>\s*\S[\s\S]*</notes>\s*", final), "normal final is not one complete notes block")
        _require(notes_mutations, "normal editor did not write its final notes")
        verify_delivery(bodies[-1], {cwd + "/output/answer.md": final}, after=notes_mutations[-1])
        harvested = _file(search, "rollouts/" + stage_name + "/harness/systemprompt.md", hashes).decode()
        contract._strategy(harvested.encode())
        if strategy_mutations:
            verify_delivery(bodies[-1], {cwd + "/context/harness/systemprompt.md": harvested}, after=strategy_mutations[-1])
        else:
            _require(contract._strategy(harvested.encode()) == contract._strategy(original["harness/systemprompt.md"].encode())
                     and session["effective_changed_from_input"] is False,
                     "changed strategy lacks an actual write/edit")
        sessions.append({"label": label, "ordinary_http_calls": len(rows), "mission_first": True,
            "complete_evidence_before_decision": True, "source_files": len(original), "lossless_views": len(views),
            "delivered_file_sha256": {name.removeprefix(cwd + "/"): value["sha256"] for name, value in delivery.items()},
            "strategy_mutations": len(strategy_mutations), "notes_mutations": len(notes_mutations),
            "normal_final_notes_sha256": _sha(final.encode()), "post_write_verification": True,
            "absent_caller_ids_normalized_in_parser_copy_only": sorted(normalized),
            "effective_changed": stages[stage_name]["effective_changed"],
            "effective_changed_from_input": session["effective_changed_from_input"],
            "original_strategy_delivery": original_delivery})
    selector = result["editor_evidence"]["sessions"]["select.seq2"]
    selector_proof = editor.validate_selector_evidence(search=search,
        study_sha256=study["study_sha256"], pilot=pilot, fixture=fixture, session=selector,
        results=state["results"], intents=state["intents"], selection=selection)
    prefix = "editor-audit/c1-contracts/select.seq2"
    record = _read(search, prefix + "/result.json", hashes)
    _sealed(record)
    _require(record == c1["sessions"]["select.seq2"] and record["fixture"] is fixture
             and record["status"] == "returned" and record["native_reply_ok"] and record["auxiliary_removed"]
             and record["binding"] == expected_binding and record["study_sha256"] == study["study_sha256"]
             and record["source_sha256"] == study["source_sha256"], "selector source-bound call differs")
    manifest = _read(search, prefix + "/manifest.json", hashes)
    _sealed(manifest)
    _require(manifest["role"] == "SELECT" and manifest["label"] == "select.seq2"
             and manifest["sha256"] == record["manifest_sha256"] and manifest["policy_id"] == contract.POLICY_ID
             and manifest["upstream_commit"] == contract.UPSTREAM_COMMIT and manifest["upstream_files"] == upstream
             and manifest["contract_source_sha256"] == expected_binding["contract_sha256"]
             and manifest["editor_profile_sha256"] == digest(editor.profile())
             and digest(manifest["context_inventory"]) == manifest["context_inventory_sha256"]
                 == record["context_inventory_sha256"], "selector evidence manifest identity differs")
    mission = _file(search, prefix + "/effective-mission.md", hashes).decode()
    raw_mission = _file(search, prefix + "/native-mission.md", hashes).decode()
    _require(mission == raw_mission == contract.selector_mission(sorted(selection["id_map"]))
             and _sha(mission.encode()) == manifest["effective_mission_sha256"] == record["effective_mission_sha256"]
             and _sha(raw_mission.encode()) == manifest["raw_mission_sha256"] == record["raw_mission_sha256"],
             "native selector instructions changed")
    _, views = _sources(search, prefix, manifest, hashes)
    index = _file(search, prefix + "/context-view/C1_INDEX.md", hashes).decode()
    canonical_index = (f"# SELECT evidence index — {contract.POLICY_ID}\n\n"
        f"Stage: select.seq2; manifest identity: {manifest['sha256']}.\n"
        "Read all ordered lossless views below; original files remain available unchanged.\n"
        "Compatibility stubs are inert. Solver delivery and editor completion are separate.\n\n")
    for entry in manifest["required_evidence"]:
        canonical_index += f"- {entry['kind']}: context/{entry['path']} ({entry['bytes']} UTF-8 bytes).\n"
        canonical_index += "".join(f"  - context/{chunk['path']} (read offset=1, limit={chunk['limit']}).\n"
                                   for chunk in entry["chunks"])
    _require(index == canonical_index, "selector factual index differs")
    manifest_text = _file(search, prefix + "/context-view/C1_MANIFEST.json", hashes).decode()
    _require(json.loads(manifest_text) == manifest, "selector visible manifest differs")
    configured = _file(search, prefix + "/configured-agent-prompt.md", hashes).decode()
    _require(configured == contract.selector_system(mission, index)
             and _sha(configured.encode()) == record["authoring_system_sha256"], "selector configured SYSTEM changed")
    profile = _read(search, prefix + "/system-profile.json", hashes)
    _require(profile["profile"] == contract.SYSTEM_ID and profile["sources"] == OPENCODE_FILES
             and profile["steps"] == editor.MAX_STEPS and profile["editor_profile_sha256"] == digest(editor.profile())
             and profile["configured_agent_prompt_sha256"] == record["authoring_system_sha256"]
             and profile["default_provider_prompt_sha256"] == record["default_provider_prompt_sha256"]
                 == OPENCODE_FILES["session/prompt/anthropic.txt"], "selector runtime SYSTEM profile changed")
    cwd = None
    for row in selector["requests"]:
        cwd = _system(state["intents"][row["slot_id"]]["request"], configured, cwd)
    if cwd is None:
        raise ContractError("selector actual SYSTEM is absent")
    output = PurePosixPath(cwd) / "output/answer.md"
    allowed_outputs = {str(output), *(posixpath.relpath(str(output), str(parent))
        for parent in (PurePosixPath(cwd), *PurePosixPath(cwd).parents))}
    _require(profile["permissions"] == {"*": "deny", "read": "allow", "write": "allow",
        "edit": {"*": "deny", **{name: "allow" for name in sorted(allowed_outputs)}}},
        "selector runtime permissions admit mutable candidate or nonoutput evidence")
    selector_body = _body(state["intents"][selector["result_slots"][-1]]["request"], set())
    expected = {cwd + "/MISSION.md": mission, cwd + "/context/C1_MANIFEST.json": manifest_text,
                cwd + "/context/C1_INDEX.md": index}
    expected.update({cwd + "/context/" + name: text for name, text in views.items()})
    selector_proof["complete_declared_instruction_delivery"] = verify_delivery(selector_body, expected)
    transport_audits = {}
    clock_records = {}
    bindings = {key: study[key] for key in ("study_sha256", "source_sha256", "policy_sha256", "launcher_sha256")}
    for stage_name in ("inv1", "dom1", "c1", "inv2", "dom2", "c2", "select.seq2"):
        label = stage_name if stage_name == "select.seq2" else stages[stage_name]["accepted_editor_sessions"][0]
        clock = _read(search, "editor-audit/conversation-deadlines/" + label + ".json", hashes)
        _sealed(clock)
        _require(clock["study_sha256"] == study["study_sha256"] and clock["source_sha256"] == study["source_sha256"]
                 and clock["fixture"] is fixture and clock["label"] == label and clock["pilot"] == pilot
                 and clock["conversation_id"] == pilot + ":adaptive:" + label and clock["seconds"] == 600
                 and clock["deadline_monotonic"] == clock["started_monotonic"] + 600
                 and clock["native_subprocess_cap_seconds"] == 600 and clock["OpenCode_fetch_cap_seconds"] == 590
                 and clock["renewable"] is False and clock["editor_profile_sha256"] == digest(editor.profile()), "absolute conversation admission clock differs")
        clock_records[label] = clock
    for slot in sorted(scoped):
        audit = bounded.read_audit(study["study_sha256"], fixture, slot, intent=state["intents"][slot],
                                   result=state["results"][slot], bindings=bindings)
        _require(audit["sdk_invoked"] is True and audit["worker_stopped"] is True and not any(
            audit[key] for key in ("late_known", "deadline_expired", "cleanup_failed", "owner_stop_required")),
            "readiness cannot use a stopped, late or uninvoked provider result")
        if audit["role"] in {"editor", "native_selector"}:
            label = slot.split(".editor.", 1)[1].rsplit(".t", 1)[0]
            clock = clock_records[label]
            _require(audit["budget"]["conversation_deadline"] == clock["deadline_monotonic"]
                     and audit["budget"]["started_monotonic"] >= clock["started_monotonic"],
                     "editor budget changed or renewed its registered conversation deadline")
        transport_audits[slot] = audit["sha256"]
    return {"kind": "phase3b-s2-counted-readiness-evidence-v1", "passed": True, "fixture": fixture,
        "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"], "branch_sha256": branch["sha256"],
        "readiness_adaptive_requests": len(scoped), "role_counts": dict(Counter(state["results"][s]["role"] for s in scoped)),
        "scoped_intents_sha256": digest({s: state["intents"][s] for s in sorted(scoped)}),
        "scoped_results_sha256": digest({s: state["results"][s] for s in sorted(scoped)}),
        "artifact_sha256": hashes, "sessions": sessions, "selector_session": selector_proof,
        "scoped_transport_audit_sha256": transport_audits,
        "conversation_admission_clock_sha256": {label: clock["sha256"] for label, clock in clock_records.items()},
        "mechanical_readiness_only": True, "semantic_grounding_review_required": True,
        "favorable_utility_required": False}


def _prepared(prepared: dict, label: str) -> tuple[dict, dict[str, str], dict[str, str], str]:
    """One source/layout proof shared by live decision gating and saved replay."""
    _require(isinstance(prepared, dict), "prepared information contract missing")
    manifest = prepared["manifest"]
    _sealed(manifest)
    _require(manifest["label"] == label and manifest["policy_id"] == contract.POLICY_ID
             and manifest["editor_profile_sha256"] == digest(editor.profile()),
             "information contract label/profile differs")
    original, views = _sources(Path("/unread-information"), "", manifest, {}, supplied=prepared["evidence_files"])
    role = manifest["role"]
    effective, index = prepared["effective_mission"], prepared["index_text"]
    if role == "SELECT":
        ids = sorted(name.removeprefix("candidates/").removesuffix(".md")
                     for name in original if name.startswith("candidates/"))
        _require(label == "select.seq2" and effective == contract.selector_mission(ids),
                 "information contract changed native selector instructions")
        configured = contract.selector_system(effective, index)
    else:
        _require(effective == contract._render(role, label, manifest["native_repair_diagnostic"]),
                 "information contract changed native author instructions")
        configured = contract.authoring_system(effective, index)
    _require(prepared["authoring_system_text"] == configured
             and _sha(effective.encode()) == manifest["effective_mission_sha256"],
             "information contract configured SYSTEM differs")
    return manifest, original, views, configured


def verify_information_before_decision(request: dict, prepared: dict, *, cwd: str, label: str) -> dict:
    """Pure guard before the first mutation or normal direct final of every pilot."""
    manifest, original, views, configured = _prepared(prepared, label)
    _require(_system(request, configured, None) == cwd, "decision belongs to another native workspace")
    body = _body(request, set())
    manifest_text = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    expected = {cwd + "/MISSION.md": prepared["effective_mission"],
                cwd + "/context/C1_MANIFEST.json": manifest_text,
                cwd + "/context/C1_INDEX.md": prepared["index_text"]}
    expected.update({cwd + "/context/" + path: text for path, text in views.items()})
    original_delivery = None
    if manifest["role"] == "SELECT":
        delivery = verify_delivery(body, expected)
    else:
        expected[cwd + "/context/harness/systemprompt.md"] = original["harness/systemprompt.md"]
        delivery, original_delivery = verify_original_strategy(body, expected, cwd=cwd,
            manifest=manifest, original=original, views=views)
    return {"kind": "phase3b-s2-information-before-decision-v1", "passed": True,
        "label": label, "manifest_sha256": manifest["sha256"], "request_sha256": digest(request),
        "actual_system_sha256": _sha(configured.encode()), "delivery": delivery,
        "original_strategy_delivery": original_delivery, "provider_calls": 0}


def verify_normal_session(request: dict, prepared: dict, *, cwd: str, label: str,
                          response: dict, harvested_strategy: str | None = None) -> dict:
    """Same normal-final delivery rule for every pilot; terminal is not normal."""
    manifest, original, _, configured = _prepared(prepared, label)
    _require(_system(request, configured, None) == cwd, "normal final changed native workspace")
    content = response.get("content")
    if not isinstance(content, list):
        raise ContractError("normal final has no provider content blocks")
    _require(response.get("stop_reason") == "end_turn"
             and not any(item.get("type") == "tool_use" for item in content),
             "normal session has no complete final response")
    final = "".join(item["text"] for item in content if item.get("type") == "text")
    body = _body(request, set())
    calls, results = _history(body)
    mutations = [identity for identity, call in calls.items() if call["name"] in {"write", "edit"}
                 and not results[identity].get("is_error")]
    output = cwd + "/output/answer.md"
    notes = [identity for identity in mutations if calls[identity]["input"]["filePath"] == output]
    proof: dict = {"kind": "phase3b-s2-normal-session-delivery-v1", "passed": True, "label": label,
        "request_sha256": digest(request), "provider_response_sha256": digest(response),
        "final_sha256": _sha(final.encode()), "notes_delivery": None, "strategy_delivery": None,
        "harvested_strategy": harvested_strategy, "harvested_strategy_sha256": None,
        "provider_calls": 0}
    if manifest["role"] == "SELECT":
        _require(all(calls[identity]["input"]["filePath"] == output for identity in mutations),
                 "native selector mutated nonoutput evidence")
        from harness2.core.selection import _CHOICE
        match = _CHOICE.search(final)
        candidates = {PurePosixPath(name).stem for name in original if name.startswith("candidates/")}
        _require(match is not None and match.group(1).strip() in candidates,
                 "native selector normal final has no valid candidate choice")
    else:
        _require(final.count("<notes>") == final.count("</notes>") == 1
                 and re.fullmatch(r"\s*<notes>\s*\S[\s\S]*</notes>\s*", final) is not None,
                 "normal author final is not one complete notes block")
        _require(bool(notes), "normal author omitted its mandatory saved notes")
        strategy_path = cwd + "/context/harness/systemprompt.md"
        _require(all(calls[identity]["input"]["filePath"] in {output, strategy_path} for identity in mutations),
                 "native author mutated an unsupported artifact")
        if not isinstance(harvested_strategy, str):
            raise ContractError("normal author lacks its actual harvested strategy witness")
        changed = [identity for identity in mutations if calls[identity]["input"]["filePath"] == strategy_path]
        if changed:
            proof["strategy_delivery"] = verify_delivery(body, {strategy_path: harvested_strategy}, after=changed[-1])
        else:
            _require(harvested_strategy == original["harness/systemprompt.md"],
                     "normal author changed strategy without a successful mutation")
        proof["harvested_strategy_sha256"] = _sha(harvested_strategy.encode())
    if notes:
        proof["notes_delivery"] = verify_delivery(body, {output: final}, after=notes[-1])
    return proof


def verify_recorded_information(*, search: Path, label: str, session: dict, results: dict, intents: dict) -> dict:
    """Recompute those same live proofs for every normal saved conversation."""
    prefix = "editor-audit/c1-contracts/" + label
    hashes: dict[str, str] = {}
    manifest = _read(search, prefix + "/manifest.json", hashes)
    # The shared source parser validates names before reading named views.
    _, views = _sources(search, prefix, manifest, hashes)
    prepared: dict = {"manifest": manifest, "evidence_files": views,
        "effective_mission": _file(search, prefix + "/effective-mission.md", hashes).decode(),
        "index_text": _file(search, prefix + "/context-view/C1_INDEX.md", hashes).decode(),
        "authoring_system_text": _file(search, prefix + "/configured-agent-prompt.md", hashes).decode()}
    slots = session["result_slots"]
    _require(bool(slots), "normal information replay has no provider requests")
    information = normal = None
    cwd = None
    from .history import HistoryGuard
    guard = HistoryGuard(lambda slot, role, request: results[slot], slots[0].rsplit(".t", 1)[0])
    for slot in slots:
        request, result = intents[slot]["request"], results[slot]
        role = "native_selector" if label == "select.seq2" else "editor"
        guard(slot, role, request)
        response = result["response"]["provider_response"]
        cwd = _system(request, prepared["authoring_system_text"], cwd)
        terminal = bool(request["messages"] and editor._terminal_shape(request["messages"][-1]))
        mutates = any(item.get("type") == "tool_use" and item.get("name") in {"write", "edit"}
                      for item in response["content"])
        if information is None and (mutates or response.get("stop_reason") == "end_turn"):
            information = verify_information_before_decision(request, prepared, cwd=cwd, label=label)
        if response.get("stop_reason") == "end_turn" and not terminal:
            witness = (session.get("normal_session_proof") or {}).get("harvested_strategy")
            normal = verify_normal_session(request, prepared, cwd=cwd, label=label,
                response=response, harvested_strategy=witness)
    _require(session.get("history_guard_audits") == guard.audits, "normal information signed history differs")
    _require(information is not None and session.get("information_proof") == information,
             "normal session omitted or changed its before-decision information proof")
    if not session.get("terminal_note_used"):
        _require(normal is not None and session.get("normal_session_proof") == normal,
                 "normal session omitted or changed its final delivery proof")
    return {"information_proof": information, "normal_session_proof": normal, "artifact_sha256": hashes}
