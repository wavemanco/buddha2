"""External final archive verifier; packed trees remain immutable and no native/model work runs."""
from __future__ import annotations
import hashlib
import json
import stat
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\arvik\code\research\Buddha2")
PREFIX = "phase3a-h1-integrated-v1"
VERIFY = ROOT / "runs" / PREFIX / "verification-v4"
sys.path.insert(0, str(VERIFY / "reviewer"))
import independent_check as b
import independent_gate as g

EVIDENCE = ROOT / "evidence" / PREFIX

def rd(p): return b.read(b.relative(p))
def sh(p): return b.sha(b.relative(p))

def main():
    study, bindings = b.study_check()
    manifest_path = EVIDENCE / "live-outcome-v1.manifest.json"
    manifest = rd(manifest_path)
    b.check(sh(manifest_path) == "e2ce7e6f38a19e499dc43f8d407f0a1261bae296a01489a740bb8a634d5519bc", "sealed live manifest changed")
    b.check(manifest["kind"] == "phase3a-hi-public-manifest-v1" and manifest["passed"] is True
            and manifest["mode"] == "live-closure" and manifest["contains_real_provider_evidence"] is True
            and manifest["packaging_provider_calls"] == 0 and manifest["scientific_complete"] is False
            and all(manifest[k] == value for k, value in bindings.items()), "foreign or misleading live manifest")
    b.check(manifest["archive"] == "evidence/" + PREFIX + "/live-outcome-v1.zip"
            and b.sha(manifest["archive"]) == manifest["archive_sha256"] == "50e69c125f2ff9b514aa959bc8be1731050f8e9566ebf69748aadeb37026345f",
            "sealed live archive changed")
    b.check(manifest["authenticated_historical_offline_streams"] == b.OFFLINE, "offline source log exception was broadened")
    expected = manifest["member_sha256"]
    archive = b.safe(manifest["archive"])
    inner_name = "evidence/" + PREFIX + "/live-outcome-v1-index.json"
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        # The complete name inventory is classified before reading members or following current-file paths.
        b.check(len(names) == len(set(names)) == manifest["member_count"] == 8059 and set(names) == set(expected)
                and all(b.public(name) for name in names), "private, escaped, unknown-stream or duplicate archive member")
        for name in names:
            info = zipped.getinfo(name)
            b.check(not info.is_dir() and not stat.S_ISLNK(info.external_attr >> 16), "nonfile or linked archive member")
            data = zipped.read(name)  # A full member read verifies its CRC at EOF.
            b.check(b.digest(data) == expected[name], "archive member SHA mismatch")
            if name in b.OFFLINE:
                b.check(expected[name] == b.OFFLINE[name], "authenticated historical fixture bytes differ")
            if name == inner_name:
                inner = json.loads(data)
                b.check(inner["mode"] == "live-closure" and all(inner[k] == v for k, v in bindings.items())
                        and inner["member_sha256"] == {n: value for n, value in expected.items() if n != inner_name}, "inner index is foreign or incomplete")
            else:
                b.check(data == b.safe(name).read_bytes(), "packed/current public bytes differ")

    release = "runs/" + PREFIX + "/verification-v4/release/"
    for name, value in study["source"]["files"].items():
        b.check(expected.get(name) == expected.get(release + "source/" + name) == value, "canonical/release source needed for replay missing")
    for name, text in study["seed_tree"].items():
        b.check(expected.get(release + "seed/" + name) == hashlib.sha256(text.encode()).hexdigest(), "declared seed file missing")
    for name in ("study.json", "live-grant.json", "offline-gate.json"):
        b.check(expected.get(release + name) == b.sha(release + name), "frozen release input missing")

    outcome_path, review_path = EVIDENCE / "live-outcome.json", EVIDENCE / "live-independent-review.json"
    outcome, review = rd(outcome_path), rd(review_path)
    b.check(sh(outcome_path) == review["outcome_file_sha256"] == "01346fc1ddbbb2e37e695eb9d8aea402c3b1f36a3fe539dd075368a4a88c9e1d"
            and sh(review_path) == "12a1f20d7acab4489633eddcd852f25116a6b2b50794e545e49109174b3b52b0"
            and review["passed"] is True and review["scientific_complete"] is False
            and review["faithful_failed_attempt_closure"] is True and all(review[k] == v for k, v in bindings.items()), "unaccepted or relabelled failed outcome")
    for p in (outcome_path, review_path):
        b.check(expected.get(b.relative(p)) == sh(p), "outcome/review missing from archive")
    run = "runs/" + PREFIX + "/native/" + study["study_sha256"] + "/live"
    journal = "runs/" + PREFIX + "/" + study["study_sha256"] + "/live/journal"
    b.check(outcome["run"] == run and outcome["journal"] == journal and outcome["scientific_complete"] is False, "outcome paths or science flag changed")
    for name, value in outcome["report_sha256"].items():
        b.check(expected.get(run + "/reports/final/" + name) == value, "canonical final report missing")
    for name in ("manifest.json", "events.jsonl"):
        b.check(expected.get(journal + "/" + name) == b.sha(journal + "/" + name), "cold journal input missing")
    for name in outcome["sanitized_launcher_records"]:
        b.check(name.endswith((".inspection.json", ".result.json")) and expected.get(name) == b.sha(name), "exact sanitized launcher record missing")

    amap_name = "runs/" + PREFIX + "/verification-v4/retained-live-transport-audit/v1/map.json"
    amap = b.read(amap_name)
    b.check(expected.get(amap_name) == review["cold_audit_retention_map_sha256"] == b.sha(amap_name)
            and len(amap["entries"]) == 256, "cold audit alias map missing")
    summary = b.read(run + "/reports/final/summary.json")
    for row in amap["entries"]:
        b.check(expected.get(row["copy"]) == row["file_sha256"] == b.sha(row["original"])
                and row["record_sha256"] == summary["transport_audit_summary"]["audit_sha256"][row["slot_id"]], "cold audit copy missing or unbound")
    rows = b.read(run + "/reports/final/rows.json")
    native_artifacts = 0
    for row in rows:
        if row["branch_status"] == "not_attempted":
            continue
        branch_name = run + "/branches/" + row["pilot"] + "-" + row["arm"] + ".json"
        b.check(expected.get(branch_name) == b.sha(branch_name), "attempted branch missing")
        branch = b.read(branch_name)
        if row["arm"] == "adaptive":
            search = run + "/search/" + row["pilot"] + "/adaptive/"
            for relative, value in branch["result"]["artifact_hashes"].items():
                b.check(expected.get(search + relative) == value, "native artifact required by replay missing")
                native_artifacts += 1

    for view in review["visibility_exports"]:
        checkpoint = view["checkpoint"]
        for name in ("manifest.json", "payload.json"):
            path = run + "/visibility/" + checkpoint + "/snapshot/" + name
            b.check(expected.get(path) == b.sha(path), "reached snapshot missing")
        tail = "export-v1" if checkpoint == "closure" else "offline-replay-v1"
        export = "runs/" + PREFIX + "/visibility-exports/" + study["study_sha256"] + "/live/" + checkpoint + "/" + tail + "/"
        for name in ("visibility-result.json", "actual-container.json", "cleanup.json", "export/result.json", "export/semantic.json", "export/logs/" + checkpoint + ".eval", "export/viewer/index.html"):
            b.check(expected.get(export + name) == b.sha(export + name), "actual view/roundtrip/cleanup evidence missing")
    b.check(expected.get(run + "/visibility/first-pair/operator-incident-v1.json") == review["operator_incident_sha256"], "preserved missed-handoff incident missing")
    for name, value in review["historical_reference_sha256_verified"].items():
        b.check(b.sha(name) == value, "accepted historical evidence changed")
    b.study_check()
    result = {"kind": "phase3a-hi-live-packet-acceptance-v1", "passed": True, "mode": "live-closure", "fixture": False, **bindings,
              "archive": manifest["archive"], "archive_sha256": manifest["archive_sha256"], "manifest_sha256": sh(manifest_path),
              "outcome_file_sha256": sh(outcome_path), "independent_outcome_review_sha256": sh(review_path),
              "members_verified": len(expected), "all_CRCs_SHA256_and_current_public_bytes_verified": True,
              "privacy_names_classified_before_content_or_metadata": True, "exact_historical_offline_log_exceptions": len(b.OFFLINE),
              "canonical_and_release_source_files_verified": 356, "cold_transport_audit_copies_verified": 256,
              "cold_native_artifacts_verified": native_artifacts, "cold_replay_inputs_present_with_explicit_audit_alias_map": True,
              "all_eight_report_bytes_previously_replayed": True, "scientific_complete": False, "phase3a_scientific_milestone_achieved": False,
              "faithful_failed_attempt_packet": True, "primary_scored": 2, "counted_attempts": 256,
              "new_known_micro_usd": 7882971, "new_reserved_micro_usd": 0, "historical_reserved_micro_usd_retained": 22880000,
              "both_reached_views_delivered": True, "first_original_timeout_preserved": True,
              "packaging_or_verifier_provider_calls": 0, "contains_real_provider_evidence": True,
              "original_folder_accessed": False, "packed_inputs_modified_by_verifier": False,
              "checker_sha256": sh(Path(__file__)), "created_utc": datetime.now(timezone.utc).isoformat()}
    g.publish(EVIDENCE / "live-packet-acceptance.json", result)
    print(json.dumps({"passed": True, "members_verified": len(expected), "scientific_complete": False,
                      "acceptance_sha256": sh(EVIDENCE / "live-packet-acceptance.json"), "packaging_or_verifier_provider_calls": 0}))

if __name__ == "__main__": main()
