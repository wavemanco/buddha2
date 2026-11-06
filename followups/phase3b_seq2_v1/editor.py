"""Versioned twenty-four-request boundary around the unchanged native proposer.

Reuse the frozen tool, response, snapshot and eligibility rules.  Only the
external conversation profile and its source-bound replay have a new version.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from harness2 import config
from harness2.core.proposer import Proposer, ProposerError
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest, read_json, write_once
from followups.phase3a_compat_c1_v1.support import PRIVATE
from followups.phase3a_v1 import editor as frozen

from .deadline import CONVERSATION_POLICY, FETCH_TIMEOUT, NATIVE_TIMEOUT
from .delivery import normalized_output
from .history import HistoryGuard
from .support import read as read_public
from .support import safe

MAX_STEPS = 24
NORMAL_STEPS = 23
PROFILE_ID = "phase3b-seq2-editor-soft-timing-v1"
_SERIAL = frozen._SERIAL
TOOLS, _FALSE = frozen.TOOLS, frozen._FALSE
_LABEL = re.compile(r"(?:(?:inv[12]|dom[12]|c[12])\.a[12]|select\.seq2)\Z")
_require = frozen._require
terminal_note, _terminal_shape = frozen.terminal_note, frozen._terminal_shape
input_snapshot, session_eligibility = frozen.input_snapshot, frozen.session_eligibility
sse = frozen.sse
TERMINAL_NOTE_SHA256 = frozen.TERMINAL_NOTE_SHA256
TERMINAL_POLICY = "opencode-max-steps-twenty-four-user-role-v1"


def selector_snapshot(context: Path, *, owned_workspace: Path | None = None) -> dict:
    """Bind the anonymous native originals, without manufacturing a strategy harvest."""
    roots = None
    if owned_workspace is not None:
        _require(owned_workspace.parent == Path("/tmp")  # nosec B108: validates the exact native-created tmpfs root; does not create a predictable directory
                 and re.fullmatch(r"harness2-prop-[A-Za-z0-9_-]{6,64}", owned_workspace.name) is not None
                 and context == owned_workspace / "context", "selector snapshot is not its owned native context")
        roots = (owned_workspace,)
    context = safe(context, roots=roots)
    manifest = read_json(safe(context / "C1_MANIFEST.json", roots=roots))
    files = manifest.get("context_inventory", {})
    _require(manifest.get("role") == "SELECT" and manifest.get("label") == "select.seq2"
             and isinstance(files, dict) and "task.md" in files
             and 2 <= len(files) <= 3 and all(name == "task.md" or
                 re.fullmatch(r"candidates/[A-Za-z0-9_-]+\.md", name) for name in files),
             "selector snapshot has noncandidate evidence")
    for name, expected in files.items():
        item = safe(context / name, roots=roots)
        data = item.read_bytes()
        _require(expected == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
                 "selector candidate bytes changed")
    body = {"kind": "phase3b-selector-input-v1", "files": files,
            "effective_strategy_sha256": None}
    return {**body, "sha256": digest(body)}


def _validated_snapshot(value: dict, label: str) -> dict:
    if label != "select.seq2":
        return input_snapshot(value["tree"])
    body = {key: item for key, item in value.items() if key != "sha256"}
    _require(set(body) == {"kind", "files", "effective_strategy_sha256"}
             and body["kind"] == "phase3b-selector-input-v1"
             and body["effective_strategy_sha256"] is None and isinstance(body["files"], dict)
             and value.get("sha256") == digest(body), "selector snapshot seal differs")
    return value


def tool_boundary(content: list, cwd: Path, *, selector: bool = False) -> None:
    """Reject private/runtime paths lexically before the frozen filesystem checks."""
    _require(not any(part.casefold() in PRIVATE for part in Path(cwd).parts), "private editor workspace")
    _require(isinstance(content, list), "editor response content must be a list")
    for block in content:
        _require(isinstance(block, dict), "invalid editor content block")
        if block.get("type") != "tool_use":
            continue
        args = block.get("input")
        _require(isinstance(args, dict) and isinstance(args.get("filePath"), str), "invalid tool file path")
        if selector and block.get("name") != "read":
            _require(block.get("name") in {"write", "edit"} and Path(args["filePath"]) == cwd / "output/answer.md",
                     "selector may not write candidate evidence or strategy")
        parts = Path(args["filePath"]).parts
        _require(not any(part.casefold() in PRIVATE or part.startswith(".")
                         or "stdout" in part.casefold() or "stderr" in part.casefold() for part in parts),
                 "private/runtime/stream editor access forbidden")
    frozen.tool_boundary(content, cwd)


def profile() -> dict:
    from .contract import READ_CONSUMPTION_POLICY_ID

    return {"id": PROFILE_ID, "steps": MAX_STEPS, "ordinary_steps": NORMAL_STEPS,
            "terminal_turn": MAX_STEPS, "terminal_note_sha256": TERMINAL_NOTE_SHA256,
        "read_consumption_policy": READ_CONSUMPTION_POLICY_ID,
            "timing_policy": copy.deepcopy(CONVERSATION_POLICY),
            "native_subprocess_cap_seconds": NATIVE_TIMEOUT, "OpenCode_fetch_cap_seconds": FETCH_TIMEOUT}


def terminal_translation() -> dict:
    return {"policy_id": TERMINAL_POLICY, "turn": MAX_STEPS, "note_sha256": TERMINAL_NOTE_SHA256,
            "from_role": "assistant", "to_role": "user"}


def configuration(base_url: str) -> dict:
    value = frozen.configuration(base_url)
    value["agent"]["build"]["steps"] = MAX_STEPS
    value["provider"]["anthropic"]["options"]["timeout"] = FETCH_TIMEOUT * 1000
    return value


def effective_request(raw: dict, *, turn: int | None = None) -> dict:
    _require(turn is None or type(turn) is int and 1 <= turn <= MAX_STEPS,
             "editor turn is outside the declared profile")
    # Reuse every frozen body/tool/thinking/billing check after validating the
    # sole declared prefill translation at its new, exact terminal boundary.
    value = copy.deepcopy(raw)
    messages = value.get("messages") if isinstance(value, dict) else None
    last = messages[-1] if isinstance(messages, list) and messages and isinstance(messages[-1], dict) else None
    terminal_prefill = bool(last and last.get("role") == "assistant" and _terminal_shape(last))
    if turn == MAX_STEPS:
        _require(terminal_prefill, "twenty-fourth request requires the pinned terminal control")
    if last and last.get("role") == "assistant":
        _require(turn == MAX_STEPS and terminal_prefill, "unsupported final assistant prefill")
        last["role"] = "user"
    return frozen.effective_request(value, turn=turn)


@contextmanager
def relay(cwd: Path, dispatch: Callable, prefix: str, record: dict, halt: Callable, *, prepared: dict):
    exchanges = threading.RLock()
    completion: dict = {}
    def observed_dispatch(slot, role, request):
        from .evidence import observe_mutation_completion

        record["mutation_witnesses"] = observe_mutation_completion(request, cwd=cwd, slot=slot,
            previous=record.get("mutation_witnesses", []))
        return dispatch(slot, role, request)

    guarded_dispatch = HistoryGuard(observed_dispatch, prefix)
    record["history_guard_profile"] = "p3a-hi-ordinary-and-terminal-v1"
    settled: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            with exchanges:
                self._exchange()

        def _exchange(self):
            try:
                _require(self.path == "/v1/messages" and self.headers.get("x-api-key") == _FALSE,
                         "unknown relay route or local credential")
                length = int(self.headers.get("Content-Length", "0"))
                _require(0 < length <= 2097152, "editor payload is outside its byte bound")
                raw = json.loads(self.rfile.read(length).decode("utf-8"))
                if record.get("fixture"):
                    record.setdefault("offline_wire", []).append(raw)
                _require(not record.get("error"), "editor conversation has a boundary hold")
                raw_sha = digest(raw)
                if raw_sha in settled:
                    record["local_response_replays"] = record.get("local_response_replays", 0) + 1
                    self._send(settled[raw_sha])
                    return
                turn = len(record["requests"]) + 1
                _require(turn <= MAX_STEPS, "editor conversation limit")
                request = effective_request(raw, turn=turn)
                translation = terminal_translation() if raw["messages"][-1].get("role") == "assistant" else None
                record["terminal_note_used"] = record.get("terminal_note_used", False) or translation is not None
                slot = f"{prefix}.t{turn:02}"
                role = "native_selector" if prefix.endswith(".select.seq2") else "editor"
                result = guarded_dispatch(slot, role, request)
                record["history_guard_audits"] = copy.deepcopy(guarded_dispatch.audits)
                record["requests"].append({"slot_id": slot, "raw_sha256": digest(raw),
                    "effective_sha256": digest(request), "result_sha256": digest(result),
                    "role_translation": translation})
                _require(result.get("status") == "response", "editor result is unresolved")
                response = result["response"]["provider_response"]
                from .evidence import verify_information_before_decision

                label = prefix.split(".editor.", 1)[1]
                decision = response.get("stop_reason") == "end_turn" or any(
                    block.get("type") == "tool_use" and block.get("name") in {"write", "edit"}
                    for block in response["content"])
                if decision and "information_proof" not in record:
                    record["information_proof"] = verify_information_before_decision(
                        request, prepared, cwd=str(cwd), label=label)
                if response.get("stop_reason") == "end_turn" and not record["terminal_note_used"]:
                    # Native output is known only after OpenCode returns its file/stdout result.
                    completion.update(request=request, response=response)
                tool_boundary(response["content"], cwd, selector=prefix.endswith(".select.seq2"))
                payload = sse(response)
                settled[raw_sha] = payload
                self._send(payload)
            except Exception as exc:
                record["error"] = type(exc).__name__
                if record.get("fixture"):
                    record["offline_error_detail"] = str(exc)
                from followups.phase3a_v1.accounting import (
                    AssessmentBudgetStop,
                    CellBudgetStop,
                    CheckpointStop,
                    PhaseBudgetStop,
                )
                if not isinstance(exc, (AssessmentBudgetStop, CellBudgetStop, CheckpointStop, PhaseBudgetStop)):
                    halt("editor_boundary_violation", evidence_sha256=digest({
                        "prefix": prefix, "error_type": type(exc).__name__, "requests": record["requests"]}))
                # Provider details and exception strings never cross into editor logs.
                payload = b'{"type":"error","error":{"type":"permission_error","message":"Phase3A boundary stopped this conversation"}}'
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def _send(self, payload):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # Keep the native subprocess scope open until every admitted request has
    # settled and its returned tool calls have passed the boundary check.
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", completion
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def validate_persisted_sessions(audit_dir: Path, *, study_sha256: str, pilot: str,
                                fixture: bool, results: dict | None = None, intents: dict | None = None) -> dict:
    """Read-only proof replay, including unfinished logical conversations."""
    from followups.phase3a_v1.accounting import IntegrityStop

    audit_dir = Path(audit_dir)
    roots = (Path(__file__).resolve().parents[2] / "runs/phase3b-seq2-v1/native",
             Path("/results/phase3b-seq2-v1/native"))
    if (not audit_dir.is_absolute() or ".." in audit_dir.parts
            or any(part.lower() in PRIVATE or "stdout" in part.casefold() or "stderr" in part.casefold()
                   for part in audit_dir.parts)
            or not any(audit_dir.is_relative_to(root) and audit_dir != root for root in roots)):
        raise IntegrityStop("persisted editor proof is outside its HI boundary")
    directory = audit_dir / "phase3a-sessions"
    binding = {"fixture": fixture, "study_sha256": study_sha256, "pilot": pilot,
               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "editor_profile_sha256": digest(profile())}
    sessions: dict[str, dict] = {}
    started: set[str] = set()
    inputs: dict[str, dict] = {}
    try:
        _require(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                         for p in (directory, *directory.parents)), "linked editor proof path")
        if not directory.exists():
            _require(not results or not any(slot.startswith(pilot + ".adaptive.editor.") for slot in results),
                     "editor results lack their durable logical-conversation intents")
            return sessions
        for path in directory.iterdir():
            match = re.fullmatch(r"((?:inv[12]|dom[12]|c[12])\.a[12]|select\.seq2)\.(started|settled)\.json", path.name)
            if match is None:
                raise ContractError("unknown editor proof file")
            _require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction())
                     and path.is_file(), "nonordinary editor proof entry")
            label, kind = match.group(1), match.group(2)
            # Session metadata can include many complete fixture wire requests.
            # Reuse the strict bounded public-artifact reader; every individual
            # provider request remains limited to 2 MiB before its SDK intent.
            value = read_public(path)
            _require(path.read_bytes() == (json.dumps(value, sort_keys=True, ensure_ascii=False,
                     allow_nan=False, indent=2) + "\n").encode("utf-8"), "editor proof bytes are not canonical")
            _require(isinstance(value, dict) and value.get("binding") == binding
                     and value.get("label") == label, "editor proof binding differs")
            if kind == "started":
                _require(set(value) == {"binding", "label", "input_snapshot"}
                         and value["input_snapshot"] == _validated_snapshot(value["input_snapshot"], label),
                         "editor conversation input differs")
                started.add(label)
                inputs[label] = value["input_snapshot"]
                continue
            _require(set(value) == {"binding", "label", "session", "sha256"}
                     and value["sha256"] == digest({k: v for k, v in value.items() if k != "sha256"}),
                     "editor settled proof seal differs")
            session = value["session"]
            _require(isinstance(session, dict) and session.get("fixture") is fixture
                     and session.get("status") in {"valid", "empty", "invalid_harvest", "invalid_inventory"},
                     "editor settled proof disposition differs")
            requests, slots = session.get("requests"), session.get("result_slots")
            _require(isinstance(requests, list) and all(isinstance(row, dict) for row in requests)
                     and isinstance(slots, list) and 0 <= len(slots) <= MAX_STEPS
                     and slots == [f"{pilot}.adaptive.editor.{label}.t{i:02}" for i in range(1, len(slots) + 1)]
                     and [row.get("slot_id") for row in requests] == slots,
                     "editor settled proof turn sequence differs")
            for row in requests:
                _require(all(isinstance(row.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", row[key])
                             for key in ("raw_sha256", "effective_sha256", "result_sha256")),
                         "editor request proof hashes differ")
                translation = row.get("role_translation")
                terminal_turn = row["slot_id"].endswith(f".t{MAX_STEPS:02}")
                _require(translation == terminal_translation() if terminal_turn else translation is None,
                         "invalid terminal translation proof")
                if results is not None:
                    result = results.get(row["slot_id"], {})
                    _require(result.get("role") == ("native_selector" if label == "select.seq2" else "editor") and result.get("status") == "response"
                             and result.get("study_sha256") == study_sha256 and result.get("fixture") is fixture
                             and result.get("request_sha256") == row["effective_sha256"]
                             and digest(result) == row["result_sha256"], "editor proof differs from authoritative results")
                if intents is not None:
                    intent = intents.get(row["slot_id"], {})
                    request = intent.get("request", {})
                    _require(digest(request) == row["effective_sha256"], "editor intent differs from effective request")
                    messages = request.get("messages", [])
                    terminal = bool(messages and row["slot_id"].endswith(f".t{MAX_STEPS:02}")
                                    and messages[-1].get("role") == "user" and _terminal_shape(messages[-1]))
                    _require(terminal == (translation is not None), "terminal translation differs from authoritative intent")
            _require(type(session.get("terminal_note_used")) is bool and session["terminal_note_used"]
                     == any(row.get("role_translation") is not None for row in requests), "terminal session flag differs")
            _require(session.get("input_snapshot") == _validated_snapshot(session["input_snapshot"], label)
                     and session.get("input_effective_strategy_sha256") == session["input_snapshot"].get("effective_strategy_sha256"),
                     "editor input strategy missing")
            if session["status"] == "valid" and label != "select.seq2":
                _require(bool(slots) and session.get("model_backed") is True and all(isinstance(session.get(key), str)
                         and re.fullmatch(r"[0-9a-f]{64}", session[key]) for key in (
                             "harvest_raw_tree_sha256", "effective_strategy_sha256")), "valid editor proof lacks its harvest")
                changed, eligible = session_eligibility(session["terminal_note_used"],
                    session["input_effective_strategy_sha256"], session["effective_strategy_sha256"])
                _require(session.get("effective_changed_from_input") is changed
                         and session.get("authentic_eligible") is eligible,
                         "terminal authenticity classification differs")
            if (session["status"] == "valid" and not session["terminal_note_used"]
                    and results is not None and intents is not None):
                from .evidence import verify_recorded_information

                verify_recorded_information(search=audit_dir.parent, label=label,
                    session=session, results=results, intents=intents)
            sessions[label] = session
        _require(set(sessions).issubset(started), "settled editor proof lacks its logical intent")
        _require(all(session["input_snapshot"] == inputs[label] for label, session in sessions.items()),
                 "settled session changed its input snapshot")
        if results is not None:
            prefix = pilot + ".adaptive.editor."
            for slot in results:
                if slot.startswith(prefix):
                    label, turn = slot[len(prefix):].rsplit(".t", 1)
                    _require(label in started and turn.isdecimal() and 1 <= int(turn) <= MAX_STEPS,
                             "authoritative editor result lacks a known logical intent")
        return sessions
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        raise IntegrityStop("persisted editor proof failed its read-only boundary") from exc


class AccountedProposer(frozen.AccountedProposer):
    """Native execution with a separately bound twenty-four-request trusted relay."""
    def __init__(self, *, pilot: str, study_sha256: str, dispatch: Callable,
                 audit_dir: Path, fixture: bool, halt: Callable):
        audit_dir = Path(audit_dir)
        roots = (Path(__file__).resolve().parents[2] / "runs/phase3b-seq2-v1/native",
                 Path("/results/phase3b-seq2-v1/native"))
        if (not audit_dir.is_absolute() or ".." in audit_dir.parts or any(part.lower() in PRIVATE or "stdout" in part.casefold() or "stderr" in part.casefold()
                   for part in audit_dir.parts)
                or not any(audit_dir.is_relative_to(root) and audit_dir != root for root in roots)
                or any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (audit_dir, *audit_dir.parents))):
            halt("editor_audit_boundary_violation")
            raise ProposerError("editor audit path failed its input boundary")
        Proposer.__init__(self, ChannelSpec(kind="opencode", model="anthropic/claude-opus-5",
                                     effort="high", steps=MAX_STEPS, timeout=NATIVE_TIMEOUT), audit_dir=audit_dir, attempts=1)
        self.pilot, self.study_sha256 = pilot, study_sha256
        self.dispatch, self.fixture = dispatch, fixture
        self.halt = halt
        self._local = threading.local()
        self._proof_dir = Path(audit_dir) / "phase3a-sessions"
        if self._proof_dir.is_symlink() or (hasattr(self._proof_dir, "is_junction") and self._proof_dir.is_junction()):
            halt("editor_audit_boundary_violation")
            raise ProposerError("linked editor proof directory")
        self._proof_dir.mkdir(parents=True, exist_ok=True)
        self._proof_binding = {"fixture": fixture, "study_sha256": study_sha256, "pilot": pilot,
                               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                               "editor_profile_sha256": digest(profile())}
        self._sessions = validate_persisted_sessions(Path(audit_dir), study_sha256=study_sha256,
                                                    pilot=pilot, fixture=fixture)
        # Supported native runtime configuration, unchanged from the accepted seam.
        # Live admission runtime_guard requires these exact pinned image paths.
        config.BUN = Path(os.environ.get("PHASE3A_BUN", "/usr/local/bin/bun"))
        config.OPENCODE_DIR = Path(os.environ.get("PHASE3A_OPENCODE", "/opt/phase3a-opencode"))

    def env(self):
        value = super().env()
        configured = json.loads(value["OPENCODE_CONFIG_CONTENT"])
        configured["agent"]["build"]["steps"] = MAX_STEPS
        configured["provider"]["anthropic"]["options"]["timeout"] = FETCH_TIMEOUT * 1000
        value["OPENCODE_CONFIG_CONTENT"] = json.dumps(configured, ensure_ascii=False, allow_nan=False)
        return value

    def call(self, mission, context_dir=None, label="", **kwargs):
        if not isinstance(label, str) or not _LABEL.fullmatch(label):
            self.halt("unexpected_native_editor_stage")
            raise ProposerError("unexpected native editor stage")
        try:
            source = safe(Path(context_dir))
            _require(source.resolve(strict=True).is_relative_to(safe(Path(self.audit_dir).parent).resolve(strict=True)),
                     "editor context escaped its task boundary")
            total = count = 0
            pending = [source]
            while pending:
                directory = pending.pop()
                for name in sorted(os.listdir(directory)):
                    _require(name.casefold() not in PRIVATE and "stdout" not in name.casefold()
                             and "stderr" not in name.casefold(), "private editor context entry")
                    item = safe(directory / name)
                    info = item.lstat()
                    _require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), "nonordinary context entry")
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(item)
                    else:
                        count += 1
                        total += info.st_size
                        _require(count <= 1000 and total <= 8_000_000, "editor context exceeds bounded profile")
        except (ContractError, OSError, TypeError):
            self.halt("editor_context_boundary_violation")
            raise ProposerError("editor context failed input boundary") from None
        self._local.label = label
        return Proposer.call(self, mission, context_dir, label, **kwargs)

    def _opencode(self, cwd, mission, system, wall):
        from .strategy import native_workspace, validate_harness, validate_harness_inventory
        with native_workspace(cwd), _SERIAL:
            label = self._local.label
            started_path = self._proof_dir / (label + ".started.json")
            if label in self._sessions or started_path.exists():
                # Native transport retries may spawn again; they never authorize another paid conversation.
                raise ProposerError("this logical conversation has already been attempted")
            try:
                captured_input = (selector_snapshot(cwd / "context", owned_workspace=cwd) if label == "select.seq2"
                    else input_snapshot(validate_harness_inventory(cwd / "context/harness")))
            except ContractError:
                self.halt("editor_input_inventory_violation")
                raise ProposerError("editor input failed inventory validation") from None
            record: dict = {"status": "started", "fixture": self.fixture, "model_backed": False,
                      "requests": [], "result_slots": [], "terminal_note_used": False,
                      "input_snapshot": captured_input,
                      "input_effective_strategy_sha256": captured_input.get("effective_strategy_sha256")}
            self._sessions[label] = record
            write_once(started_path, {"binding": self._proof_binding, "label": label, "input_snapshot": captured_input})
            self._local.home = str(cwd / ".phase3a-home")
            Path(self._local.home).mkdir()
            prefix = f"{self.pilot}.adaptive.editor.{label}"
            prepared = self._c1_contracts[label]
            with relay(cwd, self.dispatch, prefix, record, self.halt, prepared=prepared) as (url, completion):
                self._local.url = url
                answer, cost, error = Proposer._opencode(self, cwd, mission, system, wall)
            record["result_slots"] = [row["slot_id"] for row in record["requests"]]
            if record.get("error"):
                record["status"] = "boundary_stopped"
                raise ProposerError("accounted editor boundary stopped this conversation")
            if not record["terminal_note_used"]:
                from .evidence import verify_normal_session

                try:
                    output = safe(cwd / "output/answer.md", roots=(cwd,))
                    saved_output = output.read_text(encoding="utf-8", errors="replace") if output.is_file() else None
                    current = (None if label == "select.seq2" else
                               safe(cwd / "context/harness/systemprompt.md", roots=(cwd,)).read_text(encoding="utf-8"))
                    _require(bool(completion), "native editor has no normal final response")
                    record["normal_session_proof"] = verify_normal_session(
                        completion["request"], prepared, cwd=str(cwd), label=label,
                        response=completion["response"], native_output=answer, saved_output=saved_output,
                        harvested_strategy=current, mutation_witnesses=record["mutation_witnesses"])
                except (ContractError, OSError, TypeError, ValueError) as exc:
                    record.update(status="boundary_stopped", error=type(exc).__name__)
                    self.halt("native_output_binding_violation")
                    raise ProposerError("native consumed output failed its completion binding") from None
            if label == "select.seq2":
                _require(selector_snapshot(cwd / "context", owned_workspace=cwd) == captured_input,
                         "selector modified its immutable candidate evidence")
                record.update(status="valid" if answer.strip() and not error else "empty",
                    model_backed=bool(record["result_slots"]),
                    selector_answer=answer, authentic_eligible=bool(answer.strip() and not error)
                    and not record["terminal_note_used"])
                self._save_session(label, record)
                return answer, cost, error
            try:
                validate_harness_inventory(cwd / "context/harness")
            except ContractError:
                record["status"] = "invalid_inventory"
                self._save_session(label, record)
                self.halt("editor_harvest_inventory_violation")
                raise ProposerError("harvest failed the restricted inventory contract") from None
            if not record["terminal_note_used"]:
                actual = safe(cwd / "context/harness/systemprompt.md", roots=(cwd,)).read_text(encoding="utf-8")
                normal = record.get("normal_session_proof", {})
                if normal.get("harvested_strategy") != actual:
                    record.update(status="invalid_inventory", normal_harvest_mismatch={
                        "actual_harvest_sha256": hashlib.sha256(actual.encode()).hexdigest(),
                        "normal_proof_sha256": digest(normal)})
                    self._save_session(label, record)
                    self.halt("editor_harvest_differs_from_normal_proof")
                    raise ProposerError("actual harvested strategy differs from the model-visible normal proof")
            try:
                validation = validate_harness(cwd / "context/harness")
            except ContractError:
                record.update(status="invalid_harvest", model_backed=bool(record["result_slots"]))
                self._save_session(label, record)
                # Native adapter validation must see the unchanged failed shape
                # so its own second shape attempt can repair it without a CLI retry.
                return answer, cost, error
            record.update(status="valid" if answer.strip() and not error else "empty",
                          model_backed=bool(record["result_slots"]),
                          harvest_raw_tree_sha256=validation["raw_tree_sha256"],
                          effective_strategy_sha256=validation["effective_strategy_sha256"])
            changed, eligible = session_eligibility(record["terminal_note_used"],
                record["input_effective_strategy_sha256"], validation["effective_strategy_sha256"])
            record.update(effective_changed_from_input=changed,
                          authentic_eligible=record["status"] == "valid" and eligible)
            self._save_session(label, record)
            return answer, cost, error

    def phase3a_evidence(self):
        return copy.deepcopy({"fixture": self.fixture, "study_sha256": self.study_sha256,
                              "backend": "opencode", "model": "claude-opus-5",
                              "sessions": self._sessions,
                              "attestation": {"boundary_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                              "editor_profile_sha256": digest(profile())}})


def validate_selector_evidence(*, search: Path, study_sha256: str, pilot: str,
                               fixture: bool, session: dict, results: dict,
                               intents: dict, selection: dict) -> dict:
    """Replay history and prove every candidate reached the decisive native request."""
    from followups.phase3a_c1_completion_v3.evidence import _body

    from .delivery import _history, audit_delivery
    from .evidence import _file, _mutation_history, _sources, _system, verify_candidate_inspection

    saved = validate_persisted_sessions(Path(search) / "editor-audit", study_sha256=study_sha256,
        pilot=pilot, fixture=fixture, results=results, intents=intents)
    _require(saved.get("select.seq2") == session and session.get("status") == "valid"
             and session.get("model_backed") is True and session.get("authentic_eligible") is True
             and session.get("terminal_note_used") is False and selection.get("ok") is True
             and not selection.get("fallback"), "native selector did not finish normally")
    slots = session["result_slots"]
    _require(0 < len(slots) < MAX_STEPS, "native selector completion is terminal or empty")
    guard = HistoryGuard(lambda slot, role, request: results[slot], pilot + ".adaptive.editor.select.seq2")
    for slot in slots:
        request = intents[slot]["request"]
        _require(results[slot]["role"] == "native_selector", "native selector role changed")
        guard(slot, "native_selector", request)
    _require(session.get("history_guard_audits") == guard.audits,
             "native selector signed history replay differs")
    final = results[slots[-1]]["response"]["provider_response"]
    _require(final.get("stop_reason") == "end_turn" and not any(
        item.get("type") == "tool_use" for item in final.get("content", [])),
        "native selector response was incomplete")
    _require(normalized_output(session.get("selector_answer"))
             == normalized_output((session.get("normal_session_proof") or {}).get("native_output")),
             "native selector returned choice differs from its observed native output")
    body = _body(intents[slots[-1]]["request"], set())
    calls, tool_results = _history(body)
    prefix = "editor-audit/c1-contracts/select.seq2"
    manifest = read_json(safe(Path(search) / prefix / "manifest.json"))
    _require(manifest.get("role") == "SELECT" and manifest.get("label") == "select.seq2"
             and manifest.get("sha256") == digest({k: v for k, v in manifest.items() if k != "sha256"})
             and manifest["context_inventory"] == session["input_snapshot"]["files"],
             "native selector manifest differs from original candidate inventory")
    hashes: dict[str, str] = {}
    original, views = _sources(Path(search), prefix, manifest, hashes)
    configured = _file(Path(search), prefix + "/configured-agent-prompt.md", hashes).decode()
    cwd = _system(intents[slots[-1]]["request"], configured, None)
    writes, _, _ = _mutation_history(body, cwd + "/output/answer.md")
    decision = body
    if writes:
        first_mutation = writes[0]
        indices = [index for index, message in enumerate(body["messages"])
                   if message.get("role") == "assistant" and isinstance(message.get("content"), list)
                   and any(item.get("type") == "tool_use" and item.get("id") == first_mutation
                           for item in message["content"])]
        _require(len(indices) == 1, "native selector first choice mutation is ambiguous")
        decision = {"messages": body["messages"][:indices[0]]}
    expected = {cwd + "/context/" + name: value for name, value in views.items()}
    inspected = verify_candidate_inspection(decision, manifest, cwd=cwd)
    delivered = audit_delivery(decision, expected)
    notes_delivery = None
    if writes:
        saved_output = (session.get("normal_session_proof") or {}).get("saved_output")
        if not isinstance(saved_output, str):
            raise ContractError("native selector lacks its observed saved output")
        notes_delivery = audit_delivery(body, {cwd + "/output/answer.md": saved_output}, after=writes[-1])
    for call_id, call in calls.items():
        if call["name"] != "read":
            _require(call["name"] in {"write", "edit"}
                     and call["input"]["filePath"] == cwd + "/output/answer.md",
                     "native selector modified candidate evidence")
    from harness2.core.selection import _CHOICE
    match = _CHOICE.search(session.get("selector_answer", ""))
    _require(match is not None and match.group(1).strip() == selection.get("chosen_id")
             and selection.get("chosen_id") in selection.get("id_map", {}),
             "native selector choice is not its actual native candidate")
    return {"kind": "phase3b-selector-proof-v1", "passed": True, "fixture": fixture,
        "study_sha256": study_sha256, "session": "select.seq2", "normal_completion": True,
        "selected_id": selection["chosen_id"], "required_view_delivery": delivered,
        "candidate_inspection": inspected, "notes_reread_audit": notes_delivery,
        "read_consumption_policy": "read-consumption-diagnostic-v1",
        "candidate_source_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in original.items()},
        "artifact_sha256": hashes, "history_requests": len(slots)}
