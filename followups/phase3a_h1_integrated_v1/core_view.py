"""One bounded keyless canonical read/report/projection worker for HI checkpoints."""
from __future__ import annotations

import json
import multiprocessing
import os
import queue
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest
from followups.phase3a_c1_completion_v3.transport import Transport

from .support import require, safe

BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
MAX_FRAME = 1_000_000


class ForbiddenActivity(ContractError):
    """Canonical work attempted provider construction or network activity."""


def _blocked():
    stack = ExitStack()
    for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                   "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex", "subprocess.Popen", "subprocess.run"):
        stack.enter_context(patch(target, side_effect=ForbiddenActivity("canonical worker attempted external activity")))
    return stack


def _perform(spec: dict, notify=None) -> dict:
    # All canonical reads occur after the explicit worker-only access blocks.
    from . import workflow
    from .report import write_report
    from .snapshot import CanonicalIntegrityError, build_snapshot, publish_snapshot
    study = state = records = data = None
    result = {"kind": "p3a-hi-canonical-view-result-v1", **spec["bindings"],
        "checkpoint": spec["checkpoint"], "fixture": spec["fixture"], "provider_calls": 0,
        "canonical_status": "failed", "report_status": "unavailable", "report_variant": "unavailable",
        "visibility_status": "failed", "summary": None, "snapshot_sha256": None,
        "financial_state_validated": False, "reports_published": False}
    def held_records(error):
        return {"branches": {}, "seals": {}, "assessments": {}, "readiness": None,
            "validation_failure": {"exception_type": type(error).__name__,
                "scientific_use": "disqualified", "classification": "integrity_hold"},
            "deadline_stop": state.get("deadline_stop") if state is not None else None}
    def stage(value, variant):
        staging = Path(spec["reports_held_staging_path"] if variant == "held" else spec["reports_staging_path"])
        reports = write_report(value, staging)
        result.update(report_status="complete", report_variant=variant, report_sha256=digest(reports), summary=value["summary"])
    try:
        study = workflow.load_study(Path(spec["study_path"]))
        require(all(study[key] == spec["bindings"][key] for key in BINDINGS), "canonical worker source identity differs")
        state = workflow._state(study, spec["fixture"])
        result["financial_state_validated"] = True
        records = workflow._snapshot_records(Path(spec["study_path"]), study, state, spec["fixture"])
        data = workflow._fold_view(study, state, records, spec["fixture"])
        result["canonical_status"] = "complete"
    except Exception as exc:
        result["canonical_error_type"] = type(exc).__name__
        if study is not None and state is not None:
            records = held_records(exc)
            try:
                data = workflow._fold_view(study, state, records, spec["fixture"])
            except Exception as held_error:
                result["held_report_error_type"] = type(held_error).__name__
    if data is not None:
        try:
            stage(data, "validated" if result["canonical_status"] == "complete" else "held")
            if result["canonical_status"] == "complete" and notify is not None:
                notify({**result, "phase": "canonical_ready"})
        except Exception as exc:
            result.update(canonical_status="failed", report_status="failed", report_error_type=type(exc).__name__)
        if result["canonical_status"] == "complete":
            try:
                if study is None or records is None:
                    raise CanonicalIntegrityError("validated canonical inputs missing")
                manifest = publish_snapshot(build_snapshot(study, data, records, spec["checkpoint"]), Path(spec["snapshot_path"]))
                result.update(visibility_status="prepared", snapshot_sha256=manifest["snapshot_sha256"])
            except Exception as exc:
                result["projection_error_type"] = type(exc).__name__
                if isinstance(exc, (CanonicalIntegrityError, ForbiddenActivity)):
                    result["canonical_status"] = "failed"
                    # Preserve the verified normal stage; publish no completed final.
                    # The held variant reuses the same validated financial state.
                    try:
                        if study is None or state is None:
                            raise CanonicalIntegrityError("validated financial state unavailable for held reports")
                        held = workflow._fold_view(study, state, held_records(exc), spec["fixture"])
                        stage(held, "held")
                    except Exception as held_error:
                        result.update(report_status="failed", report_variant="unavailable", summary=None,
                                      held_report_error_type=type(held_error).__name__)
    return result


