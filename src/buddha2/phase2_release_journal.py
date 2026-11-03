"""One complete-pilot journal with append-only, cumulative stage authority.

The execution identity never includes a mutable grant. Authority is a separate
hash-linked record bound to an exact journal prefix; later approval cannot erase
earlier spend, release an unresolved liability or create another allowance.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from . import phase2_am1_controls as am1
from .artifacts import ContractError, digest, file_hash, read_json
from .phase2_dispatch import (
    FROZEN_PROFILES,
    DirectSDKTransport,
    _intent,
    _publish,
    _result,
    _validate_request,
    writer_lock,
)


class AuthorityError(ContractError):
    """No applicable, consistent stage authority permits this operation."""


class BudgetStopError(ContractError):
    """The next reservation cannot fit within cumulative authorized funds."""


class LiabilityError(ContractError):
    """A delivered or interrupted request still has unresolved liability."""


_BINDINGS = {"journal_id", "study_sha256", "source_sha256", "control_policy_sha256",
             "launcher_sha256", "billing_profile", "fixture"}
_GRANT_FIELDS = _BINDINGS | {"grant_id", "stage", "previous_authority_sha256", "review_sha256",
                            "cumulative_cap_micro_usd", "authorized", "grant_sha256"}


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _seal(value: dict, field: str) -> dict:
    return value | {field: digest(value)}


def _check_seal(value: Any, field: str) -> None:
    if (not isinstance(value, dict) or not _hash(value.get(field))
            or value[field] != digest({key: part for key, part in value.items() if key != field})):
        raise ContractError("invalid release record identity")


def _study(study: Any) -> None:
    from .phase2 import make_worklist

    _check_seal(study, "study_sha256")
    budget = study.get("budget_policy")
    fields = {"revision", "first_stage_max_micro_usd", "phase_max_micro_usd",
              "first_slots_max", "phase_slots_max"}
    if (not isinstance(budget, dict) or set(budget) != fields
            or budget["revision"] != "p2r-cumulative-authority-v1"
            or type(budget["first_stage_max_micro_usd"]) is not int
            or type(budget["phase_max_micro_usd"]) is not int
            or not 0 < budget["first_stage_max_micro_usd"] <= budget["phase_max_micro_usd"]
            <= am1.FULL_STUDY_MAX_MICRO_USD
            or budget["first_stage_max_micro_usd"] > am1.FIRST_BLOCK_MAX_MICRO_USD
            or budget["first_slots_max"] != 55 or budget["phase_slots_max"] != 1320
            or study.get("budget_policy_sha256") != digest(budget)):
        raise ContractError("invalid frozen release budget policy")
    if (study.get("profiles") != FROZEN_PROFILES or study.get("admission") != am1.CONTROL_POLICY
            or study.get("control_policy_sha256") != am1.CONTROL_SHA256
            or study.get("billing_profile") != am1.BILLING_PROFILE
            or not _hash(study.get("launcher_sha256"))
            or not isinstance(study.get("package_files"), dict)
            or not study["package_files"] or any(not _hash(value) for value in study["package_files"].values())
            or study.get("worklist") != make_worklist(study.get("tasks", []))):
        raise ContractError("release study/profile/control/worklist binding differs")


def _inputs(study: dict, fixture: bool) -> dict:
    _study(study)
    if type(fixture) is not bool:
        raise ContractError("explicit fixture/live mode is required")
    return {"kind": "phase2-release-journal-v1", "study_sha256": study["study_sha256"],
            "source_sha256": digest(study["package_files"]),
            "launcher_sha256": study["launcher_sha256"], "fixture": fixture,
            "control_policy_sha256": am1.CONTROL_SHA256, "billing_profile": am1.BILLING_PROFILE,
            "profiles": copy.deepcopy(FROZEN_PROFILES), "control_policy": copy.deepcopy(am1.CONTROL_POLICY),
            "slots": copy.deepcopy(study["worklist"]["slots"]),
            "budget_policy": copy.deepcopy(study["budget_policy"])}


def journal_identity(study: dict, fixture: bool) -> str:
    """Pure identity: full worklist and budget policy, never an actual grant."""
    return digest(_inputs(study, fixture))


def _path(run: Path, study_sha256: str | None = None, *, fixture: bool = True) -> Path:
    run = Path(run)
    if any(path.is_symlink() for path in (run, *run.parents)):
        raise ContractError("release journal cannot traverse links")
    if not fixture:
        from .phase2 import PROJECT

        am1.runtime_guard()
        import os

        if os.environ.get("BUDDHA2_OUTPUT_ROOT") != "/results" or PROJECT != Path("/workspace"):
            raise ContractError("live release requires fixed /workspace and /results launch mounts")
        expected = Path("/results/phase2-release-r018") / str(study_sha256) / "live/journal"
        if run != expected:
            raise ContractError("live release requires its single canonical phase journal")
    return run


def initialize_journal(run: Path, study: dict, *, fixture: bool) -> dict:
    inputs = _inputs(study, fixture)
    run = _path(run, study["study_sha256"], fixture=fixture)
    manifest = {"schema_version": 1, "run_id": digest(inputs), "inputs": inputs}
    with writer_lock(run):
        _publish(run / "manifest.json", manifest)
        _publish(run / "study.json", study)
    return manifest


def _manifest(run: Path) -> dict:
    run = _path(run)
    value = read_json(run / "manifest.json")
    if (not isinstance(value, dict) or set(value) != {"schema_version", "run_id", "inputs"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["inputs"], dict)
            or value["run_id"] != digest(value["inputs"])):
        raise ContractError("invalid release journal manifest")
    inputs = value["inputs"]
    expected = {"kind", "study_sha256", "source_sha256", "launcher_sha256", "fixture",
                "control_policy_sha256", "billing_profile", "profiles", "control_policy",
                "slots", "budget_policy"}
    if (set(inputs) != expected or inputs["kind"] != "phase2-release-journal-v1"
            or type(inputs["fixture"]) is not bool
            or inputs["control_policy_sha256"] != am1.CONTROL_SHA256
            or inputs["billing_profile"] != am1.BILLING_PROFILE
            or inputs["profiles"] != FROZEN_PROFILES or inputs["control_policy"] != am1.CONTROL_POLICY
            or any(not _hash(inputs[key]) for key in ("study_sha256", "source_sha256", "launcher_sha256"))
            or not isinstance(inputs["slots"], dict) or len(inputs["slots"]) != 1320
            or any(not isinstance(row, dict) or set(row) != {"role", "checkpoint"}
                   or row["role"] not in FROZEN_PROFILES or row["checkpoint"] not in ("canary", "expansion")
                   for row in inputs["slots"].values())
            or sum(row.get("checkpoint") == "canary" for row in inputs["slots"].values()) != 55):
        raise ContractError("release journal contract differs")
    _path(run, inputs["study_sha256"], fixture=inputs["fixture"])
    return value


def _binding(manifest: dict) -> dict:
    inputs = manifest["inputs"]
    return {"journal_id": manifest["run_id"], **{key: inputs[key] for key in _BINDINGS - {"journal_id"}}}


def grant_template(study: dict, *, fixture: bool, stage: str, grant_id: str,
                   cumulative_cap_micro_usd: int, authorized: bool = False,
                   previous_authority_sha256: str | None = None,
                   review_sha256: str | None = None) -> dict:
    inputs = _inputs(study, fixture)
    binding = _binding({"run_id": digest(inputs), "inputs": inputs})
    return _seal({**binding, "grant_id": grant_id, "stage": stage,
                  "previous_authority_sha256": previous_authority_sha256,
                  "review_sha256": review_sha256, "cumulative_cap_micro_usd": cumulative_cap_micro_usd,
                  "authorized": authorized}, "grant_sha256")


def _grant_shape(grant: Any, manifest: dict) -> None:
    _check_seal(grant, "grant_sha256")
    if (set(grant) != _GRANT_FIELDS or any(grant[key] != value for key, value in _binding(manifest).items())
            or not isinstance(grant["grant_id"], str)
            or re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", grant["grant_id"]) is None
            or grant["stage"] not in ("first", "expansion")
            or type(grant["authorized"]) is not bool
            or grant["authorized"] is manifest["inputs"]["fixture"]
            or type(grant["cumulative_cap_micro_usd"]) is not int
            or grant["cumulative_cap_micro_usd"] <= 0
            or any(grant[key] is not None and not _hash(grant[key]) for key in (
                "previous_authority_sha256", "review_sha256"))):
        raise AuthorityError("grant lacks exact study/source/control/launcher/profile/mode authority")
    ceiling = manifest["inputs"]["budget_policy"][
        "first_stage_max_micro_usd" if grant["stage"] == "first" else "phase_max_micro_usd"]
    if grant["cumulative_cap_micro_usd"] > ceiling:
        raise AuthorityError("grant exceeds the frozen stage/planning ceiling")


def _fixture_mode(grant: Any) -> bool:
    if not isinstance(grant, dict) or not isinstance(grant.get("fixture"), bool):
        raise AuthorityError("grant requires an explicit fixture/live mode")
    return grant["fixture"]


def _base_state(manifest: dict) -> dict:
    return {"run_id": manifest["run_id"], "fixture": manifest["inputs"]["fixture"],
            "status": "ready", "attempts": 0, "spent_micro_usd": 0, "reserved_micro_usd": 0,
            "canary_spent_micro_usd": 0, "canary_reserved_micro_usd": 0,
            "provider_calls": 0, "retries": 0, "results": {}}


def _prefix_sha(state: dict) -> str:
    return digest({key: state[key] for key in (
        "run_id", "fixture", "status", "attempts", "spent_micro_usd", "reserved_micro_usd",
        "canary_spent_micro_usd", "canary_reserved_micro_usd", "provider_calls", "retries", "results")})


def _events(run: Path) -> tuple[list[dict], bytes]:
    """Read one authoritative stream, verifying every byte's chained identity."""
    path = run / "events.jsonl"
    if not path.exists():
        return [], b""
    if path.is_symlink() or path.stat().st_size > 3_000_000_000:
        raise ContractError("release event stream escapes its bounded ordinary-file profile")
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    tail = lines.pop() if lines and not lines[-1].endswith(b"\n") else b""
    events, parent = [], None
    for index, line in enumerate(lines, 1):
        try:
            event = json.loads(line.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError) as exc:
            raise ContractError("release event stream contains malformed non-tail data") from exc
        _check_seal(event, "event_sha256")
        if (set(event) != {"index", "kind", "record", "previous_event_sha256", "event_sha256"}
                or type(event["index"]) is not int or event["index"] != index
                or event["previous_event_sha256"] != parent
                or event["kind"] not in ("intent", "result") or not isinstance(event["record"], dict)
                or event["kind"] != ("intent" if index % 2 else "result")):
            raise ContractError("release event order or hash chain differs")
        events.append(event)
        parent = event["event_sha256"]
    return events, tail


