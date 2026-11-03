"""Finite RP2 delivery checks and authenticated saved-RP1 diagnostic, never approval."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import traceback
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest

from .support import BASE, ROOT, read, require, safe

INVENTORY = ROOT / "evidence/phase3a-readiness-recovery-v1/acceptance-cases.json"
INVENTORY_SHA = "39e74492adeb00669c5ce18fad03dbf6211b2698685794d18d70c028d0816fb0"
CLARIFICATION = ROOT / "evidence/phase3a-readiness-recovery-v1/delivery-clarification-v1.json"
CLARIFICATION_SHA = "a5904c25fe8f10a5c9e0d26c5221c7218708f28922774a9076e862cbf6111e30"
SUPPLEMENT = ROOT / "evidence/phase3a-readiness-recovery-v1/delivery-supplemental-cases-v1.json"
SUPPLEMENT_SHA = "8d8cf1cb63eafa8f3b149e3b01c7718794c80ffc43ea56d7a607611eb1fb57a1"
AM1 = ROOT / "evidence/phase3a-readiness-recovery-v1/am1-acceptance-supplement-v1.json"
AM1_SHA = "e2f7f5121a1c5e787d8fbb58b55a6b559353e08740cc087f0b8c81e0281a940b"
AM1_AUTH = ROOT / "evidence/phase3a-readiness-recovery-v1/am1-authorization-v1.json"
AM1_AUTH_SHA = "6a3231e8cd5036df0655f6432ca0a52b3db967ccb3aafa0db0710883b1d88a68"
RP1_STUDY = "e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca"
RP1_SOURCE = "64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a"
REPORTS = ("rows.json", "coverage.json", "analysis.json", "summary.json", "accounting.json",
           "protocol.json", "readiness.json", "PHASE3A_REPORT.md")


def _hash(path: Path) -> str:
    return hashlib.sha256(safe(path).read_bytes()).hexdigest()


def _save(path: Path, value: dict) -> None:
    with safe(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def _blocks(counts: dict) -> ExitStack:
    stack = ExitStack()
    def denied(target):
        def fail(*args, **kwargs):
            counts["attempts"].append(target)
            raise ContractError("readiness diagnostic attempted external activity")
        return fail
    for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                   "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                   "socket.getaddrinfo", "subprocess.Popen", "subprocess.run"):
        stack.enter_context(patch(target, side_effect=denied(target)))
    return stack


def _saved(inventory: dict, output: Path) -> dict:
    from followups.phase3a_rc1_pilot_v1 import accounting as old_accounting
    from followups.phase3a_rc1_pilot_v1 import evidence as old_evidence
    from followups.phase3a_rc1_pilot_v1 import support as old_support

    from .evidence import diagnose_saved_rp1, diagnose_saved_rp1_original, verify_readiness

    selected = inventory["saved_input_sha256"]
    before = {name: _hash(ROOT / name) for name in selected}
    require(before == selected, "frozen saved RP1 input differs")
    old_source = old_support.source_identity()
    require(old_source["sha256"] == RP1_SOURCE and len(old_source["files"]) == 419,
            "historical RP1 source identity differs")
    study_path = old_support.BASE / "verification-v5/release/study.json"
    grant_path = old_support.BASE / "verification-v5/release/live-grant.json"
    require(old_support.file_hash(study_path) == "4a352964da4a7386075446b13e4b7790ed1f88b6f196ba66fc76cd52a53874e9"
            and old_support.file_hash(grant_path) == "f34728687d4ea841a4dcc249476c72cbb55760b81dc0fb2c2096a79bc6547923",
            "saved raw study/grant bytes differ")
    study, grant = old_support.read(study_path), old_support.read(grant_path)
    require(study["study_sha256"] == RP1_STUDY and study["source_sha256"] == RP1_SOURCE,
            "historical study differs")
    require(study["source"] == old_source and study["runtime"] == old_support.runtime_identity()
            and grant["fixture"] is False
            and grant["grant_sha256"] == digest({k: v for k, v in grant.items() if k != "grant_sha256"})
            and all(grant[k] == study[k] for k in ("study_sha256", "source_sha256", "runtime_sha256",
                                                   "policy_sha256", "launcher_sha256")),
            "saved source/runtime/grant differs")
    old_accounting.validate_authority(RP1_STUDY, grant["authority"], False,
        {k: study[k] for k in ("source_sha256", "policy_sha256", "launcher_sha256")})
    run = old_support.NATIVE / RP1_STUDY / "live"
    journal = old_support.BASE / RP1_STUDY / "live/journal"
    state = old_accounting.replay(journal)
    branch = old_support.read(run / "branches/p3a-01-adaptive.json")
    reports_before = {name: old_support.file_hash(run / "reports/final" / name) for name in REPORTS}
    result: dict = {"diagnostic_only": True, "approval_published": False,
                    "original_readiness_passed": False, "scientific_eligibility": False}
    try:
        old_evidence.verify_readiness(study, run, state, branch, False)
    except ContractError as error:
        result["original_failure"] = {"type": type(error).__name__, "message": str(error)}
    require(result.get("original_failure", {}).get("message") == "fixture read history conflicts",
            "original RP1 failure no longer reproduces")
    try:
        verify_readiness(study, run, state, branch, False)
    except ContractError:
        result["old_profile_rejected_by_live_default"] = True
    require(result.get("old_profile_rejected_by_live_default") is True,
            "live RP2 verifier accepted old-profile evidence")
    try:
        result["prospective"] = diagnose_saved_rp1(study, run, state, branch)
        proof = result["prospective"]["proof"]
        require(result["prospective"]["full_strict_predicates_passed"] is True
                and proof["readiness_adaptive_requests"] == 83 and len(proof["sessions"]) == 3
                and len(proof["scoped_transport_audit_sha256"]) == 83
                and len(proof["conversation_admission_clock_sha256"]) == 3,
                "remaining strict saved readiness predicates were not all reached")
        result["full_strict_predicates_passed"] = True
    except Exception as error:
        result["full_strict_predicates_passed"] = False
        result["prospective_failure"] = {"type": type(error).__name__, "message": str(error),
            "frames": [{"file": f.filename, "line": f.lineno, "function": f.name, "source": f.line}
                       for f in traceback.extract_tb(error.__traceback__)]}
    result["original_input_proof"] = diagnose_saved_rp1_original(study, run, state)
    missing = result["original_input_proof"]["missing_declared_views_with_no_successful_read"]
    expected_missing = [f"C1_EVIDENCE/14-{i:03}.json" for i in range(8)]
    result["all_eight_DOM_views_absent"] = missing == expected_missing
    expected_failure = ("required complete target content is absent, stale or mismatched: "
                        + result["original_input_proof"]["decision_cwd"]
                        + "/context/C1_EVIDENCE/14-000.json")
    result["faithful_missing_views_rejection"] = (result.get("prospective_failure", {}).get("type") == "ContractError"
        and result["prospective_failure"]["message"] == expected_failure and result["all_eight_DOM_views_absent"] is True)
    require(old_source == old_support.source_identity(), "historical source changed during diagnostic")
    require(before == {name: _hash(ROOT / name) for name in selected}, "saved RP1 inputs changed")
    require(reports_before == {name: old_support.file_hash(run / "reports/final" / name) for name in REPORTS},
            "saved RP1 reports changed")
    result.update(historical_source_files=419, historical_source_unchanged=True,
                  input_sha256=before, report_sha256=reports_before, inputs_and_reports_unchanged=True)
    _save(output / "saved-rp1.json", result)
    return result


def run(output: Path, study: dict | None = None) -> dict:
    """Gate hook: new output only; root verifier supplies current bindings separately."""
    output = safe(output, roots=(BASE, ROOT / "runs/phase3a-readiness-recovery-v1"))
    require(output not in (BASE, ROOT / "runs/phase3a-readiness-recovery-v1") and not output.exists(),
            "readiness correction requires a fresh output child")
    output.mkdir(parents=True, exist_ok=False)
    require(_hash(INVENTORY) == INVENTORY_SHA, "finite readiness inventory differs")
    require(_hash(CLARIFICATION) == CLARIFICATION_SHA and _hash(SUPPLEMENT) == SUPPLEMENT_SHA,
            "frozen delivery clarification/supplement differs")
    require(_hash(AM1) == AM1_SHA and _hash(AM1_AUTH) == AM1_AUTH_SHA, "frozen AM1 authority/supplement differs")
    inventory = read(INVENTORY)
    expected = {row["id"]: row for row in inventory["readiness_cases"]}
    require(len(expected) == 20, "finite readiness case count differs")
    supplemental = read(SUPPLEMENT)
    require(supplemental["original_inventory_unchanged_sha256"] == INVENTORY_SHA
            and supplemental["clarification_file_sha256"] == CLARIFICATION_SHA,
            "supplement is not bound to the original authority")
    extra = {row["id"]: row for row in supplemental["cases"]}
    require(len(extra) == 15 and not set(expected) & set(extra), "supplemental case count/identity differs")
    expected.update(extra)
    amendment = read(AM1)
    require(amendment["authority_sha256"] == AM1_AUTH_SHA and amendment["original_inventory_sha256"] == INVENTORY_SHA
            and amendment["source_view_supplement_sha256"] == SUPPLEMENT_SHA, "AM1 prior authority binding differs")
    require({r["id"] for r in amendment["expectation_overrides"]} == {"R01", "R17"}, "AM1 changed another expectation")
    for row in amendment["expectation_overrides"]:
        expected[row["id"]] = row
    require({r["id"] for r in amendment["additional_cases"]} == {"H01", "H02", "H03"}, "AM1 HI scope differs")
    expected.update({row["id"]: row for row in amendment["additional_cases"]})
    require({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"},
            "readiness regression requires actual network-none containment")
    counts: dict = {"attempts": [], "process_audit_attempts": []}
    def audit(event, args):
        if event in {"subprocess.Popen", "os.system"}:
            counts["process_audit_attempts"].append(event)
            raise ContractError("readiness regression cannot start a process")
    sys.addaudithook(audit)
    cases = []
    log = io.StringIO()
    saved: dict = {}
    failure = None
    with _blocks(counts):
        from .test_delivery import CASE_IDS, DeliveryCases
        from .test_readiness import CASE_IDS as EXTRA_IDS
        from .test_readiness import OriginalInputCases
        require(set(CASE_IDS.values()) | set(EXTRA_IDS.values()) | {"R01", "R16", "R17", "R18", "D01", "H01", "H02", "H03"} == set(expected),
                "finite readiness case coverage differs")
        for suite, mapping in ((DeliveryCases, CASE_IDS), (OriginalInputCases, EXTRA_IDS)):
            for method, case in mapping.items():
                tested = unittest.TextTestRunner(stream=log, verbosity=2).run(suite(method))
                cases.append({"id": case, "expected": expected[case]["expected"], "passed": tested.wasSuccessful(),
                              "method": method, "tests": tested.testsRun})
        try:
            saved = _saved(inventory, output)
        except Exception as error:
            failure = {"type": type(error).__name__, "message": str(error),
                       "frames": [{"file": f.filename, "line": f.lineno, "function": f.name, "source": f.line}
                                  for f in traceback.extract_tb(error.__traceback__)]}
        if saved.get("prospective_failure") is not None and saved.get("faithful_missing_views_rejection") is not True:
            failure = saved["prospective_failure"]
        saved_cases = {"R01": saved.get("faithful_missing_views_rejection") is True,
                       "R16": saved.get("original_failure", {}).get("message") == "fixture read history conflicts",
                       "R17": saved.get("faithful_missing_views_rejection") is True and saved.get("all_eight_DOM_views_absent") is True,
                       "R18": saved.get("inputs_and_reports_unchanged") is True}
        original = saved.get("original_input_proof", {})
        saved_cases["D01"] = original.get("passed") is True and original.get("scope") == "original_input_only"
        for case, passed in saved_cases.items():
            cases.append({"id": case, "expected": expected[case]["expected"], "passed": passed})
        from .hi_qualification import qualify_hi
        try:
            hi = qualify_hi()
        except Exception as error:
            hi = {"H01": False, "H02": False, "H03": False, "diagnostic_only": True,
                  "approval_published": False, "provider_calls": 0,
                  "failure": {"type": type(error).__name__, "message": str(error),
                      "frames": [{"file": f.filename, "line": f.lineno, "function": f.name, "source": f.line}
                                 for f in traceback.extract_tb(error.__traceback__)]}}
            failure = hi["failure"]
        _save(output / "hi-positive.json", hi)
        for case in ("H01", "H02", "H03"):
            cases.append({"id": case, "expected": expected[case]["expected"], "passed": hi[case] is True})
    with safe(output / "tests.log").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(log.getvalue())
    passed = len(cases) == 38 and all(case["passed"] for case in cases) and not any(counts.values())
    report = {"kind": "phase3a-rp2-readiness-correction-am1-v1", "passed": passed,
        "case_count": len(cases), "case_results": sorted(cases, key=lambda row: row["id"]),
        "inventory_sha256": INVENTORY_SHA, "saved_full_readiness_passed": saved.get("full_strict_predicates_passed") is True,
        "clarification_sha256": CLARIFICATION_SHA, "supplemental_inventory_sha256": SUPPLEMENT_SHA,
        "original_readiness_case_count": 20, "supplemental_case_count": 15,
        "am1_sha256": AM1_SHA, "am1_authority_sha256": AM1_AUTH_SHA, "am1_additional_case_count": 3,
        "saved_RP1_faithful_negative_passed": saved.get("faithful_missing_views_rejection") is True,
        "saved_HI76_full_strict_positive_passed": hi.get("H01") is True,
        "hi_case_file_sha256": _hash(output / "hi-positive.json"),
        "diagnostic_only": True, "historical_approval_published": False, "failure": failure,
        "external_activity_counters": counts, "provider_calls": 0,
        "source_file_sha256": {name: _hash(ROOT / "followups/phase3a_readiness_recovery_v1" / name)
            for name in ("delivery.py", "evidence.py", "test_delivery.py", "test_readiness.py", "hi_qualification.py", "readiness_regression.py")}}
    if study is not None:
        report.update({k: study[k] for k in ("study_sha256", "source_sha256", "runtime_sha256",
                                           "policy_sha256", "launcher_sha256")})
    if saved:
        report["saved_case_file_sha256"] = _hash(output / "saved-rp1.json")
        report["saved_case_path"] = str(output / "saved-rp1.json")
    _save(output / "result.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({k: result[k] for k in ("passed", "case_count", "failure", "provider_calls")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
