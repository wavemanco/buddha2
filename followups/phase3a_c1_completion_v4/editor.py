"""Versioned sixteen-request editor boundary around the unchanged native proposer.

Reuse the frozen tool, response, snapshot and eligibility rules.  Only the
external conversation profile and its source-bound replay have a new version.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
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

MAX_STEPS = 16
NORMAL_STEPS = 15
PROFILE_ID = "phase3a-r3-editor-sixteen-v1"
_SERIAL = frozen._SERIAL
TOOLS, _LABEL, _FALSE = frozen.TOOLS, frozen._LABEL, frozen._FALSE
_require = frozen._require
terminal_note, _terminal_shape = frozen.terminal_note, frozen._terminal_shape
input_snapshot, session_eligibility = frozen.input_snapshot, frozen.session_eligibility
tool_boundary, sse = frozen.tool_boundary, frozen.sse
TERMINAL_NOTE_SHA256 = frozen.TERMINAL_NOTE_SHA256
TERMINAL_POLICY = "opencode-max-steps-sixteen-user-role-v1"


def profile() -> dict:
    return {"id": PROFILE_ID, "steps": MAX_STEPS, "ordinary_steps": NORMAL_STEPS,
            "terminal_turn": MAX_STEPS, "terminal_note_sha256": TERMINAL_NOTE_SHA256,
            "native_subprocess_cap_seconds": 600, "OpenCode_fetch_cap_seconds": 590}


def terminal_translation() -> dict:
    return {"policy_id": TERMINAL_POLICY, "turn": MAX_STEPS, "note_sha256": TERMINAL_NOTE_SHA256,
            "from_role": "assistant", "to_role": "user"}


def configuration(base_url: str) -> dict:
    value = frozen.configuration(base_url)
    value["agent"]["build"]["steps"] = MAX_STEPS
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
        _require(terminal_prefill, "sixteenth request requires the pinned terminal control")
    if last and last.get("role") == "assistant":
        _require(turn == MAX_STEPS and terminal_prefill, "unsupported final assistant prefill")
        last["role"] = "user"
    return frozen.effective_request(value, turn=turn)


@contextmanager
def relay(cwd: Path, dispatch: Callable, prefix: str, record: dict, halt: Callable):
    exchanges = threading.RLock()
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
                _require(0 < length <= 1048576, "editor payload is outside its byte bound")
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
                result = dispatch(slot, "editor", request)
                record["requests"].append({"slot_id": slot, "raw_sha256": digest(raw),
                    "effective_sha256": digest(request), "result_sha256": digest(result),
                    "role_translation": translation})
                _require(result.get("status") == "response", "editor result is unresolved")
                response = result["response"]["provider_response"]
                tool_boundary(response["content"], cwd)
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
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def validate_persisted_sessions(audit_dir: Path, *, study_sha256: str, pilot: str,
                                fixture: bool, results: dict | None = None, intents: dict | None = None) -> dict:
    """Read-only proof replay, including unfinished logical conversations."""
    from followups.phase3a_v1.accounting import IntegrityStop

    audit_dir = Path(audit_dir)
    roots = (Path(__file__).resolve().parents[2] / "runs/phase3a-compat-c1-v1/completion-v4",
             Path("/results/phase3a-compat-c1-v1/completion-v4"))
    if (not audit_dir.is_absolute() or ".." in audit_dir.parts
            or any(part.lower() in PRIVATE for part in audit_dir.parts)
            or not any(audit_dir.is_relative_to(root) and audit_dir != root for root in roots)):
        raise IntegrityStop("persisted editor proof is outside its R3 boundary")
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
            match = re.fullmatch(r"((?:inv1|dom1|agg1)\.a[12])\.(started|settled)\.json", path.name)
            if match is None:
                raise ContractError("unknown editor proof file")
            _require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction())
                     and path.is_file(), "nonordinary editor proof entry")
            label, kind = match.group(1), match.group(2)
            value = read_json(path)
            _require(path.read_bytes() == (json.dumps(value, sort_keys=True, ensure_ascii=False,
                     allow_nan=False, indent=2) + "\n").encode("utf-8"), "editor proof bytes are not canonical")
            _require(isinstance(value, dict) and value.get("binding") == binding
                     and value.get("label") == label, "editor proof binding differs")
            if kind == "started":
                _require(set(value) == {"binding", "label", "input_snapshot"}
                         and value["input_snapshot"] == input_snapshot(value["input_snapshot"]["tree"]),
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
                    _require(result.get("role") == "editor" and result.get("status") == "response"
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
            _require(session.get("input_snapshot") == input_snapshot(session["input_snapshot"]["tree"])
                     and session.get("input_effective_strategy_sha256") == session["input_snapshot"]["effective_strategy_sha256"],
                     "editor input strategy missing")
            if session["status"] == "valid":
                _require(bool(slots) and session.get("model_backed") is True and all(isinstance(session.get(key), str)
                         and re.fullmatch(r"[0-9a-f]{64}", session[key]) for key in (
                             "harvest_raw_tree_sha256", "effective_strategy_sha256")), "valid editor proof lacks its harvest")
                changed, eligible = session_eligibility(session["terminal_note_used"],
                    session["input_effective_strategy_sha256"], session["effective_strategy_sha256"])
                _require(session.get("effective_changed_from_input") is changed
                         and session.get("authentic_eligible") is eligible,
                         "terminal authenticity classification differs")
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
    """Native execution with a separately bound sixteen-request trusted relay."""
    def __init__(self, *, pilot: str, study_sha256: str, dispatch: Callable,
                 audit_dir: Path, fixture: bool, halt: Callable):
        audit_dir = Path(audit_dir)
        roots = (Path(__file__).resolve().parents[2] / "runs/phase3a-compat-c1-v1/completion-v4",
                 Path("/results/phase3a-compat-c1-v1/completion-v4"))
        if (not audit_dir.is_absolute() or ".." in audit_dir.parts or any(part.lower() in PRIVATE for part in audit_dir.parts)
                or not any(audit_dir.is_relative_to(root) and audit_dir != root for root in roots)
                or any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (audit_dir, *audit_dir.parents))):
            halt("editor_audit_boundary_violation")
            raise ProposerError("editor audit path failed its input boundary")
        Proposer.__init__(self, ChannelSpec(kind="opencode", model="anthropic/claude-opus-5",
                                     effort="high", steps=MAX_STEPS, timeout=600), audit_dir=audit_dir)
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
        value["OPENCODE_CONFIG_CONTENT"] = json.dumps(configured, ensure_ascii=False, allow_nan=False)
        return value

    def _opencode(self, cwd, mission, system, wall):
        from followups.phase3a_v1.strategy import validate_harness, validate_harness_inventory
        with _SERIAL:
            label = self._local.label
            started_path = self._proof_dir / (label + ".started.json")
            if label in self._sessions or started_path.exists():
                # Native transport retries may spawn again; they never authorize another paid conversation.
                raise ProposerError("this logical conversation has already been attempted")
            try:
                captured_input = input_snapshot(validate_harness_inventory(cwd / "context/harness"))
            except ContractError:
                self.halt("editor_input_inventory_violation")
                raise ProposerError("editor input failed inventory validation") from None
            record: dict = {"status": "started", "fixture": self.fixture, "model_backed": False,
                      "requests": [], "result_slots": [], "terminal_note_used": False,
                      "input_snapshot": captured_input,
                      "input_effective_strategy_sha256": captured_input["effective_strategy_sha256"]}
            self._sessions[label] = record
            write_once(started_path, {"binding": self._proof_binding, "label": label, "input_snapshot": captured_input})
            self._local.home = str(cwd / ".phase3a-home")
            Path(self._local.home).mkdir()
            prefix = f"{self.pilot}.adaptive.editor.{label}"
            with relay(cwd, self.dispatch, prefix, record, self.halt) as url:
                self._local.url = url
                answer, cost, error = Proposer._opencode(self, cwd, mission, system, wall)
            record["result_slots"] = [row["slot_id"] for row in record["requests"]]
            if record.get("error"):
                record["status"] = "boundary_stopped"
                raise ProposerError("accounted editor boundary stopped this conversation")
            try:
                validate_harness_inventory(cwd / "context/harness")
            except ContractError:
                record["status"] = "invalid_inventory"
                self._save_session(label, record)
                self.halt("editor_harvest_inventory_violation")
                raise ProposerError("harvest failed the restricted inventory contract") from None
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
