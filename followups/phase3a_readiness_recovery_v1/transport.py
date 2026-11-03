"""Reuse the accepted owned-worker transport with a fresh HI audit namespace."""
from pathlib import Path
from typing import Any

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v3 import transport as parent
from followups.phase3a_c1_completion_v3.transport import (
    TransportFailure,
    make_failure,
    normalize,
    provider_request_id,
    reject_final_assistant_prefill,
    retain_response,
    validate_audit,
)


class Transport(parent.Transport):
    """Require the consumed startup attachment before constructing a live SDK path."""

    def __init__(self, *, startup_attachment: dict | None = None, **kwargs: Any) -> None:
        self.startup_attachment = None
        if kwargs.get("http_transports") is None:
            from .supervision import require_transport_attachment

            self.startup_attachment = require_transport_attachment(startup_attachment)
        # The parent separately requires concrete SDK MockTransports and fixed fake
        # keys for fixture construction; arbitrary HTTP transports cannot bypass this.
        super().__init__(**kwargs)


def audit_path(study_sha256: str, fixture: bool, slot_id: str) -> Path:
    validated = parent.audit_path(study_sha256, fixture, slot_id)
    return Path("/results/phase3a-readiness-recovery-v1") / validated.relative_to(
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
