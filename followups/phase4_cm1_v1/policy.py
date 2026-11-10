"""Finite P4-CM1 child grants for the existing accounted transport."""
from __future__ import annotations

import copy
import re
from collections import Counter
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, read_json
from buddha2.phase2_contracts import MAX_PROMPT_CHARS, MAX_RESPONSE_CHARS
from followups.phase3a_v1.strategy import MAX_CHARS
from followups.phase3b_seq2_v1 import ledger_core as core

ID = "phase4-cm1-child-accounting-v1"
AUTHORITY = Path(__file__).resolve().parents[2] / "evidence/phase4-cm1-v1/authorization-v1.json"
ALLOCATIONS = {"dev": 100_000_000, "inference": 850_000_000, "assessment": 250_000_000}
COUNTS = {"dev": 1161, "inference": 1569, "assessment": 39}


def _require(value: object, message: str) -> None:
    if not value:
        raise ContractError(message)


def _authority(expected: str) -> None:
    _require(core._hash(expected) and file_hash(AUTHORITY) == expected,
             "P4 parent authorization bytes differ")
    value = read_json(AUTHORITY)
    _require(isinstance(value, dict) and value.get("kind") == "phase4-cm1-authorization-v1"
        and value.get("authorized") is True
        and value.get("definition_version") == "1.0"
        and value.get("definition_sha256") == "835ecae90d089c90c73b0b98ed4086deea13c9e83304fe9070c26f3892b05579"
        and value.get("total_cap_micro_usd") == 1_200_000_000
        and value.get("allocations_micro_usd") == {"development": ALLOCATIONS["dev"],
            "inference": ALLOCATIONS["inference"], "assessment": ALLOCATIONS["assessment"]}
        and value.get("inference_cell_cap_micro_usd") == 75_000_000
        and value.get("maximum_admissions") == 40914
        and value.get("keys_after_offline_acceptance") is True,
        "P4 parent authorization scope differs")


def payload_limits() -> dict[str, int]:
    """Nested task JSON plus outer request JSON needs up to seven bytes per character."""
    frame = 65_536
    prompt = MAX_PROMPT_CHARS
    answer = MAX_RESPONSE_CHARS + 256  # Full permitted response plus its identifier.
    # The source-bound factual index and retained tool history may exceed 2 MiB.
    # The published HTTP ceiling is still hard; this does not promise model-context fit.
    editor = min(128_000_000, 7 * (artifact_limits()["context_total_bytes"] + 24 * 2_000_000 + frame))
    return {
        "plan": 7 * (prompt + MAX_CHARS + frame),
        "answer": 7 * (prompt + MAX_CHARS + 2000 + frame),
        "rank": 7 * (prompt + MAX_CHARS + 10 * answer + frame),
        "fixed_selector": 7 * (prompt + 12 * 10 * answer + frame),
        "editor": editor,
        "native_selector": editor,
        **core.POLICY["evaluator_payload_bytes"],
    }


def request_limits(profile: dict) -> dict[str, int]:
    """The ledger validates the full grant once; each request checks its pure wire contract."""
    _require(isinstance(profile, dict) and profile.get("id") == ID
        and profile.get("role_payload_bytes") == payload_limits(), "P4 request capacity contract differs")
    return dict(profile["role_payload_bytes"])


def artifact_limits() -> dict[str, int]:
    """Bound the actual C-N delivery/history shapes, separately from request bytes."""
    frame = 65_536
    # JSON can require six ASCII bytes for each permitted control character.
    portfolio = 6 * (MAX_PROMPT_CHARS + 10 * (MAX_RESPONSE_CHARS + 256)) + frame
    # Twelve settled responses; parent, ranked and rank-derivation portfolios.
    rollout = 12 * (2_000_000 + frame) + 3 * portfolio + frame
    rank_request = 7 * (MAX_PROMPT_CHARS + MAX_CHARS + 10 * (MAX_RESPONSE_CHARS + 256) + frame)
    trajectory = 12 * (2_000_000 + frame) + rank_request
    context_file = max(trajectory, portfolio, 2 * 4 * MAX_CHARS) + frame
    # Two references and, in c2, five earlier probes, with strategies and notes.
    context_total = 7 * (trajectory + portfolio + 2 * 4 * MAX_CHARS + frame) + 4 * MAX_PROMPT_CHARS
    # Existing hardware capacity remains finite. This is not a claim that every
    # maximal fixed-search combination fits the journal or the 4 GiB worker.
    # Lossless views use 4,096-character pieces. Include one rounding piece per
    # admitted context file, the originals, routing files, manifest and index.
    installed_files = (context_total + 4095) // 4096 + 128
    installed_bytes = min(1_500_000_000, 9 * context_total + 1024 * installed_files + frame)
    return {"rollout_bytes": rollout, "context_file_bytes": context_file,
            "context_total_bytes": context_total, "installed_context_files": installed_files,
            "installed_context_bytes": installed_bytes, "saved_artifact_bytes": 1_500_000_000}


