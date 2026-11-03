"""Narrow inspected host boundary for the separately identified four-pair native adaptation pilot."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, read_json, write_once
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_SHA256
from buddha2.phase2_dispatch import writer_lock
from buddha2.phase2_release_launch import (
    _ENVIRONMENT as _BASE_ENVIRONMENT,
)
from buddha2.phase2_release_launch import (
    HOST_PROJECT,
    HOST_RUNS,
    _bind_credentials,
    _credentials,
    _host_path,
    _path,
)

from .accounting import IMAGE_ID, journal_identity, replay, runtime_guard
from .support import RESULTS

_ENVIRONMENT = _BASE_ENVIRONMENT | {"PHASE3A_OPENCODE", "PHASE3A_BUN"}

_HASH = re.compile(r"[0-9a-f]{64}")
_BINDINGS = ("study_sha256", "source_sha256", "policy_sha256", "runtime_sha256",
             "launcher_sha256", "grant_sha256")


def _live_study_claim(checked: dict, *, publish: bool = False) -> dict:
    """One immutable accepted R2 pilot; grants cannot multiply the allowance."""
    if (checked.get("mode") != "provider" or checked.get("fixture") is not False
            or any(not isinstance(checked.get(k), str) or _HASH.fullmatch(checked[k]) is None for k in _BINDINGS)
            or not isinstance(checked.get("run"), str)
            or Path(checked["run"]) != RESULTS / checked["study_sha256"] / "live"):
        raise ContractError("live-study claim requires the canonical provider scope")
    record = {"kind": "phase3a-r2-live-study-claim-v1", **{k: checked[k] for k in _BINDINGS}}
    path = _path(RESULTS / "live-study.json")
    if publish:
        write_once(path, record)
    elif path.exists():
        expected = (json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        if path.read_bytes() != expected:
            raise ContractError("another study or grant already claims this R2 allowance")
    return record


def _workflow_preflight(study: Path, grant: Path, fixture: bool) -> dict:
    from .workflow import preflight as check

    return check(study, grant, fixture)


def _workflow_run(study: Path, grant: Path, stage: str, transport: Any) -> dict:
    from .editor import proposer_factory
    from .workflow import run

    return run(study, grant, stage=stage, transport=transport, proposer_factory=proposer_factory)


def command(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> list[str]:
    return ["-B", "-m", "followups.phase3a_v1.launch", "--command", "execute",
            "--study", str(study), "--grant", str(grant), "--stage", stage, "--mode", mode,
            "--inspection", str(inspection)]


def preflight(study: Path, grant: Path, stage: str, mode: str) -> dict:
    runtime_guard()
    study, grant = _path(study), _path(grant)
    if stage not in ("first", "remaining") or mode not in ("preflight", "mock", "provider-config", "provider"):
        raise ContractError("unknown Phase3A launch mode")
    proposed = read_json(grant)
    if not isinstance(proposed, dict):
        raise ContractError("explicit Phase3A authority required")
    fixture = proposed.get("fixture") if mode in ("preflight", "provider-config") else mode == "mock"
    if not isinstance(fixture, bool):
        raise ContractError("authority must declare fixture or provider mode")
    value = _workflow_preflight(study, grant, fixture)
    if (not isinstance(value, dict)
            or any(not isinstance(value.get(k), str) or _HASH.fullmatch(value[k]) is None for k in _BINDINGS)
            or value.get("fixture") is not fixture or value.get("provider_calls") != 0
            or value.get("credentials_read") is not False):
        raise ContractError("Phase3A scope or canonical bindings differ")
    run, journal = _path(Path(value["run"])), _path(Path(value["journal"]))
    expected = RESULTS / value["study_sha256"] / ("mock" if fixture else "live")
    if run != expected or journal != run / "journal":
        raise ContractError("Phase3A launch returned another scope journal")
    prepared = read_json(study)
    bindings = {key: value[key] for key in ("source_sha256", "policy_sha256", "launcher_sha256")}
    journal_id = journal_identity(study_sha256=value["study_sha256"], slots=prepared["slots"],
        authority=proposed["authority"], fixture=bool(fixture), bindings=bindings, editor_tools=prepared["editor_tools"])
    if (journal / "manifest.json").exists():
        state = replay(journal)
        if state["run_id"] != journal_id or state["status"] != "ready" or state["reserved_micro_usd"] != 0:
            raise ContractError("current ledger differs or has an unresolved hold")
    else:
        state = None
    if stage == "remaining" and (state is None or not state["engineering_review"]):
        raise ContractError("remaining execution requires the original first-pair engineering review")
    checked = {"kind": "phase3a-launch-preflight-v1", **value, "study_path": str(study),
            "grant_path": str(grant), "run": str(run), "journal": str(journal), "mode": mode,
            "stage": stage, "journal_id": journal_id, "control_policy_sha256": CONTROL_SHA256,
            "billing_profile": BILLING_PROFILE, "cap_micro_usd": 205860000,
            "first_pair_cap_micro_usd": 50860000, "slot_count": 775,
            "configuration_only": mode == "provider-config", "credential_access": False,
            "provider_requests": 0}
    if mode == "provider":
        _live_study_claim(checked)
    return checked


def validate_inspection(record: Any, checked: dict, path: Path) -> None:
    if (not isinstance(record, dict)
            or set(record) != {"kind", "preflight", "container", "inspection_sha256"}
            or record["kind"] != "phase3a-host-inspection-v1" or record["preflight"] != checked
            or record["inspection_sha256"] != digest({k: v for k, v in record.items() if k != "inspection_sha256"})):
        raise ContractError("host inspection differs from current Phase3A authority")
    mode = checked["mode"]
    expected = {
        "image": IMAGE_ID, "image_os": "linux", "image_architecture": "amd64",
        "network_mode": "bridge" if mode in ("provider", "provider-config") else "none",
        "read_only_rootfs": True, "privileged": False, "publish_all_ports": False,
        "pids_limit": 256, "memory": 4294967296, "nano_cpus": 2000000000,
        # Declarative bounded Docker tmpfs; no temporary file is created here.
        "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none",  # nosec B108
        "working_dir": "/workspace", "entrypoint": ["python"], "open_stdin": True,
        "tty": False, "port_bindings": {}, "state_at_inspection": "created",
        "command": command(Path(checked["study_path"]), Path(checked["grant_path"]), checked["stage"], mode, path),
    }
    c = record["container"]
    fields = set(expected) | {"container_id", "cap_drop", "security_opt", "mounts", "environment_names"}
    if (not isinstance(c, dict) or set(c) != fields
            or any(type(c.get(k)) is not type(v) or c.get(k) != v for k, v in expected.items())
            or not isinstance(c.get("container_id"), str) or _HASH.fullmatch(c["container_id"]) is None
            or c["cap_drop"] != ["ALL"]
            or c["security_opt"] not in (["no-new-privileges"], ["no-new-privileges:true"])):
        raise ContractError("actual container differs from the Phase3A contract")
    names = c["environment_names"]
    if (not isinstance(names, list) or any(not isinstance(n, str) for n in names)
            or len(names) != len(set(names)) or set(names) != _ENVIRONMENT):
        raise ContractError("unexpected container environment")
    if not isinstance(c["mounts"], list) or len(c["mounts"]) != 2:
        raise ContractError("unexpected container mounts")
    mounts = {}
    for mount in c["mounts"]:
        if (not isinstance(mount, dict) or set(mount) != {"type", "source", "destination", "rw"}
                or mount["type"] != "bind" or type(mount["rw"]) is not bool
                or mount["destination"] not in ("/workspace", "/results")
                or mount["destination"] in mounts):
            raise ContractError("invalid container mount metadata")
        mounts[mount["destination"]] = (_host_path(mount["source"]), mount["rw"])
    if mounts != {"/workspace": (_host_path(HOST_PROJECT), False), "/results": (_host_path(HOST_RUNS), True)}:
        raise ContractError("container mounts escape the new project")


def execute(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> dict:
    checked = preflight(study, grant, stage, mode)
    with writer_lock(Path(checked["run"]) / "launch-owner"):
        checked = preflight(study, grant, stage, mode)
        path = _path(inspection)
        record = read_json(path)
        validate_inspection(record, checked, path)
        if mode in ("preflight", "provider-config") or checked["configuration_only"]:
            raise ContractError("configuration-only inspection cannot dispatch")
        interfaces = {p.name for p in Path("/sys/class/net").iterdir()}
        if (os.environ.get("BUDDHA2_RELEASE_LAUNCH_MODE") != mode
                or os.environ.get("BUDDHA2_OFFLINE") != ("1" if mode == "mock" else "0")
                or "lo" not in interfaces or (mode == "mock") != (interfaces == {"lo"})):
            raise ContractError("actual network mode differs from inspected launch")
        print(json.dumps({"credential_input_ready": True, "study_sha256": checked["study_sha256"],
                          "grant_sha256": checked["grant_sha256"],
                          "host_inspection_sha256": record["inspection_sha256"]}), flush=True)
        keys = _credentials(sys.stdin)
        transport = None
        try:
            if preflight(study, grant, stage, mode) != checked:
                raise ContractError("Phase3A source or authority changed during credential entry")
            if mode == "mock":
                if set(keys.values()) != {"fixture-not-a-secret"}:
                    raise ContractError("mock launch accepts only explicit fake keys")
                from .mocks import SDKMock

                with SDKMock() as mock:
                    result = _workflow_run(study, grant, stage, mock.transport)
                    for row in mock.records:
                        write_once(Path(checked["run"]) / "wire" / f"{row['slot_id']}.json", row)
                    return {**result, "new_mock_http_calls": mock.http_calls}
            _live_study_claim(checked, publish=True)
            _bind_credentials(checked, keys)
            from .transport import Transport

            transport = Transport(anthropic_api_key=keys["anthropic_api_key"],
                                  openai_api_key=keys["openai_api_key"])
            return _workflow_run(study, grant, stage, transport)
        finally:
            for key in keys:
                keys[key] = ""
            if transport is not None:
                transport._anthropic.close()
                transport._openai.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", choices=("preflight", "execute"), required=True)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--mode", choices=("preflight", "mock", "provider-config", "provider"), required=True)
    parser.add_argument("--stage", choices=("first", "remaining"), required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--inspection", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.study, args.grant, args.stage, args.mode)
            if args.record is not None:
                write_once(_path(args.record), result)
        else:
            if args.inspection is None:
                raise ContractError("execution requires actual host inspection")
            result = execute(args.study, args.grant, args.stage, args.mode, args.inspection)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception:
        print(json.dumps({"error": "controlled_followup_launch_failed", "raw_error_suppressed": True}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
