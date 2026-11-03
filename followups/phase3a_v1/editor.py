"""Accounted HTTP seam around the actual pinned Harness²/OpenCode proposer.

The stock scheduler, prompts, tool implementation, editing and harvesting run
unchanged. The trusted relay admits requests and inspects tool-use arguments
before exposing them to OpenCode; no real provider key reaches that process.
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

_SERIAL = threading.RLock()
TOOLS = ("read", "write", "edit")
_LABEL = re.compile(r"(?:inv1|dom1|agg1)\.a[12]\Z")
_RAW_ALLOWED = {"model", "messages", "system", "max_tokens", "thinking", "output_config",
                "tools", "tool_choice", "stream", "metadata", "service_tier", "inference_geo"}
_FALSE = "fixture-not-a-secret"
TERMINAL_NOTE_SHA256 = "dd27eb87f2347972e29af2187fea9fa8498fdd012044a60c23179083806b685f"
TERMINAL_POLICY = "opencode-max-steps-user-role-v1"


def terminal_note() -> str:
    path = Path(os.environ.get("PHASE3A_OPENCODE", "/opt/phase3a-opencode")) / "packages/opencode/src/session/prompt/max-steps.txt"
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == TERMINAL_NOTE_SHA256, "pinned terminal note differs")
    return raw.decode("utf-8", errors="strict")


def terminal_translation() -> dict:
    return {"policy_id": TERMINAL_POLICY, "turn": 8, "note_sha256": TERMINAL_NOTE_SHA256,
            "from_role": "assistant", "to_role": "user"}


def input_snapshot(tree: dict) -> dict:
    from .accounting import IntegrityStop
    from .strategy import EMPTY_FILES, validate_tree

    _require(isinstance(tree, dict) and set(tree) == {"systemprompt.md", *EMPTY_FILES}
             and all(isinstance(value, str) for value in tree.values())
             and all(tree[name] == "" for name in EMPTY_FILES), "invalid session input inventory")
    try:
        effective = validate_tree(tree)["effective_strategy_sha256"]
    except IntegrityStop:
        raise
    except ContractError:
        effective = None
    return {"tree": copy.deepcopy(tree), "raw_tree_sha256": digest(tree),
            "strategy_valid": effective is not None, "effective_strategy_sha256": effective}


def session_eligibility(terminal: bool, input_hash: str | None, output_hash: str) -> tuple[bool | None, bool]:
    changed = output_hash != input_hash if input_hash is not None else None
    return changed, not terminal or changed is True


def _terminal_shape(message: dict) -> bool:
    if not isinstance(message, dict) or set(message) != {"role", "content"}:
        return False
    blocks = message["content"]
    if not isinstance(blocks, list) or len(blocks) != 1 or not isinstance(blocks[0], dict):
        return False
    block = blocks[0]
    return (set(block) in ({"type", "text"}, {"type", "text", "cache_control"})
        and block.get("type") == "text" and block.get("text") == terminal_note()
        and ("cache_control" not in block or block["cache_control"] in (
            {"type": "ephemeral"}, {"type": "ephemeral", "ttl": "5m"})))


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def configuration(base_url: str) -> dict:
    return {
        "autoupdate": False, "share": "disabled", "snapshot": False,
        "enabled_providers": ["anthropic"], "plugin": [], "mcp": {}, "lsp": False,
        "permission": {"*": "deny", "read": "allow", "write": "allow", "edit": "allow"},
        "agent": {"build": {"steps": 8, "permission": {
            "*": "deny", "read": "allow", "write": "allow", "edit": "allow"}},
            "title": {"disable": True}, "summary": {"disable": True}, "compaction": {"disable": True}},
        "provider": {"anthropic": {
            "npm": "@ai-sdk/anthropic", "options": {
                "apiKey": _FALSE, "baseURL": base_url, "timeout": 590000},
            "whitelist": ["claude-opus-5"],
            "models": {"claude-opus-5": {
                "id": "claude-opus-5", "name": "Phase3A Opus 5 editor",
                "reasoning": True, "temperature": False, "tool_call": True,
                "limit": {"context": 1000000, "output": 16000},
                "options": {"thinking": {"type": "adaptive"}, "effort": "high"},
                "variants": {"high": {"thinking": {"type": "adaptive"}, "effort": "high"}},
                "cost": {"input": 5, "output": 25, "cache_read": .5, "cache_write": 6.25},
                "modalities": {"input": ["text"], "output": ["text"]}}}}}}


def effective_request(raw: dict, *, turn: int | None = None) -> dict:
    _require(isinstance(raw, dict) and not set(raw).difference(_RAW_ALLOWED),
             "OpenCode sent unsupported provider controls")
    _require(raw.get("model") == "claude-opus-5" and raw.get("max_tokens") == 16000,
             "OpenCode editor model/output bound mismatch")
    _require(raw.get("thinking") == {"type": "adaptive"}
             and raw.get("output_config") == {"effort": "high"},
             "OpenCode adaptive/high profile mismatch")
    _require(raw.get("stream") is True, "OpenCode relay requires the frozen streaming contract")
    tools = raw.get("tools", [])
    _require(isinstance(tools, list) and len(tools) <= len(TOOLS)
             and len({tool.get("name") for tool in tools}) == len(tools)
             and all(isinstance(tool, dict) and tool.get("name") in TOOLS
                     and set(tool).issubset({"name", "description", "input_schema", "cache_control", "eager_input_streaming"})
                     and ("eager_input_streaming" not in tool or type(tool["eager_input_streaming"]) is bool)
                     for tool in tools), "OpenCode exposed an undeclared tool")
    body = copy.deepcopy(raw)
    body.pop("stream")
    messages = body.get("messages")
    _require(isinstance(messages, list) and messages and isinstance(messages[-1], dict), "invalid editor history")
    messages = body["messages"]
    if messages[-1].get("role") == "assistant":
        _require(turn == 8 and _terminal_shape(messages[-1]), "unsupported final assistant prefill")
        messages[-1]["role"] = "user"
    # The relay supplies the declared transport-level tier/geography controls.
    # Prompt, message history, tool schemas and reasoning remain exactly as sent.
    for field, value in (("service_tier", "standard_only"), ("inference_geo", "global")):
        _require(field not in body or body[field] == value, "OpenCode billing control mismatch")
        body[field] = value
    return body


def tool_boundary(content: list, cwd: Path) -> None:
    _require(isinstance(content, list), "editor response content must be a list")
    root = cwd.resolve(strict=True)
    writes = {root / "context/harness/systemprompt.md", root / "output/answer.md"}
    for block in content:
        _require(isinstance(block, dict), "invalid provider content block")
        if block.get("type") != "tool_use":
            _require(block.get("type") in {"text", "thinking", "redacted_thinking"},
                     "unsupported editor content block")
            continue
        name, args = block.get("name"), block.get("input")
        _require(name in TOOLS and isinstance(args, dict), "editor requested a prohibited tool")
        keys = {"read": {"filePath", "offset", "limit"},
                "write": {"filePath", "content"},
                "edit": {"filePath", "oldString", "newString", "replaceAll"}}[name]
        _require(not set(args).difference(keys) and isinstance(args.get("filePath"), str),
                 "editor tool arguments violate the pinned tool contract")
        candidate = Path(args["filePath"])
        _require(candidate.is_absolute() and ".." not in candidate.parts,
                 "editor file access must use an absolute non-traversing path")
        _require(not any(p.is_symlink() for p in (candidate, *candidate.parents)),
                 "editor tool access cannot traverse links")
        resolved = candidate.resolve()
        _require(resolved.is_relative_to(root), "editor attempted access outside its own workspace")
        if name != "read":
            _require(resolved in writes, "editor may only edit the declared strategy and final answer")
        else:
            _require(not any(part.startswith(".") for part in resolved.relative_to(root).parts),
                     "editor cannot read runtime/configuration state")


def sse(response: dict) -> bytes:
    """Losslessly expose an already-settled Anthropic message as its SSE contract."""
    chunks = []

    def emit(kind, payload):
        chunks.append("event: " + kind + "\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n")

    header = {key: value for key, value in response.items() if key not in {"content", "stop_reason", "stop_sequence"}}
    header.update(content=[], stop_reason=None, stop_sequence=None)
    header["usage"] = dict(response["usage"], output_tokens=0)
    emit("message_start", {"type": "message_start", "message": header})
    for index, block in enumerate(response["content"]):
        block = copy.deepcopy(block)
        kind = block["type"]
        delta = None
        if kind == "text":
            text, block["text"] = block.get("text", ""), ""
            delta = {"type": "text_delta", "text": text}
        elif kind == "thinking":
            text, signature = block.get("thinking", ""), block.get("signature", "")
            block.update(thinking="", signature="")
            delta = {"type": "thinking_delta", "thinking": text}
        elif kind == "tool_use":
            value, block["input"] = block.get("input", {}), {}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(value, ensure_ascii=False)}
        emit("content_block_start", {"type": "content_block_start", "index": index, "content_block": block})
        if delta:
            emit("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta})
        if kind == "thinking":
            emit("content_block_delta", {"type": "content_block_delta", "index": index,
                                          "delta": {"type": "signature_delta", "signature": signature}})
        emit("content_block_stop", {"type": "content_block_stop", "index": index})
    emit("message_delta", {"type": "message_delta", "delta": {
        "stop_reason": response["stop_reason"], "stop_sequence": response.get("stop_sequence")},
        "usage": response["usage"]})
    emit("message_stop", {"type": "message_stop"})
    return "".join(chunks).encode("utf-8")


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
                _require(turn <= 8, "editor conversation limit")
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
                from .accounting import (
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
    from .accounting import IntegrityStop

    directory = Path(audit_dir) / "phase3a-sessions"
    binding = {"fixture": fixture, "study_sha256": study_sha256, "pilot": pilot,
               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    sessions: dict[str, dict] = {}
    started: set[str] = set()
    inputs: dict[str, dict] = {}
    try:
        _require(not any(p.is_symlink() for p in (directory, *directory.parents)), "linked editor proof path")
        if not directory.exists():
            _require(not results or not any(slot.startswith(pilot + ".adaptive.editor.") for slot in results),
                     "editor results lack their durable logical-conversation intents")
            return sessions
        for path in directory.iterdir():
            _require(not path.is_symlink() and path.is_file(), "nonordinary editor proof entry")
            match = re.fullmatch(r"((?:inv1|dom1|agg1)\.a[12])\.(started|settled)\.json", path.name)
            if match is None:
                raise ContractError("unknown editor proof file")
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
                     and isinstance(slots, list) and 0 <= len(slots) <= 8
                     and slots == [f"{pilot}.adaptive.editor.{label}.t{i:02}" for i in range(1, len(slots) + 1)]
                     and [row.get("slot_id") for row in requests] == slots,
                     "editor settled proof turn sequence differs")
            for row in requests:
                _require(all(isinstance(row.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", row[key])
                             for key in ("raw_sha256", "effective_sha256", "result_sha256")),
                         "editor request proof hashes differ")
                translation = row.get("role_translation")
                _require(translation is None or translation == terminal_translation()
                         and row["slot_id"].endswith(".t08"), "invalid terminal translation proof")
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
                    terminal = bool(messages and row["slot_id"].endswith(".t08")
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
                    _require(label in started and turn.isdecimal() and 1 <= int(turn) <= 8,
                             "authoritative editor result lacks a known logical intent")
        return sessions
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        raise IntegrityStop("persisted editor proof failed its read-only boundary") from exc


class AccountedProposer(Proposer):
    """Native Proposer with an explicit, bounded transport environment."""
    def __init__(self, *, pilot: str, study_sha256: str, dispatch: Callable,
                 audit_dir: Path, fixture: bool, halt: Callable):
        audit_dir = Path(audit_dir)
        if ".." in audit_dir.parts or any(p.is_symlink() for p in (audit_dir, *audit_dir.parents)):
            halt("editor_audit_boundary_violation")
            raise ProposerError("editor audit path failed its input boundary")
        super().__init__(ChannelSpec(kind="opencode", model="anthropic/claude-opus-5",
                                     effort="high", steps=8, timeout=600), audit_dir=audit_dir)
        self.pilot, self.study_sha256 = pilot, study_sha256
        self.dispatch, self.fixture = dispatch, fixture
        self.halt = halt
        self._local = threading.local()
        self._proof_dir = Path(audit_dir) / "phase3a-sessions"
        self._proof_dir.mkdir(parents=True, exist_ok=True)
        self._proof_binding = {"fixture": fixture, "study_sha256": study_sha256, "pilot": pilot,
                               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self._sessions = validate_persisted_sessions(Path(audit_dir), study_sha256=study_sha256,
                                                    pilot=pilot, fixture=fixture)
        config.BUN = Path(os.environ.get("PHASE3A_BUN", "/usr/local/bin/bun"))
        config.OPENCODE_DIR = Path(os.environ.get("PHASE3A_OPENCODE", "/opt/phase3a-opencode"))

    def env(self):
        _require(hasattr(self._local, "url"), "editor relay scope missing")
        # Allow only a small runtime environment; all real keys remain in controller memory.
        env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
        env.update({"HOME": self._local.home, "XDG_CONFIG_HOME": self._local.home,
                    "OPENCODE_CONFIG_CONTENT": json.dumps(configuration(self._local.url)),
                    "OPENCODE_DISABLE_PROJECT_CONFIG": "true", "OPENCODE_DISABLE_AUTOUPDATE": "true",
                    "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true", "OPENCODE_DISABLE_MODELS_FETCH": "true",
                    "OPENCODE_DISABLE_LSP_DOWNLOAD": "true", "OPENCODE_DISABLE_AUTOCOMPACT": "true",
                    "OPENCODE_DISABLE_CLAUDE_CODE": "true", "OPENCODE_DISABLE_EXTERNAL_SKILLS": "true",
                    "OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER": "true",
                    "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX": "16000"})  # nosec B105: output-token ceiling, not a credential
        return env

    def call(self, mission, context_dir=None, label="", **kwargs):
        if not isinstance(label, str) or not _LABEL.fullmatch(label):
            self.halt("unexpected_native_editor_stage")
            raise ProposerError("unexpected native editor stage")
        try:
            source = Path(context_dir)
            _require(".." not in source.parts and not any(p.is_symlink() for p in (source, *source.parents)),
                     "editor context path traverses a link or parent")
            _require(source.resolve(strict=True).is_relative_to(Path(self.audit_dir).parent.resolve(strict=True)),
                     "editor context escaped its own task boundary")
            total, count = 0, 0
            for item in source.rglob("*"):
                _require(not item.is_symlink() and (item.is_file() or item.is_dir()),
                         "editor context contains a link or nonordinary entry")
                if item.is_file():
                    count += 1
                    total += item.stat().st_size
                    _require(count <= 1000 and total <= 8000000, "editor context exceeds its bounded profile")
        except (ContractError, OSError, TypeError):
            self.halt("editor_context_boundary_violation")
            raise ProposerError("editor context failed its input boundary") from None
        self._local.label = label
        return super().call(mission, context_dir, label, **kwargs)

    def _opencode(self, cwd, mission, system, wall):
        from .strategy import validate_harness, validate_harness_inventory
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
                answer, cost, error = super()._opencode(cwd, mission, system, wall)
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

    def _save_session(self, label, record):
        proof = {"binding": self._proof_binding, "label": label, "session": copy.deepcopy(record)}
        proof["sha256"] = digest(proof)
        write_once(self._proof_dir / (label + ".settled.json"), proof)

    def phase3a_evidence(self):
        return copy.deepcopy({"fixture": self.fixture, "study_sha256": self.study_sha256,
                              "backend": "opencode", "model": "claude-opus-5",
                              "sessions": self._sessions,
                              "attestation": {"boundary_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})


def proposer_factory(*, task=None, pilot, dispatch, audit_dir, study_sha256, halt, fixture=False, **kwargs):
    pilot_id = pilot["pilot_id"] if isinstance(pilot, dict) else pilot
    return AccountedProposer(pilot=pilot_id, study_sha256=study_sha256, dispatch=dispatch,
                             audit_dir=Path(audit_dir), fixture=fixture, halt=halt)
