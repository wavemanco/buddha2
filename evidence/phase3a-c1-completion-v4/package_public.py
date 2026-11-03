"""Assemble one immutable, source-bound public packet using only the standard library.

Run after the three source/gate-bound scope reviews and non-author cross-checks.
This R3 helper has no provider route and never includes raw HTML artifacts.
An archive without its verified external .manifest.json is an unaccepted partial.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).absolute().parents[2]
EVIDENCE = ROOT / "evidence/phase3a-c1-completion-v4"
RUNS = ROOT / "runs"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
INTERNAL = "PUBLIC_PACKET_MANIFEST.json"


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def relative(value):
    name = PurePosixPath(value)
    require(name.parts and not name.is_absolute() and ".." not in name.parts and "." not in name.parts
            and ":" not in value and "\\" not in value
            and all(part.casefold() not in PRIVATE for part in name.parts), "unsafe/private packet path")
    return name


def checked_path(value):
    value = Path(value)
    if not value.is_absolute():
        value = ROOT / value
    require(value.is_relative_to(ROOT) and value != ROOT, "packet input escaped the approved new root")
    relative(value.relative_to(ROOT).as_posix())
    return value


def node(path, missing=False):
    """No metadata access until the complete lexical path has been checked."""
    path = checked_path(path)
    for parent in reversed((path, *path.parents)):
        if parent == ROOT.parent:
            continue
        if parent != ROOT and not parent.is_relative_to(ROOT):
            continue
        try:
            info = parent.lstat()
        except FileNotFoundError:
            if missing:
                return None
            raise
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400), "linked packet input/output")
        require(stat.S_ISDIR(info.st_mode) if parent != path else stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                "nonordinary packet entry")
    return info


def stream(path):
    expected = node(path)
    require(expected is not None and stat.S_ISREG(expected.st_mode), "packet input is not a regular file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    opened = os.fstat(descriptor)
    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
        os.close(descriptor)
        raise ValueError("packet input changed during open")
    return os.fdopen(descriptor, "rb")


def file_hash(path):
    with stream(path) as source:
        result = hashlib.file_digest(source, "sha256").hexdigest()
    node(path)
    return result


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate packet JSON key")
            result[key] = value
        return result
    with stream(path) as source:
        return json.load(source, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite packet JSON")))


def container_path(value):
    name = PurePosixPath(value)
    require(name.parts[:2] == ("/", "results") and ".." not in name.parts, "foreign container evidence path")
    return checked_path(RUNS.joinpath(*name.parts[2:]))


def retained_candidates(add):
    records = {}
    for version, expected in (
        ("v1", "211cceaef82271ac708d3d9edaa0082b5c8153622e6e47edd3397d9dec5015fa"),
        ("v2", "422ede3d625024520c563b7542308dd16ef594526a92e0f49c36692894878b93"),
    ):
        rejection_path = EVIDENCE / f"unaccepted-candidate-{version}/candidate-rejection.json"
        require(file_hash(rejection_path) == expected, "rejected candidate record changed")
        rejection = read(rejection_path)
        require(rejection.get("passed") is False and rejection.get("scientific_complete") is False,
                "rejected candidate cannot become accepted evidence")
        add(rejection_path)
        for name, expected_hash in rejection["snapshot_sha256"].items():
            target = ROOT.joinpath(*relative(name).parts)
            require(file_hash(target) == expected_hash, "rejected candidate public evidence changed")
            add(target)
        records[version] = rejection
    return records


def build(mode, verification, output, live_inspections=()):
    require(ROOT == Path(r"C:\Users\arvik\code\research\Buddha2") or ROOT == Path("/workspace"),
            "packager is outside the approved new root")
    verification, output = checked_path(verification), checked_path(output)
    require(verification.is_relative_to(RUNS / "phase3a-c1-completion-v4") and verification.name.startswith("verification-v") and verification.name.removeprefix("verification-v").isdecimal(),
            "packet requires the explicit complete verification candidate evidence")
    require(output.is_relative_to(EVIDENCE) and output.suffix == ".zip", "packet output must be a new completion ZIP")
    manifest_path = output.with_suffix(".manifest.json")
    require(node(output, missing=True) is None and node(manifest_path, missing=True) is None, "packet outputs are immutable")
    source = read(verification / "source-before.json")
    study = read(verification / "release/study.json")
    sha = study["study_sha256"]
    require(sha == digest({k: v for k, v in study.items() if k != "study_sha256"})
            and study["source"] == source and source["sha256"] == study["source_sha256"] == digest(source["files"]),
            "packet study/source identity differs")
    gate = read(verification / "release/offline-gate.json")
    require(gate["sha256"] == digest({k: v for k, v in gate.items() if k != "sha256"}) and gate["passed"] is True
            and gate["study_sha256"] == sha and gate["source_sha256"] == source["sha256"]
            and gate["runtime_sha256"] == study["runtime_sha256"] and gate["provider_calls"] == 0
            and gate["real_credentials_used"] is False, "offline gate is absent or foreign")
    require(set(gate["checks"]) == {"tests", "static", "matrix", "replay", "launcher", "preservation"}, "gate groups differ")
    for reference in gate["checks"].values():
        target = container_path(reference["path"])
        item = read(target)
        require(file_hash(target) == reference["sha256"] and item["passed"] is True and item["study_sha256"] == sha
                and item["source_sha256"] == source["sha256"], "packet gate evidence differs")
    gate_hash = file_hash(verification / "release/offline-gate.json")
    certificates = {}
    for name, field, expected in (
        ("launch-acceptance.json", "gate_sha256", gate_hash),
        ("scientific-acceptance.json", "offline_gate_seal_sha256", gate["sha256"]),
        ("admission-acceptance.json", "offline_gate_file_sha256", gate_hash),
        ("independent-admission-review.json", "offline_gate_file_sha256", gate_hash),
        ("independent-launch-review.json", "offline_gate_file_sha256", gate_hash),
    ):
        target = EVIDENCE / name
        certificate = read(target)
        require(certificate.get("passed") is True
                and all(certificate.get(key) == study[key] for key in (
                    "study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256"))
                and certificate.get(field) == expected,
                "independent source/gate-bound certificate missing or foreign")
        certificates[name] = file_hash(target)
    members: dict[str, dict[str, Any]] = {}
    excluded = []

    def add(path):
        path = checked_path(path)
        name = path.relative_to(ROOT).as_posix()
        if path.suffix.casefold() in {".html", ".htm"}:
            excluded.append(name)
            return
        if path == output or path == manifest_path or (path.is_relative_to(EVIDENCE)
                and (path.suffix == ".zip" or path.name.endswith(".manifest.json"))):
            excluded.append(name)
            return
        info = node(path)
        require(info is not None and stat.S_ISREG(info.st_mode), "packet member is not regular")
        value = {"sha256": file_hash(path), "bytes": info.st_size}
        require(name not in members or members[name] == value, "packet member changed between explicit roots")
        members[name] = value

    def tree(path):
        path = checked_path(path)
        require(stat.S_ISDIR(node(path).st_mode), "packet tree missing")
        pending = [path]
        while pending:
            directory = pending.pop()
            node(directory)
            for name in sorted(os.listdir(directory)):
                # Names only: private entries receive no lstat/open/read at all.
                if name.casefold() in PRIVATE or Path(name).suffix.casefold() in {".html", ".htm"}:
                    excluded.append((directory / name).relative_to(ROOT).as_posix())
                    continue
                child = directory / name
                info = node(child)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(child)
                else:
                    add(child)

    for name, expected in source["files"].items():
        path = ROOT.joinpath(*relative(name).parts)
        require(file_hash(path) == expected, "frozen working source differs")
        add(path)
    tree(verification)
    native = RUNS / "phase3a-compat-c1-v1/completion-v4" / sha
    tree(native / "mock")
    tree(RUNS / "phase3a-c1-completion-v4" / sha / "mock/journal")
    tree(RUNS / "phase3a-c1-completion-v4" / sha / "mock/transport-audit")
    # Only the exact host handles named by this verified study, never all launch history.
    host = read(verification / "launcher-host.json")
    require(len(host) == 2 and {r["action"] for r in host} == {"mock", "config"}, "host coverage differs")
    inspection_paths = [container_path(row["inspection_path"]) for row in host]
    live_handles = set()
    require(mode == "final" or not live_inspections, "offline packets cannot include live scope")
    for value in live_inspections:
        inspection = checked_path(value)
        item = read(inspection)
        require(item["preflight"]["study_sha256"] == sha and item["preflight"]["source_sha256"] == source["sha256"]
                and item["preflight"]["mode"] == "provider" and item["preflight"]["fixture"] is False,
                "foreign live host inspection")
        inspection_paths.append(inspection)
        live_handles.add(inspection.name.removesuffix(".inspection.json"))
    for inspection in inspection_paths:
        parent = inspection.parent
        require(parent == RUNS / "phase3a-c1-completion-v4/launcher" and inspection.name.endswith(".inspection.json"),
                "foreign host inspection")
        prefix = inspection.name.removesuffix(".inspection.json")
        require(len(prefix) == 32 and all(c in "0123456789abcdef" for c in prefix), "invalid host handle")
        for name in sorted(os.listdir(parent)):
            if name.startswith(prefix + ".") and name.casefold() not in PRIVATE:
                if prefix in live_handles and any(token in name.casefold() for token in (".stdout", ".stderr")):
                    excluded.append((parent / name).relative_to(ROOT).as_posix())
                    continue
                add(parent / name)
    live_summary = None
    if mode == "final":
        require(live_inspections, "final packet requires explicit same-study live host inspection(s)")
        tree(native / "live")
        tree(RUNS / "phase3a-r2-v1" / sha / "live/journal")
        tree(RUNS / "phase3a-c1-completion-v4" / sha / "live/transport-audit")
        # Include the exact public closure subtree whenever that closure exists.
        closeout = RUNS / "phase3a-c1-completion-v4/live-closeout-v1"
        if node(closeout, missing=True) is not None:
            tree(closeout)
        claim_path = RUNS / "phase3a-c1-completion-v4/live-study.json"
        claim = read(claim_path)
        require(claim["study_sha256"] == sha and claim["source_sha256"] == source["sha256"], "foreign live allowance claim")
        add(claim_path)
        target = native / "live/reports/final/summary.json"
        if node(target, missing=True) is not None:
            live_summary = read(target)
            require(live_summary["study_sha256"] == sha and live_summary["fixture"] is False, "foreign final live summary")
    tree(EVIDENCE)
    rejection = retained_candidates(add)["v1"]
    rejection_path = EVIDENCE / "unaccepted-candidate-v1/candidate-rejection.json"
    for name in ("PHASE3A_C1_COMPLETION_R3_RUNBOOK.md", "PHASE3A_C1_COMPLETION_R3_REPORT.md", "PHASE3A_C1_COMPLETION_R3_LIVE_REPORT.md"):
        path = ROOT / name
        if node(path, missing=True) is not None:
            add(path)
    if mode == "final":
        outcome = read(EVIDENCE / "live-outcome.json")
        require(all(name in members and members[name]["sha256"] == expected
                    for name, expected in outcome["artifact_sha256"].items()),
                "final packet omits or differs from explicitly bound live-outcome evidence")
    parent_manifest_path = ROOT / "evidence/phase3a-c1-completion-v3/live-outcome-v1.manifest.json"
    parent_acceptance_path = ROOT / "evidence/phase3a-c1-completion-v3/live-packet-acceptance.json"
    require(file_hash(parent_manifest_path) == "0a59e2e9b51ea7992eaa732a11fddfd3c2ec15a798b2d2b012a2251c0ee64129"
            and file_hash(parent_acceptance_path) == "b11b6d09c856c277ce0866121c51c21634a1bdc71fe47d0b6fb0932be531195b",
            "accepted closed R2 packet metadata changed")
    parent_manifest, parent_acceptance = read(parent_manifest_path), read(parent_acceptance_path)
    parent_archive = ROOT / "evidence/phase3a-c1-completion-v3/live-outcome-v1.zip"
    require(parent_manifest["passed"] is True and parent_acceptance["passed"] is True
            and parent_manifest["source_sha256"] == parent_acceptance["source_sha256"]
            == "b17f977af8c893989870216aa8e92e09a4538f7d63555cceae73095998b37e9d"
            and file_hash(parent_archive) == parent_manifest["archive_sha256"] == parent_acceptance["archive_sha256"]
            == "7b026fbe76282269149e34e507651dbd6da3693a68ce261e943ec2689952dd05",
            "accepted closed R2 archive changed")
    references = {p.relative_to(ROOT).as_posix(): {"sha256": file_hash(p), "bytes": node(p).st_size}
                  for p in (parent_manifest_path, parent_archive, parent_acceptance_path)}
    retained_offline = {}
    if mode == "final":
        accepted_archive = EVIDENCE / "offline-kit-v1.zip"
        accepted_manifest = EVIDENCE / "offline-kit-v1.manifest.json"
        accepted_receipt = EVIDENCE / "packet-acceptance.json"
        manifest, receipt = read(accepted_manifest), read(accepted_receipt)
        require(manifest.get("passed") is True and receipt.get("passed") is True
                and manifest["study_sha256"] == receipt["study_sha256"] == sha
                and manifest["source_sha256"] == receipt["source_sha256"] == source["sha256"]
                and manifest["archive_sha256"] == receipt["archive_sha256"] == file_hash(accepted_archive),
                "final closure lacks its accepted immutable offline packet")
        retained_offline = {p.relative_to(ROOT).as_posix(): {"sha256": file_hash(p), "bytes": node(p).st_size}
                            for p in (accepted_archive, accepted_manifest, accepted_receipt)}
    body = {"kind": "phase3a-c1-completion-public-packet-v1", "mode": mode,
        "created_utc": datetime.now(timezone.utc).isoformat(), "study_sha256": sha,
        "source_sha256": source["sha256"], "runtime_sha256": study["runtime_sha256"],
        "offline_gate_sha256": file_hash(verification / "release/offline-gate.json"),
        "source_files": source["files"], "input_members": dict(sorted(members.items())),
        "closed_parent_references_not_recopied": references,
        "accepted_offline_references_not_recopied": retained_offline,
        "retained_rejected_candidate": {"record_sha256": file_hash(rejection_path),
            "source_sha256": rejection["terminal"]["source_sha256"],
            "included_public_files": len(rejection["snapshot_sha256"])},
        "excluded_before_metadata": sorted(set(excluded)),
        "independent_certificate_sha256": certificates,
        "known_limits": {"new_cap_micro_usd": 205860000, "included_first_cap_micro_usd": 50860000,
            "included_readiness_micro_usd": 20000000, "historical_known_micro_usd": 13101271,
            "historical_reserved_micro_usd": 22880000, "cumulative_max_micro_usd": 241841271,
            "new_max_attempts": 775, "potential_request_slots": 967, "cumulative_max_attempts": 1679, "old_unknown_released": False},
        "live_summary": live_summary, "offline_fixture_is_scientific_or_provider_readiness": False,
        "private_entry_metadata_or_content_not_read": True,
        "string_matching_cannot_establish_sensitive_data_absence": True}
    internal = (json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    expected = {name: value["sha256"] for name, value in members.items()}
    expected[INTERNAL] = hashlib.sha256(internal).hexdigest()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with stream(ROOT.joinpath(*PurePosixPath(name).parts)) as source_file, archive.open(info, "w") as destination:
                calculated = hashlib.sha256()
                while chunk := source_file.read(1024 * 1024):
                    calculated.update(chunk)
                    destination.write(chunk)
            require(calculated.hexdigest() == expected[name], "packet input changed during archiving")
        archive.writestr(INTERNAL, internal)
    with zipfile.ZipFile(output) as archive:
        require(archive.testzip() is None and len(archive.namelist()) == len(expected)
                and set(archive.namelist()) == set(expected), "packet ZIP CRC/inventory mismatch")
        for name, expected_hash in expected.items():
            with archive.open(name) as source_file:
                calculated = hashlib.sha256()
                while chunk := source_file.read(1024 * 1024):
                    calculated.update(chunk)
                require(calculated.hexdigest() == expected_hash, "packet member SHA mismatch")
    require(all(file_hash(ROOT.joinpath(*relative(name).parts)) == value["sha256"] for name, value in members.items()),
            "working input changed before packet close")
    result = {"kind": "phase3a-c1-completion-public-packet-verification-v1", "passed": True,
        "mode": mode, "study_sha256": sha, "source_sha256": study["source_sha256"],
        "archive": output.relative_to(ROOT).as_posix(), "archive_sha256": file_hash(output),
        "archive_bytes": node(output).st_size, "member_count": len(expected), "member_sha256": dict(sorted(expected.items())),
        "all_member_SHA256_and_CRC_verified": True, "working_bytes_identical": True,
        "manifest_member": INTERNAL, "closed_parent_references": references}
    with manifest_path.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "final"), required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-inspection", type=Path, action="append", default=[],
                        help="Final mode: exact public provider inspection path; may be repeated")
    arguments = parser.parse_args()
    result = build(arguments.mode, arguments.verification, arguments.output, arguments.live_inspection)
    print(json.dumps({key: result[key] for key in ("passed", "mode", "study_sha256", "source_sha256",
        "archive", "archive_sha256", "archive_bytes", "member_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
