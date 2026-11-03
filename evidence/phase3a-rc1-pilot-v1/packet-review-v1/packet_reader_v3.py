"""Independent RP1 packet reader; standard library, read-only, no extraction or receipts.

Use --self-test while preparation is incomplete. A real audit requires the finished
packet, complete gate and independent acceptance; missing inputs fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unittest
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from unittest.mock import patch

ROOT = Path(r"C:\Users\arvik\code\research\Buddha2")
PREFIX = "phase3a-rc1-pilot-v1"
EVIDENCE = "evidence/" + PREFIX
VERIFICATION = "runs/" + PREFIX + "/verification-v5"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
CACHES = {"__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
BINDINGS = {
    "study_sha256": "e2fd01fab453fdbe4a30297f282301738a42484f238d6a52afe1105f93f62cca",
    "source_sha256": "64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a",
    "runtime_sha256": "7326091ad5226fe701f4e7c8fe7801125673497221269fffdfc291c7ce492ed2",
    "policy_sha256": "46e30ea03eb67af8985edbdfce17efa844644a7765590f4aed138cc61b11ce6e",
    "launcher_sha256": "f8d509d72ae66936d88971f5d26cd6b5ad07e8ba63a2788e2fa3a2966de7bb6e",
}
GROUPS = {"static", "matrix", "replay", "tests", "windows-tests", "launcher",
          "inspect", "preservation", "regression", "native-fixtures"}
STEMS = {"offline": "offline-kit-v1", "mock-closure": "mock-outcome-v1",
         "live-closure": "live-outcome-v1"}
CLASSIFICATION = "evidence/phase2-release-r018/independent-acceptance.json"
CLASSIFICATION_SHA = "f8c729dbbb23ab98efacb4a66e67a73189d830a3c837c6acf347a77036703ea7"
OFFLINE_NAMES = {
    f"evidence/phase2-release-r018/runtime/{stem}.{stream}.log"
    for stem in ("current-source-historical-rejected", "final-static-checks", "full-suite",
                 "historical-am1-resume", "historical-r010-replay", "independent-full-rehearsal",
                 "unreviewed-expansion-rejected")
    for stream in ("stdout", "stderr")
}
REPORTS = {"PHASE3A_REPORT.md"} | {
    name + ".json" for name in ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")
}
HASH = re.compile(r"[0-9a-f]{64}")


def require(ok: object, message: str) -> None:
    if not ok:
        raise ValueError(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def pairs(items: list) -> dict:
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def json_read(raw: bytes) -> dict:
    def nonfinite(_: str) -> None:
        raise ValueError("nonfinite JSON")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    require(isinstance(value, dict), "JSON record is not an object")
    return value


def stream_name(name: str) -> bool:
    return any("stdout" in part.casefold() or "stderr" in part.casefold()
               for part in name.replace("\\", "/").split("/"))


def public_name(name: str, allowed_streams: dict | None = None) -> PurePosixPath:
    require(isinstance(name, str) and name and "\0" not in name
            and ":" not in name and "\\" not in name, "unsafe relative name")
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name
            and all(part not in {".", ".."} and part.casefold() not in PRIVATE
                    for part in path.parts), "private/traversing/noncanonical name")
    require(not stream_name(name) or name in (allowed_streams or {}),
            "unknown or provider stream rejected before metadata/content")
    require(all(not part.endswith((" ", ".")) and not any(c in part for c in '<>"|?*')
                for part in path.parts), "Windows alias/wildcard name")
    return path


def metadata(name: str, allowed_streams: dict | None = None, directory: bool = False):
    relative = public_name(name, allowed_streams)
    current = ROOT
    root_info = ROOT.lstat()
    require(stat.S_ISDIR(root_info.st_mode) and not stat.S_ISLNK(root_info.st_mode)
            and not getattr(root_info, "st_file_attributes", 0) & 0x400, "linked approved root")
    for index, part in enumerate(relative.parts):
        current /= part
        info = current.lstat()
        require(not stat.S_ISLNK(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400, "linked/reparse input")
        require(stat.S_ISDIR(info.st_mode) if index < len(relative.parts) - 1 else
                stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
                "nonordinary input")
    return current, info


def opened(name: str, allowed_streams: dict | None = None):
    path, expected = metadata(name, allowed_streams)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
    observed = os.fstat(descriptor)
    if (not stat.S_ISREG(observed.st_mode)
            or (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino)):
        os.close(descriptor)
        raise ValueError("input changed during open")
    return os.fdopen(descriptor, "rb")


def read_bytes(name: str, allowed_streams: dict | None = None) -> bytes:
    with opened(name, allowed_streams) as source:
        return source.read()


def file_hash(name: str, allowed_streams: dict | None = None) -> str:
    with opened(name, allowed_streams) as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(name: str) -> dict:
    return json_read(read_bytes(name))


def bound(value: dict) -> None:
    require(all(value.get(key) == expected for key, expected in BINDINGS.items()),
            "five release IDs differ")


def sealed(value: dict, field: str = "sha256") -> None:
    require(value.get(field) == digest({k: v for k, v in value.items() if k != field}),
            "record seal differs")


def offline_streams(raw: bytes, verification: str) -> dict:
    # This function authenticates the classification before any log/copy metadata.
    require(byte_hash(raw) == CLASSIFICATION_SHA, "offline classification receipt changed")
    receipt = json_read(raw)
    require(receipt["independent_checks"]["real_provider_calls"] == 0,
            "historical log classification is not offline")
    originals = {name: receipt["evidence"][name] for name in sorted(OFFLINE_NAMES)}
    require(all(isinstance(v, str) and HASH.fullmatch(v) for v in originals.values()),
            "historical log evidence hash is invalid")
    copies = {verification + "/release/source/" + name: expected
              for name, expected in originals.items()}
    require(len(originals) == len(copies) == 14, "historical log allowance differs")
    return originals | copies


def public_tree(name: str) -> set[str]:
    """Walk one explicit new root; reject links and skip names before metadata."""
    metadata(name, directory=True)
    pending, result = [name], set()
    while pending:
        directory = pending.pop()
        for leaf in sorted(os.listdir(ROOT.joinpath(*PurePosixPath(directory).parts))):
            if (leaf.casefold() in PRIVATE or leaf in CACHES
                    or "stdout" in leaf.casefold() or "stderr" in leaf.casefold()):
                continue
            child = directory + "/" + leaf
            public_name(child)
            # File-versus-directory classification follows lexical exclusion.
            path = ROOT.joinpath(*PurePosixPath(child).parts)
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, "st_file_attributes", 0) & 0x400, "linked tree entry")
            if stat.S_ISDIR(info.st_mode):
                metadata(child, directory=True)
                pending.append(child)
            else:
                metadata(child)
                result.add(child)
    return result


def optional_file(name: str) -> bool:
    try:
        metadata(name)
        return True
    except FileNotFoundError:
        return False


def optional_tree(name: str) -> set[str]:
    try:
        metadata(name, directory=True)
    except FileNotFoundError:
        return set()
    return public_tree(name)


def inventory(names: list[str], expected: set[str], allowed_streams: dict) -> None:
    for name in names:
        public_name(name, allowed_streams)
    require(len(names) == len(set(names)) == len({n.casefold() for n in names}),
            "duplicate/case-aliased archive members")
    require(set(names) == expected, "archive contains missing or undeclared members")


def mode_claims(manifest: dict, mode: str, scientific: bool | None = None) -> None:
    if mode == "offline":
        require(manifest.get("provider_calls") == 0, "offline manifest claims provider activity")
    else:
        require(manifest.get("contains_real_provider_evidence") is (mode == "live-closure")
                and type(manifest.get("scientific_complete")) is bool
                and type(scientific) is bool
                and manifest["scientific_complete"] is scientific,
                "closure manifest real-evidence/scientific claims contradict verified records")


def retained_launcher(launcher: dict, acceptance: dict) -> dict:
    """Resolve every gate launcher dependency through its exact included public copy."""
    rows = launcher.get("actions")
    require(isinstance(rows, list) and len(rows) == 2
            and {row.get("action") for row in rows} == {"mock", "config"},
            "launcher action evidence differs")
    originals = {}
    for row in rows:
        require(row.get("provider_calls") == 0 and row.get("actual_credentials_used") is False,
                "launcher credential/provider scope differs")
        fields = [("inspection", "inspection_sha256")]
        if row["action"] == "mock":
            fields.append(("runtime", "runtime_sha256"))
        else:
            require("runtime" not in row and "runtime_sha256" not in row,
                    "configuration-only launcher has runtime evidence")
        for path_key, hash_key in fields:
            value = row.get(path_key)
            require(isinstance(value, str), "missing exact launcher artifact path")
            if value.startswith("/results/"):
                name = "runs/" + value.removeprefix("/results/")
            else:
                absolute = Path(value)
                require(absolute.is_absolute() and absolute.is_relative_to(ROOT),
                        "launcher artifact escaped research root")
                name = absolute.relative_to(ROOT).as_posix()
            public_name(name)
            require(re.fullmatch("runs/" + re.escape(PREFIX)
                    + r"/launcher/[0-9a-f]{32}\.(?:inspection|result)\.json", name) is not None,
                    "launcher dependency is not an exact sanitized handle")
            require(isinstance(row.get(hash_key), str) and HASH.fullmatch(row[hash_key]),
                    "invalid launcher artifact hash")
            require(name not in originals, "duplicate launcher dependency")
            originals[name] = row[hash_key]
    require(len(originals) == 3, "launcher dependency coverage differs")
    map_name = VERIFICATION + "/retained-launcher/mapping.json"
    map_raw = read_bytes(map_name)
    mapping = json_read(map_raw)
    require(set(mapping) == set(originals), "retained launcher map has missing/extra dependencies")
    refs = {map_name: byte_hash(map_raw)}
    copies = {}
    for original, expected in originals.items():
        entry = mapping[original]
        require(isinstance(entry, dict) and set(entry) == {"copy", "sha256"}
                and entry["sha256"] == expected, "retained launcher mapping differs")
        copy = entry["copy"]
        public_name(copy)
        require(copy == VERIFICATION + "/retained-launcher/" + PurePosixPath(original).name,
                "retained launcher copy escaped exact public retention directory")
        original_raw = read_bytes(original)
        require(byte_hash(original_raw) == expected and read_bytes(copy) == original_raw,
                "original and retained launcher bytes differ")
        item = json_read(original_raw)
        preflight = item.get("preflight")
        require(isinstance(preflight, dict), "sanitized launcher evidence lacks preflight")
        bound(preflight)
        refs[original] = refs[copy] = expected
        copies[copy] = expected
    declared = acceptance.get("retained_launcher_artifact_sha256")
    require(isinstance(declared, dict) and all(declared.get(n) == h for n, h in refs.items()),
            "independent acceptance does not bind launcher originals/copies/map")
    return {"originals": originals, "copies": copies, "map": {map_name: byte_hash(map_raw)},
            "all_evidence": refs}


def audit(mode: str, outcome_name: str | None = None, review_name: str | None = None,
          expected_archive: str | None = None, expected_manifest: str | None = None,
          expected_gate: str | None = None) -> dict:
    require(mode in STEMS, "unknown packet mode")
    require((mode == "offline" and outcome_name is None and review_name is None)
            or (mode != "offline" and isinstance(outcome_name, str) and isinstance(review_name, str)),
            "packet mode requires exact closure inputs")
    stem = STEMS[mode]
    archive = EVIDENCE + "/" + stem + ".zip"
    manifest_name = EVIDENCE + "/" + stem + ".manifest.json"
    index_name = EVIDENCE + "/" + stem + "-index.json"
    study_name = VERIFICATION + "/release/study.json"
    gate_name = VERIFICATION + "/release/offline-gate.json"
    acceptance_name = EVIDENCE + "/independent-acceptance.json"
    # No packet or acceptance is fabricated if any of these inputs is absent.
    study_raw = read_bytes(study_name)
    study = json_read(study_raw)
    bound(study)
    sealed(study, "study_sha256")
    source = study["source"]["files"]
    require(len(source) == 419 and digest(source) == BINDINGS["source_sha256"]
            and study["source"]["sha256"] == BINDINGS["source_sha256"],
            "419-file source identity differs")
    require(digest(study["runtime"]) == BINDINGS["runtime_sha256"]
            and digest(study["policy"]) == BINDINGS["policy_sha256"],
            "runtime/policy identities differ")
    classification_raw = read_bytes(CLASSIFICATION)
    allowed = offline_streams(classification_raw, VERIFICATION)
    require({name for name in source if stream_name(name)} == OFFLINE_NAMES,
            "source stream references exceed exact fourteen-log allowance")
    for name, expected in source.items():
        public_name(name, allowed)
        require(isinstance(expected, str) and HASH.fullmatch(expected), "invalid source hash")
    gate_raw = read_bytes(gate_name)
    gate = json_read(gate_raw)
    bound(gate)
    sealed(gate)
    gate_sha = byte_hash(gate_raw)
    require(gate.get("passed") is True and gate.get("provider_calls") == 0
            and gate.get("real_credentials_used") is False
            and set(gate.get("checks", {})) == GROUPS, "complete offline gate is absent/foreign")
    acceptance_raw = read_bytes(acceptance_name)
    acceptance = json_read(acceptance_raw)
    bound(acceptance)
    require(acceptance.get("passed") is True
            and acceptance.get("offline_gate_file_sha256") == gate_sha,
            "independent offline acceptance is absent/foreign")
    if expected_gate is not None:
        require(HASH.fullmatch(expected_gate) and gate_sha == expected_gate, "expected gate hash differs")
    expected_members = set(source)
    expected_members |= {VERIFICATION + "/release/source/" + name for name in source}
    expected_members |= {CLASSIFICATION, acceptance_name}
    expected_members |= public_tree(VERIFICATION)
    gate_refs = {}
    for group, reference in gate["checks"].items():
        raw_path = reference["path"]
        require(isinstance(raw_path, str) and raw_path ==
                "/results/" + PREFIX + "/verification-v5/" + group + ".json",
                "gate reference escaped exact verification root")
        name = "runs/" + raw_path.removeprefix("/results/")
        item_raw = read_bytes(name)
        require(byte_hash(item_raw) == reference["sha256"], "gate reference bytes differ")
        item = json_read(item_raw)
        bound(item)
        require(item.get("passed") is True, "gate group failed")
        gate_refs[name] = reference["sha256"]
    retention = retained_launcher(read(VERIFICATION + "/launcher.json"), acceptance)
    regression = read(VERIFICATION + "/regression.json")
    for reference in regression.get("retained_diagnostic_refs", []):
        name = reference["path"]
        require(isinstance(name, str) and name.startswith("runs/" + PREFIX + "/"),
                "retained diagnostic escaped new namespace")
        public_name(name)
        require(file_hash(name) == reference["sha256"], "retained diagnostic differs")
        expected_members.add(name)
    for leaf in ("host-launch-test-incident.md", "unaccepted-candidate-v1.json",
                 "unaccepted-candidate-v2.json", "unaccepted-candidate-v3.json"):
        name = EVIDENCE + "/" + leaf
        if optional_file(name):
            expected_members.add(name)
    fixture = mode != "live-closure"
    branch = "mock" if fixture else "live"
    run = "runs/" + PREFIX + "/native/" + BINDINGS["study_sha256"] + "/" + branch
    journal = "runs/" + PREFIX + "/" + BINDINGS["study_sha256"] + "/" + branch + "/journal"
    exports = "runs/" + PREFIX + "/visibility-exports/" + BINDINGS["study_sha256"] + "/" + branch
    closure = review = None
    closure_reports = {}
    if mode != "offline":
        for name in (outcome_name, review_name):
            require(isinstance(name, str) and name.startswith(EVIDENCE + "/"),
                    "closure metadata escaped exact evidence root")
            public_name(name)
            expected_members.add(name)
        closure_raw = read_bytes(outcome_name)
        closure, review = json_read(closure_raw), read(review_name)
        bound(closure)
        bound(review)
        require(closure.get("kind") == "phase3a-rp1-outcome-v1"
                and closure.get("closed") is True and closure.get("fixture") is fixture
                and closure.get("run") == run and closure.get("journal") == journal
                and review.get("passed") is True and review.get("fixture") is fixture
                and review.get("outcome_file_sha256") == byte_hash(closure_raw),
                "closure/review is absent, foreign or incomplete")
        require(set(closure.get("report_sha256", {})) == REPORTS, "closure report inventory differs")
        closure_reports = closure["report_sha256"]
        for name in closure.get("sanitized_launcher_records", []):
            require(isinstance(name, str) and re.fullmatch(
                "runs/" + re.escape(PREFIX) + r"/launcher/[0-9a-f]{32}\.(?:inspection|result)\.json",
                name) is not None, "launcher record is not an exact sanitized handle")
            public_name(name)
            expected_members.add(name)
    for directory in (run, journal, exports):
        expected_members |= optional_tree(directory)
    manifest_raw = read_bytes(manifest_name)
    manifest = json_read(manifest_raw)
    bound(manifest)
    archive_sha = file_hash(archive)
    manifest_sha = byte_hash(manifest_raw)
    for actual, expected in ((archive_sha, expected_archive), (manifest_sha, expected_manifest)):
        if expected is not None:
            require(HASH.fullmatch(expected) and actual == expected, "expected packet hash differs")
    require(manifest.get("kind") == "phase3a-rp1-public-manifest-v1"
            and manifest.get("passed") is True and manifest.get("mode") == mode
            and manifest.get("archive") == archive and manifest.get("archive_sha256") == archive_sha
            and manifest.get("offline_gate_file_sha256") == gate_sha,
            "producer manifest core differs")
    require(manifest.get("authenticated_historical_offline_streams") == allowed
            and manifest.get("offline_classification_receipt_sha256") == CLASSIFICATION_SHA,
            "manifest broadened historical-stream whitelist")
    require(manifest.get("packaging_provider_calls") == 0
            and manifest.get("original_folder_accessed") is False,
            "producer scope declaration differs")
    mode_claims(manifest, mode, closure.get("scientific_complete") if closure is not None else None)
    observed, sizes = {}, {}
    total_bytes = 0
    with opened(archive) as source_archive, zipfile.ZipFile(source_archive) as zipped:
        names = zipped.namelist()
        inventory(names, expected_members | {index_name}, allowed)
        require(set(manifest.get("member_sha256", {})) == set(names)
                and manifest.get("member_count") == len(names), "external member inventory differs")
        # Only after every member name is authorized do we read index/member payloads.
        index_raw = zipped.read(index_name)
        index = json_read(index_raw)
        bound(index)
        require(index.get("kind") == "phase3a-rp1-public-packet-v1" and index.get("mode") == mode
                and index.get("offline_gate_file_sha256") == gate_sha
                and index.get("authenticated_historical_offline_streams") == allowed
                and index.get("offline_classification_receipt_sha256") == CLASSIFICATION_SHA
                and index.get("credentials_read") is False
                and index.get("private_and_provider_streams_read") is False
                and set(index.get("member_sha256", {})) == expected_members,
                "generated inner index differs")
        require(index_raw == canonical(index) + b"\n", "inner index encoding differs")
        for name in names:
            info = zipped.getinfo(name)
            mode_bits = stat.S_IFMT(info.external_attr >> 16)
            require(not info.is_dir() and not name.endswith("/")
                    and mode_bits in {0, stat.S_IFREG} and not info.external_attr & 0x10
                    and not info.flag_bits & 1, "nonordinary/encrypted archive member")
            calculated, crc, length = hashlib.sha256(), 0, 0
            with zipped.open(info) as archived:
                if name == index_name:
                    while chunk := archived.read(1024 * 1024):
                        calculated.update(chunk)
                        crc = zlib.crc32(chunk, crc)
                        length += len(chunk)
                else:
                    with opened(name, allowed) as working:
                        while chunk := archived.read(1024 * 1024):
                            require(working.read(len(chunk)) == chunk, "archive/current bytes differ")
                            calculated.update(chunk)
                            crc = zlib.crc32(chunk, crc)
                            length += len(chunk)
                        require(working.read(1) == b"", "working file has additional bytes")
            observed[name], sizes[name] = calculated.hexdigest(), length
            total_bytes += length
            require(observed[name] == manifest["member_sha256"][name]
                    and length == info.file_size and crc & 0xffffffff == info.CRC,
                    "independent member SHA256/size/CRC differs")
            if name != index_name:
                require(observed[name] == index["member_sha256"][name], "inner member hash differs")
            if name in allowed:
                require(observed[name] == allowed[name], "authenticated offline log bytes changed")
        for name, expected in source.items():
            require(observed.get(name) == observed.get(VERIFICATION + "/release/source/" + name) == expected,
                    "current/retained source differs")
        require(observed[study_name] == byte_hash(study_raw)
                and observed[gate_name] == gate_sha
                and observed[acceptance_name] == byte_hash(acceptance_raw)
                and observed[CLASSIFICATION] == CLASSIFICATION_SHA,
                "packet root evidence differs")
        require(all(observed.get(name) == expected for name, expected in gate_refs.items()),
                "archived gate evidence differs")
        require(all(observed.get(n) == h for n, h in (retention["copies"] | retention["map"]).items()),
                "packet omits or changes retained launcher companions/map")
        require(observed["phase3a-rc1-pilot.ps1"] == BINDINGS["launcher_sha256"],
                "archived launcher differs")
        if closure is not None:
            for name, expected in closure_reports.items():
                require(observed.get(run + "/reports/final/" + name) == expected, "closure report differs")
            summary = json_read(zipped.read(run + "/reports/final/summary.json"))
            require(summary.get("study_sha256") == BINDINGS["study_sha256"]
                    and summary.get("fixture") is fixture
                    and type(summary.get("scientific_complete")) is bool
                    and type(closure.get("scientific_complete")) is bool
                    and closure["scientific_complete"] is summary["scientific_complete"],
                    "closure scientific flag differs")
            for name, expected in closure.get("artifact_sha256", {}).items():
                public_name(name, allowed)
                require(observed.get(name) == expected, "explicit outcome artifact absent/changed")
    for name, expected in source.items():
        require(file_hash(name, allowed) == expected, "effective source changed during audit")
    require(file_hash(archive) == archive_sha and file_hash(manifest_name) == manifest_sha
            and file_hash(gate_name) == gate_sha and file_hash(acceptance_name) == byte_hash(acceptance_raw),
            "packet/gate/acceptance changed during audit")
    return {
        "kind": "phase3a-rp1-independent-packet-reader-result-v1", "passed": True, "mode": mode,
        **BINDINGS, "archive": archive, "archive_sha256": archive_sha,
        "archive_bytes": metadata(archive)[1].st_size, "manifest_sha256": manifest_sha,
        "offline_gate_file_sha256": gate_sha, "independent_acceptance_sha256": byte_hash(acceptance_raw),
        "member_count": len(observed), "working_files_compared_byte_for_byte": len(observed) - 1,
        "total_uncompressed_bytes_verified": total_bytes, "source_refs_verified": 419,
        "retained_source_refs_verified": 419, "gate_groups_verified": sorted(GROUPS),
        "retained_launcher_original_refs_verified": len(retention["originals"]),
        "retained_launcher_copies_verified": len(retention["copies"]),
        "retained_launcher_artifact_sha256": retention["all_evidence"],
        "authenticated_historical_original_logs": 14, "authenticated_current_source_copies": 14,
        "all_member_SHA256_CRC_size_verified": True, "complete_declared_inventory_verified": True,
        "no_extraction": True, "provider_calls": 0, "credentials_read": False,
        "receipt_written": False, "original_folder_accessed": False,
        "verification_scope": "Packet bytes/source/gate bindings only; scientific completion requires separate actual evidence review.",
        "findings": [],
    }


class ReaderSelfTests(unittest.TestCase):
    def test_private_and_unknown_streams_reject_before_metadata(self):
        names = ["runs/x/Credential-Binding.JSON", "runs/x/.env/child", "runs/x/.writer.lock",
                 "runs/x/auth.json", "runs/x/credentials.json", "runs/x/PROVIDER_STDERR.log",
                 "runs/x/new.stdout.log", "runs/phase3a-c1-completion-v4/launcher/old.stdout.log"]
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata touched")) as check:
            for name in names:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    metadata(name)
            check.assert_not_called()

    def test_exact_allowance_does_not_authorize_other_copies(self):
        name = next(iter(OFFLINE_NAMES))
        allowed = {name: "0" * 64, VERIFICATION + "/release/source/" + name: "0" * 64}
        public_name(name, allowed)
        public_name(VERIFICATION + "/release/source/" + name, allowed)
        with self.assertRaises(ValueError):
            public_name("runs/" + PREFIX + "/verification-v4/release/source/" + name, allowed)
        with self.assertRaises(ValueError):
            offline_streams(b'{"independent_checks":{"real_provider_calls":0}}', VERIFICATION)

    def test_duplicate_json_and_untrusted_inventory_reject(self):
        with self.assertRaises(ValueError):
            json_read(b'{"passed":true,"passed":false}')
        with self.assertRaises(ValueError):
            inventory(["runs/x/unknown.json"], {"runs/x/expected.json"}, {})
        with self.assertRaises(ValueError):
            inventory(["runs/x/a.json", "runs/x/A.json"], {"runs/x/a.json", "runs/x/A.json"}, {})


    def test_mode_specific_publication_claims_reject_contradictions(self):
        mode_claims({"provider_calls": 0}, "offline")
        with self.assertRaises(ValueError):
            mode_claims({"provider_calls": 1}, "offline")
        valid = {"contains_real_provider_evidence": True, "scientific_complete": False}
        mode_claims(valid, "live-closure", False)
        with self.assertRaises(ValueError):
            mode_claims(valid, "live-closure", True)
        with self.assertRaises(ValueError):
            mode_claims(valid, "mock-closure", False)

    def test_unsafe_names_and_unmatched_closure_inputs_reject(self):
        for name in ("../escape", "/absolute", "a//b", "a/../b", "a\\b", "a:b", "a/b."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                public_name(name)
        with self.assertRaises(ValueError):
            audit("live-closure")
        with self.assertRaises(ValueError):
            audit("offline", EVIDENCE + "/outcome.json", EVIDENCE + "/review.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(STEMS), default="offline")
    parser.add_argument("--outcome", help="Exact project-relative closure outcome JSON")
    parser.add_argument("--review", help="Exact project-relative independent closure review JSON")
    parser.add_argument("--expect-archive-sha256")
    parser.add_argument("--expect-manifest-sha256")
    parser.add_argument("--expect-gate-file-sha256")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReaderSelfTests)
        tested = unittest.TextTestRunner(verbosity=2).run(suite)
        print(json.dumps({"self_tests_passed": tested.wasSuccessful(),
                          "packet_accepted": False, "receipt_written": False}))
        return 0 if tested.wasSuccessful() else 1
    try:
        value = audit(args.mode, args.outcome, args.review, args.expect_archive_sha256,
                      args.expect_manifest_sha256, args.expect_gate_file_sha256)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"passed": False, "packet_accepted": False, "receipt_written": False,
                          "error_type": type(exc).__name__, "reason": str(exc)}))
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
