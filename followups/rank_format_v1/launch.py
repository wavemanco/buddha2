"""Narrow inspected host boundary for the separately identified four-order follow-up."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, read_json, write_once
from buddha2.phase2 import IMAGE_ID
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_POLICY, runtime_guard
from buddha2.phase2_dispatch import writer_lock
from buddha2.phase2_release_launch import (
    _ENVIRONMENT,
    HOST_PROJECT,
    HOST_RUNS,
    _bind_credentials,
    _credentials,
    _host_path,
    _path,
)

_HASH = re.compile(r"[0-9a-f]{64}")
_BINDINGS = ("study_sha256", "source_sha256", "policy_sha256", "control_policy_sha256",
             "launcher_sha256", "grant_sha256", "journal_id")


def _workflow_preflight(study: Path, grant: Path, fixture: bool) -> dict:
    from .workflow import preflight as check

    return check(study, grant, fixture)


def _workflow_run(study: Path, grant: Path, transport: Any) -> dict:
    from .workflow import run

    return run(study, grant, transport)


def command(study: Path, grant: Path, mode: str, inspection: Path) -> list[str]:
    return ["-B", "-m", "followups.rank_format_v1.launch", "--command", "execute",
            "--study", str(study), "--grant", str(grant), "--mode", mode,
            "--inspection", str(inspection)]


def preflight(study: Path, grant: Path, mode: str) -> dict:
    runtime_guard()
    study, grant = _path(study), _path(grant)
    if mode not in ("preflight", "mock", "provider-config", "provider"):
        raise ContractError("unknown follow-up launch mode")
    proposed = read_json(grant)
    if not isinstance(proposed, dict):
        raise ContractError("explicit follow-up authority required")
    fixture = proposed.get("fixture") if mode in ("preflight", "provider-config") else mode == "mock"
    if type(fixture) is not bool:
        raise ContractError("authority must declare fixture or provider mode")
    value = _workflow_preflight(study, grant, fixture)
    if (not isinstance(value, dict)
            or any(not isinstance(value.get(k), str) or _HASH.fullmatch(value[k]) is None for k in _BINDINGS)
            or value.get("fixture") is not fixture or value.get("billing_profile") != BILLING_PROFILE
            or value.get("slot_count") != 44 or value.get("role_counts") != {"group": 4, "quality": 40}
            or value.get("cap_micro_usd") != 30000000):
        raise ContractError("follow-up scope or canonical bindings differ")
    run, journal = _path(Path(value["run"])), _path(Path(value["journal"]))
    expected = (Path("/results/phase2b-rank-format-v1") / value["study_sha256"] / "mock"
                if fixture else Path("/results/phase2-am1") / value["study_sha256"] / "first-block")
    if run != expected or journal != run / "journal":
        raise ContractError("follow-up launch returned another scope journal")
    return {"kind": "rank-format-launch-preflight-v1", **value, "study_path": str(study),
            "grant_path": str(grant), "run": str(run), "journal": str(journal), "mode": mode,
            "configuration_only": mode == "provider-config", "credential_access": False,
            "provider_requests": 0}


def validate_inspection(record: Any, checked: dict, path: Path) -> None:
    if (not isinstance(record, dict)
            or set(record) != {"kind", "preflight", "container", "inspection_sha256"}
            or record["kind"] != "rank-format-host-inspection-v1" or record["preflight"] != checked
            or record["inspection_sha256"] != digest({k: v for k, v in record.items() if k != "inspection_sha256"})):
        raise ContractError("host inspection differs from current follow-up authority")
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
        "command": command(Path(checked["study_path"]), Path(checked["grant_path"]), mode, path),
    }
    c = record["container"]
    fields = set(expected) | {"container_id", "cap_drop", "security_opt", "mounts", "environment_names"}
    if (not isinstance(c, dict) or set(c) != fields
            or any(type(c.get(k)) is not type(v) or c.get(k) != v for k, v in expected.items())
            or not isinstance(c.get("container_id"), str) or _HASH.fullmatch(c["container_id"]) is None
            or c["cap_drop"] != ["ALL"]
            or c["security_opt"] not in (["no-new-privileges"], ["no-new-privileges:true"])):
        raise ContractError("actual container differs from the follow-up contract")
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


def execute(study: Path, grant: Path, mode: str, inspection: Path) -> dict:
    checked = preflight(study, grant, mode)
    with writer_lock(Path(checked["run"]) / "launch-owner"):
        checked = preflight(study, grant, mode)
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
            if preflight(study, grant, mode) != checked:
                raise ContractError("follow-up source or authority changed during credential entry")
            if mode == "mock":
                if set(keys.values()) != {"fixture-not-a-secret"}:
                    raise ContractError("mock launch accepts only explicit fake keys")
                from buddha2.phase2_am1_mock import SDKMock

                with SDKMock() as mock:
                    result = _workflow_run(study, grant, mock.transport)
                    for row in mock.records:
                        write_once(Path(checked["run"]) / "wire" / f"{row['slot_id']}.json", row)
                    return {**result, "new_mock_http_calls": mock.http_calls}
            _bind_credentials(checked, keys)
            from buddha2.phase2_dispatch import DirectSDKTransport

            transport = DirectSDKTransport(anthropic_api_key=keys["anthropic_api_key"],
                                           openai_api_key=keys["openai_api_key"], control_policy=CONTROL_POLICY)
            return _workflow_run(study, grant, transport)
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
    parser.add_argument("--record", type=Path)
    parser.add_argument("--inspection", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.study, args.grant, args.mode)
            if args.record is not None:
                write_once(_path(args.record), result)
        else:
            if args.inspection is None:
                raise ContractError("execution requires actual host inspection")
            result = execute(args.study, args.grant, args.mode, args.inspection)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception:
        print(json.dumps({"error": "controlled_followup_launch_failed", "raw_error_suppressed": True}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
