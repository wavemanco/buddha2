"""Accept the immutable main packet plus its exact sanitized-launcher evidence companion."""
from __future__ import annotations

import json
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import independent_check as base
import independent_gate as gate

ROOT, VERIFY, EVIDENCE = base.ROOT, base.VERIFY, base.EVIDENCE


def main():
    # This nonpublishing function checks every main CRC/SHA/current byte and the accepted whole gate.
    main_review = gate.packet_checks()
    study, bindings = base.study_check()
    main_manifest_path = EVIDENCE / "offline-kit-v1.manifest.json"
    manifest_path = EVIDENCE / "offline-kit-v1-launcher-evidence.manifest.json"
    manifest = gate.read(manifest_path)
    base.check(main_review["archive_sha256"] == "9f9fe14aa89b0d524c3f76a97ff9304465f55c90631a5d4544d593532d697308"
               and gate.sha(main_manifest_path) == "044628dc74123b2bfd15bd92ca9edc80a3db0d5cc4a392232a3f520768817fce",
               "initial main packet bytes were changed")
    base.check(gate.sha(manifest_path) == "6afcac294685d29dbc708c815eca4322352414217bb7af5b31e5c9e5d728aed4"
               and manifest["kind"] == "p3a-hi-launcher-supplement-manifest-v1" and manifest["passed"] is True
               and manifest["packaging_provider_calls"] == 0
               and all(manifest[k] == value for k, value in bindings.items()), "companion manifest is foreign or changed")
    expected_common = {"main_archive": main_review["archive"], "main_archive_sha256": main_review["archive_sha256"],
                       "main_manifest": base.relative(main_manifest_path), "main_manifest_sha256": gate.sha(main_manifest_path),
                       "launcher_group_file_sha256": gate.sha(VERIFY / "launcher.json"),
                       "composition_review_file_sha256": gate.sha(VERIFY / "reviewer/launcher-composition-review-v1.json")}
    base.check(all(manifest[k] == value for k, value in expected_common.items()), "companion is not bound to the accepted main/group/review")
    archive = base.safe(manifest["archive"])
    base.check(base.sha(manifest["archive"]) == manifest["archive_sha256"] == "383aa35b76194e007d76de8ffd8821b8a571b126ae6f160d96b5c58c49f6b3d7", "companion archive changed")
    map_name = base.relative(VERIFY / "retained-launcher-evidence/map.json")
    base.check(manifest["map"] == map_name and base.sha(map_name) == manifest["map_sha256"], "companion map changed")
    mapping = base.read(map_name)
    base.check(mapping["kind"] == "p3a-hi-launcher-supplement-map-v1" and mapping["provider_calls"] == 0
               and all(mapping[k] == value for k, value in {**bindings, **expected_common}.items()), "map is foreign or has wrong provenance")
    accepted = {}
    for row in gate.read(VERIFY / "launcher.json")["actions"]:
        for key in ("inspection", "runtime"):
            if key in row:
                name = base.relative(gate.host_path(row[key]))
                accepted[name] = row[key + "_sha256"]
    base.check(len(accepted) == 3 and len(mapping["entries"]) == 3
               and {entry["original"]: entry["sha256"] for entry in mapping["entries"]} == accepted,
               "companion does not contain exactly the accepted three sanitized records")
    expected = {map_name: manifest["map_sha256"]}
    for entry in mapping["entries"]:
        original, copy = entry["original"], entry["copy"]
        base.check(base.public(original) and base.public(copy)
                   and copy == base.relative(VERIFY / "retained-launcher-evidence" / Path(original).name), "companion copy path escaped whitelist")
        base.check(base.sha(original) == base.sha(copy) == entry["sha256"]
                   and base.safe(original).read_bytes() == base.safe(copy).read_bytes(), "copy differs from accepted current original")
        base.check(copy not in expected, "duplicate companion copy")
        expected[copy] = entry["sha256"]
    base.check(manifest["member_count"] == 4 and manifest["member_sha256"] == expected, "companion inventory differs")
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        # Validate all member names before any content or current-file metadata access.
        base.check(len(names) == len(set(names)) == 4 and set(names) == set(expected)
                   and all(base.public(name) for name in names), "private/unknown/duplicate companion member")
        for name in names:
            info = zipped.getinfo(name)
            base.check(not info.is_dir() and not stat.S_ISLNK(info.external_attr >> 16), "nonfile/linked companion member")
            data = zipped.read(name)  # Complete read verifies the CRC at EOF.
            base.check(base.digest(data) == expected[name] and data == base.safe(name).read_bytes(), "companion CRC/SHA/current bytes differ")
    base.study_check()
    result = {**main_review, "bundle_complete": True, "bundle_kind": "p3a-hi-main-plus-launcher-evidence-v1",
              "main_archive_independently_sufficient": False,
              "companion_archive": manifest["archive"], "companion_archive_sha256": manifest["archive_sha256"],
              "companion_manifest": base.relative(manifest_path), "companion_manifest_sha256": gate.sha(manifest_path),
              "companion_map": map_name, "companion_map_sha256": manifest["map_sha256"],
              "companion_members_verified": 4, "bundle_members_verified": main_review["members_verified"] + 4,
              "launcher_original_to_copy_map_verified": True, "all_bundle_CRCs_SHA256_and_current_bytes_verified": True,
              "required_keyless_launch_preflight": "Verify this complete receipt and both archive/manifest parts before fresh keys; the unchanged frozen runtime validates its main packet fields only.",
              "reviewer": "hi_final_acceptance: nonauthor", "created_utc": datetime.now(timezone.utc).isoformat(),
              "checker_sha256": gate.sha(Path(__file__)), "main_checker_sha256": gate.sha(VERIFY / "reviewer/independent_gate.py")}
    gate.publish(VERIFY / "reviewer/bundle-packet-review-v1.json", result)
    gate.publish(EVIDENCE / "packet-acceptance.json", result)
    print(json.dumps({"passed": True, "bundle_complete": True, "main_members": main_review["members_verified"], "companion_members": 4,
                      "receipt_sha256": gate.sha(EVIDENCE / "packet-acceptance.json"), "provider_calls": 0}))


if __name__ == "__main__":
    main()
