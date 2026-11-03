"""Bounded AM1 HI76 inputs. Preparation imports only the Python standard library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "runs/phase3a-h1-integrated-v1/"
STUDY = "a233fbc5ed3fedaa21e6b364ecfbfdd15496e25c005897067eb2cc7aed90d28a"
SOURCE = "2440535e5274c106a44efb28cf9533308b7dbea8fd8768649a089145cbc150a3"
SUPPLEMENT = "evidence/phase3a-readiness-recovery-v1/am1-acceptance-supplement-v1.json"
SUPPLEMENT_SHA = "e2f7f5121a1c5e787d8fbb58b55a6b559353e08740cc087f0b8c81e0281a940b"
AUTHORITY = "evidence/phase3a-readiness-recovery-v1/am1-authorization-v1.json"
AUTHORITY_SHA = "6a3231e8cd5036df0655f6432ca0a52b3db967ccb3aafa0db0710883b1d88a68"
CLOSED = "evidence/phase3a-h1-integrated-v1/live-outcome-v1.manifest.json"
CLOSED_SHA = "e2ce7e6f38a19e499dc43f8d407f0a1261bae296a01489a740bb8a634d5519bc"
CANDIDATE = "runs/phase3a-readiness-recovery-v1/reviewer/hi-positive-candidate-review-v1.json"
RETENTION = "verification-v4/retained-live-transport-audit/v1/map.json"
REPORTS = ("rows.json", "coverage.json", "analysis.json", "summary.json", "accounting.json",
           "protocol.json", "readiness.json", "PHASE3A_REPORT.md")
JOURNAL = STUDY + "/live/journal/"
RUN = "native/" + STUDY + "/live/"
REVIEW = RUN + "readiness-review.json"
STUDY_FILE = "verification-v4/release/study.json"


def _require(value: Any, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _lexical(name: str) -> PurePosixPath:
    rel = PurePosixPath(name)
    _require(rel.parts and not rel.is_absolute() and ".." not in rel.parts and ":" not in name and "\\" not in name
             and not any(p.casefold() in {".env", ".writer.lock", "credential-binding.json", "auth.json", "credentials.json"}
                         or "stdout" in p.casefold() or "stderr" in p.casefold() for p in rel.parts), "private/unsafe HI input")
    return rel


def _path(root: Path, name: str) -> Path:
    rel = _lexical(name)
    current = root
    for part in rel.parts:
        current /= part
        _require(not current.is_symlink() and not (hasattr(current, "is_junction") and current.is_junction()), "linked HI input")
    return current


def _json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate HI input JSON key")
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite HI input")))
    _require(type(value) is dict, "HI input must be an object")
    return value


def _authenticated(root: Path, name: str, expected: str) -> bytes:
    data = _path(root, name).read_bytes()
    _require(_sha(data) == expected, "HI input hash differs: " + name)
    return data


def _plan(supplement: dict, record: dict, closed: dict, retained: dict) -> dict[str, dict]:
    candidate = supplement["hi_candidate"]
    members = closed["member_sha256"]
    plan: dict[str, dict] = {}
    def add(relative: str, role: str, expected: str | None = None) -> None:
        origin = PREFIX + relative
        _lexical(origin)
        actual = members[origin]
        _require(expected is None or expected == actual, "HI closed member binding differs")
        plan[relative] = {"origin": origin, "sha256": actual, "role": role}
    for origin, expected in candidate["known_input_sha256"].items():
        _require(origin.startswith(PREFIX), "HI fixed metadata escaped its namespace")
        add(origin.removeprefix(PREFIX), "source_or_historical_metadata", expected)
    add(JOURNAL + "manifest.json", "readiness_journal_manifest", candidate["journal_manifest_sha256"])
    plan[JOURNAL + "events.jsonl"] = {"origin": PREFIX + JOURNAL + "events.jsonl",
        "sha256": candidate["journal_prefix_sha256"], "role": "readiness_prefix_152_lines"}
    add(RUN + "barrier-readiness.json", "readiness_barrier", candidate["readiness_barrier_sha256"])
    for name, expected in record["proof"]["artifact_sha256"].items():
        add(RUN + "search/p3a-01/adaptive/" + name, "readiness_search_evidence", expected)
    for slot, seal in record["proof"]["scoped_transport_audit_sha256"].items():
        filename = _sha(_canonical({"slot_id": slot})) + ".json"
        relative = STUDY + "/live/transport-audit/" + filename
        matches = [row for row in retained["entries"] if row["slot_id"] == slot]
        _require(len(matches) == 1, "HI retained audit identity missing/duplicate")
        row = matches[0]
        _lexical(row["copy"])
        _require(row["original"] == PREFIX + relative
                 and row["file_sha256"] == members[row["copy"]], "HI retained audit copy binding differs")
        plan[relative] = {"origin": row["copy"], "original": row["original"],
                          "sha256": row["file_sha256"], "record_sha256": row["record_sha256"],
                          "audit_seal_sha256": seal, "role": "readiness_scoped_transport_audit"}
    for name in REPORTS:
        add(RUN + "reports/final/" + name, "preservation_sentinel_never_readiness_input")
    _require(len(record["proof"]["scoped_transport_audit_sha256"]) == 76, "HI requires exactly76 audits")
    return plan


def _check_audit(row: dict, data: bytes) -> None:
    if row["role"] == "readiness_scoped_transport_audit":
        audit = _json(data)
        _require(_sha(_canonical(audit)) == row["record_sha256"] and audit["sha256"] == row["audit_seal_sha256"],
                 "HI audit full-record digest/internal seal differ")


def prepare_hi_inputs(target: Path) -> dict:
    """Host-only fresh bounded export; mount target RO at the original HI canonical root."""
    target = Path(target)
    parent = ROOT / "runs/phase3a-readiness-recovery-v1"
    _require(target.is_absolute() and target.is_relative_to(parent) and target != parent,
             "HI input export needs a fresh RP2 child")
    _path(ROOT, target.relative_to(ROOT).as_posix())
    _require(not target.exists(), "HI input export target already exists")
    supplement = _json(_authenticated(ROOT, SUPPLEMENT, SUPPLEMENT_SHA))
    _authenticated(ROOT, AUTHORITY, AUTHORITY_SHA)
    closed_raw = _authenticated(ROOT, CLOSED, CLOSED_SHA)
    candidate_raw = _authenticated(ROOT, CANDIDATE, supplement["hi_candidate"]["candidate_review_sha256"])
    candidate = supplement["hi_candidate"]
    record = _json(_authenticated(ROOT, PREFIX + REVIEW, candidate["readiness_record_sha256"]))
    closed = _json(closed_raw)
    retention_raw = _authenticated(ROOT, PREFIX + RETENTION, closed["member_sha256"][PREFIX + RETENTION])
    plan = _plan(supplement, record, closed, _json(retention_raw))
    target.mkdir(parents=True, exist_ok=False)
    for relative, row in plan.items():
        if row["role"] == "readiness_prefix_152_lines":
            with _path(ROOT, row["origin"]).open("rb") as stream:
                chunks = [stream.readline(8_000_001) for _ in range(152)]
            _require(all(c.endswith(b"\n") and len(c) <= 8_000_000 for c in chunks), "HI prefix line boundary differs")
            data = b"".join(chunks)
            _require(_sha(data) == row["sha256"], "HI exact152-line readiness prefix differs")
        else:
            data = _authenticated(ROOT, row["origin"], row["sha256"])
        _check_audit(row, data)
        path = _path(target, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    for name, data in (("_am1/closed-live-manifest.json", closed_raw), ("_am1/candidate-review.json", candidate_raw),
                       ("_am1/transport-retention-map.json", retention_raw)):
        path = _path(target, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        plan[name] = {"sha256": _sha(data), "role": "authentication_metadata"}
    inventory = {"kind": "phase3a-rp2-am1-HI76-inputs-v1", "files": plan, "study_sha256": STUDY,
                 "source_sha256": SOURCE, "supplement_sha256": SUPPLEMENT_SHA, "provider_calls": 0,
                 "later_full_journal_not_read": True, "journal_prefix_lines": 152,
                 "report_bytes_are_preservation_sentinels_only": True}
    inventory["sha256"] = _sha(_canonical(inventory))
    with (target / "input-inventory.json").open("xb") as stream:
        stream.write(json.dumps(inventory, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n")
    return inventory


def validate_hi_inputs(root: Path) -> dict:
    """Recompute the exact dynamic allowlist from pinned metadata, then every input hash."""
    supplement = _json(_authenticated(ROOT, SUPPLEMENT, SUPPLEMENT_SHA))
    _authenticated(ROOT, AUTHORITY, AUTHORITY_SHA)
    closed = _json(_authenticated(root, "_am1/closed-live-manifest.json", CLOSED_SHA))
    candidate_raw = _authenticated(root, "_am1/candidate-review.json", supplement["hi_candidate"]["candidate_review_sha256"])
    record = _json(_authenticated(root, REVIEW, supplement["hi_candidate"]["readiness_record_sha256"]))
    retention_hash = closed["member_sha256"][PREFIX + RETENTION]
    retention = _json(_authenticated(root, "_am1/transport-retention-map.json", retention_hash))
    expected = _plan(supplement, record, closed, retention)
    expected.update({"_am1/closed-live-manifest.json": {"sha256": CLOSED_SHA, "role": "authentication_metadata"},
                     "_am1/candidate-review.json": {"sha256": _sha(candidate_raw), "role": "authentication_metadata"},
                     "_am1/transport-retention-map.json": {"sha256": retention_hash, "role": "authentication_metadata"}})
    inventory = _json(_path(root, "input-inventory.json").read_bytes())
    _require(inventory["files"] == expected and inventory["sha256"] == _sha(_canonical(
        {k: v for k, v in inventory.items() if k != "sha256"})), "HI exported input inventory differs")
    for name, row in expected.items():
        _check_audit(row, _authenticated(root, name, row["sha256"]))
    return inventory


def qualify_hi() -> dict:
    """Run only inside credential-free network-none H1 with the bounded HI root RO."""
    from buddha2.artifacts import ContractError
    from followups.phase3a_h1_integrated_v1 import accounting as old_accounting

    from .evidence import diagnose_saved_hi, verify_readiness

    root = Path("/results/phase3a-h1-integrated-v1")
    inventory = validate_hi_inputs(root)
    study = _json(_path(root, STUDY_FILE).read_bytes())
    branch = _json(_path(root, RUN + "branches/p3a-01-adaptive.json").read_bytes())
    state = old_accounting.replay(root / JOURNAL)
    _require(state["attempts"] == len(state["intents"]) == len(state["results"]) == 76, "HI prefix coverage differs")
    rejected = False
    try:
        verify_readiness(study, root / RUN, state, branch, False)
    except ContractError:
        rejected = True
    _require(rejected, "live RP2 default accepted the legacy HI profile")
    proof = diagnose_saved_hi(study, root / RUN, state, branch)
    result = proof["proof"]
    _require(result["readiness_adaptive_requests"] == 76 and result["role_counts"] == {
        "answer": 40, "editor": 28, "plan": 4, "rank": 4}
        and [row["lossless_views"] for row in result["sessions"]] == [20, 20, 63]
        and len(result["scoped_transport_audit_sha256"]) == 76
        and len(result["conversation_admission_clock_sha256"]) == 3, "HI strict tail coverage differs")
    _require(validate_hi_inputs(root) == inventory, "HI inputs changed during qualification")
    return {"H01": True, "H02": rejected, "H03": True, "diagnostic_only": True,
            "approval_published": False, "scientific_eligibility": False, "provider_calls": 0,
            "input_inventory_sha256": inventory["sha256"], "input_file_count": len(inventory["files"]),
            "input_files_unchanged": True, "all_eight_report_sentinels_unchanged": True, "proof": proof}
