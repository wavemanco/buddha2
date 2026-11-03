"""Nonauthor acceptance of display-only V2; no native fold, provider or UI execution."""
from __future__ import annotations
import csv
import io
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\arvik\code\research\Buddha2")
sys.path.insert(0, str(ROOT / "runs/phase3a-h1-integrated-v1/verification-v4/reviewer"))
import independent_check as old

EVIDENCE = ROOT / "evidence/inspect-display-v2"
RUN = ROOT / "runs/inspect-display-v2"
IMAGE = "sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d"

def rd(p): return old.read(old.relative(p))
def sh(p): return old.sha(old.relative(p))
def check(v, why): old.check(v, why)
def absent(cid):
    r = subprocess.run(["docker", "inspect", "--format", "{{.Id}} {{.State.Running}}", cid], cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
    check(r.returncode != 0 and "no such object" in r.stderr.lower(), "owned display container remains")

def main():
    study, bindings = old.study_check()
    retained_path = EVIDENCE / "retained-evidence.json"
    retained = rd(retained_path)
    check(retained["provider_calls"] == 0 and len(retained["files"]) == 24, "retained proof inventory differs")
    for name, row in retained["files"].items():
        check(old.public(name) and old.public(row["source"]), "nonpublic retained reference")
        data = old.safe(row["source"]).read_bytes()
        check(sh(EVIDENCE / name) == old.digest(data) == row["file_sha256"] and len(data) == row["bytes"], "retained/source proof differs")
    for name, expected in retained["source_code"].items():
        check(old.sha(name) == expected, "new display code changed after proof")
    check(retained["source_code"]["followups/inspect_display_v2/display.py"] == "7b7f1bfc6ced0ae7d4137ade03e47ae30068bfb1737c9f75fc6f70726ceed963", "unreviewed display source")
    provenance_path = RUN / "inputs-v1/provenance.json"
    provenance = rd(provenance_path)
    check(sh(provenance_path) == "12862b8493de14371b5c1fe15ed8490a261cf8cc3c5af4480c79307a56b49ba4"
          and provenance["source_identities"] == bindings and provenance["scientific_complete"] is False
          and provenance["provider_calls_made_by_derivation"] == 0 and provenance["raw_messages_included"] is False, "foreign or misleading provenance")
    derivation = rd(RUN / "inputs-v1/validation-v1.json")
    check(derivation["passed"] is True and derivation["helper_sha256"] == retained["source_code"]["followups/inspect_display_v2/provenance.py"]
          and derivation["provenance_sha256"] == sh(provenance_path) and len(derivation["negative_checks"]) == 10
          and all(derivation["negative_checks"].values()) and derivation["frozen_functions_patched"] is False,
          "exact provenance derivation/negative proof differs")
    references = {}
    def collect(value):
        if isinstance(value, dict):
            if "path" in value and "file_sha256" in value:
                check(old.public(value["path"]), "private/stream provenance reference")
                check(value["path"] not in references or references[value["path"]] == value["file_sha256"], "conflicting provenance reference")
                references[value["path"]] = value["file_sha256"]
            for item in value.values(): collect(item)
        elif isinstance(value, list):
            for item in value: collect(item)
    collect(provenance)
    check(all(old.sha(name) == expected for name, expected in references.items()), "source provenance reference changed")
    rows = provenance["requests"]
    expected_counts = {"answer": 140, "editor": 54, "fixed_selector": 1, "group": 3, "plan": 14, "quality": 30, "rank": 14}
    check(len(rows) == len({r["slot_id"] for r in rows}) == provenance["attempts"] == 256
          and dict(Counter(r["role"] for r in rows)) == expected_counts
          and sum(r["spent_micro_usd"] for r in rows) == provenance["spent_micro_usd"] == 7882971
          and sum(r["diagnostic"] for r in rows) == 11, "native counts/cost/diagnostic differ")
    canonical = ROOT / "runs/phase3a-h1-integrated-v1/native" / study["study_sha256"] / "live/reports/final"
    outcome = rd(ROOT / "evidence/phase3a-h1-integrated-v1/live-outcome.json")
    for name, ref in provenance["canonical_files"].items():
        check(sh(canonical / name) == ref["file_sha256"] == outcome["report_sha256"][name], "old canonical report changed")
    protocol = rd(canonical / "protocol.json")
    requests = {r["slot_id"]: r for r in protocol["requests"]}
    for row in rows:
        native = requests[row["slot_id"]]
        audit = old.read(row["source"]["audit"]["path"])
        check(row["declared_config"] == native["requested_parameters"]
              and row["started_at_utc"] == audit["budget"]["started_utc"] and row["finished_at_utc"] == audit["finished_utc"]
              and row["source"]["audit_record_sha256"] == old.digest(old.canonical(audit))
              and row["source"]["result_record_sha256"] == native["result_sha256"], "display request/config/date differs from actual source")
    for label in ("ruff", "mypy", "bandit"):
        item = rd(RUN / "root-statics-v3" / (label + ".json"))
        check(item["exit_code"] == 0 and item["provider_calls"] == 0, "final project statics failed")
    mypy = rd(RUN / "root-statics-v3/mypy.json")
    check("/code/pyproject.toml" in mypy["command"] and "--config-file" in mypy["command"], "actual project type configuration not used")
    source_mounts = {
        "/code/followups/inspect_display_v2/display.py": (ROOT / "followups/inspect_display_v2/display.py", False),
        "/code/followups/inspect_visibility_i1/importer.py": (ROOT / "followups/inspect_visibility_i1/importer.py", False),
        "/code/followups/inspect_visibility_i1/paths.py": (ROOT / "followups/inspect_visibility_i1/paths.py", False),
        "/input/closure.eval": (ROOT / provenance["old_closure_log"]["path"], False),
        "/input/provenance.json": (provenance_path, False)}
    for phase in ("tests-v3", "verification-v2"):
        actual, run = rd(RUN / phase / "actual-container.json"), rd(RUN / phase / "container-run.json")
        expected = {**source_mounts, "/out": (RUN / phase, True)}
        if phase == "tests-v3":
            expected["/code/followups/inspect_display_v2/test_display.py"] = (ROOT / "followups/inspect_display_v2/test_display.py", False)
        check(actual["image"] == IMAGE and actual["network"] == "none" and actual["read_only"] is True
              and {m["Destination"]: (Path(m["Source"]), m["RW"]) for m in actual["mounts"]} == expected,
              "actual display/test isolation/mounts differ")
        check(run["exit_code"] == run["cleanup_exit_code"] == 0 and run["source_and_inputs_unchanged"] is True, "display/test execution or cleanup failed")
        check(all(old.sha(name) == sha for name, sha in run["source_and_input_sha256"].items()), "executed display/test bytes changed")
        absent(actual["id"])
    tests = rd(RUN / "tests-v3/container-run.json")
    executed = re.findall(r"^(test_\w+) \(followups\.inspect_display_v2\.test_display\.DisplayChecks\.\1\) \.\.\. ok$", tests["error_output"], re.MULTILINE)
    check(len(executed) == len(set(executed)) == 7 and "Ran 7 tests" in tests["error_output"], "seven exact final tests not covered")
    proof = rd(RUN / "verification-v2/export/result.json")
    check(proof["passed"] and proof["roundtrip_equal"] and proof["all_original_raw_attachment_values_preserved"]
          and proof["resolved_native_values_preserved"] and proof["native_evidence_preserved"]
          and proof["native_request_count"] == 256 and proof["native_scientific_complete"] is False
          and proof["activity_graph_available"] is False and proof["inspect_usage_absent"] is True
          and proof["provider_calls"] == proof["api_spend"] == 0 and not any(proof["model_network_attempts"].values()), "actual display export failed or invents execution")
    independent = rd(RUN / "reviewer/independent-reader-v1/result.json")
    check(independent["passed"] and independent["old_log_sha256"] == proof["old_closure_log_sha256"]
          and independent["new_log_sha256"] == "ae69d14e45fdbf370c87e660bd93fc38f87cf47320702004350323528a873e63"
          and independent["provenance_sha256"] == sh(provenance_path)
          and independent["all_old_raw_attachments_preserved"] > 0
          and independent["all_old_native_fields_and_event_prefixes_preserved"] is True
          and independent["added_info_events"] == independent["role_call_count"] == independent["csv_request_count"] == 256
          and independent["role_count"] == 7 and independent["diagnostic_request_count"] == 11
          and independent["invented_model_or_tool_events"] == independent["provider_calls"] == 0
          and not any(independent["model_network_attempts"].values()), "independent saved-reader check failed")
    ir = RUN / "reviewer/independent-reader-v1"
    check(rd(ir / "execution.json")["exit_code"] == rd(ir / "remove.json")["exit_code"] == 0, "independent reader cleanup failed")
    absent(rd(ir / "actual-container.json")["id"])
    csv_rows = list(csv.DictReader(io.StringIO((RUN / "verification-v2/export/native-audit.csv").read_text(encoding="utf-8"))))
    check(len(csv_rows) == 256 and sum(int(r["spent_micro_usd"]) for r in csv_rows) == 7882971
          and sum(r["diagnostic"] == "True" for r in csv_rows) == 11, "CSV counts differ")
    ui_path = EVIDENCE / "viewer-check.json"
    ui = rd(ui_path)
    check(sh(ui_path) == "d262e7f4255d9bb5b031d2a1a960883da80421d7f0e7307ddf711fde13bcf315"
          and ui["source_display_sha256"] == retained["source_code"]["followups/inspect_display_v2/display.py"]
          and ui["saved_log_sha256"] == independent["new_log_sha256"]
          and ui["models"]["role_counts"] == expected_counts and ui["models"]["roles_view_selected"] is True
          and ui["task"]["start"] == "2026-10-31 07:52:53" and ui["task"]["end"] == "2026-10-31 10:11:43"
          and ui["activity"]["graph_available"] is False and ui["activity"]["synthetic_model_or_tool_events_added"] is False,
          "actual root UI proof missing or inconsistent")
    for name, expected in {
        "evidence/phase3a-h1-integrated-v1/offline-kit-v1.zip": "9f9fe14aa89b0d524c3f76a97ff9304465f55c90631a5d4544d593532d697308",
        "evidence/phase3a-h1-integrated-v1/offline-kit-v1-launcher-evidence.zip": "383aa35b76194e007d76de8ffd8821b8a571b126ae6f160d96b5c58c49f6b3d7",
        "evidence/phase3a-h1-integrated-v1/live-outcome-v1.zip": "50e69c125f2ff9b514aa959bc8be1731050f8e9566ebf69748aadeb37026345f",
        "evidence/phase3a-h1-integrated-v1/live-outcome.json": "01346fc1ddbbb2e37e695eb9d8aea402c3b1f36a3fe539dd075368a4a88c9e1d"}.items():
        check(old.sha(name) == expected, "frozen old experiment/archive changed")
    old.study_check()
    result = {"kind": "inspect-display-v2-independent-acceptance-v1", "passed": True, **bindings,
              "source_code_sha256": retained["source_code"], "retained_evidence_map_sha256": sh(retained_path), "retained_files_verified": 24,
              "provenance_sha256": sh(provenance_path), "source_references_verified": len(references),
              "new_saved_log_sha256": independent["new_log_sha256"], "old_saved_log_sha256": independent["old_log_sha256"],
              "export_result_sha256": sh(RUN / "verification-v2/export/result.json"),
              "independent_saved_reader_sha256": sh(ir / "result.json"), "independent_reader_code_sha256": sh(RUN / "reviewer/saved_reader_v1.py"),
              "actual_ui_proof_sha256": sh(ui_path), "ui_proof_observer": "root CUA actual viewer; independently checked against saved data",
              "canonical_source_files_unchanged": 356, "old_archives_snapshots_eight_reports_unchanged": True,
              "native_requests": 256, "diagnostic_requests": 11, "native_spent_micro_usd": 7882971,
              "all_native_evidence_and_raw_attachments_preserved": True, "added_timed_info_events": 256, "fabricated_model_or_tool_events": 0,
              "role_counts": expected_counts, "controller_dates": provenance["controller"], "api_activity_dates": provenance["activity"],
              "activity_graph_available": False, "models_view_limitation": ui["models"]["default_models_view_limitation"],
              "authoritative_configuration_view": "Roles", "scientific_complete": False, "new_scientific_claims": False,
              "provider_calls_by_fix_or_verifier": 0, "original_folder_accessed": False,
              "checker_sha256": sh(Path(__file__)), "created_utc": datetime.now(timezone.utc).isoformat()}
    target = EVIDENCE / "independent-acceptance.json"
    with target.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"passed": True, "acceptance_sha256": sh(target), "native_requests": 256, "provider_calls_by_verifier": 0}))

if __name__ == "__main__": main()
