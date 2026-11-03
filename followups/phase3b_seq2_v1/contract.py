"""Round-aware, lossless evidence contract around the unchanged native seq2 proposer."""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any

from buddha2.artifacts import digest
from followups.phase3a_c1_completion_v2 import contract as final_contract
from followups.phase3a_compat_c1_v1 import contract as frozen

from . import editor
from .support import PRIVATE, safe

POLICY_ID = "portfolio-authoring-seq2-v1"
SYSTEM_ID = "BUDDHA2-SEQ2-SYSTEM-V1"
UPSTREAM_COMMIT = frozen.UPSTREAM_COMMIT
MANIFEST_NAME, INDEX_NAME, EVIDENCE_DIR = frozen.MANIFEST_NAME, frozen.INDEX_NAME, frozen.EVIDENCE_DIR
ContractError, FINAL_RULE = frozen.ContractError, final_contract.FINAL_RULE
IMPLEMENTATION_PATH = Path(__file__)
_upstream, _strategy = frozen._upstream, frozen._strategy
STAGES = ("inv1", "dom1", "c1", "inv2", "dom2", "c2")
PAGING_RULE = ("The Read tool may show only a page or a byte-limited prefix of a file. "
    "For MISSION.md, C1_MANIFEST.json, C1_INDEX.md and every required evidence view, follow its range footer "
    "with further bounded offset/limit reads until every original numbered line is delivered. "
    "Batch independent pages and views; a listing, issued read or truncated prefix is not complete content.\n")
_HISTORY = {"inv1": (), "dom1": (), "c1": ("inv1", "dom1"),
    "inv2": ("inv1", "dom1", "c1"), "dom2": ("inv1", "dom1", "c1"),
    "c2": ("inv1", "dom1", "c1", "inv2", "dom2")}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def benchmark_prompts():
    from harness2.core.spec import BenchPrompts
    return BenchPrompts(
        work="Produce ten useful, distinct answers that satisfy the supplied request.",
        inv_levers="Improve general instructions for planning, answering, or ordering the answers.",
        dom_levers="Improve the same instructions for this particular request and its constraints.",
        domain_guidance="This solver is a fixed portfolio API pipeline, not an OpenCode solver. "
            "Only systemprompt.md is editable: one strict JSON object with exactly answer_system, "
            "plan_system and rank_system, each a nonempty string. Those decoded strings replace "
            "only the corresponding API system messages. All other request fields and the call "
            "topology are fixed. Keep the three empty compatibility files and canonical README "
            "stubs unchanged. No scripts, plugins, skills or subagents are available.")


def _layout(role: str, label: str | None = None) -> tuple[set[str], list[tuple[str, str]]]:
    if label is None:
        raise ContractError("seq2 evidence layout requires the exact round label")
    stage = label.split(".", 1)[0]
    if stage not in STAGES:
        raise ContractError("unknown seq2 authoring stage")
    required = [("task.md", "task_contract"), ("harness/systemprompt.md", "current_strategy")]
    for base in ("base1", "base2"):
        required.extend([(f"rollouts/{base}.md", "base_trajectory"),
            (f"deliverables/{base}/answers.json.txt", "base_answers"),
            (f"deliverables/{base}/INDEX.md", "routing_index")])
    allowed = {name for name, _ in required}
    allowed.update("harness/" + name for name in frozen._COMPATIBILITY)
    for candidate in _HISTORY[stage]:
        required.extend([(f"pool/{candidate}/harness/systemprompt.md", "candidate_strategy"),
            (f"pool/{candidate}/harness.diff", "candidate_diff"),
            (f"decisions/{candidate}.md", "editor_decision"),
            (f"pool/{candidate}/rollout.md", "probe_trajectory"),
            (f"pool/{candidate}/produced.md", "probe_answers")])
        allowed.update(f"pool/{candidate}/harness/" + name for name in frozen._COMPATIBILITY)
    allowed.update(name for name, _ in required)
    return allowed, required


def _mission(mission: str, label: str) -> tuple[str, str | None]:
    if not isinstance(label, str) or re.fullmatch(r"(?:inv[12]|dom[12]|c[12])\.a[12]", label) is None:
        raise ContractError("unexpected native seq2 stage/attempt")
    _upstream()
    stage = label.split(".", 1)[0]
    role = "INV" if stage.startswith("inv") else "DOM" if stage.startswith("dom") else "AGG"
    repair = None
    raw = mission
    if label.endswith(".a2"):
        if mission.count(frozen._REPAIR) != 1 or not mission.endswith(frozen._REPAIR_END):
            raise ContractError("unexpected native seq2 repair mission")
        raw, repair = mission.split(frozen._REPAIR)
        repair = repair[:-len(frozen._REPAIR_END)]
        if not 0 < len(repair.encode("utf-8")) <= 20_000:
            raise ContractError("native repair diagnostic exceeds its bound")
    from harness2.core import context, prompts

    from .strategy import _public_surface
    t = int(stage[-1])
    job = (prompts.compose_round(benchmark_prompts(), _public_surface(), t=t, k=2)
        if role == "AGG" else prompts.propose(benchmark_prompts(), role, _public_surface(),
                                             k=2, index=t, round_t=t))
    tree = context.ContextTree(root=Path("/unread-context"), task_id="unused",
        rollouts=["base1", "base2"], deliverables=["base1", "base2"],
        harness_files=1 + len(frozen._COMPATIBILITY), library=False,
        pool=list(_HISTORY[stage]), decisions=len(_HISTORY[stage]))
    if raw != context.mission(tree, job=job):
        raise ContractError("native seq2 mission differs from the actual pinned round-aware contract")
    return role, repair


