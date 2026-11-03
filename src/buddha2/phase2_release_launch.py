"""Bound host inspection and explicit stdin credentials for the P2-R launcher.

Inspection is supplied by the fixed host launcher after it examines Docker's
actual container configuration. This module revalidates the frozen release and
grant before reading stdin or constructing a provider client. It is not an
independent attestation of a malicious host or domain-level egress enforcement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import re
import sys
from pathlib import Path
from typing import Any

from .artifacts import ContractError, digest, read_json, write_once
from .phase2 import IMAGE_ID
from .phase2_am1_controls import BILLING_PROFILE, CONTROL_POLICY, runtime_guard
from .phase2_dispatch import writer_lock

HOST_PROJECT = r"C:\Users\arvik\code\research\Buddha2"
HOST_RUNS = HOST_PROJECT + r"\runs"
_HASH = re.compile(r"[0-9a-f]{64}")
_ENVIRONMENT = {
    "PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256",
    "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED", "PYTHONNOUSERSITE",
    "HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "TRANSFORMERS_OFFLINE",
    "TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS", "PYTHONPATH", "NOVELTYBENCH_ROOT",
    "BUDDHA2_NB_UPSTREAM", "HARNESS2_ROOT", "BUDDHA2_OUTPUT_ROOT",
    "BUDDHA2_TEST_OUTPUT_ROOT", "BUDDHA2_OFFLINE", "TMPDIR", "BUDDHA2_IMAGE_ID",
    "BUDDHA2_RELEASE_LAUNCH_MODE",
}
_BINDINGS = ("study_sha256", "control_policy_sha256", "launcher_sha256", "grant_sha256", "journal_id")


def _path(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ContractError("launch files require absolute nonlinked run paths")
    resolved = path.resolve()
    if not resolved.is_relative_to(Path("/results")) or resolved == Path("/results"):
        raise ContractError("launch files must remain beneath /results")
    return resolved


def _host_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ContractError("invalid inspected host path")
    match = re.fullmatch(r"/(?:run/desktop/mnt/host|host_mnt)/([A-Za-z])/(.*)", value)
    if match:
        value = match[1].upper() + ":\\" + match[2].replace("/", "\\")
    if not re.match(r"^[A-Za-z]:[\\/]", value):
        raise ContractError("unsupported inspected host path")
    return ntpath.normcase(ntpath.normpath(value))


def execution_command(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> list[str]:
    return ["-B", "-m", "buddha2.phase2_release_launch", "execute", "--study", str(study),
            "--grant", str(grant), "--stage", stage, "--mode", mode,
            "--inspection", str(inspection)]


def preflight(study: Path, grant: Path, stage: str, mode: str) -> dict:
    from .phase2_release import launch_preflight

    runtime_guard()
    study, grant = _path(study), _path(grant)
    if stage not in ("first", "expansion") or mode not in ("preflight", "mock", "provider-config", "provider"):
        raise ContractError("unknown launch stage or mode")
    proposed = read_json(grant)
    if not isinstance(proposed, dict):
        raise ContractError("grant must be an explicit authority object")
    fixture = proposed.get("fixture") if mode == "preflight" else mode != "provider"
    if type(fixture) is not bool:
        raise ContractError("grant must declare fixture or provider authority")
    value = launch_preflight(study, grant, stage, fixture)
    if not isinstance(value, dict) or any(
        not isinstance(value.get(key), str) or _HASH.fullmatch(value[key]) is None for key in _BINDINGS
    ):
        raise ContractError("release preflight lacks canonical launch bindings")
    run = _path(Path(value["run"]))
    expected_run = Path("/results/phase2-release-r018") / value["study_sha256"] / ("mock" if fixture else "live")
    if run != expected_run:
        raise ContractError("release preflight returned another phase journal")
    return {"kind": "phase2-release-preflight-v1", **value, "study_path": str(study),
            "grant_path": str(grant), "run": str(run), "stage": stage, "mode": mode,
            "fixture": fixture, "configuration_only": mode == "provider-config",
            "credential_access": False, "provider_requests": 0}


def validate_inspection(record: Any, checked: dict, *, inspection: Path) -> None:
    """Validate a sanitized, content-bound record of the inspected actual container."""
    if (not isinstance(record, dict) or set(record) != {"kind", "preflight", "container", "inspection_sha256"}
            or record["kind"] != "phase2-release-host-inspection-v1"
            or record["preflight"] != checked
            or record["inspection_sha256"] != digest({k: v for k, v in record.items() if k != "inspection_sha256"})):
        raise ContractError("host inspection differs from current release/grant bindings")
    container = record["container"]
    mode = checked["mode"]
    expected = {
        "image": IMAGE_ID, "image_os": "linux", "image_architecture": "amd64",
        "network_mode": "bridge" if mode in ("provider", "provider-config") else "none",
        "read_only_rootfs": True, "privileged": False, "publish_all_ports": False,
        "pids_limit": 256, "memory": 4294967296, "nano_cpus": 2000000000,
        # Expected bounded Docker tmpfs mount, not a temporary file creation.
        "tmpfs": {"/tmp": "rw,nosuid,nodev,size=536870912"}, "log_driver": "none",  # nosec B108
        "working_dir": "/workspace", "entrypoint": ["python"], "open_stdin": True, "tty": False,
        "port_bindings": {},
        "state_at_inspection": "created",
        "command": execution_command(Path(checked["study_path"]), Path(checked["grant_path"]),
                                     checked["stage"], mode, inspection),
    }
    allowed = set(expected) | {"container_id", "cap_drop", "security_opt", "mounts", "environment_names"}
    if (not isinstance(container, dict) or set(container) != allowed
            or any(type(container.get(key)) is not type(value) or container.get(key) != value
                   for key, value in expected.items())
            or not isinstance(container.get("container_id"), str)
            or _HASH.fullmatch(container["container_id"]) is None
            or container.get("cap_drop") != ["ALL"]
            or container.get("security_opt") not in (["no-new-privileges"], ["no-new-privileges:true"])):
        raise ContractError("created container differs from the supported launch contract")
    names = container.get("environment_names")
    if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
            or len(names) != len(set(names)) or set(names) != _ENVIRONMENT):
        raise ContractError("created container has an unexpected environment")
    mounts = container.get("mounts")
    if not isinstance(mounts, list) or len(mounts) != 2:
        raise ContractError("created container has unexpected mounts")
    actual = {}
    for mount in mounts:
        if (not isinstance(mount, dict) or set(mount) != {"type", "source", "destination", "rw"}
                or mount["type"] != "bind" or type(mount["rw"]) is not bool
                or mount["destination"] not in ("/workspace", "/results")
                or mount["destination"] in actual):
            raise ContractError("created container has invalid mount metadata")
        actual[mount["destination"]] = (_host_path(mount["source"]), mount["rw"])
    if actual != {"/workspace": (_host_path(HOST_PROJECT), False), "/results": (_host_path(HOST_RUNS), True)}:
        raise ContractError("created container mounts are outside the approved new project")


def _credentials(stream: Any) -> dict[str, str]:
    try:
        raw = stream.read(16385)
        value = json.loads(raw) if isinstance(raw, str) and len(raw) <= 16384 else None
    except (ValueError, OSError) as exc:
        raise ContractError("invalid explicit credential input") from exc
    fields = {"anthropic_api_key", "openai_api_key"}
    if not isinstance(value, dict) or set(value) != fields or any(
        not isinstance(value[key], str) or not 1 <= len(value[key]) <= 4096
        or any(not 33 <= ord(char) <= 126 for char in value[key]) for key in fields
    ):
        raise ContractError("two explicit nonempty provider keys are required")
    return value


def _bind_credentials(checked: dict, keys: dict[str, str]) -> dict:
    record = {"kind": "phase2-release-credential-binding-v1",
              "study_sha256": checked["study_sha256"],
              "control_policy_sha256": checked["control_policy_sha256"],
              "launcher_sha256": checked["launcher_sha256"], "billing_profile": BILLING_PROFILE,
              "credential_fingerprints": {provider: hashlib.sha256(
                  ("buddha2-provider-key-v1\0" + provider + "\0" + keys[provider + "_api_key"]).encode("utf-8")
              ).hexdigest() for provider in ("anthropic", "openai")}}
    write_once(_path(Path(checked["run"]) / "credential-binding.json"), record)
    return record


def execute(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> dict:
    # Recheck every source/grant binding before any stdin credential read.
    checked = preflight(study, grant, stage, mode)
    # This lock precedes credential readiness/SDK construction and is distinct
    # from the runner's owner and journal locks, so nested execution is safe.
    with writer_lock(Path(checked["run"]) / "launch-owner"):
        return _execute_locked(study, grant, stage, mode, inspection, checked)


def _execute_locked(study: Path, grant: Path, stage: str, mode: str,
                    inspection: Path, checked: dict) -> dict:
    from .phase2_release import launch_execute

    inspection = _path(inspection)
    validate_inspection(read_json(inspection), checked, inspection=inspection)
    if mode in ("preflight", "provider-config") or checked["configuration_only"]:
        raise ContractError("configuration inspection cannot dispatch requests")
    interfaces = {path.name for path in Path("/sys/class/net").iterdir()}
    if (os.environ.get("BUDDHA2_RELEASE_LAUNCH_MODE") != mode
            or os.environ.get("BUDDHA2_OFFLINE") != ("1" if mode == "mock" else "0")
            or "lo" not in interfaces or (mode == "mock") != (interfaces == {"lo"})):
        raise ContractError("actual runtime network mode differs from inspected launch")
    if mode == "mock":
        from .phase2_am1_mock import SDKMock

        with SDKMock() as mock:
            result = launch_execute(study, grant, stage, mock.transport)
            for item in mock.records:
                write_once(Path(checked["run"]) / "wire" / f"{item['slot_id']}.json", item)
            return {**result, "new_mock_http_calls": mock.http_calls,
                    "host_inspection_sha256": read_json(inspection)["inspection_sha256"]}
    print(json.dumps({"credential_input_ready": True, "study_sha256": checked["study_sha256"],
                      "grant_sha256": checked["grant_sha256"],
                      "host_inspection_sha256": read_json(inspection)["inspection_sha256"]}), flush=True)
    keys = _credentials(sys.stdin)
    from .phase2_dispatch import DirectSDKTransport

    transport = None
    try:
        _bind_credentials(checked, keys)
        transport = DirectSDKTransport(anthropic_api_key=keys["anthropic_api_key"],
                                       openai_api_key=keys["openai_api_key"], control_policy=CONTROL_POLICY)
        return launch_execute(study, grant, stage, transport)
    finally:
        for key in keys:
            keys[key] = ""
        if transport is not None:
            transport._anthropic.close()
            transport._openai.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "execute"))
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--stage", choices=("first", "expansion"), required=True)
    parser.add_argument("--mode", choices=("preflight", "mock", "provider-config", "provider"), required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--inspection", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = preflight(args.study, args.grant, args.stage, args.mode)
            if args.record is not None:
                write_once(_path(args.record), result)
        else:
            if args.inspection is None:
                raise ContractError("execution requires the inspected host launch record")
            result = execute(args.study, args.grant, args.stage, args.mode, args.inspection)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception:
        # Provider errors may contain transport data. Keep raw exceptions out of
        # stdout/stderr, host runtime records and future secret-bearing sessions.
        print(json.dumps({"error": "controlled_launch_failed", "raw_error_suppressed": True}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
