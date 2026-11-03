"""R3 changes only the declared finite editor allowance of the R1 contract."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from buddha2.artifacts import digest
from followups.phase3a_c1_completion_v2 import contract as parent

from . import editor

POLICY_ID = "portfolio-authoring-c1-completion-r3-v1"
SYSTEM_ID = "BUDDHA2-C1-COMPLETION-R3-SYSTEM-V1"
UPSTREAM_COMMIT = parent.UPSTREAM_COMMIT
MANIFEST_NAME, INDEX_NAME, EVIDENCE_DIR = parent.MANIFEST_NAME, parent.INDEX_NAME, parent.EVIDENCE_DIR
_layout, _upstream, _mission, _strategy = parent._layout, parent._upstream, parent._mission, parent._strategy
ContractError, FINAL_RULE, frozen = parent.ContractError, parent.FINAL_RULE, parent.frozen
IMPLEMENTATION_PATH = Path(__file__)

_OLD_ALLOWANCE = """At most eight provider requests are available. Rounds one through seven are ordinary rounds; round
eight carries the pinned text-only maximum-steps instruction. Finish normally before that boundary."""
_NEW_ALLOWANCE = """At most sixteen provider requests are available. Rounds one through fifteen are ordinary rounds; round
sixteen carries the pinned text-only maximum-steps instruction. Finish normally before that boundary."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _render(role: str, label: str, repair: str | None) -> str:
    value = parent._render(role, label, repair)
    header = f"Authoring contract: {parent.POLICY_ID}; stage {label}."
    if value.count(header) != 1 or value.count(_OLD_ALLOWANCE) != 1:
        raise ContractError("frozen authoring identity/allowance changed")
    return value.replace(header, f"Authoring contract: {POLICY_ID}; stage {label}.", 1).replace(_OLD_ALLOWANCE, _NEW_ALLOWANCE, 1)


def authoring_system(effective: str, index: str) -> str:
    return SYSTEM_ID + "\n" + parent._COMMON + effective + "\n\n# Frozen factual evidence index\n" + index + "\n\n" + FINAL_RULE


def prepare_contract(mission: str, context_dir: Path, label: str) -> dict:
    prepared = copy.deepcopy(parent.prepare_contract(mission, context_dir, label))
    manifest = prepared["manifest"]
    prior_sha, prior_policy = manifest["sha256"], manifest["policy_id"]
    effective = _render(manifest["role"], label, manifest["native_repair_diagnostic"])
    manifest.update(policy_id=POLICY_ID, contract_source_sha256=_sha(Path(__file__).read_bytes()),
        prior_contract_source_sha256=_sha(Path(parent.__file__).read_bytes()), prior_policy_id=prior_policy,
        editor_profile_sha256=digest(editor.profile()), effective_mission_sha256=_sha(effective.encode()),
        final_response_rule_sha256=_sha(FINAL_RULE.encode()))
    manifest["sha256"] = digest({k: v for k, v in manifest.items() if k != "sha256"})
    index = prepared["index_text"]
    if index.count(prior_sha) != 1 or index.count(prior_policy) != 1:
        raise ContractError("frozen factual index identity changed")
    index = index.replace(prior_sha, manifest["sha256"], 1).replace(prior_policy, POLICY_ID, 1)
    prepared.update(effective_mission=effective, index_text=index, authoring_system_text=authoring_system(effective, index))
    return prepared