def publish_reports(spec: dict, result: dict) -> bool:
    """Only a proven stopped core worker can publish its exact report variant."""
    if not result.get("worker_stopped") or result.get("report_status") != "complete":
        return False
    variant = result.get("report_variant")
    if result.get("canonical_status") == "complete":
        require(variant == "validated", "validated canonical view has another report variant")
    else:
        require(variant == "held" and result.get("financial_state_validated") is True
                and isinstance(result.get("summary"), dict)
                and result["summary"].get("scientific_complete") is False,
                "failed canonical view cannot publish completed reports")
    staging = safe(Path(spec["reports_held_staging_path"] if variant == "held" else spec["reports_staging_path"]))
    final = safe(Path(spec["reports_path"]))
    require(staging.is_dir() and not final.exists(), "canonical report publication requires fresh final path")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.rename(staging, final)
    result["reports_published"] = True
    return True


def worker_main(connection, spec: dict, behavior: str | None = None) -> None:
    def emit(value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        require(len(raw) <= MAX_FRAME, "canonical result frame exceeds its bound")
        connection.send_bytes(raw)
    try:
        with _blocked():
            if behavior is not None:
                require(spec["fixture"], "fixture worker behavior cannot enter live work")
                if behavior == "hang":
                    time.sleep(60)
                    return
                if behavior == "partial":
                    os.write(connection.fileno(), (1000).to_bytes(4, "big") + b"{")
                    time.sleep(60)
                    return
                if behavior == "oversized":
                    connection.send_bytes(b"x" * (MAX_FRAME + 1))
                    return
                if behavior in {"network", "constructor", "subprocess"}:
                    if behavior == "network":
                        import socket
                        socket.create_connection(("127.0.0.1", 1))
                    elif behavior == "subprocess":
                        import subprocess  # nosec B404
                        subprocess.run([sys.executable, "-V"], check=True)  # nosec B603: explicit blocked negative fixture
                    else:
                        import anthropic
                        anthropic.Anthropic(api_key="fixture-not-a-secret")
                if behavior in {"small", "large", "projection-hang", "bootstrap"}:
                    result = {"kind": "p3a-hi-canonical-view-result-v1", **spec["bindings"],
                        "checkpoint": spec["checkpoint"], "fixture": True, "provider_calls": 0,
                        "canonical_status": "complete", "report_status": "complete", "report_variant": "validated", "visibility_status": "failed",
                        "summary": {"study_sha256": spec["bindings"]["study_sha256"], "fixture": True, "payload": "x" * (MAX_FRAME // 2 if behavior == "large" else 1)},
                        "snapshot_sha256": None, "financial_state_validated": True}
                    if behavior == "bootstrap":
                        from . import IMPORT_PRIVACY
                        result["summary"] = {"study_sha256": spec["bindings"]["study_sha256"], "import_privacy": dict(IMPORT_PRIVACY), "fixture": True}
                    if behavior == "projection-hang":
                        emit({**result, "phase": "canonical_ready"})
                        time.sleep(60)
                        return
                else:
                    raise ContractError("unknown fixture worker behavior")
            else:
                result = _perform(spec, emit)
    except Exception as exc:
        result = {"kind": "p3a-hi-canonical-view-result-v1", **spec["bindings"],
            "checkpoint": spec["checkpoint"], "fixture": spec["fixture"], "provider_calls": 0,
            "canonical_status": "failed", "report_status": "unavailable", "report_variant": "unavailable", "visibility_status": "failed",
            "summary": None, "snapshot_sha256": None, "financial_state_validated": False,
            "canonical_error_type": type(exc).__name__}
    try:
        emit({**result, "phase": "terminal"})
    except (BrokenPipeError, EOFError, OSError):
        # The controller already owns timeout/IPC classification and stop proof.
        pass
    finally:
        connection.close()


def collect(spec: dict, *, deadline: float, cleanup: float = 15, behavior: str | None = None,
            process_factory=None, stop_worker=None) -> dict:
    """Bound spawn, full-frame receipt and cleanup; never block controller on IPC."""
    require(behavior is None or spec["fixture"], "live worker cannot inject fixture behavior")
    require(process_factory is None or spec["fixture"], "live worker cannot replace process creation")
    require(stop_worker is None or spec["fixture"], "live worker cannot replace stop proof")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = (process_factory or context.Process)(target=worker_main, args=(child, spec, behavior), daemon=True)
    incoming: queue.Queue = queue.Queue(maxsize=2)
    stop = threading.Event()
    outgoing: queue.Queue = queue.Queue()
    helpers = []
    def starter():
        try:
            process.start()
            child.close()
        except BaseException:
            incoming.put({"ipc_error": "start_failure"})
    def reader():
        try:
            while not stop.is_set():
                value = json.loads(parent.recv_bytes(MAX_FRAME).decode("utf-8"))
                incoming.put({"result": value})
                if isinstance(value, dict) and value.get("phase") == "terminal":
                    return
        except BaseException:
            incoming.put({"ipc_error": "incomplete_or_invalid_frame"})
    for target in (starter, reader):
        helper = threading.Thread(target=target, daemon=True)
        helpers.append(helper)
        helper.start()
    state = {"process": process, "parent": parent, "child": child, "helpers": helpers,
             "stop": stop, "outgoing": outgoing, "done": False}
    ready = terminal = None
    failure = "canonical_timeout"
    try:
        while time.monotonic() < deadline - cleanup:
            try:
                message = incoming.get(timeout=max(0.0, deadline - cleanup - time.monotonic()))
            except queue.Empty:
                break
            if "result" not in message:
                failure = message.get("ipc_error", "invalid_frame")
                break
            value = message["result"]
            require(isinstance(value, dict) and value.get("kind") == "p3a-hi-canonical-view-result-v1"
                and all(value.get(key) == spec["bindings"][key] for key in BINDINGS)
                and value.get("checkpoint") == spec["checkpoint"] and value.get("fixture") is spec["fixture"]
                and type(value.get("provider_calls")) is int and value["provider_calls"] == 0
                and value.get("canonical_status") in {"complete", "failed"}
                and value.get("report_status") in {"complete", "failed", "unavailable"}
                and value.get("report_variant") in {"validated", "held", "unavailable"}
                and value.get("phase") in {"canonical_ready", "terminal"}
                and isinstance(value.get("financial_state_validated"), bool)
                and (value.get("summary") is None or isinstance(value["summary"], dict)
                    and value["summary"].get("study_sha256") == spec["bindings"]["study_sha256"]
                    and value["summary"].get("fixture") is spec["fixture"]),
                "canonical worker returned a foreign or malformed frame")
            if value["canonical_status"] == "complete":
                require(value["report_status"] == "complete" and value["financial_state_validated"]
                        and isinstance(value["summary"], dict), "canonical completion lacks validated reports")
            if value["phase"] == "canonical_ready":
                require(ready is None and value["canonical_status"] == "complete"
                        and value["report_status"] == "complete" and value["financial_state_validated"]
                        and isinstance(value["summary"], dict), "invalid canonical milestone")
                ready = value
            else:
                require(ready is None or value["summary"] == ready["summary"]
                    or value["canonical_status"] == "failed" and value["report_variant"] == "held"
                    and isinstance(value["summary"], dict) and value["summary"].get("scientific_complete") is False,
                    "canonical summary changed after validation without a held report")
                terminal = value
                state["done"] = True
                break
        if terminal is not None:
            result = terminal
        elif ready is not None and failure == "canonical_timeout":
            result = {**ready, "visibility_status": "timeout", "projection_error_type": "projection_timeout"}
        else:
            result = {"canonical_status": "failed", "canonical_error_type": failure, "summary": None,
                      "report_status": "unavailable", "visibility_status": "failed", "snapshot_sha256": None}
    except Exception as exc:
        result = {"canonical_status": "failed", "canonical_error_type": type(exc).__name__, "summary": None,
                  "report_status": "unavailable", "visibility_status": "failed", "snapshot_sha256": None}
    finally:
        stopped = (stop_worker or Transport._stop)(state, deadline)
    result["worker_stopped"] = stopped
    result["cleanup_proof"] = "stopped" if stopped else "unconfirmed"
    if not stopped:
        result["canonical_status"] = "failed"
        result["canonical_error_type"] = "worker_cleanup_unconfirmed"
    return result