def _append_event(run: Path, kind: str, record: dict, events: list[dict]) -> None:
    event = _seal({"index": len(events) + 1, "kind": kind, "record": record,
                   "previous_event_sha256": events[-1]["event_sha256"] if events else None}, "event_sha256")
    raw = (json.dumps(event, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > 2_000_000:
        raise ContractError("single release event exceeds the artifact profile")
    path = run / "events.jsonl"
    if path.is_symlink():
        raise ContractError("release event stream cannot be a link")
    with path.open("ab") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(run, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    events.append(event)


def _with_authority(state: dict, grants: list[dict], review: dict | None) -> dict:
    active = grants[-1] if grants else None
    first = [record for record in grants if record["grant"]["stage"] == "first"]
    return state | {"authority": active["grant"] if active else None,
                    "authority_sha256": active["authority_sha256"] if active else None,
                    "authority_stage": active["grant"]["stage"] if active else None,
                    "authorized_cap_micro_usd": active["grant"]["cumulative_cap_micro_usd"] if active else 0,
                    "first_stage_cap_micro_usd": first[-1]["grant"]["cumulative_cap_micro_usd"] if first else 0,
                    "review_sha256": review["review_sha256"] if review else None}


def _check_new_grant(grant: dict, manifest: dict, state: dict, grants: list[dict],
                     review: dict | None) -> None:
    _grant_shape(grant, manifest)
    if state["status"] != "ready":
        raise LiabilityError("unresolved delivery/usage liability blocks further authority")
    if any(record["grant"]["grant_id"] == grant["grant_id"] for record in grants):
        raise AuthorityError("grant ID is already bound to a different authority record")
    active = grants[-1] if grants else None
    if grant["previous_authority_sha256"] != (active["authority_sha256"] if active else None):
        raise AuthorityError("grant is out of order or lacks its exact authority predecessor")
    if active is None:
        if grant["stage"] != "first" or state["attempts"] or grant["review_sha256"] is not None:
            raise AuthorityError("first authority must precede all requests and permit only the first block")
    elif grant["stage"] == "first":
        if (active["grant"]["stage"] != "first" or review is not None or grant["review_sha256"] is not None
                or grant["cumulative_cap_micro_usd"] <= active["grant"]["cumulative_cap_micro_usd"]):
            raise AuthorityError("replay-as-new grant cannot add credit or reopen a reviewed first block")
    else:
        if review is None or grant["review_sha256"] != review["review_sha256"]:
            raise AuthorityError("expansion requires the exact successful first-block review")
        if grant["cumulative_cap_micro_usd"] < active["grant"]["cumulative_cap_micro_usd"]:
            raise AuthorityError("cumulative authority cannot discard earlier authorized funds")
        if (active["grant"]["stage"] == "expansion"
                and grant["cumulative_cap_micro_usd"] == active["grant"]["cumulative_cap_micro_usd"]):
            raise AuthorityError("replay-as-new expansion grant cannot add credit")
    if grant["cumulative_cap_micro_usd"] < state["spent_micro_usd"] + state["reserved_micro_usd"]:
        raise AuthorityError("grant does not cover earlier cumulative spend and liability")


def _first_evidence(run: Path, study: dict, state: dict) -> dict:
    from .phase2 import PROJECT
    from .phase2_analysis import validate_analysis_evidence
    from .phase2_coverage import slot_coverage
    from .phase2_native import NativeAssessment

    first = [row for row in study["worklist"]["outputs"] if row["checkpoint"] == "canary"]
    portfolios, assessments, hashes = [], [], {}
    for row in first:
        for field in ("portfolio_path", "assessment_path"):
            path = run.parent / row[field]
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise ContractError("review evidence cannot traverse links")
            try:
                hashes[row[field]] = file_hash(path)
            except OSError as exc:
                raise AuthorityError("first-block review requires every saved portfolio and assessment") from exc
        portfolio = read_json(run.parent / row["portfolio_path"])
        portfolios.append(portfolio)
        assessments.append(read_json(run.parent / row["assessment_path"]) | {
            "method": row["method"], "repeat": row["repeat"], "order_id": row["order_id"],
            "study_sha256": study["study_sha256"]})
    if (len(first) != 3 or state["status"] != "ready" or state["reserved_micro_usd"] != 0
            or any(study["worklist"]["slots"][slot]["checkpoint"] != "canary" for slot in state["results"])
            or any(row.get("status") != "scored" for row in assessments)):
        raise AuthorityError("first-block review requires three scored orders and reconciled first-only accounting")
    native = NativeAssessment(PROJECT / ".upstream/novelty-bench")
    validated = validate_analysis_evidence(study, assessments, portfolios, state, native,
                                          fixture=state["fixture"])
    coverage = slot_coverage(study, state["results"], portfolios, assessments)
    first_slots = {slot for slot, row in study["worklist"]["slots"].items() if row["checkpoint"] == "canary"}
    accepted = {"ok", "refused", "empty", "truncated", "not_needed_nonhead"}
    if (any(coverage["slots"][slot] not in accepted for slot in first_slots)
            or any(coverage["orders"][row["order_id"]] != "scored" for row in first)
            or validated["unresolved_liabilities"]):
        raise AuthorityError("incomplete composed first-block coverage cannot unlock expansion")
    return {"files": hashes, "coverage_sha256": digest(coverage),
            "native_evidence_sha256": digest(validated)}


def _review_body(run: Path, study: dict, state: dict, *, review_id: str, cutoff: str) -> dict:
    from .phase2_decisions import _time

    _time(cutoff)
    if not isinstance(review_id, str) or re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", review_id) is None:
        raise AuthorityError("review requires an explicit operator evidence reference")
    manifest = _manifest(run)
    return _seal({**_binding(manifest), "review_id": review_id, "cutoff": cutoff, "approved": True,
                  "prefix_attempts": state["attempts"], "prefix_sha256": _prefix_sha(state),
                  "first_evidence": _first_evidence(run, study, state)}, "review_sha256")


def _replay(run: Path, *, study: dict | None = None) -> tuple[dict, list[dict], dict | None]:
    manifest = _manifest(run)
    if study is None:
        study_path = run / "study.json"
        study = read_json(study_path)
    _study(study)
    if manifest["inputs"] != _inputs(study, manifest["inputs"]["fixture"]):
        raise ContractError("journal differs from its frozen execution study")
    if any(path.is_symlink() for path in run.rglob("*")):
        raise ContractError("journal contains a linked record")
    state = _base_state(manifest)
    grants: list[dict] = []
    review = read_json(run / "reviews/first.json") if (run / "reviews/first.json").exists() else None
    if review is not None:
        _check_seal(review, "review_sha256")
        fields = _BINDINGS | {"review_id", "cutoff", "approved", "prefix_attempts", "prefix_sha256",
                              "first_evidence", "review_sha256"}
        if (set(review) != fields or review["approved"] is not True
                or type(review["prefix_attempts"]) is not int or not 0 <= review["prefix_attempts"] <= 55
                or not _hash(review["prefix_sha256"])
                or any(review.get(key) != value for key, value in _binding(manifest).items())):
            raise AuthorityError("first review belongs to another phase")
    grant_paths = sorted((run / "authority").glob("*.grant.json"))
    records = []
    for index, path in enumerate(grant_paths, 1):
        if path.name != f"{index:04}.grant.json":
            raise AuthorityError("authority sequence has a gap")
        record = read_json(path)
        _check_seal(record, "authority_sha256")
        if set(record) != {"grant", "attempts_at_grant", "prefix_sha256", "authority_sha256"}:
            raise AuthorityError("authority record fields differ")
        if (type(record["attempts_at_grant"]) is not int or not 0 <= record["attempts_at_grant"] <= 1320
                or not _hash(record["prefix_sha256"])):
            raise AuthorityError("authority record prefix is invalid")
        records.append(record)
    events, tail = _events(run)
    if tail and (not events or events[-1]["kind"] != "intent"):
        raise ContractError("truncated intent tail: halt without repair or another attempt")
    intents = [event["record"] for event in events if event["kind"] == "intent"]
    cursor = 0
    review_verified = False
    last_result_sha = None
    for index in range(len(intents) + 1):
        if review is not None and review.get("prefix_attempts") == index:
            expected = _review_body(run, study, state, review_id=review["review_id"], cutoff=review["cutoff"])
            if review != expected:
                raise AuthorityError("first review differs from exact saved native/accounting evidence")
            review_verified = True
        while cursor < len(records) and records[cursor].get("attempts_at_grant") == index:
            record = records[cursor]
            if record["prefix_sha256"] != _prefix_sha(state):
                raise AuthorityError("authority prefix does not preserve earlier cumulative accounting")
            _check_new_grant(record["grant"], manifest, state, grants, review if review_verified else None)
            grants.append(record)
            cursor += 1
        if index == len(intents):
            break
        if state["status"] != "ready":
            raise ContractError("request sequence has a gap or continued after unknown liability")
        intent = intents[index]
        slot = intent.get("slot_id")
        slots = manifest["inputs"]["slots"]
        if (slot not in slots or slot in state["results"] or intent.get("role") != slots[slot]["role"]):
            raise ContractError("journal contains a repeated or undeclared slot")
        role = intent["role"]
        _validate_request(role, intent.get("request"))
        if not am1.admitted(role, intent["request"]):
            raise ContractError("saved request exceeded its unchanged payload cap")
        active = grants[-1] if grants else None
        expected_intent = _intent(manifest, slot, role, intent["request"], index + 1) | {
            "authority_sha256": active["authority_sha256"] if active else None,
            "previous_result_sha256": last_result_sha}
        if intent != expected_intent:
            raise ContractError("request intent or authority/prefix identity changed")
        _admit_authority(state, grants, review if review_verified else None, slots[slot]["checkpoint"],
                         intent["reservation_micro_usd"])
        event_index = index * 2 + 1
        result = (events[event_index]["record"] if event_index < len(events) else
                  _result(intent, None, unknown=True, control_policy=am1.CONTROL_POLICY))
        if result != _result(intent, result.get("response"), unknown=result.get("response") is None,
                             control_policy=am1.CONTROL_POLICY):
            raise ContractError("saved response/usage/accounting identity changed")
        state["results"][slot] = result
        state["attempts"] += 1
        state["spent_micro_usd"] += result["spent_micro_usd"] or 0
        state["reserved_micro_usd"] += result["reserved_micro_usd"]
        if slots[slot]["checkpoint"] == "canary":
            state["canary_spent_micro_usd"] += result["spent_micro_usd"] or 0
            state["canary_reserved_micro_usd"] += result["reserved_micro_usd"]
        state["status"] = "blocked-unknown" if result["status"] == "unknown" else "ready"
        state["provider_calls"] = 0 if state["fixture"] else state["attempts"]
        last_result_sha = digest(result)
    if cursor != len(records) or review is not None and not review_verified:
        raise AuthorityError("authority/review references an unavailable future journal prefix")
    final = _with_authority(state, grants, review)
    final["journal_integrity"] = "truncated-result-tail" if tail else "complete-records"
    return final, grants, review


def replay_journal(run: Path) -> dict:
    return _replay(run)[0]


def _admit_authority(state: dict, grants: list[dict], review: dict | None,
                     checkpoint: str, amount: int) -> None:
    if state["status"] != "ready":
        raise LiabilityError("unresolved delivery/usage liability; do not redispatch")
    if not grants:
        raise AuthorityError("no applicable first-stage spending authority")
    active = grants[-1]["grant"]
    if checkpoint == "expansion" and (active["stage"] != "expansion" or review is None):
        raise AuthorityError("expansion requires saved successful review and cumulative authority")
    if checkpoint == "canary" and review is not None:
        raise AuthorityError("the reviewed first block cannot acquire another paid attempt")
    if state["spent_micro_usd"] + state["reserved_micro_usd"] + amount > active["cumulative_cap_micro_usd"]:
        raise BudgetStopError("cumulative authorized reservation ceiling reached")


def validate_grant(run: Path, study: dict, grant: dict) -> dict:
    fixture = _fixture_mode(grant)
    initialize_journal(run, study, fixture=fixture)
    with writer_lock(run):
        return validate_grant_unlocked(run, study, grant)


def publish_grant(run: Path, study: dict, grant: dict) -> dict:
    # Initialize before locking, then revalidate the complete prefix under lock.
    initialize_journal(run, study, fixture=_fixture_mode(grant))
    _publish(Path(run) / "study.json", study)
    with writer_lock(run):
        record = validate_grant_unlocked(run, study, grant)
        existing = sorted((run / "authority").glob("*.grant.json"))
        for path in existing:
            if read_json(path) == record:
                return record
        _publish(run / "authority" / f"{len(existing) + 1:04}.grant.json", record)
        return record


def validate_grant_unlocked(run: Path, study: dict, grant: dict) -> dict:
    manifest = _manifest(run)
    if manifest["inputs"] != _inputs(study, _fixture_mode(grant)):
        raise AuthorityError("grant study differs from the immutable phase journal")
    state, grants, review = _replay(run, study=study)
    _grant_shape(grant, manifest)
    for record in grants:
        if record["grant"] == grant:
            return record
        if record["grant"]["grant_id"] == grant["grant_id"]:
            raise AuthorityError("grant ID conflicts with a previously recorded grant")
    _check_new_grant(grant, manifest, state, grants, review)
    return _seal({"grant": copy.deepcopy(grant), "attempts_at_grant": state["attempts"],
                  "prefix_sha256": _prefix_sha(state)}, "authority_sha256")


def make_first_review(run: Path, study: dict, *, review_id: str, cutoff: str,
                       approved: bool = True) -> dict:
    if approved is not True:
        raise AuthorityError("a declined review cannot unlock expansion")
    state, grants, review = _replay(run, study=study)
    if review is not None:
        if review["review_id"] != review_id or review["cutoff"] != cutoff:
            raise AuthorityError("the first review is already immutable")
        return review
    if not grants or grants[-1]["grant"]["stage"] != "first":
        raise AuthorityError("review requires the first-stage authority and no expansion")
    return _review_body(run, study, state, review_id=review_id, cutoff=cutoff)


def publish_review(run: Path, study: dict, review: dict) -> dict:
    if not isinstance(review, dict):
        raise AuthorityError("review must be an explicit object")
    review_id, cutoff, approved = review.get("review_id"), review.get("cutoff"), review.get("approved")
    if not isinstance(review_id, str) or not isinstance(cutoff, str) or not isinstance(approved, bool):
        raise AuthorityError("review lacks explicit operator reference, cutoff or approval")
    with writer_lock(run):
        expected = make_first_review(run, study, review_id=review_id, cutoff=cutoff, approved=approved)
        if review != expected:
            raise AuthorityError("review does not match actual saved first-block evidence")
        _publish(run / "reviews/first.json", review)
        return review


class ReleaseDispatcher:
    """Complete frozen worklist; stage authority is append-only and cumulative."""

    def __init__(self, run: Path, *, study: dict, transport: Any):
        self.run, self.study, self.transport = Path(run), copy.deepcopy(study), transport
        self.manifest = initialize_journal(self.run, study, fixture=transport.fixture)
        _publish(self.run / "study.json", study)
        self.state()

    def state(self) -> dict:
        return replay_journal(self.run)

    def require_stage(self, stage: str) -> dict:
        if stage not in ("first", "expansion"):
            raise AuthorityError("unknown release execution stage")
        state = self.state()
        if state["status"] != "ready":
            raise LiabilityError("unresolved phase liability blocks execution")
        if state["authority"] is None:
            raise AuthorityError("no applicable release spending authority")
        if stage == "expansion" and (state["authority_stage"] != "expansion" or state["review_sha256"] is None):
            raise AuthorityError("expansion requires saved successful review and cumulative authority")
        return state

    def dispatch(self, slot_id: str, role: str, request: dict, *, checkpoint: str = "canary") -> dict:
        request = copy.deepcopy(request)
        slots = self.manifest["inputs"]["slots"]
        if slot_id not in slots or slots[slot_id] != {"role": role, "checkpoint": checkpoint}:
            raise ContractError("request is not a declared full-study role/checkpoint slot")
        _validate_request(role, request)
        if not am1.admitted(role, request):
            raise ContractError("request exceeds the unchanged AM-1 payload safeguard")
        if not self.transport.fixture and (not isinstance(self.transport, DirectSDKTransport)
                                          or self.transport.control_policy != am1.CONTROL_POLICY):
            raise AuthorityError("live release requires the exact pinned direct SDK transport")
        with writer_lock(self.run):
            state, grants, review = _replay(self.run, study=self.study)
            if slot_id in state["results"]:
                result = state["results"][slot_id]
                if result["request_sha256"] != digest(request):
                    raise ContractError("saved slot request identity changed")
                return result
            amount = am1.reservation(role)
            _admit_authority(state, grants, review, checkpoint, amount)
            index = state["attempts"] + 1
            previous = next(reversed(state["results"].values()), None)
            intent = _intent(self.manifest, slot_id, role, request, index) | {
                "authority_sha256": grants[-1]["authority_sha256"],
                "previous_result_sha256": digest(previous) if previous is not None else None}
            events, tail = _events(self.run)
            if tail:
                raise LiabilityError("truncated journal tail remains unresolved; do not append")
            _append_event(self.run, "intent", intent, events)
            try:
                response = copy.deepcopy(self.transport.create(role, copy.deepcopy(request)))
                result = _result(intent, response, control_policy=am1.CONTROL_POLICY)
                digest(result)
                if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 1_900_000:
                    raise ContractError("provider result exceeds the bounded artifact profile")
            except Exception:
                result = _result(intent, None, unknown=True, control_policy=am1.CONTROL_POLICY)
            _append_event(self.run, "result", result, events)
            return result