def _render(role: str, label: str, repair: str | None) -> str:
    value = final_contract._render(role, label, repair)
    value = value.replace(f"Authoring contract: {final_contract.POLICY_ID}; stage {label}.",
                          f"Authoring contract: {POLICY_ID}; stage {label}.", 1)
    value = value.replace("one native Harness² agg,k=1 path", "one native Harness² seq,k=2 path")
    value = value.replace("There is one base solver rollout.", "There are two shared reference solver rollouts.")
    value = value.replace("Compose one final strategy from the base and both candidates. Resolve overlaps; retain only defensible changes.",
        "Compose this round checkpoint from the current harness and complete cumulative candidate pool. Resolve overlaps; retain only defensible changes.")
    value = value.replace("both candidate strategies, diffs, editor decisions, full probe trajectories and produced answers.",
        "all indexed candidate strategies, diffs, earlier author decisions, full probe trajectories and produced answers. Every role must read the complete indexed earlier pool.")
    value = value.replace("At most eight provider requests are available. Rounds one through seven are ordinary rounds; round\neight carries",
        "At most twenty-four provider requests are available. Rounds one through twenty-three are ordinary rounds; round\ntwenty-four carries")
    stage = label.split(".", 1)[0]
    current = "the original seed" if stage.endswith("1") else "the first composed checkpoint c1"
    return value + (f"\n\n# Current round and carry\nThis is round {stage[-1]} of two. The current editable harness is {current}. "
        "KEEP_BASE means keep that current input, not automatically reset to the original seed. "
        "The two reference executions remain shared observations. The complete indexed earlier pool and author notes "
        "are available in this context and must be read before deciding. Do not infer repeated proof from dependent samples.\n")


def authoring_system(effective: str, index: str) -> str:
    return SYSTEM_ID + "\n" + final_contract._COMMON + PAGING_RULE + effective + "\n\n# Frozen factual evidence index\n" + index + "\n\n" + FINAL_RULE


def _inventory(context: Path, allowed: set[str]) -> dict[str, bytes]:
    context = safe(context)
    allowed_dirs = {parent.as_posix() for name in allowed for parent in Path(name).parents if str(parent) != "."}
    result: dict[str, bytes] = {}
    pending = [context]
    while pending:
        directory = pending.pop()
        for name in sorted(os.listdir(directory)):
            if name.casefold() in PRIVATE or "stdout" in name.casefold() or "stderr" in name.casefold():
                raise ContractError("private native context entry forbidden")
            target = directory / name
            relative = target.relative_to(context).as_posix()
            if relative not in allowed and relative not in allowed_dirs:
                raise ContractError("unexpected native context path")
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
        raise ContractError("native context inventory/byte limit differs")
    for name in result:
        if name.endswith("/systemprompt.md") and (name == "harness/systemprompt.md" or name.startswith("pool/")):
            prefix = name.removesuffix("systemprompt.md")
            for relative, expected in frozen._COMPATIBILITY.items():
                if _sha(result[prefix + relative]) != expected:
                    raise ContractError("inert compatibility files changed")
    return result


