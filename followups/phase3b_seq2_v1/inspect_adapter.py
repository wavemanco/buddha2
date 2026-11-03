"""Passive saved-log export plus a keyless host launcher for the isolated Inspect image."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess  # nosec B404
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from followups.inspect_visibility_i1.importer import block_execution, decode

from .snapshot import (
    ROOT,
    VISIBILITY_OWNER_KIND,
    VISIBILITY_REQUEST_KIND,
    VISIBILITY_RESULT_KIND,
    ProjectionError,
    canonical,
    checked_path,
    lexical,
    output_path,
    read_snapshot,
    validate_projection,
)

IMAGE = "sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d"
HERE = Path(__file__).resolve().parent
RESULT_KIND = VISIBILITY_RESULT_KIND


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectionError(message)


def _write(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def _claim_owner(path: Path, value: dict) -> None:
    """Publish complete visibility ownership bytes atomically, without replacing a winner."""
    fd, temporary = tempfile.mkstemp(prefix="visibility-owner-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def _semantic(log, source_attachments: dict) -> dict:
    return {"status": log.status, "error": log.error.model_dump() if log.error else None,
            "eval": log.eval.model_dump(), "stats": log.stats.model_dump(), "results": log.results,
            "samples": [{"id": s.id, "epoch": s.epoch, "input": s.input, "target": s.target,
                         "description": s.description, "started_at": s.started_at, "completed_at": s.completed_at,
                         "output": s.output.model_dump(),
                         "scores": s.scores, "error": s.error.model_dump() if s.error else None,
                         "metadata": s.metadata, "model_usage": s.model_usage, "role_usage": s.role_usage,
                         "events": [{"event": event.event, "data": event.data, "timestamp": event.timestamp.isoformat(),
                                     "source": event.source} for event in s.events],
                         "attachments": source_attachments[s.id]} for s in log.samples]}


def export_snapshot(snapshot_dir: Path, output: Path) -> dict:
    """Called in the core-only Inspect image. Canonical files are never writable here."""
    counts = block_execution()
    payload, manifest, raw = read_snapshot(snapshot_dir)
    validate_projection(payload)
    # Imports happen only after the model/network blocks have been installed.
    from inspect_ai.event import InfoEvent
    from inspect_ai.log import (
        EvalConfig,
        EvalDataset,
        EvalError,
        EvalLog,
        EvalSample,
        EvalSpec,
        bundle_log_dir,
        read_eval_log,
        write_eval_log,
    )
    from inspect_ai.model import ModelOutput

    lexical(str(output))
    _require(output.is_absolute() and output.parent == Path("/out") and output.name not in {"", ".", ".."},
             "export must use a fresh direct child of /out")
    checked_path(output, Path("/out"), missing=True)
    _require(not output.exists(), "export output must be fresh")
    finals = {(r["pilot"], r["target"]): r["portfolio"] for r in payload["finals"]}
    tasks = {t["pilot_id"]: t for t in payload["tasks"]}
    attachments = {name: data.decode("utf-8") for name, data in raw.items()}
    samples = []
    sources = {}
    for row in payload["rows"]:
        sid = f"{row['pilot']}/{row['target']}"
        portfolio = finals[row["pilot"], row["target"]]
        responses = portfolio["responses"] if portfolio is not None else None
        display = ModelOutput()
        if responses is not None:
            # This is explicitly an ordered portfolio display, not one native model completion.
            display = ModelOutput.from_content(model="imported-native-portfolio",
                                               content=json.dumps(responses, ensure_ascii=False, indent=2))
            display.choices[0].message.id = f"{payload['checkpoint']}-{sid}-portfolio-display"
        aid = row["assessment_id"]
        assessment = payload["native_assessments"].get(aid)
        failed = row["status"] in {"invalid_group", "group_refused", "invalid_quality", "quality_refused",
                                   "unvalidated_integrity_hold", "unvalidated_known_deadline_stop",
                                   "unvalidated_unknown_deadline_hold"}
        error = None
        if failed:
            message = f"Imported native primary status: {row['status']}"
            explanation = message + "\nThis is an imported status, not an Inspect execution traceback."
            error = EvalError(message=message, traceback=explanation, traceback_ansi=explanation)
        disposition = "not_reached" if row.get("branch_status") == "not_attempted" else row["status"]
        meta = {"native_row": row, "selected_portfolio": portfolio, "native_assessment": assessment,
                "origin_task": tasks[row["pilot"]], "snapshot_sha256": manifest["payload_sha256"],
                "snapshot_checkpoint": payload["checkpoint"], "fixture": payload["fixture"],
                "source_identities": payload["source_identities"], "origin_request_parameters": payload["requests"],
                "native_status_is_authoritative": True, "future_not_attempted_is_not_failure": True,
                "display_disposition": disposition,
                "assessment_target": row["target"],
                "delivered_output_aliases": [alias for alias in payload["selected_aliases"]
                    if alias["pilot"] == row["pilot"] and alias["arm"] == row["arm"]
                    and alias["assessment_id"] == aid
                    and (row["target"] == "fixed" or alias.get("selected_checkpoint") == row["target"])],
                "checkpoint_views_are_not_independent_prompt_units": True,
                "inference_audits_shared_across_native_checkpoint_views": row["arm"] == "adaptive",
                "not_reached_refers_to_selected_primary_record_not_all_partial_native_work": True,
                "inspect_served_calls": 0, "inspect_usage": None,
                "display_mapping": "Frozen native values; portfolio JSON is display-only; no reconstructed conversation or Inspect score."}
        sample = EvalSample(id=sid, epoch=1, input=tasks[row["pilot"]].get("prompt", ""), target=[],
                            description=f"FROZEN {payload['checkpoint']}: {sid}; {disposition}; native {row['status']}",
                            output=display, scores=None, error=error, metadata=meta,
                            attachments=attachments,
                            events=[InfoEvent(timestamp=datetime.fromisoformat(payload["native_audit"]["observed_at_utc"].replace("Z", "+00:00")),
                                              data={"imported_native_row": row,
                                                    "selected_portfolio": portfolio,
                                                    "native_assessment": assessment})])
        samples.append(sample)
        sources[sid] = attachments
    # Inspect's saved-log reader orders string sample IDs. Match that display order
    # prospectively; native execution and response order remain exact in the snapshot.
    samples.sort(key=lambda sample: sample.id)
    complete = payload["summary"].get("scientific_complete") is True
    display_complete = payload["summary"].get("complete_primary") is True
    log_status = "success" if display_complete else "started" if payload["checkpoint"] == "first-pair" else "error"
    error = None
    if log_status == "error":
        message = "Imported native pilot closure is scientifically incomplete"
        error = EvalError(message=message, traceback=message + "\nNot an Inspect execution traceback.",
                          traceback_ansi=message + "\nNot an Inspect execution traceback.")
    log = EvalLog(status=log_status, error=error, results=None, samples=samples,
                  eval=EvalSpec(created=datetime.now(timezone.utc).isoformat(), task="P3B-S2 frozen native snapshot", task_version="1.0",
                                task_id=f"p3b-s2-{payload['checkpoint']}", eval_id=manifest["payload_sha256"],
                                run_id=payload["study_sha256"], model="none",
                                dataset=EvalDataset(name="Four exposed prompts / twelve assessment targets", samples=12,
                                                    sample_ids=[s.id for s in samples]), config=EvalConfig(),
                                tags=["FROZEN_SNAPSHOT", "IMPORTED", "NO_MODEL_CALLS",
                                      "SYNTHETIC" if payload["fixture"] else "NATIVE_EVIDENCE"],
                                metadata={"snapshot": payload, "manifest": manifest,
                                          "display_timestamp_is_not_native": True,
                                          "sample_display_order": "sorted sample IDs; native execution order remains in imported tasks/coverage",
                                          "log_status_mapping": "first-pair started means frozen partial evidence, never live Inspect work; success follows canonical complete_primary, with fixture/scientific_complete retained separately"}))
    from .inspect_projection import NOTICE, audit_csv, project
    log = project(log, payload, datetime.now(timezone.utc).isoformat())
    expected = _semantic(log, sources)
    output.mkdir()
    (output / "logs").mkdir()
    target = output / "logs" / f"{payload['checkpoint']}.eval"
    write_eval_log(log, target)
    saved = read_eval_log(target, resolve_attachments=True)
    raw_saved = read_eval_log(target, resolve_attachments=False)
    actual_sources = {s.id: {name: s.attachments[name] for name in raw} for s in raw_saved.samples}
    actual = _semantic(saved, actual_sources)
    if actual != expected:
        pending: list[tuple[str, object, object]] = [("$", expected, actual)]
        differences: list[dict] = []
        while pending and len(differences) < 30:
            location, left, right = pending.pop()
            if left == right:
                continue
            if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
                pending.extend((f"{location}.{key}", left[key], right[key]) for key in left)
            elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
                pending.extend((f"{location}[{i}]", a, b) for i, (a, b) in enumerate(zip(left, right, strict=True)))
            else:
                differences.append({"path": location, "expected_type": type(left).__name__,
                                    "actual_type": type(right).__name__,
                                    "expected_sha256": hashlib.sha256(canonical(left)).hexdigest(),
                                    "actual_sha256": hashlib.sha256(canonical(right)).hexdigest()})
        _write(output / "roundtrip-differences.json", differences)
    _require(actual == expected, "Inspect roundtrip changed native snapshot semantics")
    _require(not any(counts.values()), "actual export attempted a model or network call")
    bundle_log_dir(log_dir=str(output / "logs"), output_dir=str(output / "viewer"), overwrite=False)
    _require(not any(counts.values()), "viewer bundling attempted external activity")
    (output / "native-audit.csv").write_text(audit_csv(payload), encoding="utf-8", newline="")
    (output / "DISPLAY_NOTES.md").write_text(NOTICE + "\n", encoding="utf-8")
    _write(output / "semantic.json", actual)
    replay_semantic = json.loads(canonical(actual))
    replay_semantic["eval"].pop("created")  # Actual export time is distinct from frozen native replay identity.
    proof = {"kind": RESULT_KIND, "study_sha256": payload["study_sha256"],
             "checkpoint": payload["checkpoint"], "snapshot_sha256": manifest["payload_sha256"],
             "visibility_status": "complete", "provider_calls": 0, "api_spend": 0,
             "roundtrip_equal": True, "semantic_sha256": hashlib.sha256(canonical(replay_semantic)).hexdigest(),
             "source_attachment_bytes_preserved": True, "model_network_attempts": counts,
             "native_scientific_complete": complete, "inspect_results_absent": True,
              "native_scores_are_imported_metadata": True, "samples": 12,
             "actual_exported_at_utc": log.eval.created, "task_dates_basis": log.eval.metadata["presentation"]["task_dates_basis"],
             "native_admitted_request_count": len(payload["requests"]),
             "native_audit_interval_count": log.eval.metadata["presentation"]["native_audit_interval_count"],
             "activity_graph_available": False, "model_tool_events_fabricated": False}
    _write(output / "result.json", proof)
    return proof


def _host_command(args: list[str], deadline: float, *, reserve: float = 15) -> dict:
    _require(args[0] == "docker", "only the fixed Docker host commands are allowed")
    executable = shutil.which("docker")
    if executable is None:
        raise ProjectionError("Docker CLI is unavailable")
    args = [executable, *args[1:]]
    remaining = deadline - time.monotonic() - reserve
    if remaining <= 0:
        raise TimeoutError("visibility job deadline")
    result = subprocess.run(args, cwd=ROOT, timeout=remaining, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=False)  # nosec B603
    return {"command": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def host_export(snapshot_dir: Path, output: Path, *, ack: Path | None = None, timeout: float = 600) -> dict:
    """Trusted keyless host launches only a separate network-none saved-log process."""
    _require(0 < timeout <= 600, "visibility timeout exceeds defined window")
    # Lexical namespace checks precede exists/lstat; the child may never write the native tree.
    for value in (snapshot_dir, output, ack):
        if value is not None:
            lexical(str(value))
    base = ROOT / "runs/phase3b-seq2-v1"
    _require(snapshot_dir.is_absolute() and snapshot_dir.is_relative_to(base / "native"),
             "snapshot input outside native public visibility path")
    parts = snapshot_dir.relative_to(base / "native").parts
    _require(len(parts) == 5 and len(parts[0]) == 64 and all(c in "0123456789abcdef" for c in parts[0])
             and parts[1] in {"mock", "live"} and parts[2] == "visibility"
             and parts[3] in {"first-pair", "closure"} and parts[4] == "snapshot",
             "snapshot input shape differs")
    export_base = base / "visibility-exports"
    _require(output.is_absolute() and output != export_base and output.is_relative_to(export_base),
             "export writes must stay in separate visibility-exports namespace")
    if ack is not None:
        _require(ack == snapshot_dir.parent / "result.json", "ack is not this exact visibility result")
    snapshot_dir = output_path(snapshot_dir)
    payload, manifest, _ = read_snapshot(snapshot_dir, scope=ROOT / "runs/phase3b-seq2-v1")
    _require(payload["study_sha256"] == parts[0] and payload["checkpoint"] == parts[3]
             and payload["fixture"] is (parts[1] == "mock"), "public snapshot directory identity differs")
    output = output_path(output)
    _require(not output.exists() and not output.is_relative_to(snapshot_dir), "fresh separate export root required")
    if ack is not None:
        ack = output_path(ack)
        _require(ack.name == "result.json" and ack.parent.name == payload["checkpoint"]
                 and ack.parent.parent.name == "visibility", "ack is not a visibility-only result path")
        _require(not ack.exists(), "visibility acknowledgment already exists")
    request: dict | None = None
    remaining = timeout
    if ack is not None:
        request_path = checked_path(snapshot_dir.parent / "request.json", base)
        _require(request_path.is_file() and request_path.stat().st_size <= 65_536,
                 "visibility request type/size invalid")
        decoded_request = decode(request_path.read_bytes())
        if not isinstance(decoded_request, dict):
            raise ProjectionError("visibility request binding differs")
        request = decoded_request
        _require(request.get("kind") == VISIBILITY_REQUEST_KIND
                 and all(request.get(key) == manifest[key] for key in
                         ("study_sha256", "checkpoint", "snapshot_sha256", "fixture"))
                 and request.get("timeout_seconds") == 600 and request.get("cleanup_reserve_seconds") == 15
                 and request.get("snapshot_dir") == "/results/" + snapshot_dir.relative_to(ROOT / "runs").as_posix()
                 and request.get("result_path") == "/results/" + ack.relative_to(ROOT / "runs").as_posix(),
                 "visibility request binding differs")
        _require(isinstance(request.get("started_at_utc"), str) and isinstance(request.get("deadline_at_utc"), str),
                 "visibility request lacks original UTC deadline")
        started = datetime.fromisoformat(request["started_at_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(request["deadline_at_utc"].replace("Z", "+00:00"))
        _require(started.tzinfo is not None and expires.tzinfo is not None
                 and started.utcoffset() == expires.utcoffset() == timezone.utc.utcoffset(started)
                 and 0 < (expires - started).total_seconds() <= 600.001,
                 "invalid original visibility deadline")
        remaining = min(timeout, (expires - datetime.now(timezone.utc)).total_seconds())
    deadline = time.monotonic() + max(0, remaining)
    output.mkdir(parents=True)
    name = "buddha2-s2-view-" + hashlib.sha256(str(output).encode()).hexdigest()[:16]
    code_files = {
        HERE / "inspect_adapter.py": "/code/followups/phase3b_seq2_v1/inspect_adapter.py",
        HERE / "snapshot.py": "/code/followups/phase3b_seq2_v1/snapshot.py",
        HERE / "inspect_projection.py": "/code/followups/phase3b_seq2_v1/inspect_projection.py",
        ROOT / "followups/inspect_visibility_i1/importer.py": "/code/followups/inspect_visibility_i1/importer.py",
        ROOT / "followups/inspect_visibility_i1/paths.py": "/code/followups/inspect_visibility_i1/paths.py",
    }
    container_command = ["python", "-B", "-m", "followups.phase3b_seq2_v1.inspect_adapter",
                         "export", "--snapshot", "/snapshot", "--output", "/out/export"]
    mounts = []
    for source, target in code_files.items():
        checked_path(source, ROOT)
        mounts += ["--mount", f"type=bind,source={source},target={target},readonly"]
    for filename in ("manifest.json", "payload.json"):
        source = checked_path(snapshot_dir / filename, ROOT)
        mounts += ["--mount", f"type=bind,source={source},target=/snapshot/{filename},readonly"]
    mounts += ["--mount", f"type=bind,source={output},target=/out"]
    result = {"kind": RESULT_KIND, "study_sha256": payload["study_sha256"],
              "checkpoint": payload["checkpoint"], "snapshot_sha256": manifest["payload_sha256"],
              "visibility_status": "failed", "provider_calls": 0, "exporter_stopped": True}
    owned_id: str | None = None
    owns_receipt = False
    try:
        if request is not None:
            launch_allowed = deadline - time.monotonic() > 15
            owner = {"kind": VISIBILITY_OWNER_KIND, "study_sha256": payload["study_sha256"],
                     "checkpoint": payload["checkpoint"], "snapshot_sha256": manifest["snapshot_sha256"],
                     "deadline_at_utc": request["deadline_at_utc"],
                     "exporter_started": launch_allowed,
                     "state": "claimed" if launch_allowed else "closed_without_export"}
            # Same exclusive path as the core's expiry seal: a losing/late host can never launch.
            _claim_owner(snapshot_dir.parent / "ownership.json", owner)
            owns_receipt = True
            if not launch_allowed:
                raise TimeoutError("original visibility window is closed for launch")
        result.update(exporter_stopped=False, cleanup_verified=False, container_ownership="unresolved_create")
        create = _host_command(["docker", "create", "--name", name, "--network", "none", "--read-only",
                                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                                "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456",  # nosec B108 - container-private tmpfs
                                "-e", "PYTHONPATH=/code", *mounts, "--workdir", "/out", IMAGE,
                                *container_command], deadline)
        returned_id = create.get("stdout")
        candidate_id = returned_id.strip() if isinstance(returned_id, str) else ""
        if create.get("exit_code") == 0 and len(candidate_id) == 64 and all(
                c in "0123456789abcdef" for c in candidate_id):
            # Successful create output is the sole ownership proof; bind before any later write/action.
            owned_id = candidate_id
            result.update(container_ownership="owned_id", owned_container_id=owned_id)
        _write(output / "create.json", create)
        if owned_id is None:
            raise ProjectionError("visibility create did not establish an owned full container ID")
        actual = _host_command(["docker", "inspect", owned_id], deadline)
        _require(actual["exit_code"] == 0, "owned visibility container inspection failed")
        detail = json.loads(actual["stdout"])[0]
        _write(output / "actual-container.json", {"container_id": detail.get("Id"),
                                                  "requested_container_id": owned_id,
                                                  "image": detail["Image"], "mounts": detail["Mounts"],
                                                  "network_mode": detail["HostConfig"]["NetworkMode"],
                                                  "read_only_root": detail["HostConfig"]["ReadonlyRootfs"],
                                                  "cap_drop": detail["HostConfig"]["CapDrop"],
                                                  "security_options": detail["HostConfig"]["SecurityOpt"],
                                                  "command": detail["Config"]["Cmd"],
                                                  "entrypoint": detail["Config"]["Entrypoint"],
                                                  "workdir": detail["Config"]["WorkingDir"],
                                                  "environment_names": sorted(v.split("=", 1)[0]
                                                                              for v in detail["Config"]["Env"])})
        expected_mounts = {target: (source, False, "bind") for source, target in code_files.items()}
        expected_mounts.update({f"/snapshot/{name}": (snapshot_dir / name, False, "bind")
                                for name in ("manifest.json", "payload.json")})
        expected_mounts["/out"] = (output, True, "bind")
        actual_mounts = {m["Destination"]: (Path(m["Source"]), m["RW"], m["Type"])
                         for m in detail["Mounts"]}
        env_names = {value.split("=", 1)[0] for value in detail["Config"]["Env"]}
        _require(detail.get("Id") == owned_id
                 and detail["Image"] == IMAGE and detail["HostConfig"]["NetworkMode"] == "none"
                 and detail["HostConfig"]["ReadonlyRootfs"]
                 and detail["HostConfig"]["CapDrop"] == ["ALL"]
                 and detail["HostConfig"]["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges:true"])
                 and detail["Config"]["Cmd"] == container_command and detail["Config"]["Entrypoint"] in (None, [])
                 and detail["Config"]["WorkingDir"] == "/out"
                 and len(detail["Mounts"]) == len(expected_mounts) and actual_mounts == expected_mounts
                 and env_names <= {"GPG_KEY", "HOME", "LANG", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH",
                                   "PYTHONUNBUFFERED", "PYTHON_SHA256", "PYTHON_VERSION"},
                 "visibility containment differs")
        execution = _host_command(["docker", "start", "--attach", owned_id], deadline)
        _write(output / "execution.json", execution)
        _require(execution["exit_code"] == 0, "visibility saved-log export failed")
        exported = json.loads((output / "export/result.json").read_bytes())
        _require(all(exported.get(key) == result[key] for key in
                     ("kind", "study_sha256", "checkpoint", "snapshot_sha256", "provider_calls"))
                 and exported.get("visibility_status") == "complete", "visibility result differs")
        result["visibility_status"] = "complete"
    except (TimeoutError, subprocess.TimeoutExpired):
        result["visibility_status"] = "timeout"
    except FileExistsError:
        result["failure_type"] = "visibility_ownership_already_claimed"
        result["exporter_stopped"] = False  # This process cannot attest another owner's state.
    except Exception as exc:
        result["failure_type"] = type(exc).__name__  # No exception prose, headers or credentials.
    finally:
        if owned_id is not None:
            try:
                removed = _host_command(["docker", "rm", "-f", owned_id], deadline, reserve=0)
                _write(output / "cleanup.json", removed)
                if removed["exit_code"]:
                    result["visibility_status"] = "failed"
                    result["cleanup_verified"] = False
                else:
                    result["exporter_stopped"] = True
                    result["cleanup_verified"] = True
            except (TimeoutError, subprocess.TimeoutExpired):
                result["visibility_status"] = "timeout"
                result["cleanup_verified"] = False
            except Exception as exc:
                result["visibility_status"] = "failed"
                result["cleanup_verified"] = False
                result["cleanup_failure_type"] = type(exc).__name__
        _write(output / "visibility-result.json", result)
        if ack is not None and owns_receipt:
            _write(ack, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=("export", "host"))
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ack")
    args = parser.parse_args()
    for raw in (args.snapshot, args.output, args.ack):
        if raw is not None:
            lexical(raw)
    if args.mode == "export":
        _require(args.snapshot == "/snapshot" and args.ack is None, "only explicit snapshot mounts are supported")
        result = export_snapshot(Path(args.snapshot), Path(args.output))
    else:
        result = host_export(Path(args.snapshot), Path(args.output), ack=Path(args.ack) if args.ack else None)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
