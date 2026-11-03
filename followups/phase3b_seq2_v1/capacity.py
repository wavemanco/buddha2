"""Observed-size, full native context capacity evidence; strictly fixture-only and offline."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from harness2.core.proposer import ProposerError

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_bytes_once

from . import adapter, contract, editor, ledger_core, native, strategy
from .mocks import SDKMock
from .support import NATIVE, PARENT_STUDY_SHA, ROOT, path, publish, require, safe, seal

PARENT_LIVE = ROOT / "runs/phase3a-readiness-recovery-v1/native" / PARENT_STUDY_SHA / "live"
ALIASES = {"base1": "base1", "base2": "base1", "inv1": "inv1", "dom1": "dom1", "c1": "agg1",
           "inv2": "inv1", "dom2": "dom1", "c2": "agg1"}
HISTORY = {"inv1": (), "dom1": (), "c1": ("inv1", "dom1"),
           "inv2": ("inv1", "dom1", "c1"), "dom2": ("inv1", "dom1", "c1"),
           "c2": ("inv1", "dom1", "c1", "inv2", "dom2")}


def _copy(source: Path, target: Path, inventory: dict) -> dict:
    source = Path(source)
    require(source.is_absolute() and ".." not in source.parts and source.is_relative_to(PARENT_LIVE / "search"),
            "capacity input is outside named exposed native artifacts")
    relative = source.relative_to(PARENT_LIVE / "search").parts
    require(len(relative) >= 3 and relative[0] in {f"p3a-{n:02}" for n in range(1, 5)}
            and relative[1] == "adaptive" and not any("score" in name.casefold() or "grade" in name.casefold()
                or "assessment" in name.casefold() for name in relative), "capacity input is not a named solver/native artifact")
    source = safe(source)
    data = source.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    write_bytes_once(safe(target), data)
    inventory[source.relative_to(ROOT).as_posix()] = {"sha256": sha, "bytes": len(data),
                                                   "copy": str(target)}
    return json.loads(data) if source.suffix == ".json" else {}


def assemble(output: Path) -> dict:
    # The copied source harnesses stay immutable after population; reuse the existing
    # before/after readonly validator rather than rehash every source for every view.
    with strategy.validation_scope(readonly=True):
        return _assemble(output)


def _assemble(output: Path) -> dict:
    """Borrow exact public solver artifacts, not old assessments or new candidates."""
    from harness2.core import context, prompts, schedule
    from harness2.core.spec import ChannelSpec, RunView

    output = path(output)
    require(output.is_relative_to(NATIVE) and not output.exists(), "capacity requires a fresh explicit fixture-only native root")
    output.mkdir(parents=True)
    inventory: dict = {}
    cases: list[dict] = []
    inputs: list[dict] = []
    profile = []
    for number in range(1, 5):
        pilot = f"p3a-{number:02}"
        source = PARENT_LIVE / "search" / pilot / "adaptive"
        destination = output / "inputs" / pilot
        identity = _copy(source / "identity.json", destination / "identity.json", inventory)
        task = identity["task"]
        old = schedule.Namespace("noveltybench-phase3a", "portfolio-api", "agg", 1, None, identity["tag"])
        summary = _copy(old.task_dir(source / "native", task["id"]) / "summary.json",
                        destination / "summary.json", inventory)
        notes = {stage["label"]: stage["notes"] for stage in summary["modes"]["agg"]["stages"]}
        runs = {}
        for label in ("base1", "inv1", "dom1", "agg1"):
            original = source / "rollouts" / label
            copied = destination / "rollouts" / label
            rollout = _copy(original / "rollout.json", copied / "rollout.json", inventory)
            require(rollout["status"] == "complete" and len(rollout["requests"]) == 12,
                    "capacity requires the complete already-exposed solver record")
            checked_harness = strategy.validate_harness(original / "harness")
            for relative in checked_harness["raw_files_sha256"]:
                _copy(original / "harness" / relative, copied / "harness" / relative, inventory)
            require(strategy.validate_harness(copied / "harness") == checked_harness, "capacity copy changed a strategy")
            runs[label] = copied
        channel = ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=24, timeout=600)
        cap_adapter = native.PortfolioAdapter(task, runs["base1"] / "harness", study_sha256=digest({"capacity": pilot}),
            run_root=output / "assembly" / pilot, tag="capacity-fixture",
            dispatch=lambda *args: (_ for _ in ()).throw(ContractError("capacity assembly cannot dispatch")),
            fixture=True, channel=channel, known_results={})
        views = {label: RunView(label=label, run_id="capacity-borrowed/" + label, run_dir=runs[original], ok=True,
                               delivered=True) for label, original in ALIASES.items()}
        for label, view in views.items():
            trajectory = cap_adapter.trajectory(view.run_dir, obs_trunc=50_000)
            answers = cap_adapter.deliverable_text(view.run_dir)
            profile.append({"pilot": pilot, "label": label, "borrowed_source": ALIASES[label],
                "trajectory_utf8_bytes": len(trajectory.encode()), "answers_utf8_bytes": len(answers.encode()),
                "strategy_utf8_bytes": (view.run_dir / "harness/systemprompt.md").stat().st_size,
                "notes_utf8_bytes": len(notes.get(ALIASES[label], "").encode())})
        for label in native.STAGES:
            round_number = int(label[-1])
            role = "INV" if label.startswith("inv") else "DOM" if label.startswith("dom") else "AGG"
            baseline = runs["base1"] if round_number == 1 else runs["agg1"]
            prior = HISTORY[label]
            tree = context.build(output / "contexts" / pilot / label, cap_adapter, task["id"],
                [views["base1"], views["base2"]], harness_dir=baseline / "harness", library_dir=None,
                pool=[(earlier, views[earlier].run_dir / "harness", views[earlier]) for earlier in prior],
                decisions={earlier: notes[ALIASES[earlier]] for earlier in prior})
            job = (prompts.compose_round(contract.benchmark_prompts(), cap_adapter.substrate.surface(), t=round_number, k=2)
                if role == "AGG" else prompts.propose(contract.benchmark_prompts(), role,
                    cap_adapter.substrate.surface(), k=2, index=round_number, round_t=round_number))
            mission = context.mission(tree, job=job)
            prepared = contract.prepare_contract(mission, tree.root, label + ".a1")
            manifest = prepared["manifest"]
            required = manifest["required_evidence"]
            require(set(manifest["context_inventory"]) == contract._layout(role, label + ".a1")[0], "capacity context omitted evidence")
            row = {"pilot": pilot, "label": label, "root": str(tree.root), "mission": mission,
                "required_evidence_files": len(required), "lossless_views": sum(len(entry["chunks"]) for entry in required),
                "original_utf8_bytes": sum(value["bytes"] for value in manifest["context_inventory"].values()),
                "derived_view_utf8_bytes": sum(len(value.encode()) for value in prepared["evidence_files"].values()),
                "configured_system_utf8_bytes": len(prepared["authoring_system_text"].encode()),
                "context_inventory": manifest["context_inventory"], "round": round_number,
                "current_source": "base1" if round_number == 1 else "agg1",
                "full_cumulative_labels": list(prior), "two_reference_labels": ["base1", "base2"],
                "manifest_sha256": manifest["sha256"], "no_trimming_or_summaries": True}
            cases.append(row)
        inputs.append({"pilot": pilot, "task": task, "runs": {key: str(value) for key, value in runs.items()}})
    for source, row in inventory.items():
        require(file_hash(safe(ROOT / source)) == row["sha256"], "historical capacity input changed")
    result = seal({"kind": "phase3b-capacity-assembly-v1", "fixture": True, "provider_calls": 0,
        "source_inventory": inventory, "observed_component_profile": profile, "contexts": cases,
        "inputs": inputs, "aliases": ALIASES, "complete_native_contexts": 24,
        "limitation": "Exact components borrowed from exposed3A; duplicated references/checkpoints are capacity fixtures, not new model samples or genuine recursive research evidence."})
    publish(output / "assembly.json", result)
    return result


class CapacitySDK:
    """Real pinned SDK serialization with concrete in-memory fake HTTP only."""
    def __init__(self, study_sha256: str, output: Path | None = None):
        self.study_sha256 = study_sha256
        self.mock = SDKMock()
        self.results: dict = {}
        self.intents: dict = {}
        self.requests: list[dict] = []
        self.sdk_calls = 0
        self.rejects = 0
        self.output = output
        self.proposer: adapter.CompatibleProposer | None = None
        self._actual_wires: dict = {}

    def __enter__(self):
        import anthropic
        import httpx2

        def handle(request):
            self._actual_wire_bytes = len(request.content)
            self._actual_wire_sha256 = hashlib.sha256(request.content).hexdigest()
            selected = self.mock._selected
            if selected is not None:
                self._actual_wires[selected[1]] = {"bytes": self._actual_wire_bytes,
                    "sha256": self._actual_wire_sha256, "request": json.loads(request.content)}
            return self.mock._handle(request, http_module=httpx2)

        self.client = anthropic.Anthropic(api_key="fixture-not-a-secret", max_retries=0,
            base_url="https://api.anthropic.com", http_client=httpx2.Client(trust_env=False,
                transport=httpx2.MockTransport(handle)))
        return self

    def __exit__(self, *exc):
        try:
            self.publish_serialization()
        finally:
            self.client.close()

    def publish_serialization(self):
        if self.output is None:
            return
        files = {}
        for slot, intent in self.intents.items():
            target = self.output / "serializations" / (slot + ".json")
            row = next((value for value in self.requests if value["slot_id"] == slot), None)
            value = {"wire": row, "actual_http_wire": self._actual_wires.get(slot),
                     "intent": intent, "result": self.results.get(slot)}
            publish(target, value)
            files[slot] = {"path": target.relative_to(self.output).as_posix(), "sha256": file_hash(target)}
        sessions = ({} if self.proposer is None else {
            key: {name: value for name, value in session.items() if name != "offline_wire"}
            for key, session in self.proposer.phase3a_evidence()["sessions"].items()})
        publish(self.output / "actual-sdk-serialization.json", {"fixture": True, "provider_calls": 0,
            "files": files, "sessions": sessions, "sdk_mock_calls": self.sdk_calls,
            "mock_errors": copy.deepcopy(self.mock.c1_errors)})

    def dispatch(self, slot: str, role: str, request: dict) -> dict:
        from .transport import normalize
        tools = read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
        try:
            ledger_core.validate_request(role, request, editor_tools=tools)
        except ContractError:
            self.rejects += 1
            raise
        require(slot not in self.results, "capacity cannot resend a fixture request")
        intent = {"slot_id": slot, "role": role, "fixture": True, "study_sha256": self.study_sha256,
            "request_sha256": digest(request), "request": copy.deepcopy(request)}
        self.intents[slot] = intent
        self.mock.select(role, slot)
        self.sdk_calls += 1
        message = self.client.messages.create(**request)
        response = normalize(role, message.model_dump(mode="json", exclude_none=True), message._request_id, 0.0)
        result = {"slot_id": slot, "role": role, "fixture": True, "study_sha256": self.study_sha256,
            "status": "response", "request_sha256": digest(request), "dispatch_id": "capacity-fixture:" + slot,
            "spent_micro_usd": 0, "reserved_micro_usd": 0, "intent_sha256": digest(intent), "response": response}
        self.results[slot] = result
        wire = self.mock.records[-1]
        self.requests.append({"slot_id": slot, "role": role, "effective_bytes": len(ledger_core._wire(request)),
            "sdk_serialized_bytes": self._actual_wire_bytes, "sdk_serialized_sha256": self._actual_wire_sha256,
            "request_sha256": digest(request), "actual_sdk_request": copy.deepcopy(wire["request"]),
            "response_content": copy.deepcopy(wire["response"]["content"])})
        return copy.deepcopy(result)


def _boundary(request: dict, role: str, sdk: CapacitySDK) -> dict:
    """Independent exact schema/byte-bound negatives; never claimed as realistic evidence."""
    positive = copy.deepcopy(request)
    positive["messages"] = [{"role": "user", "content": "BOUNDARY-FIXTURE "}]
    positive["messages"][0]["content"] += "x" * (2_097_152 - len(ledger_core._wire(positive)))
    tools = read_json(ROOT / "followups/phase3a_v1/editor-tools.json")
    ledger_core.validate_request(role, positive, editor_tools=tools)
    require(len(ledger_core._wire(positive)) == 2_097_152, "exact byte fixture is not exact")
    negative = copy.deepcopy(positive)
    negative["messages"][0]["content"] += "x"
    count = sdk.sdk_calls
    try:
        sdk.dispatch("capacity-oversize-" + role, role, negative)
    except ContractError:
        pass
    else:
        raise ContractError("oversize capacity body was admitted")
    require(sdk.sdk_calls == count, "oversize rejection reached SDK")
    return {"role": role, "exact_bytes": 2_097_152, "oversize_bytes": 2_097_153,
            "sdk_calls": sdk.sdk_calls - count, "rejected_before_intent": "capacity-oversize-" + role not in sdk.intents,
            "scope": "Separate byte/schema boundary only; realistic evidence is the unchanged native-context history above."}


def prove(output: Path) -> dict:
    require({entry.name for entry in Path("/sys/class/net").iterdir()} == {"lo"}, "capacity requires actual network-none containment")
    return _probe(output, assemble(output))


def _probe(output: Path, assembly: dict) -> dict:
    from harness2.core import selection
    from harness2.core.spec import ChannelSpec, RunView

    require({entry.name for entry in Path("/sys/class/net").iterdir()} == {"lo"}, "capacity requires actual network-none containment")
    largest = max(assembly["contexts"], key=lambda row: row["derived_view_utf8_bytes"] + row["configured_system_utf8_bytes"])
    source = next(row for row in assembly["inputs"] if row["pilot"] == largest["pilot"])
    study = digest({"kind": "capacity-only-not-a-study-grant", "assembly": assembly["sha256"]})
    clocks: dict = {}
    with CapacitySDK(study, output) as sdk:
        prop = adapter.CompatibleProposer(pilot="p3b-01", study_sha256=study, dispatch=sdk.dispatch,
            audit_dir=output / "editor-audit", fixture=True,
            halt=lambda *args, **kwargs: None, register_contract=sdk.mock.register_contract,
            register_deadline=lambda identity, deadline: clocks.setdefault(identity, deadline))
        sdk.proposer = prop
        observed_stages = [largest, *[row for row in assembly["contexts"]
            if row["pilot"] == largest["pilot"] and row["label"] != largest["label"]]]
        require(len(observed_stages) == 6, "capacity requires the complete six-stage observed context package")
        for observed in observed_stages:
            reply = prop.call(observed["mission"], Path(observed["root"]), observed["label"] + ".a1",
                              max_attempts=1, harvest="context/harness")
            require(reply.ok and reply.text.strip(), "full-context author did not complete")
        channel = ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=24, timeout=600)
        cap_adapter = native.PortfolioAdapter(source["task"], Path(source["runs"]["base1"]) / "harness",
            study_sha256=study, run_root=output / "selector-adapter", tag="capacity-only", dispatch=sdk.dispatch,
            fixture=True, channel=channel, known_results={})
        candidates = {label: RunView(label=label, run_id="capacity-only/" + label,
            run_dir=Path(source["runs"]["agg1"]), ok=True, delivered=True) for label in ("c1", "c2")}
        chosen = selection.run_selection(source["task"]["id"], 2, "seq", candidates,
            adapter=cap_adapter, prop=prop, work_dir=output / "probe", pool_kind="finals")
        require(chosen.ok and not chosen.fallback and not chosen.trivial, "full native capacity selector did not complete normally")
        # Fixed-generation replay uses complete exposed text, explicitly relabelled as a fixture.
        templates = [read_json(Path(source["runs"][key]) / "rollout.json") for key in ("base1", "inv1", "dom1", "agg1")]
        cursor = {"candidate": -1, "answer": 0}
        def fixed_dispatch(slot, role, request):
            if role == "fixed_selector":
                return sdk.dispatch(slot, role, request)
            if role == "plan":
                cursor["candidate"] += 1
                cursor["answer"] = 0
            original = templates[cursor["candidate"] % len(templates)]
            rows = [row for row in original["requests"] if row["role"] == role]
            selected = rows[cursor["answer"]] if role == "answer" else rows[0]
            if role == "answer":
                cursor["answer"] += 1
            raw = copy.deepcopy(selected["response"])
            raw["request_id"] = "capacity-exposed-text-copy-" + slot
            return {"slot_id": slot, "role": role, "fixture": True, "study_sha256": study,
                "status": "response", "request_sha256": digest(request), "dispatch_id": "capacity-copy:" + slot,
                "spent_micro_usd": 0, "reserved_micro_usd": 0, "intent_sha256": digest({"slot": slot}), "response": raw}
        fixed = strategy.fixed_best12(source["task"], Path(source["runs"]["base1"]) / "harness",
            study_sha256=study, run_id="capacity-only-fixed12", dispatch=fixed_dispatch, fixture=True)
        require(fixed["status"] == "complete" and len(fixed["candidates"]) == 12, "complete fixed capacity selector did not finish")
        sessions = editor.validate_persisted_sessions(output / "editor-audit", study_sha256=study,
            pilot="p3b-01", fixture=True, results=sdk.results, intents=sdk.intents)
        require(len(sessions) == 7 and all(row["status"] == "valid" and row.get("normal_session_proof")
            and row.get("information_proof") for row in sessions.values()), "capacity full-read normal proofs are missing")
        require(all(row["sdk_serialized_bytes"] <= 2_097_152 for row in sdk.requests),
                "actual SDK serialization exceeds the declared byte ceiling")
        boundaries = [_boundary(next(row["request"] for row in sdk.intents.values() if row["role"] == role), role, sdk)
                      for role in ("editor", "native_selector", "fixed_selector")]
        reserves = {role: ledger_core._reservation(role) for role in ("editor", "native_selector", "fixed_selector")}
        require(all(row["input"] == 1_000_000 and row["micro_usd"] == 11_440_000 for row in reserves.values()),
                "serialized bytes were confused with the independent full model-input liability")
        sdk.publish_serialization()
        aggregate = prop.phase3a_evidence()
        branch = {"kind": "capacity-only-branch-envelope-v1", "fixture": True,
            "c1_evidence": prop.c1_evidence(), "result": {"editor_evidence": aggregate,
                "rollouts": {label: read_json(Path(source["runs"][original]) / "rollout.json")
                             for label, original in ALIASES.items()}}}
        aggregate_bytes = len((json.dumps(aggregate, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
        branch_bytes = len((json.dumps(branch, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
        require(max(aggregate_bytes, branch_bytes) <= 32_000_000,
                "measured combined observed editor/branch metadata exceeds existing32,000,000-byte artifact bound")
        publish(output / "aggregate-editor-evidence.json", aggregate)
        publish(output / "aggregate-branch-envelope.json", branch)
        from . import workflow
        require(native.read_json(output / "aggregate-editor-evidence.json") == aggregate
                and native.read_json(output / "aggregate-branch-envelope.json") == branch
                and workflow.read(output / "aggregate-branch-envelope.json") == branch,
                "actual native/workflow public readers did not preserve combined observed metadata")
        result = seal({"kind": "phase3b-s2-capacity-v1", "passed": True, "fixture": True, "provider_calls": 0,
            "source_inventory": assembly["source_inventory"], "source_assembly_sha256": assembly["sha256"],
            "complete_native_contexts": 24, "largest_author_context": largest,
            "sdk_mock_calls": sdk.sdk_calls, "actual_history_serialized": True,
            "maximum_effective_bytes": max(row["effective_bytes"] for row in sdk.requests),
            "maximum_sdk_serialized_bytes": max(row["sdk_serialized_bytes"] for row in sdk.requests),
            "payload_ceiling_bytes": 2_097_152, "full_read_proofs": {key: {"information": row["information_proof"],
                "normal": row["normal_session_proof"]} for key, row in sessions.items()},
            "fixed_candidates": 12, "native_candidates": 2, "no_trimming_or_summaries": True,
            "byte_boundary_negatives": boundaries, "independent_model_reservations": reserves,
            "combined_editor_evidence_bytes": aggregate_bytes, "combined_branch_envelope_bytes": branch_bytes,
            "public_artifact_bound_bytes": 32_000_000, "all_six_author_contexts_exercised": True,
            "combined_native_and_workflow_readers_passed": True,
            "clock_records": clocks, "capacity_only_no_scientific_effect_or_live_readiness_claim": True})
        publish(output / "capacity.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prove(args.output)
    except (ContractError, ProposerError, OSError, ValueError, KeyError, TypeError) as exc:
        target = safe(args.output / "capacity.json")
        if not target.exists():
            publish(target, seal({"kind": "phase3b-s2-capacity-v1", "passed": False, "provider_calls": 0,
                "fixture": True, "decision": "change-required", "error_type": type(exc).__name__, "reason": str(exc),
                "no_trimming_or_cap_change": True}))
        print({"passed": False, "decision": "change-required", "error_type": type(exc).__name__})
        return 1
    print({"passed": result["passed"], "maximum_effective_bytes": result["maximum_effective_bytes"],
           "sdk_mock_calls": result["sdk_mock_calls"], "provider_calls": 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
