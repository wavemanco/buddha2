"""R1 final-output reminder around frozen C1 evidence/context preparation."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from buddha2.artifacts import digest
from followups.phase3a_compat_c1_v1 import contract as frozen

POLICY_ID = "portfolio-authoring-c1-completion-r1-v1"
SYSTEM_ID = "BUDDHA2-C1-COMPLETION-R1-SYSTEM-V1"
UPSTREAM_COMMIT = frozen.UPSTREAM_COMMIT
MANIFEST_NAME, INDEX_NAME, EVIDENCE_DIR = frozen.MANIFEST_NAME, frozen.INDEX_NAME, frozen.EVIDENCE_DIR
_layout, _upstream, _mission, _strategy = frozen._layout, frozen._upstream, frozen._mission, frozen._strategy
ContractError = frozen.ContractError

FINAL_RULE = """# Mandatory final-response envelope and verbatim notes
Put ALL verification commentary inside your one saved <notes> block in output/answer.md.
Re-read that file, then return its SAME COMPLETE block, INCLUDING the literal opening <notes>
and closing </notes> tags, as the entire final assistant response. Do not return an acknowledgement
or a summary of the file. No verification sentence, preface, explanation, Markdown fence, file link
or suffix may appear outside the block. Saving and re-reading the file do not replace returning it.

KEEP_BASE format example (structure only; supply your actual evidence and limitation):
<notes>
kept -> KEEP_BASE -> cite the actual source event and explain the evidential limitation.
</notes>

Edit format example (structure only; do not copy an unsupported claim):
<notes>
revised -> describe the consumed-field edit -> cite the actual source event and its limitation.
</notes>

The final response and saved notes must agree. Any verification result belongs inside that block.
This is an output-format rule, not evidence supporting an edit or KEEP_BASE."""

_COMMON = ("You author a bounded portfolio strategy through read, write and edit only.\n"
    "Use exactly those available tools; no task delegation, todo tool, shell, skills or plugins exist.\n"
    "Read MISSION.md first. The identical role contract and factual index below give the paths\n"
    "needed to batch the remaining reads after that first read. Verify actual delivered content.\n\n")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _render(role: str, label: str, repair: str | None) -> str:
    mission = frozen._render(role, label, repair)
    header = f"Authoring contract: {frozen.POLICY_ID}; stage {label}."
    if mission.count(header) != 1:
        raise ContractError("frozen C1 role header changed")
    return mission.replace(header, f"Authoring contract: {POLICY_ID}; stage {label}.", 1) + "\n\n" + FINAL_RULE


def authoring_system(effective: str, index: str) -> str:
    """One canonical composition shared by the adapter and saved-transcript proof."""
    return SYSTEM_ID + "\n" + _COMMON + effective + "\n\n# Frozen factual evidence index\n" + index + "\n\n" + FINAL_RULE


def prepare_contract(mission: str, context_dir: Path, label: str) -> dict:
    prepared = copy.deepcopy(frozen.prepare_contract(mission, context_dir, label))
    manifest = prepared["manifest"]
    effective = _render(manifest["role"], label, manifest["native_repair_diagnostic"])
    manifest.update(policy_id=POLICY_ID, contract_source_sha256=_sha(Path(__file__).read_bytes()),
        base_contract_source_sha256=_sha(Path(frozen.__file__).read_bytes()), base_policy_id=frozen.POLICY_ID,
        effective_mission_sha256=_sha(effective.encode("utf-8")), final_response_rule_sha256=_sha(FINAL_RULE.encode("utf-8")))
    manifest["sha256"] = digest({k: v for k, v in manifest.items() if k != "sha256"})
    index = (f"# {manifest['role']} evidence index — {POLICY_ID}\n\n"
        f"Stage: {label}; manifest identity: {manifest['sha256']}.\n"
        "Read all ordered lossless views below; original files remain available unchanged.\n"
        "Compatibility stubs are inert. Solver delivery and editor completion are separate.\n\n")
    for entry in manifest["required_evidence"]:
        index += f"- {entry['kind']}: context/{entry['path']} ({entry['bytes']} UTF-8 bytes).\n"
        index += "".join(f"  - context/{chunk['path']} (read offset=1, limit={chunk['limit']}).\n" for chunk in entry["chunks"])
    prepared.update(effective_mission=effective, index_text=index, authoring_system_text=authoring_system(effective, index))
    return prepared
