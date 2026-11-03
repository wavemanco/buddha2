"""HI changes only the declared finite editor allowance of the R1 contract."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from buddha2.artifacts import digest
from followups.phase3a_c1_completion_v2 import contract as parent

from . import editor
from .support import PRIVATE, safe

POLICY_ID = "portfolio-authoring-c1-completion-hi-v1"
SYSTEM_ID = "BUDDHA2-C1-COMPLETION-HI-SYSTEM-V1"
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



def _inventory(context: Path, allowed: set[str]) -> dict[str, bytes]:
    """Same exact native inventory under HI roots, lexical checks before metadata."""
    context = safe(context)
    allowed_dirs = {p.as_posix() for name in allowed for p in Path(name).parents if str(p) != "."}
    result = {}
    pending = [context]
    while pending:
        directory = pending.pop()
        for name in sorted(os.listdir(directory)):
            if name.casefold() in PRIVATE:
                raise ContractError("private native context entry is forbidden")
            target = directory / name
            relative = target.relative_to(context).as_posix()
            if relative not in allowed and relative not in allowed_dirs:
                raise ContractError("unexpected context path")
            target = safe(target)
            info = target.lstat()
            if stat.S_ISDIR(info.st_mode):
                if relative not in allowed_dirs:
                    raise ContractError("unexpected context directory")
                pending.append(target)
            else:
                if not stat.S_ISREG(info.st_mode) or relative not in allowed or info.st_size > 1_000_000:
                    raise ContractError("unsupported context file")
                data = target.read_bytes()
                data.decode("utf-8", errors="strict")
                result[relative] = data
    if set(result) != allowed or sum(map(len, result.values())) > 8_000_000:
        raise ContractError("context inventory/byte limit differs")
    for prefix in ("harness/", "pool/inv1/harness/", "pool/dom1/harness/"):
        if prefix + "systemprompt.md" in result:
            for relative, expected in frozen._COMPATIBILITY.items():
                if _sha(result[prefix + relative]) != expected:
                    raise ContractError("inert compatibility files changed")
    return result


def prepare_contract(mission: str, context_dir: Path, label: str) -> dict:
    """Reuse frozen layout/views/mission/render, rebind only the inventory boundary."""
    role, repair = _mission(mission, label)
    upstream = _upstream()
    allowed, required = _layout(role)
    context = Path(context_dir)
    original = _inventory(context, allowed)
    strategy_valid, strategy_sha = True, None
    try:
        strategy_sha = digest(_strategy(original["harness/systemprompt.md"]))
    except ContractError:
        if repair is None:
            raise
        strategy_valid = False
    for relative, kind in required:
        if kind == "candidate_strategy":
            _strategy(original[relative])
    effective = _render(role, label, repair)
    entries: list[dict[str, Any]] = []
    auxiliary: dict[str, str] = {}
    for index, (relative, kind) in enumerate(required):
        chunks, files = frozen._views(relative, original[relative], index)
        auxiliary.update(files)
        entries.append({"path": relative, "kind": kind, "bytes": len(original[relative]),
                        "sha256": _sha(original[relative]), "chunks": chunks})
    inventory = {relative: {"bytes": len(data), "sha256": _sha(data)} for relative, data in original.items()}
    manifest = {"kind": "phase3a-c1-evidence-v1", "policy_id": POLICY_ID, "role": role, "label": label,
        "upstream_commit": UPSTREAM_COMMIT, "upstream_files": upstream,
        "contract_source_sha256": _sha(Path(__file__).read_bytes()),
        "prior_contract_source_sha256": _sha(Path(parent.__file__).read_bytes()), "prior_policy_id": parent.POLICY_ID,
        "base_contract_source_sha256": _sha(Path(frozen.__file__).read_bytes()), "base_policy_id": frozen.POLICY_ID,
        "raw_mission_sha256": _sha(mission.encode()), "effective_mission_sha256": _sha(effective.encode()),
        "context_inventory": inventory, "context_inventory_sha256": digest(inventory),
        "input_strategy_valid": strategy_valid, "input_effective_strategy_sha256": strategy_sha,
        "native_repair_diagnostic": repair, "required_evidence": entries,
        "editor_profile_sha256": digest(editor.profile()), "final_response_rule_sha256": _sha(FINAL_RULE.encode())}
    manifest["sha256"] = digest(manifest)
    index_text = (f"# {role} evidence index \u2014 {POLICY_ID}\n\n"
        f"Stage: {label}; manifest identity: {manifest['sha256']}.\n"
        "Read all ordered lossless views below; original files remain available unchanged.\n"
        "Compatibility stubs are inert. Solver delivery and editor completion are separate.\n\n")
    for entry in entries:
        index_text += f"- {entry['kind']}: context/{entry['path']} ({entry['bytes']} UTF-8 bytes).\n"
        index_text += "".join(f"  - context/{chunk['path']} (read offset=1, limit={chunk['limit']}).\n" for chunk in entry["chunks"])
    if _inventory(context, allowed) != original:
        raise ContractError("native context changed while preparing contract")
    return {"effective_mission": effective, "authoring_system_text": authoring_system(effective, index_text),
            "index_text": index_text, "manifest": manifest, "evidence_files": auxiliary}
