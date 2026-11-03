"""Read-only HI readiness proof; normal completion precedes terminal sixteen."""
from __future__ import annotations

import json
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
from followups.phase3a_c1_completion_v3.evidence import (
    _sources as _parent_sources,
)
from followups.phase3a_compat_c1_v1.support import OPENCODE_FILES

from . import contract, editor
from . import transport as bounded
from .delivery import _collect, _history, verify_delivery, verify_original_strategy
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
    return _ValidationProfile("phase3a_readiness_recovery_v1", "PHASE3A_RP2_RECOVERY_DEFINITION.md",
                              NATIVE, contract, editor, bounded)


def _sources(search: Path, prefix: str, manifest: dict, hashes: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    # The inherited reader verifies lossless bytes; reject stream/private names before it touches metadata.
    for entry in manifest["required_evidence"]:
        for chunk in entry["chunks"]:
            name = chunk["path"]
            parts = PurePosixPath(name).parts
            _require(isinstance(name, str) and parts and not any(
                p.casefold() in {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
                or "stdout" in p.casefold() or "stderr" in p.casefold() for p in parts),
                "private/stream readiness view forbidden")
    return _parent_sources(search, prefix, manifest, hashes)

def verify_readiness(study: dict, run: Path, state: dict, branch: dict, fixture: bool) -> dict:
    """Verify saved delivery/normal completion, never model quality or efficacy."""
    try:
        return _verify(study, run, state, branch, fixture, _live_profile())
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("counted readiness evidence is incomplete or invalid") from error


def diagnose_saved_rp1(study: dict, run: Path, state: dict, branch: dict) -> dict:
    """Prospective validation of one authenticated old case, never an RP1 approval."""
    from followups.phase3a_rc1_pilot_v1 import contract as old_contract
    from followups.phase3a_rc1_pilot_v1 import editor as old_editor
    from followups.phase3a_rc1_pilot_v1 import support as old_support
    from followups.phase3a_rc1_pilot_v1 import transport as old_transport

    _require(study["study_sha256"] == "e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca"
             and study["source_sha256"] == "64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a"
             and digest({k: v for k, v in study.items() if k != "study_sha256"}) == study["study_sha256"]
             and digest(study["source"]["files"]) == study["source_sha256"]
             and Path(run) == old_support.NATIVE / study["study_sha256"] / "live"
             and digest(branch) == "7ee6e071bd5a3b6e59fdbb2a51df41060601d6dfe35a1dd3d56cb16fe533ebd2",
             "saved RP1 diagnostic has foreign identities")
    for module, name in ((old_contract, "contract.py"), (old_editor, "editor.py"),
                         (old_transport, "transport.py")):
        relative = "followups/phase3a_rc1_pilot_v1/" + name
        _require(Path(module.__file__ or "") == ROOT / relative
                 and _sha((ROOT / relative).read_bytes()) == study["source"]["files"][relative],
                 "saved RP1 validation dependency changed")
    profile = _ValidationProfile("phase3a_rc1_pilot_v1", "PHASE3A_RC1_PILOT_DEFINITION.md",
                                 old_support.NATIVE, old_contract, old_editor, old_transport)
    proof = _verify(study, run, state, branch, False, profile)
    return {"kind": "phase3a-rp2-saved-rp1-readiness-diagnostic-v1", "diagnostic_only": True,
            "original_readiness_passed": False, "approval_published": False,
            "scientific_eligibility": False, "full_strict_predicates_passed": True, "proof": proof}


def diagnose_saved_rp1_original(study: dict, run: Path, state: dict) -> dict:
    """D01 authenticates only the original input; it cannot approve missing other views."""
    _require(study["study_sha256"] == "e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca"
             and Path(run).parts[-2:] == (study["study_sha256"], "live"), "foreign D01 saved case")
    slot = "p3a-01.adaptive.editor.agg1.a1.t07"
    intent = state["intents"][slot]
    _require(intent["request_sha256"] == "234cbed39a5d3cbd8e0469a3309ff0208870e149f90754be2652df0307eacb17",
             "D01 decision request differs")
    decision = _body(intent["request"], set())
    calls, results = _history(decision)
    hashes: dict[str, str] = {}
    search, prefix = run / "search/p3a-01/adaptive", "editor-audit/c1-contracts/agg1.a1"
    manifest = _read(search, prefix + "/manifest.json", hashes)
    _sealed(manifest)
    _require(_sha((search / prefix / "manifest.json").read_bytes()) ==
             "82d57d0fd5c524bdb4f40ff51fcd9730c678daa83fe850ffb292295b3e485016", "D01 manifest differs")
    original, views = _sources(search, prefix, manifest, hashes)
    entry = manifest["required_evidence"][1]
    text = original["harness/systemprompt.md"]
    first = next(iter(calls.values()))
    _require(first["name"] == "read" and first["input"]["filePath"].endswith("/MISSION.md"), "D01 mission-first differs")
    cwd = first["input"]["filePath"].removesuffix("/MISSION.md")
    _require(entry["kind"] == "current_strategy" and entry["path"] == "harness/systemprompt.md"
             and len(text.encode()) == entry["bytes"] == 1211 and _sha(text.encode()) == entry["sha256"],
             "D01 original source identity differs")
    delivered = verify_delivery(decision, {cwd + "/context/" + c["path"]: views[c["path"]] for c in entry["chunks"]})
    _require(sum(row["source_lines"] for row in delivered.values()) == 18, "D01 visible view coverage differs")
    raw = _collect(decision, {cwd + "/context/harness/systemprompt.md"}).get(cwd + "/context/harness/systemprompt.md", {})
    lines = text.splitlines()
    _require(all(1 <= n <= len(lines) and lines[n-1] == value for n, value in raw.items()), "D01 raw contradiction")
    read_paths = {c["input"]["filePath"] for identity, c in calls.items()
                  if c["name"] == "read" and not results[identity].get("is_error")}
    missing = [c["path"] for item in manifest["required_evidence"] for c in item["chunks"]
               if cwd + "/context/" + c["path"] not in read_paths]
    return {"passed": True, "diagnostic_only": True, "scope": "original_input_only", "decision_cwd": cwd,
            "route": "declared_lossless_view", "source_path": entry["path"], "source_sha256": entry["sha256"],
            "source_utf8_bytes": 1211, "view_numbered_lines": 18, "view_delivery": delivered,
            "global_tool_call_count": len(calls), "global_owned_result_count": len(results),
            "missing_declared_views_with_no_successful_read": missing, "artifact_sha256": hashes,
            "full_readiness_passed": False, "approval_published": False, "scientific_eligibility": False}


def diagnose_saved_hi(study: dict, run: Path, state: dict, branch: dict) -> dict:
    """Exactly the approved HI76 prefix through current strict predicates, never approval."""
    from followups.phase3a_h1_integrated_v1 import contract as old_contract
    from followups.phase3a_h1_integrated_v1 import editor as old_editor
    from followups.phase3a_h1_integrated_v1 import support as old_support
    from followups.phase3a_h1_integrated_v1 import transport as old_transport

    identities = {
        "study": study["study_sha256"] == "a233fbc5ed3fedaa21e6b364ecfbfdd15496e25c005897067eb2cc7aed90d28a",
        "source": study["source_sha256"] == "2440535e5274c106a44efb28cf9533308b7dbea8fd8768649a089145cbc150a3",
        "study_seal": digest({k: v for k, v in study.items() if k != "study_sha256"}) == study["study_sha256"],
        "source_map": digest(study["source"]["files"]) == study["source_sha256"],
        "branch_digest": digest(branch) == "784bcee70d014ac050d4ff542102e8128e51dfd313ed7f900a746bf3c09ac9b3",
        "prefix_count": state["attempts"] == 76 and len(state["intents"]) == len(state["results"]) == 76}
    _require(all(identities.values()), "HI diagnostic identity differs: " + ",".join(k for k, v in identities.items() if not v))
    _require(run == old_support.NATIVE / study["study_sha256"] / "live",
             "HI diagnostic run differs: " + str(run) + " != " + str(old_support.NATIVE / study["study_sha256"] / "live"))
    for module, name in ((old_contract, "contract.py"), (old_editor, "editor.py"), (old_transport, "transport.py")):
        relative = "followups/phase3a_h1_integrated_v1/" + name
        _require(Path(module.__file__ or "") == ROOT / relative
                 and _sha((ROOT / relative).read_bytes()) == study["source"]["files"][relative],
                 "HI validation dependency changed")
    profile = _ValidationProfile("phase3a_h1_integrated_v1", "PHASE3A_H1_INTEGRATED_PILOT_DEFINITION.md",
                                 old_support.NATIVE, old_contract, old_editor, old_transport)
    proof = _verify(study, run, state, branch, False, profile)
    return {"diagnostic_only": True, "approval_published": False, "scientific_eligibility": False,
            "full_strict_predicates_passed": True, "proof": proof}


def _verify(study: dict, run: Path, state: dict, branch: dict, fixture: bool,
            validation: _ValidationProfile) -> dict:
    contract, editor, bounded = validation.contract, validation.editor, validation.transport
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
    _require(search.is_absolute() and ".." not in search.parts and Path(run).is_relative_to(validation.native_root), "invalid readiness run path")
    hashes: dict[str, str] = {}
    scoped = {slot for slot, row in state["intents"].items() if row["cell"] == "p3a-01:adaptive"}
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
                 and manifest["editor_profile_sha256"] == digest(editor.profile())
                 and manifest["prior_policy_id"] == contract.parent.POLICY_ID
                 and manifest["prior_contract_source_sha256"] == _sha(Path(contract.parent.__file__).read_bytes())
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
            "pilot": "p3a-01", "fixture": fixture}, "accepted native session differs from its saved audit")
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
                     and not stages[stage_name]["effective_changed"], "changed strategy lacks an actual write/edit")
        sessions.append({"label": label, "ordinary_http_calls": len(rows), "mission_first": True,
            "complete_evidence_before_decision": True, "source_files": len(original), "lossless_views": len(views),
            "delivered_file_sha256": {name.removeprefix(cwd + "/"): value["sha256"] for name, value in delivery.items()},
            "strategy_mutations": len(strategy_mutations), "notes_mutations": len(notes_mutations),
            "normal_final_notes_sha256": _sha(final.encode()), "post_write_verification": True,
            "absent_caller_ids_normalized_in_parser_copy_only": sorted(normalized),
            "effective_changed": stages[stage_name]["effective_changed"],
            "original_strategy_delivery": original_delivery})
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
                 and clock["renewable"] is False and clock["editor_profile_sha256"] == digest(editor.profile()), "absolute conversation admission clock differs")
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