def _prepare(mission: str, context: Path, label: str, role: str, repair: str | None,
             allowed: set[str], required: list[tuple[str, str]], effective: str) -> dict:
    original = _inventory(context, allowed)
    strategy_valid, strategy_sha = True, None
    if role != "SELECT":
        try:
            strategy_sha = digest(_strategy(original["harness/systemprompt.md"]))
        except ContractError:
            if repair is None:
                raise
            strategy_valid = False
        for relative, kind in required:
            if kind == "candidate_strategy":
                _strategy(original[relative])
    entries: list[dict[str, Any]] = []
    auxiliary: dict[str, str] = {}
    for index, (relative, kind) in enumerate(required):
        chunks, files = frozen._views(relative, original[relative], index)
        auxiliary.update(files)
        entries.append({"path": relative, "kind": kind, "bytes": len(original[relative]),
                        "sha256": _sha(original[relative]), "chunks": chunks})
    inventory = {relative: {"bytes": len(data), "sha256": _sha(data)} for relative, data in original.items()}
    manifest = {"kind": "phase3a-c1-evidence-v1", "policy_id": POLICY_ID, "role": role, "label": label,
        "upstream_commit": UPSTREAM_COMMIT, "upstream_files": _upstream(),
        "contract_source_sha256": _sha(Path(__file__).read_bytes()),
        "prior_contract_source_sha256": _sha(Path(final_contract.__file__).read_bytes()), "prior_policy_id": final_contract.POLICY_ID,
        "base_contract_source_sha256": _sha(Path(frozen.__file__).read_bytes()), "base_policy_id": frozen.POLICY_ID,
        "raw_mission_sha256": _sha(mission.encode()), "effective_mission_sha256": _sha(effective.encode()),
        "context_inventory": inventory, "context_inventory_sha256": digest(inventory),
        "input_strategy_valid": strategy_valid, "input_effective_strategy_sha256": strategy_sha,
        "native_repair_diagnostic": repair, "required_evidence": entries,
        "editor_profile_sha256": digest(editor.profile()), "final_response_rule_sha256": _sha(FINAL_RULE.encode())}
    manifest["sha256"] = digest(manifest)
    index_text = (f"# {role} evidence index — {POLICY_ID}\n\nStage: {label}; manifest identity: {manifest['sha256']}.\n"
        "Read all ordered lossless views below; original files remain available unchanged.\n"
        "Compatibility stubs are inert. Solver delivery and editor completion are separate.\n\n")
    for entry in entries:
        index_text += f"- {entry['kind']}: context/{entry['path']} ({entry['bytes']} UTF-8 bytes).\n"
        index_text += "".join(f"  - context/{chunk['path']} (read offset=1, limit={chunk['limit']}).\n" for chunk in entry["chunks"])
    if _inventory(context, allowed) != original:
        raise ContractError("native context changed while preparing contract")
    system = selector_system(effective, index_text) if role == "SELECT" else authoring_system(effective, index_text)
    return {"effective_mission": effective, "authoring_system_text": system,
            "index_text": index_text, "manifest": manifest, "evidence_files": auxiliary}


def prepare_contract(mission: str, context_dir: Path, label: str) -> dict:
    role, repair = _mission(mission, label)
    allowed, required = _layout(role, label)
    return _prepare(mission, Path(context_dir), label, role, repair, allowed, required, _render(role, label, repair))


def prepare_selector_contract(mission: str, context_dir: Path, label: str) -> dict:
    if label != "select.seq2" or type(mission) is not str or not 0 < len(mission.encode()) <= 200_000:
        raise ContractError("unexpected native selector mission")
    context = safe(context_dir)
    # Candidate IDs are generated by the actual pinned native selector. Only its named, anonymous
    # deliverables are admitted here; no strategy, trajectory or judge directory may enter.
    names = sorted(os.listdir(safe(context / "candidates")))
    if not 1 <= len(names) <= 2 or any(re.fullmatch(r"[A-Za-z0-9_-]+\.md", name) is None for name in names):
        raise ContractError("native selector candidate names differ")
    ids = [name[:-3] for name in names]
    if mission != selector_mission(ids):
        raise ContractError("native selector mission differs from pinned full-artifact contract")
    required = [("task.md", "task_contract"), *[("candidates/" + name, "selection_candidate") for name in names]]
    return _prepare(mission, context, label, "SELECT", None, {name for name, _ in required}, required, mission)


def selector_system(effective: str, index: str) -> str:
    return (SYSTEM_ID + "\nUse only read to inspect evidence; output/answer.md is the sole optional writable artifact. "
        "Read MISSION.md first and all declared lossless views before deciding. If saving output/answer.md, "
        "re-read it and return that exact complete native output as the final response. Preserve the native why and choice format.\n"
        + PAGING_RULE + effective + "\n\n# Frozen factual evidence index\n" + index)


def selector_mission(ids: list[str]) -> str:
    from harness2.core import prompts
    if not isinstance(ids, list) or not 1 <= len(ids) <= 2 or len(set(ids)) != len(ids) or any(
        not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None for value in ids):
        raise ContractError("unsupported anonymous selector IDs")
    return "\n\n".join([prompts.select(benchmark_prompts(), len(ids), pool_kind="finals", assets_note=""),
        "# YOUR EVIDENCE\n\nIt is on disk. Read it -- do not answer from this message alone.\n\n"
        "context/task.md                 the instructions\n"
        "context/source/                 task source materials, when supplied\n"
        f"context/candidates/<id>.md      one file per candidate: {', '.join(sorted(ids))}\n"
        + "\nOpen every candidate before choosing. Choose exactly one of: " + ", ".join(sorted(ids)) + "."])