def context_limits(profile: dict) -> dict[str, int]:
    request_limits(profile)
    expected = artifact_limits()
    _require(profile.get("artifact_limits") == expected, "P4 artifact capacity contract differs")
    return expected


def _scope(kind: str, pair: str) -> None:
    _require(isinstance(kind, str) and kind in COUNTS and isinstance(pair, str)
        and (pair in {"dev02", "dev04"} if kind == "dev"
             else re.fullmatch(r"p4-(?:0[1-9]|1[0-9]|2[0-4])", pair) is not None),
        "P4 child kind or prompt identity differs")


def _slot_scope(slots: dict, kind: str, pair: str, *, recovery_policy: str | None = None) -> None:
    _scope(kind, pair)
    _require(recovery_policy in (None, "required-plan-rank-once-v1"), "invalid recovery worklist policy")
    extra = {"dev": 192, "inference": 200, "assessment": 0}[kind] if recovery_policy else 0
    _require(isinstance(slots, dict) and len(slots) == COUNTS[kind] + extra, "P4 child worklist size differs")
    counts: Counter = Counter()
    conversations: dict[str, set[int]] = {}
    for name, row in slots.items():
        _require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,240}", name)
            and isinstance(row, dict), "P4 slot identity differs")
        role, cell = row.get("role"), row.get("cell")
        _require(row.get("pair") == pair and role in core.ROLES
            and cell in {pair + ":adaptive", pair + ":fixed", "assessment"}
            and ((cell == "assessment") == (role in {"group", "quality"})),
            "P4 slot role, cell or prompt differs")
        if role in {"editor", "native_selector"}:
            pattern = r":(?:inv1|dom1|c1|inv2|dom2|c2)\.a[12]" if role == "editor" else r":select\.seq2"
            conversation, turn = row.get("conversation"), row.get("turn")
            _require(set(row) == {"role", "cell", "pair", "conversation", "turn"}
                and cell == pair + ":adaptive" and isinstance(conversation, str)
                and re.fullmatch(re.escape(cell) + pattern, conversation) is not None
                and type(turn) is int and 1 <= turn <= 24
                and name == f"{pair}.adaptive.editor.{conversation.removeprefix(cell + ':')}.t{turn:02}",
                "P4 native conversation or turn differs")
            conversations.setdefault(conversation, set()).add(turn)
        else:
            _require(set(row) == {"role", "cell", "pair"}, "P4 slot metadata differs")
        if name.endswith(".recovery1"):
            original = slots.get(name.removesuffix(".recovery1"))
            _require(recovery_policy is not None and role in {"plan", "rank"} and original == row,
                     "recovery lacks its original required producer slot")
        counts[cell, role] += 1
    expected: Counter = Counter()
    if kind == "inference":
        expected.update({(pair + ":adaptive", role): count for role, count in
            {"plan": 8, "answer": 80, "rank": 8, "editor": 288, "native_selector": 24}.items()})
    if kind in {"dev", "inference"}:
        expected.update({(pair + ":fixed", role): count for role, count in
            {"plan": 96, "answer": 960, "rank": 96, "fixed_selector": 9}.items()})
    else:
        expected.update({("assessment", "group"): 9, ("assessment", "quality"): 30})
    if recovery_policy and kind in {"dev", "inference"}:
        expected.update({(pair + ":fixed", "plan"): 96, (pair + ":fixed", "rank"): 96})
        if kind == "inference":
            expected.update({(pair + ":adaptive", "plan"): 4, (pair + ":adaptive", "rank"): 4})
    _require(counts == expected and len(conversations) == (13 if kind == "inference" else 0)
        and all(turns == set(range(1, 25)) for turns in conversations.values()),
        "P4 frozen role population differs")


