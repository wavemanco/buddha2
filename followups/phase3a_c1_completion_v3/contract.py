"""R2 transports the exact frozen R1 authoring contract without changing it."""
from pathlib import Path

from followups.phase3a_c1_completion_v2 import contract as implementation
from followups.phase3a_c1_completion_v2.contract import (
    EVIDENCE_DIR,
    FINAL_RULE,
    INDEX_NAME,
    MANIFEST_NAME,
    POLICY_ID,
    SYSTEM_ID,
    UPSTREAM_COMMIT,
    ContractError,
    _layout,
    _mission,
    _render,
    _strategy,
    _upstream,
    authoring_system,
    prepare_contract,
)

IMPLEMENTATION_PATH = Path(implementation.__file__)
frozen = implementation.frozen

__all__ = ["EVIDENCE_DIR", "FINAL_RULE", "INDEX_NAME", "MANIFEST_NAME", "POLICY_ID", "SYSTEM_ID",
           "UPSTREAM_COMMIT", "ContractError", "_layout", "_mission", "_render", "_strategy", "_upstream",
           "authoring_system", "prepare_contract", "IMPLEMENTATION_PATH", "frozen"]
