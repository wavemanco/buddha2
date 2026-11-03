"""Inspected, separately claimed C1 completion controller with explicit stdin keys."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError, digest, read_json, write_once
from buddha2.phase2_am1_controls import BILLING_PROFILE, CONTROL_SHA256
from buddha2.phase2_dispatch import writer_lock
from buddha2.phase2_release_launch import _bind_credentials, _credentials, _path
from followups.phase3a_v1 import launch as frozen

from . import accounting
from .support import BASE, NATIVE

MODULE = "followups.phase3a_c1_completion_v1.launch"
_HASH = re.compile(r"[0-9a-f]{64}")
_BINDINGS = ("study_sha256", "source_sha256", "policy_sha256", "runtime_sha256", "launcher_sha256", "grant_sha256")
_ENVIRONMENT = frozen._ENVIRONMENT
HOST_PROJECT, HOST_RUNS = frozen.HOST_PROJECT, frozen.HOST_RUNS
STAGES = ("readiness", "first", "remaining", "all")
MODES = ("preflight", "mock", "provider-config", "provider")


def _completion_path(value: Path) -> Path:
    """Reject old/private input and record locations before filesystem inspection."""
    value = Path(value)
    if (not value.is_absolute() or ".." in value.parts or not value.is_relative_to(BASE) or value == BASE
            or any(part.lower() in {"credential-binding.json", ".writer.lock", ".env", "credentials.json", "auth.json"}
                   for part in value.parts)):
        raise ContractError("launch inputs/inspection/records must stay in the new public completion scope")
    return _path(value)


def _live_study_claim(checked: dict, *, publish: bool = False) -> dict:
    """One new immutable allowance claim; never open an old R2 global claim."""
    if (checked.get("mode") != "provider" or checked.get("fixture") is not False
            or any(not isinstance(checked.get(k), str) or _HASH.fullmatch(checked[k]) is None for k in _BINDINGS)
            or checked["study_sha256"] in accounting.RETIRED_STUDIES
            or Path(checked.get("run", "")) != NATIVE / checked["study_sha256"] / "live"
            or Path(checked.get("journal", "")) != accounting.canonical_journal(checked["study_sha256"], False)):
        raise ContractError("completion claim requires the exact fresh provider scope")
    record = {"kind": "phase3a-c1-completion-live-study-claim-v1", **{k: checked[k] for k in _BINDINGS},
        "run": checked["run"], "journal": checked["journal"], "cap_micro_usd": 205860000,
        "first_cap_micro_usd": 50860000, "readiness_included_micro_usd": 20000000}
    path = _path(BASE / "live-study.json")
    if publish:
        write_once(path, record)
    elif path.exists():
        expected = (json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
        if path.read_bytes() != expected:
            raise ContractError("another completion study or grant already claims this allowance")
    return record


def _workflow_preflight(study: Path, grant: Path, fixture: bool, stage: str, *, configuration_only: bool = False) -> dict:
    from .workflow import preflight as check
    return check(study, grant, fixture, stage, require_offline_gate=not configuration_only)


def _workflow_run(study: Path, grant: Path, stage: str, transport: Any) -> dict:
    from .workflow import run
    return run(study, grant, stage=stage, transport=transport)


def command(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> list[str]:
    return ["-B", "-m", MODULE, "--command", "execute", "--study", str(study), "--grant", str(grant),
            "--stage", stage, "--mode", mode, "--inspection", str(inspection)]


def preflight(study: Path, grant: Path, stage: str, mode: str) -> dict:
    accounting.runtime_guard()
    study, grant = _completion_path(study), _completion_path(grant)
    if stage not in STAGES or mode not in MODES:
        raise ContractError("unknown completion launch stage/mode")
    proposed = read_json(grant)
    if not isinstance(proposed, dict):
        raise ContractError("explicit completion authority is required")
    raw_fixture = proposed.get("fixture") if mode in ("preflight", "provider-config") else mode == "mock"
    if type(raw_fixture) is not bool:
        raise ContractError("completion authority must declare its mode")
    fixture = bool(raw_fixture)
    value = _workflow_preflight(study, grant, fixture, stage, configuration_only=mode == "provider-config")
    if (not isinstance(value, dict)
            or any(not isinstance(value.get(k), str) or _HASH.fullmatch(value[k]) is None for k in _BINDINGS)
            or value.get("fixture") is not fixture or type(value.get("provider_calls")) is not int
            or value["provider_calls"] != 0 or value.get("credentials_read") is not False):
        raise ContractError("completion scope/bindings differ")
    run, journal = _path(Path(value["run"])), _path(Path(value["journal"]))
    if (run != NATIVE / value["study_sha256"] / ("mock" if fixture else "live")
            or journal != accounting.canonical_journal(value["study_sha256"], fixture)):
        raise ContractError("completion returned a foreign physical root or journal")
    prepared = read_json(study)
    bindings = {key: value[key] for key in ("source_sha256", "policy_sha256", "launcher_sha256")}
    journal_id = accounting.journal_identity(study_sha256=value["study_sha256"], slots=prepared["slots"],
        authority=proposed["authority"], fixture=fixture, bindings=bindings, editor_tools=prepared["editor_tools"])
    if (journal / "manifest.json").exists():
        state = accounting.replay(journal)
        if state["run_id"] != journal_id or state["status"] != "ready" or state["reserved_micro_usd"] != 0:
            raise ContractError("completion journal has another identity or unresolved hold")
    checked = {**value, "kind": "phase3a-c1-completion-launch-preflight-v1",
        "study_path": str(study), "grant_path": str(grant), "run": str(run), "journal": str(journal),
        "mode": mode, "stage": stage, "journal_id": journal_id, "control_policy_sha256": CONTROL_SHA256,
        "billing_profile": BILLING_PROFILE, "cap_micro_usd": 205860000, "first_pair_cap_micro_usd": 50860000,
        "readiness_included_micro_usd": 20000000, "slot_count": 775,
        "configuration_only": mode == "provider-config", "credential_access": False, "provider_requests": 0}
    if mode == "provider":
        _live_study_claim(checked)
    return checked


def validate_inspection(record: Any, checked: dict, path: Path) -> None:
    """Validate new namespace literally, then reuse the frozen full Docker contract."""
    if (not isinstance(record, dict) or set(record) != {"kind", "preflight", "container", "inspection_sha256"}
            or record["kind"] != "phase3a-c1-completion-host-inspection-v1" or record["preflight"] != checked
            or record["inspection_sha256"] != digest({k: v for k, v in record.items() if k != "inspection_sha256"})
            or not isinstance(record["container"], dict)
            or record["container"].get("command") != command(Path(checked["study_path"]), Path(checked["grant_path"]),
                                                        checked["stage"], checked["mode"], path)):
        raise ContractError("actual completion inspection/command differs")
    # Only the already-validated command/module and record kind are translated;
    # all actual image, environment, mount, permission and resource values remain.
    adapted = copy.deepcopy(record)
    adapted["kind"] = "phase3a-host-inspection-v1"
    adapted["container"]["command"] = frozen.command(Path(checked["study_path"]), Path(checked["grant_path"]),
                                                     checked["stage"], checked["mode"], path)
    adapted["inspection_sha256"] = digest({k: v for k, v in adapted.items() if k != "inspection_sha256"})
    frozen.validate_inspection(adapted, checked, path)


def execute(study: Path, grant: Path, stage: str, mode: str, inspection: Path) -> dict:
    checked = preflight(study, grant, stage, mode)
    with writer_lock(Path(checked["run"]) / "launch-owner"):
        checked = preflight(study, grant, stage, mode)
        path = _completion_path(inspection)
        record = read_json(path)
        validate_inspection(record, checked, path)
        if mode in ("preflight", "provider-config") or checked["configuration_only"]:
            raise ContractError("configuration-only completion cannot dispatch")
        interfaces = {p.name for p in Path("/sys/class/net").iterdir()}
        if (os.environ.get("BUDDHA2_RELEASE_LAUNCH_MODE") != mode
                or os.environ.get("BUDDHA2_OFFLINE") != ("1" if mode == "mock" else "0")
                or "lo" not in interfaces or (mode == "mock") != (interfaces == {"lo"})):
            raise ContractError("actual completion network differs from inspection")
        print(json.dumps({"credential_input_ready": True, "study_sha256": checked["study_sha256"],
            "grant_sha256": checked["grant_sha256"], "host_inspection_sha256": record["inspection_sha256"]}), flush=True)
        keys = _credentials(sys.stdin)
        transport = None
        try:
            if preflight(study, grant, stage, mode) != checked:
                raise ContractError("completion source/authority changed during key entry")
            if mode == "mock":
                if set(keys.values()) != {"fixture-not-a-secret"}:
                    raise ContractError("mock completion accepts only explicit fake keys")
                from .mocks import StudyMock
                with StudyMock() as mock:
                    result = _workflow_run(study, grant, stage, mock.transport)
                    for row in mock.records:
                        write_once(Path(checked["run"]) / "wire" / f"{row['slot_id']}.json", row)
                    return {**result, "new_mock_http_calls": mock.http_calls}
            _live_study_claim(checked, publish=True)
            _bind_credentials(checked, keys)
            from followups.phase3a_v1.transport import Transport
            transport = Transport(anthropic_api_key=keys["anthropic_api_key"], openai_api_key=keys["openai_api_key"])
            # A single controller retains the keys only in RAM across all workflow barriers.
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
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--inspection", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.study, args.grant, args.stage, args.mode)
            if args.record is not None:
                write_once(_completion_path(args.record), result)
        else:
            if args.inspection is None:
                raise ContractError("completion requires actual host inspection")
            result = execute(args.study, args.grant, args.stage, args.mode, args.inspection)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception:
        print(json.dumps({"error": "controlled_completion_launch_failed", "raw_error_suppressed": True}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