def _build(kind: str, pair: str, *, parent_sha256: str, authorization_sha256: str,
           allocation_sha256: str, remaining_total_micro_usd: int,
           remaining_allocation_micro_usd: int, slots_sha256: str,
           generation_study_sha256: str | None = None, continuation: dict | None = None,
           recovery_policy: str | None = None, remaining_admissions: int | None = None) -> dict:
    _scope(kind, pair)
    _require(recovery_policy in (None, "required-plan-rank-once-v1"), "invalid required-artifact policy")
    _authority(authorization_sha256)
    _require(all(core._hash(value) for value in (parent_sha256, allocation_sha256, slots_sha256)),
             "P4 parent/allocation/worklist binding differs")
    _require(core._hash(generation_study_sha256) if kind == "assessment"
        else generation_study_sha256 is None, "P4 assessment generation identity differs")
    if continuation is not None:
        from followups.phase3b_seq2_v1 import accounting
        _require(isinstance(continuation, dict) and set(continuation) == {
            "logical_study_sha256", "origins", "carried_cells"}, "invalid continuation profile")
        _require(continuation == accounting.continuation_binding(continuation["origins"],
            logical_study_sha256=continuation["logical_study_sha256"]), "origin cell counters differ")
        _require(all(cell in {pair + ":fixed", pair + ":adaptive", "assessment"}
            for cell in continuation["carried_cells"]), "continuation imports another prompt")
        for reference in continuation["origins"]:
            origin_state, origin_manifest = accounting._read_reference_cached(reference)
            if (origin_state["active_unsettled_intents"] or origin_state["durable_unknown_results"]
                    or origin_state["reserved_micro_usd"]
                    or origin_state["transport_audit_summary"]["missing_or_invalid_slots"]):
                raise core.LiabilityStop("origin unit quarantined before successor ledger admission")
            scope = origin_manifest["inputs"]["policy"].get("phase4_child", {})
            _require(scope.get("kind") == kind and scope.get("pair") == pair,
                     "continuation imports another phase or prompt scope")
    _require(type(remaining_total_micro_usd) is int and 0 < remaining_total_micro_usd <= 1_200_000_000
        and type(remaining_allocation_micro_usd) is int
        and 0 < remaining_allocation_micro_usd <= ALLOCATIONS[kind],
        "P4 remaining allocation is invalid")
    cap = min(remaining_total_micro_usd, remaining_allocation_micro_usd,
              {"dev": 75_000_000, "inference": 150_000_000, "assessment": 250_000_000}[kind])
    fixed_roles = {"plan": 96, "answer": 960, "rank": 96, "fixed_selector": 9}
    native_roles = {"plan": 8, "answer": 80, "rank": 8, "editor": 288, "native_selector": 24}
    if recovery_policy:
        fixed_roles.update(plan=192, rank=192)
        native_roles.update(plan=12, rank=12)
    bounds = {}
    for arm, roles in (("fixed", fixed_roles), ("adaptive", native_roles)):
        bounds[arm] = {"http": sum(roles.values()),
            **{field: sum(core._reservation(role)[field] * count for role, count in roles.items())
               for field in ("input", "output")}}
    value = copy.deepcopy(core.POLICY)
    value.update(id=ID, phase_micro_usd=cap, first_micro_usd=cap, cell_micro_usd=75_000_000,
        assessment_micro_usd=cap if kind == "assessment" else 0,
        first_assessment_micro_usd=cap if kind == "assessment" else 0,
        execution_pairs=[pair], maximum_admitted_attempts=COUNTS[kind], cell_bounds=bounds,
        role_payload_bytes=payload_limits(), artifact_limits=artifact_limits(),
        phase4_child={"kind": kind, "pair": pair, "parent_sha256": parent_sha256,
            "authorization_sha256": authorization_sha256, "allocation_sha256": allocation_sha256,
            "remaining_total_micro_usd": remaining_total_micro_usd,
            "remaining_allocation_micro_usd": remaining_allocation_micro_usd,
            "slots_sha256": slots_sha256, "generation_study_sha256": generation_study_sha256})
    if recovery_policy:
        value["phase4_child"]["recovery_policy"] = recovery_policy
        value["maximum_admitted_attempts"] += {"dev": 192, "inference": 200, "assessment": 0}[kind]
    if continuation is not None:
        value["phase4_child"]["continuation"] = copy.deepcopy(continuation)
        used = sum(row["attempts"] for row in continuation["carried_cells"].values())
        _require(used <= value["maximum_admitted_attempts"], "origin consumed its finite request envelope")
        value["maximum_admitted_attempts"] -= used
    if remaining_admissions is not None:
        _require(type(remaining_admissions) is int and 0 <= remaining_admissions <= 40914,
                 "invalid remaining parent admissions")
        value["phase4_child"]["remaining_admissions"] = remaining_admissions
        value["maximum_admitted_attempts"] = min(value["maximum_admitted_attempts"], remaining_admissions)
    return value


def make(kind: str, pair: str, *, slots: dict, **allocation) -> dict:
    """The parent coordinator owns serial allocation and supplies the actual frozen slots."""
    _slot_scope(slots, kind, pair, recovery_policy=allocation.get("recovery_policy"))
    return _build(kind, pair, slots_sha256=digest(slots), **allocation)


def validate(profile: dict, slots: dict | None = None) -> dict:
    _require(isinstance(profile, dict) and profile.get("id") == ID
        and isinstance(profile.get("phase4_child"), dict), "P4 child profile missing")
    allocation = profile["phase4_child"]
    _require(set(allocation) - {"continuation", "recovery_policy", "remaining_admissions"} == {"kind", "pair", "parent_sha256", "authorization_sha256",
        "allocation_sha256", "remaining_total_micro_usd", "remaining_allocation_micro_usd", "slots_sha256",
        "generation_study_sha256"},
        "P4 allocation fields differ")
    expected = _build(**allocation)
    _require(profile == expected, "P4 child policy or reservation contract differs")
    if slots is not None:
        _slot_scope(slots, allocation["kind"], allocation["pair"], recovery_policy=allocation.get("recovery_policy"))
        _require(digest(slots) == allocation["slots_sha256"], "P4 actual worklist differs")
    return copy.deepcopy(profile)
