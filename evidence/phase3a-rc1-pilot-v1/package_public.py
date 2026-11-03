"""Seal a public HI offline packet from explicit accepted roots, never live streams."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "phase3a-rc1-pilot-v1"
EVIDENCE = ROOT / "evidence" / PREFIX
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
OFFLINE_RECEIPT = "evidence/phase2-release-r018/independent-acceptance.json"
OFFLINE_RECEIPT_SHA = "f8c729dbbb23ab98efacb4a66e67a73189d830a3c837c6acf347a77036703ea7"
OFFLINE_NAMES = {f"evidence/phase2-release-r018/runtime/{stem}.{stream}.log"
                 for stem in ("current-source-historical-rejected", "final-static-checks", "full-suite",
                              "historical-am1-resume", "historical-r010-replay", "independent-full-rehearsal",
                              "unreviewed-expansion-rejected") for stream in ("stdout", "stderr")}


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def public(name: str, offline_streams: dict | None = None) -> bool:
    parts = name.replace("\\", "/").split("/")
    return bool(parts) and all(p and p not in {".", ".."} and p.casefold() not in PRIVATE
                               and (("stdout" not in p.casefold() and "stderr" not in p.casefold())
                                    or name in (offline_streams or {})) for p in parts)


def safe(name: str, *, missing: bool = False, offline_streams: dict | None = None) -> Path:
    relative = PurePosixPath(name)
    if not public(name, offline_streams) or relative.is_absolute() or relative.as_posix() != name or ":" in name or "\\" in name:
        raise ValueError("packet path is not public and relative")
    result = ROOT.joinpath(*relative.parts)
    path = ROOT
    for part in relative.parts:
        path /= part
        try:
            info = path.lstat()
        except FileNotFoundError:
            if missing:
                return result
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("packet source traverses a link")
    return path


def read(name: str) -> dict:
    value = json.loads(safe(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("packet reference is not an object")
    return value


def authenticated_offline_streams() -> dict:
    """Classify only the fourteen historical fixture logs before touching their metadata."""
    raw = safe(OFFLINE_RECEIPT).read_bytes()
    if digest(raw) != OFFLINE_RECEIPT_SHA:
        raise ValueError("historical offline classification receipt changed")
    receipt = json.loads(raw)
    if receipt["independent_checks"]["real_provider_calls"] != 0:
        raise ValueError("historical source logs lack an offline classification")
    return {name: receipt["evidence"][name] for name in sorted(OFFLINE_NAMES)}


def package(verification: Path, *, mode: str = "offline", outcome: Path | None = None,
            review: Path | None = None) -> dict:
    if mode not in {"offline", "mock-closure", "live-closure"} or ((mode == "offline") != (outcome is None and review is None)):
        raise ValueError("packet mode and explicit closure inputs differ")
    verification = Path(verification)
    if not verification.is_absolute() or not verification.is_relative_to(ROOT / "runs" / PREFIX):
        raise ValueError("packet needs the exact new verification root")
    safe(verification.relative_to(ROOT).as_posix())
    release = verification / "release"
    study = read((release / "study.json").relative_to(ROOT).as_posix())
    gate = read((release / "offline-gate.json").relative_to(ROOT).as_posix())
    acceptance_name = f"evidence/{PREFIX}/independent-acceptance.json"
    acceptance = read(acceptance_name)
    bindings = {key: study[key] for key in
                ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")}
    if (any(not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value) for value in bindings.values())
            or digest(canonical({k: v for k, v in study.items() if k != "study_sha256"})) != study["study_sha256"]
            or digest(canonical(study["source"]["files"])) != study["source_sha256"]):
        raise ValueError("packet study/source identities are not authenticated")
    gate_bytes = safe((release / "offline-gate.json").relative_to(ROOT).as_posix()).read_bytes()
    if (gate.get("passed") is not True or acceptance.get("passed") is not True
            or any(gate.get(k) != v or acceptance.get(k) != v for k, v in bindings.items())
            or acceptance.get("offline_gate_file_sha256") != digest(gate_bytes)):
        raise ValueError("unaccepted or foreign source-bound offline gate")
    groups = {"static", "matrix", "replay", "tests", "windows-tests", "launcher", "inspect", "preservation", "regression", "native-fixtures"}
    if set(gate.get("checks", {})) != groups:
        raise ValueError("packet requires every defined offline gate group")
    for reference in gate["checks"].values():
        raw = reference["path"]
        if not isinstance(raw, str) or not raw.startswith(f"/results/{PREFIX}/"):
            raise ValueError("gate reference escaped HI")
        name = "runs/" + raw.removeprefix("/results/")
        target = safe(name)
        check = read(name)
        if (not target.is_relative_to(verification) or digest(target.read_bytes()) != reference["sha256"]
                or check.get("passed") is not True or any(check.get(k) != v for k, v in bindings.items())):
            raise ValueError("gate evidence changed or is foreign")
    stem = {"offline": "offline-kit-v1", "mock-closure": "mock-outcome-v1", "live-closure": "live-outcome-v1"}[mode]
    archive = safe(f"evidence/{PREFIX}/{stem}.zip", missing=True)
    manifest_path = safe(f"evidence/{PREFIX}/{stem}.manifest.json", missing=True)
    if archive.exists() or manifest_path.exists():
        raise ValueError("packet destination already exists")
    members: dict[str, bytes] = {}
    stream_names = {name for name in study["source"]["files"] if not public(name)}
    offline_streams = authenticated_offline_streams() if stream_names else {}
    if not stream_names <= set(offline_streams):
        raise ValueError("source contains an unknown or real-provider stream/private name")
    offline_copies = {(release / "source" / name).relative_to(ROOT).as_posix(): expected
                      for name, expected in offline_streams.items()}
    offline_streams.update(offline_copies)

    def include(name: str) -> None:
        data = safe(name, offline_streams=offline_streams).read_bytes()
        if name in offline_streams and digest(data) != offline_streams[name]:
            raise ValueError("authenticated offline source log changed")
        if name in members and members[name] != data:
            raise ValueError("packet member changed between declared roots")
        members[name] = data

    def walk(directory: Path) -> None:
        # Lexical exclusions happen before entry classification or lstat.
        for name in sorted(os.listdir(directory)):
            if not public(name) or name in {"__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}:
                continue
            item = directory / name
            relative = item.relative_to(ROOT).as_posix()
            checked = safe(relative)
            mode = checked.lstat().st_mode
            if stat.S_ISDIR(mode):
                walk(checked)
            elif stat.S_ISREG(mode):
                include(relative)
            else:
                raise ValueError("packet source has an unsupported type")

    for name, expected in study["source"]["files"].items():
        include(name)
        if digest(members[name]) != expected:
            raise ValueError("frozen source drift before packaging")
    if offline_streams:
        include(OFFLINE_RECEIPT)
        for name in offline_copies:
            include(name)
    include(acceptance_name)
    walk(verification)
    regression_name = (verification / "regression.json").relative_to(ROOT).as_posix()
    for reference in read(regression_name).get("retained_diagnostic_refs", []):
        name = reference["path"]
        if not isinstance(name, str) or not name.startswith(f"runs/{PREFIX}/"):
            raise ValueError("retained diagnostic escaped HI")
        include(name)
        if digest(members[name]) != reference["sha256"]:
            raise ValueError("retained diagnostic changed")
    for note in ("host-launch-test-incident.md", "unaccepted-candidate-v1.json", "unaccepted-candidate-v2.json", "unaccepted-candidate-v3.json"):
        name = f"evidence/{PREFIX}/{note}"
        if safe(name, missing=True).exists():
            include(name)
    sha = study["study_sha256"]
    fixture = mode != "live-closure"
    branch = "mock" if fixture else "live"
    if mode != "offline":
        if outcome is None or review is None:
            raise ValueError("closure needs an explicit outcome and independent review")
        names = []
        for item in (outcome, review):
            if not item.is_absolute() or not item.is_relative_to(ROOT / "evidence" / PREFIX):
                raise ValueError("closure metadata escaped HI evidence")
            name = item.relative_to(ROOT).as_posix()
            safe(name)
            names.append(name)
        closed, audited = map(read, names)
        run_name = f"runs/{PREFIX}/native/{sha}/{branch}"
        journal_name = f"runs/{PREFIX}/{sha}/{branch}/journal"
        if (closed.get("kind") != "phase3a-rp1-outcome-v1" or closed.get("closed") is not True
                or closed.get("fixture") is not fixture or closed.get("run") != run_name
                or closed.get("journal") != journal_name
                or audited.get("passed") is not True or audited.get("fixture") is not fixture
                or audited.get("outcome_file_sha256") != digest(safe(names[0]).read_bytes())
                or any(closed.get(k) != v or audited.get(k) != v for k, v in bindings.items())):
            raise ValueError("closure or independent review is foreign or incomplete")
        reports = {name + ".json" for name in ("rows", "coverage", "analysis", "summary", "accounting", "protocol", "readiness")}
        reports.add("PHASE3A_REPORT.md")
        if set(closed.get("report_sha256", {})) != reports:
            raise ValueError("closure must bind all eight canonical reports")
        for name, expected in closed["report_sha256"].items():
            if digest(safe(run_name + "/reports/final/" + name).read_bytes()) != expected:
                raise ValueError("closed report bytes differ")
        summary = read(run_name + "/reports/final/summary.json")
        if (summary.get("study_sha256") != sha or summary.get("fixture") is not fixture
                or type(summary.get("scientific_complete")) is not bool or type(closed.get("scientific_complete")) is not bool
                or closed.get("scientific_complete") is not summary.get("scientific_complete")):
            raise ValueError("closed report belongs to another study/mode")
        for name in ("manifest.json", "events.jsonl"):
            safe(journal_name + "/" + name)
        for name in names:
            include(name)
        # Exact public host records only, never a launcher directory/stream sweep.
        for name in closed.get("sanitized_launcher_records", []):
            if not isinstance(name, str) or not name.startswith(f"runs/{PREFIX}/launcher/") or not name.endswith((".inspection.json", ".result.json")):
                raise ValueError("closure launcher reference is not an exact sanitized record")
            include(name)
    for directory in (ROOT / "runs" / PREFIX / "native" / sha / "mock",
                      ROOT / "runs" / PREFIX / sha / "mock" / "journal",
                      ROOT / "runs" / PREFIX / "visibility-exports" / sha / "mock") if mode == "offline" else (
                      ROOT / run_name, ROOT / journal_name,
                      ROOT / "runs" / PREFIX / "visibility-exports" / sha / branch):
        checked_directory = safe(directory.relative_to(ROOT).as_posix(), missing=True)
        if checked_directory.exists():
            walk(directory)
    inner = {"kind": "phase3a-rp1-public-packet-v1", "mode": mode, **bindings,
             "offline_gate_file_sha256": digest(gate_bytes),
             "credentials_read": False, "private_and_provider_streams_read": False,
             "authenticated_historical_offline_streams": offline_streams,
             "offline_classification_receipt_sha256": OFFLINE_RECEIPT_SHA if offline_streams else None,
             "member_sha256": {name: digest(data) for name, data in sorted(members.items())}}
    members[f"evidence/{PREFIX}/{stem}-index.json"] = canonical(inner) + b"\n"
    if any(digest(safe(name, offline_streams=offline_streams).read_bytes()) != expected
           for name, expected in study["source"]["files"].items()):
        raise ValueError("frozen source changed during packaging")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for name, data in sorted(members.items()):
            zipped.writestr(name, data)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None or set(zipped.namelist()) != set(members):
            raise ValueError("packet CRC or inventory differs")
        for name, data in members.items():
            if zipped.read(name) != data:
                raise ValueError("packet member bytes differ")
    manifest = {"kind": "phase3a-rp1-public-manifest-v1", "passed": True, "mode": mode, **bindings,
                "archive": archive.relative_to(ROOT).as_posix(), "archive_sha256": digest(archive.read_bytes()),
                "offline_gate_file_sha256": digest(gate_bytes), "member_count": len(members),
                "member_sha256": {name: digest(data) for name, data in sorted(members.items())},
                "private_unknown_and_provider_stream_names_excluded_before_metadata": True,
                "authenticated_historical_offline_streams": offline_streams,
                "offline_classification_receipt_sha256": OFFLINE_RECEIPT_SHA if offline_streams else None,
                "packaging_provider_calls": 0, "original_folder_accessed": False}
    if mode == "offline":
        manifest["provider_calls"] = 0
    else:
        manifest["contains_real_provider_evidence"] = not fixture
        manifest["scientific_complete"] = summary["scientific_complete"]
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return {"archive": manifest["archive"], "archive_sha256": manifest["archive_sha256"],
            "manifest_sha256": digest(manifest_path.read_bytes()), "members": len(members)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--mode", choices=("offline", "mock-closure", "live-closure"), default="offline")
    parser.add_argument("--outcome", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.verification, mode=args.mode, outcome=args.outcome, review=args.review)))


if __name__ == "__main__":
    main()
