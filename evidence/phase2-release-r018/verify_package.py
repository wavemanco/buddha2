"""One stdlib-only, read-only audit of the completed P2-R continuation archive.

Run on the Windows host only after packaging. The sole write is a new
package-review.json. Secret checks are bounded checks of recognizable patterns
and structured fields; they cannot certify absence of arbitrary unknown secrets.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(r"C:\Users\arvik\code\research\Buddha2")
EVIDENCE = ROOT / "evidence/phase2-release-r018"
RELEASE = "runs/phase2-release-r018/release/"
EXPECTED = {f"R-{index}": "pass" for index in range(1, 10)}
FIXTURES = {"fixture-not-a-secret", "fixture-a", "fixture-o", "fixture-changed"}
FIXED = (
    "AGENTS.md", "README.md", "EXPERIMENT_PLAN.md", "PHASE_DEFINITIONS.md",
    "PRE_PHASE2B_BLOCK.md", "PHASE2B_EXECUTION_KIT_REPORT.md", "PHASE2B_RUNBOOK.md",
    "DECISIONS.md", "requirements.lock", "requirements-build.lock", "upstreams.lock.json",
    "phase0.ps1", "phase2-release.ps1", "specifications/archive/phase-definitions-0.18.md",
)
EXCLUDED = {"manifest.json", "p2r-execution-kit.zip", "package-record.json", "package-review.json"}
TOKEN = re.compile(rb"(?<![A-Za-z0-9_])sk-(?:ant-)?[A-Za-z0-9_-]{20,}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8"))


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def decoded(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def safe_file(name: str) -> Path:
    pure = PurePosixPath(name)
    require(bool(name) and not pure.is_absolute() and ".." not in pure.parts
            and "\\" not in name and ":" not in name, "unsafe archive member path")
    path = ROOT.joinpath(*pure.parts)
    require(not any(part.is_symlink() for part in (path, *path.parents))
            and path.resolve(strict=True).is_relative_to(ROOT), "package member traverses a link/escape")
    return path


def inspect_json(value, counters: dict) -> None:
    if isinstance(value, list):
        for item in value:
            inspect_json(item, counters)
    elif isinstance(value, dict):
        if {"grant_id", "stage", "authorized"}.issubset(value):
            require(value["authorized"] is False, "package contains authorized grant")
            require(value.get("fixture") in (True, False), "grant lacks explicit fixture/live mode")
            counters["unapproved_or_fixture_grant_objects"] += 1
        for key, item in value.items():
            if key in {"api_key", "anthropic_api_key", "openai_api_key"}:
                fixture = isinstance(item, str) and item in FIXTURES
                require(item is None or fixture, "nonfixture raw credential field in JSON evidence")
                counters["recognized_fixture_credential_fields"] += int(fixture)
            inspect_json(item, counters)


def main() -> None:
    require(Path(__file__).resolve().parents[2] == ROOT and not ROOT.is_symlink(), "wrong project root")
    review_path = EVIDENCE / "package-review.json"
    require(not review_path.exists(), "package review is immutable; refuse a second audit")
    manifest_path, record_path = EVIDENCE / "manifest.json", EVIDENCE / "package-record.json"
    archive_path = EVIDENCE / "p2r-execution-kit.zip"
    manifest_raw, record_raw = manifest_path.read_bytes(), record_path.read_bytes()
    manifest, record = decoded(manifest_raw), decoded(record_raw)
    archive_sha = sha(archive_path.read_bytes())
    require(manifest["kind"] == "p2r-complete-execution-kit-manifest"
            and manifest["specification"] == "0.18" and manifest["closure"] == "0.19", "wrong package identity")
    require(record["kind"] == "p2r-execution-kit-package" and record["all_members_verified"] is True
            and record["archive_sha256"] == archive_sha and record["manifest_sha256"] == sha(manifest_raw)
            and record["bytes"] == archive_path.stat().st_size, "package record/hash differs")
    require(record["provider_calls"] == record["api_spend_micro_usd"] == 0
            and record["actual_credentials_supplied"] is False and record["paid_authority_included"] is False,
            "package record claims real activity/authority")
    required_inventory = set(FIXED)
    for folder in (EVIDENCE, ROOT / "runs/phase2-release-r018", ROOT / "src", ROOT / "tests"):
        for path in folder.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and not (
                    path.parent == EVIDENCE and path.name in EXCLUDED):
                required_inventory.add(path.relative_to(ROOT).as_posix())
    require(set(manifest["files"]) == required_inventory, "manifest omits/adds a current continuation member")
    counters = {"unapproved_or_fixture_grant_objects": 0, "recognized_fixture_credential_fields": 0}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        expected = set(manifest["files"]) | {"evidence/phase2-release-r018/manifest.json"}
        require(len(names) == len(set(names)) == record["entries"] and set(names) == expected,
                "ZIP inventory/duplicate entries differ")
        require(archive.testzip() is None, "ZIP CRC failure")
        require(archive.read("evidence/phase2-release-r018/manifest.json") == manifest_raw,
                "embedded manifest differs")
        for info in archive.infolist():
            require(not info.is_dir() and not stat.S_ISLNK(info.external_attr >> 16), "ZIP contains directory/link")
            path, raw = safe_file(info.filename), archive.read(info)
            require(path.read_bytes() == raw, "current working bytes differ from archive: " + info.filename)
            if info.filename in manifest["files"]:
                require(sha(raw) == manifest["files"][info.filename], "manifest member SHA differs: " + info.filename)
            require(TOKEN.search(raw) is None, "recognizable nonfixture provider-key pattern in package")
            if info.filename.endswith(".json"):
                inspect_json(decoded(raw), counters)

        def member(name):
            require(name in manifest["files"], "required handoff member absent: " + name)
            return decoded(archive.read(name))

        study = member(RELEASE + "study.json")
        require(study["study_sha256"] == canonical({key: value for key, value in study.items() if key != "study_sha256"})
                == manifest["study_sha256"] and study["execution_authorized"] is False, "study identity/authority differs")
        require(len(study["package_files"]) == 26, "release source inventory is not 26 files")
        for name, expected_sha in study["package_files"].items():
            for prefix in ("src/buddha2/", RELEASE + "source/"):
                require(manifest["files"].get(prefix + name) == expected_sha, "study/current/retained source differs")
        require(manifest["files"]["phase2-release.ps1"] == manifest["files"][RELEASE + "launcher/phase2-release.ps1"]
                == study["launcher_sha256"], "PowerShell source binding differs")
        acceptance = member("evidence/phase2-release-r018/independent-acceptance.json")
        readiness = member(RELEASE + "release-readiness.json")
        require(acceptance["status"] == "pass" and acceptance["requirements"] == EXPECTED
                and acceptance["study_sha256"] == study["study_sha256"], "independent R-1..R-9 acceptance incomplete")
        require(readiness["kind"] == "p2r-offline-release-acceptance" and readiness["requirements"] == EXPECTED
                and readiness["offline_gate_passed"] is True
                and readiness["study_sha256"] == study["study_sha256"]
                and readiness["source_sha256"] == canonical(study["package_files"])
                and readiness["launcher_sha256"] == study["launcher_sha256"]
                and readiness["control_policy_sha256"] == study["control_policy_sha256"]
                and readiness["acceptance_sha256"] == canonical({key: value for key, value in readiness.items()
                                                                  if key != "acceptance_sha256"}),
                "source-bound readiness marker differs")
        require(bool(readiness["evidence"]), "release marker lacks evidence")
        acceptance_name = "evidence/phase2-release-r018/independent-acceptance.json"
        require(readiness["evidence"].get(acceptance_name) == manifest["files"][acceptance_name],
                "release marker does not bind the independent acceptance")
        for name, expected_sha in readiness["evidence"].items():
            require(manifest["files"].get(name) == expected_sha, "readiness evidence is absent/different")
        checklist = archive.read("evidence/phase2-release-r018/REQUIREMENTS.md").decode("utf-8")
        for requirement in EXPECTED:
            require(re.search(r"^\|\s*" + re.escape(requirement) + r"(?:\s|:).*\|\s*[Pp]ass\s*\|\s*$",
                              checklist, re.MULTILINE) is not None, "checklist requirement is not passed: " + requirement)
        packet, cost = member(RELEASE + "launch-packet.json"), member(RELEASE + "cost-sheet.json")
        require(packet["kind"] == "p2r-unapproved-launch-packet" and packet["authorized"] is False
                and packet["provider_requests_authorized"] == 0 and packet["operator_keys_supplied"] is False
                and packet["account_access_verified"] is False and packet["live_billing_verified"] is False
                and packet["study_sha256"] == study["study_sha256"] and cost["authorized"] is False
                and packet["cost_sheet_sha256"] == canonical(cost), "launch packet supplies authority or loses binding")
    require("Continuation snapshot" in manifest["limitations"]
            and "preserved parent studies" in manifest["limitations"]
            and "installed immutable image" in manifest["limitations"], "snapshot incorrectly represented as standalone")
    require(sha(archive_path.read_bytes()) == archive_sha and manifest_path.read_bytes() == manifest_raw
            and record_path.read_bytes() == record_raw, "package changed during audit")
    review = {"kind": "p2r-independent-continuation-package-review", "status": "pass",
              "study_sha256": study["study_sha256"], "archive_sha256": archive_sha,
              "manifest_sha256": sha(manifest_raw), "entries": record["entries"],
              "zip_crc_inventory_and_all_member_hashes": "pass", "working_bytes_equal_archive": True,
              "source_files": 26, "source_launcher_acceptance_marker_bindings": "pass",
              "requirements": EXPECTED, "continuation_snapshot_not_standalone": True,
              "unapproved_launch_packet": True, "authorized_grant_objects": 0,
              "bounded_recognizable_key_pattern_check": "pass", **counters,
              "secret_check_limit": "Recognizable provider-token patterns and structured JSON credential fields only; does not prove absence of arbitrary unknown secrets. No host credential or environment lookup.",
              "provider_calls": 0, "api_spend_micro_usd": 0, "real_credential_access": False,
              "only_write": "evidence/phase2-release-r018/package-review.json"}
    with review_path.open("x", encoding="utf-8") as stream:
        json.dump(review, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps(review, sort_keys=True))


if __name__ == "__main__":
    main()
