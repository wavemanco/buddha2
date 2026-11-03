"""Reuse the accepted owned-worker transport with a fresh HI audit namespace."""
from pathlib import Path

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v3 import transport as parent
from followups.phase3a_c1_completion_v3.transport import (
    Transport,
    TransportFailure,
    make_failure,
    normalize,
    provider_request_id,
    reject_final_assistant_prefill,
    retain_response,
    validate_audit,
)


def audit_path(study_sha256: str, fixture: bool, slot_id: str) -> Path:
    validated = parent.audit_path(study_sha256, fixture, slot_id)
    return Path("/results/phase3a-rc1-pilot-v1") / validated.relative_to(
        "/results/phase3a-c1-completion-v3")


def read_audit(study_sha256: str, fixture: bool, slot_id: str, *,
               intent: dict, result: dict, bindings: dict) -> dict:
    from .support import path, read

    target = path(audit_path(study_sha256, fixture, slot_id))
    if not target.is_file() or target.stat().st_size > 2_000_000:
        raise ContractError("missing/oversized authoritative HI transport audit")
    record = read(target)
    return validate_audit(record, intent=intent, result=result, bindings=bindings)


__all__ = ["Transport", "TransportFailure", "make_failure", "normalize", "provider_request_id",
           "reject_final_assistant_prefill", "retain_response", "audit_path", "read_audit", "validate_audit"]
