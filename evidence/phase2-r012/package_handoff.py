"""Verify preservation and freeze the bounded offline policy handoff.

Run only after final verification, for example:
python evidence/phase2-r012/package_handoff.py --verification evidence/phase2-r012/verification.json
The verification record supplies successful runtime paths and the observed check counts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/phase2-r012"
ALLOWED_CHANGES = {
    "src/buddha2/__main__.py", "README.md", "AGENTS.md", "EXPERIMENT_PLAN.md",
    "PHASE_DEFINITIONS.md",
}
ORIGINAL_STUDY = "4de2d582d4a5f6f289df70284295da2c67961a1a26384957dd3a43a2635c982e"
ORIGINAL_ARCHIVE = "54ae99efa70c513da92578a0edad4a2f26b2581ac9466c38dace83630f5f3084"
GENERATED = {"phase2-policy-kit.zip", "manifest.json", "closeout.json"}


def checked(path: Path | str, *, exists: bool = True) -> Path:
    """Keep every inspected, copied and written path within this new project."""
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise RuntimeError("handoff paths cannot traverse links")
    resolved = path.resolve(strict=exists)
    if not resolved.is_relative_to(ROOT):
        raise RuntimeError("handoff path escapes the new project")
    return resolved


def sha(path: Path | str) -> str:
    return hashlib.sha256(checked(path).read_bytes()).hexdigest()


def load(path: Path | str) -> dict:
    value = json.loads(checked(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("handoff input requires a JSON object")
    return value


def canonical(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def preserve(path: Path, raw: bytes) -> None:
    path = checked(path, exists=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError(f"immutable artifact differs: {path.name}")
        return
    # Publish a fully flushed temporary file without replacing another writer.
    import os

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise RuntimeError(f"concurrent immutable artifact differs: {path.name}") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save(path: Path, value: object) -> None:
    preserve(path, (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n").encode("utf-8"))


def tree(directory: str | Path) -> dict[str, str]:
    directory = checked(directory)
    result = {}
    for item in sorted(directory.rglob("*")):
        checked(item)
        if item.is_file() and "__pycache__" not in item.parts:
            result[item.relative_to(directory).as_posix()] = sha(item)
    return result


def verify_preservation(study: dict) -> dict:
    before = load(EVIDENCE / "before.json")
    if len(before["tracked_files"]) != 331:
        raise RuntimeError("unexpected starting tracked-file inventory")
    changed = sorted(relative for relative, expected in before["tracked_files"].items()
                     if sha(relative) != expected)
    if set(changed) != ALLOWED_CHANGES:
        raise RuntimeError(f"unexpected baseline changes: {changed}")
    old_manifest_path = ROOT / "evidence/phase2-r010/manifest.json"
    if sha(old_manifest_path) != before["historical_manifest_sha256"]:
        raise RuntimeError("historical manifest changed")
    old_manifest = load(old_manifest_path)
    if len(old_manifest["files"]) != 2314:
        raise RuntimeError("unexpected historical manifest inventory")
    old_archive_path = ROOT / "evidence/phase2-r010/phase2a-kit.zip"
    if sha(old_archive_path) != ORIGINAL_ARCHIVE:
        raise RuntimeError("historical archive changed")
    historical_references = []
    with zipfile.ZipFile(old_archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("historical archive CRC failure")
        for relative, expected in old_manifest["files"].items():
            if sha(relative) == expected:
                continue
            if relative not in ALLOWED_CHANGES:
                raise RuntimeError(f"historical artifact changed: {relative}")
            raw = archive.read(relative)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise RuntimeError(f"historical revision not preserved: {relative}")
            historical_references.append(relative)
    if set(historical_references) != ALLOWED_CHANGES:
        raise RuntimeError("historical source/document recovery differs from expected revisions")
    old_start = load(ROOT / "evidence/phase2-r010/execution-start.json")
    for relative, expected in old_start["existing_source_and_run_files"].items():
        if sha(relative) != expected:
            raise RuntimeError(f"prior source/result changed: {relative}")
    upstream_counts = {}
    for name, source in old_start["upstream"].items():
        for relative, expected in source["tracked_files"].items():
            if sha(ROOT / ".upstream" / name / relative) != expected:
                raise RuntimeError(f"pinned upstream changed: {name}/{relative}")
        upstream_counts[name] = len(source["tracked_files"])
    if upstream_counts != {"harness2": 114, "novelty-bench": 169}:
        raise RuntimeError("unexpected pinned source inventory")
    execution = load(ROOT / "runs/phase2-r010/walkthrough-execution-complete.json")
    if len(execution["files"]) != 2218:
        raise RuntimeError("unexpected historical walkthrough inventory")
    old_run = ROOT / "runs/phase2-r010/walkthrough-complete"
    for relative, expected in execution["files"].items():
        if sha(old_run / relative) != expected:
            raise RuntimeError(f"historical walkthrough changed: {relative}")
    original = load(ROOT / "runs/phase2-r010/frozen-study/study.json")
    if (original["study_sha256"] != ORIGINAL_STUDY
            or canonical({key: value for key, value in original.items() if key != "study_sha256"}) != ORIGINAL_STUDY):
        raise RuntimeError("historical study identity changed")
    if tree(ROOT / "runs/phase2-r012/retained-r010-source") != original["package_files"]:
        raise RuntimeError("historical replay source differs from retained generation source")
    for field in ("tasks", "source_audit", "exposure", "selection_policy", "templates", "profiles",
                  "worklist", "human_check", "upstream_pins", "lockfiles", "procedure_hashes",
                  "shared_generator_settings_sha256", "caps", "admission", "failure_policy",
                  "runtime_image_id", "runtime_python", "native_evaluator"):
        if study[field] != original[field]:
            raise RuntimeError(f"policy refresh changed frozen execution input: {field}")
    for relative, expected in study["lockfiles"].items():
        if sha(relative) != expected:
            raise RuntimeError("dependency lock changed")
    frozen = ROOT / "runs/phase2-r012/frozen-study/source"
    if tree(frozen) != study["package_files"] or tree(ROOT / "src/buddha2") != study["package_files"]:
        raise RuntimeError("effective package differs from frozen source bundle")
    return {"tracked_baseline_files": 331, "changed_baseline_files": changed,
            "unchanged_baseline_files": 331 - len(changed),
            "historical_manifest_entries_verified": 2314,
            "historical_revisions_verified_in_original_archive": historical_references,
            "prior_source_result_files_unchanged": len(old_start["existing_source_and_run_files"]),
            "historical_walkthrough_files_unchanged": 2218,
            "upstream_files_unchanged": upstream_counts,
            "original_folder_accessed": False, "no_original_mounts_or_working_directories": True}


def mount_source(value: str) -> str:
    if value.startswith(("/run/desktop/mnt/host/", "/host_mnt/")):
        suffix = value.split("/host/", 1)[-1] if "/host/" in value else value.removeprefix("/host_mnt/")
        drive, tail = suffix.split("/", 1)
        value = drive + ":/" + tail
    return str(PureWindowsPath(value)).casefold()


def runtimes(verification: dict, image: str) -> tuple[dict, dict[str, str]]:
    records = verification.get("runtime_records")
    if not isinstance(records, dict) or not {"exercise", "full_tests", "checks"}.issubset(records):
        raise RuntimeError("verification requires exercise, full_tests and checks runtime records")
    saved, logs = {}, {}
    root_source = mount_source(str(ROOT))
    runs_source = mount_source(str(ROOT / "runs"))
    for role, relative in records.items():
        if not isinstance(role, str) or not re.fullmatch(r"[a-z0-9_-]+", role):
            raise RuntimeError("invalid runtime evidence role")
        source = checked(relative)
        runtime = load(source)
        if (runtime.get("ExitCode") != 0 or runtime.get("State") != "exited"
                or runtime.get("NetworkMode") != "none"
                or runtime.get("ReadonlyRootfs") is not True or runtime.get("Image") != image
                or runtime.get("OOMKilled") is not False
                or "ALL" not in runtime.get("CapDrop", [])
                or not any(item.startswith("no-new-privileges") for item in runtime.get("SecurityOpt", []))
                or not 0 < runtime.get("PidsLimit", 0) <= 256
                or not 0 < runtime.get("Memory", 0) <= 4 * 1024 ** 3
                or not 0 < runtime.get("NanoCpus", 0) <= 2_000_000_000):
            raise RuntimeError(f"runtime failed offline containment: {role}")
        if any(re.search(r"(API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)$", item.split("=", 1)[0], re.I)
               for item in runtime.get("Env", [])):
            raise RuntimeError(f"runtime has a credential-named environment variable: {role}")
        tmpfs = runtime.get("Tmpfs", {})
        options = tmpfs.get("/tmp", "") if isinstance(tmpfs, dict) else ""
        size = re.search(r"(?:^|,)size=(\d+)([kmg]?)(?:,|$)", options, re.I)
        if (set(tmpfs) != {"/tmp"} or not {"rw", "nosuid", "nodev"}.issubset(options.split(","))
                or size is None
                or not 0 < int(size[1]) * 1024 ** {"": 0, "k": 1, "m": 2, "g": 3}[size[2].lower()] <= 512 * 1024 ** 2):
            raise RuntimeError(f"runtime temporary workspace is not bounded: {role}")
        actual_mounts = set()
        for mount in runtime.get("Mounts", []):
            if mount.get("Type") != "bind":
                raise RuntimeError("unexpected runtime mount type")
            actual_mounts.add((mount_source(mount["Source"]), mount["Destination"], mount["RW"]))
        expected_mounts = {(root_source, "/workspace", False), (runs_source, "/results", True)}
        if role == "historical_replay":
            expected_mounts.add((mount_source(str(ROOT / "runs/phase2-r012/retained-r010-source")),
                                 "/workspace/src/buddha2", False))
        if actual_mounts != expected_mounts:
            raise RuntimeError(f"runtime mounts are outside the approved exact roots: {role}")
        runtime_logs = runtime.get("Logs", {})
        captured = []
        for key in ("Stdout", "Stderr"):
            name = runtime_logs.get(key)
            if not isinstance(name, str) or Path(name).name != name:
                raise RuntimeError("invalid runtime log filename")
            path = checked(source.parent / name)
            if sha(path) != runtime_logs.get(key + "Sha256"):
                raise RuntimeError(f"runtime log hash changed: {role}/{key}")
            preserve(EVIDENCE / "runtime" / path.name, path.read_bytes())
            captured.append(path.read_text(encoding="utf-8"))
        preserve(EVIDENCE / "runtime" / source.name, source.read_bytes())
        saved[role] = (EVIDENCE / "runtime" / source.name).relative_to(ROOT).as_posix()
        logs[role] = "\n".join(captured)
    return saved, logs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    args = parser.parse_args()
    verification_path = checked(args.verification)
    verification = load(verification_path)
    study = load(ROOT / "runs/phase2-r012/frozen-study/study.json")
    if (study.get("specification") != "0.12" or study.get("parent_preparation_sha256") != ORIGINAL_STUDY
            or study.get("study_sha256") != canonical({k: v for k, v in study.items() if k != "study_sha256"})
            or study.get("decision_policy_sha256") != canonical(study.get("decision_policies"))
            or study.get("specification_sha256") != sha(EVIDENCE / "specification-0.12.md")
            or study.get("execution_authorized") is not False):
        raise RuntimeError("refreshed preparation identity/policy is invalid")
    preservation = verify_preservation(study)
    runtime_records, logs = runtimes(verification, study["runtime_image_id"])
    checks = verification.get("checks", {})
    for key in ("ruff", "mypy", "bandit_medium_high", "pip_check"):
        if checks.get(key) != "pass":
            raise RuntimeError(f"required check is not passing: {key}")
    for key in ("project_tests", "phase2_tests_included", "upstream_harness2_tests"):
        if type(checks.get(key)) is not int or checks[key] <= 0:
            raise RuntimeError("observed test counts are required")
    if (f"Ran {checks['project_tests']} tests" not in logs["full_tests"]
            or f"Ran {checks['upstream_harness2_tests']} tests" not in logs["checks"]
            or not all(marker in logs["checks"] for marker in (
                "All checks passed!", "Success: no issues found", "No broken requirements found.",
                "-m bandit", "-m ruff", "-m mypy"))):
        raise RuntimeError("reported checks/counts are not supported by successful runtime logs")
    phase2_count = len(re.findall(
        r"(?m)^test[^\n]*\((?:tests\.)?test_phase2[._]", logs["full_tests"]))
    if phase2_count != checks["phase2_tests_included"]:
        raise RuntimeError("Phase 2 test count differs from full-suite test-name evidence")
    if "historical_replay" not in logs or not all(marker in logs["historical_replay"] for marker in (
        '"native_assessments": 72', '"analysis_identical": true', '"coverage_identical": true',
        '"generation_requests": 0', '"provider_calls": 0',
    )):
        raise RuntimeError("historical source replay is not supported by successful runtime evidence")
    demonstration = load(ROOT / "runs/phase2-r012/demonstration.json")
    if (demonstration.get("fixture") is not True
            or demonstration.get("prepared_study_sha256") != study["study_sha256"]
            or demonstration.get("historical_study_sha256_unchanged") != ORIGINAL_STUDY
            or demonstration.get("historical_files_verified_unchanged") != 2218
            or demonstration.get("benchmark_synthetic_seed") != "A"
            or demonstration.get("human_without_forms") != "inconclusive"
            or demonstration.get("human_with_late_synthetic_concerns") != "B"
            or any(demonstration.get(key) != 0 for key in (
                "provider_calls", "generation_requests", "human_ratings", "experiment_api_spend_usd"))
            or any(demonstration.get(key) is not True for key in (
                "same_execution_and_native_assessment", "divergent_continuation",
                "benchmark_immutable_replay_identical"))
            or not demonstration.get("commands")
            or any(command.get("exit_code") != 0 for command in demonstration["commands"])):
        raise RuntimeError("offline demonstration is missing required outcomes")
    entries = set()
    for directory in ("src/buddha2", "strategies/fixed", "tools", "runs/phase2-r012",
                      "runs/phase2-r010/frozen-study", "runs/phase2-r010/walkthrough-complete",
                      "evidence/phase2-r012"):
        for path in checked(directory).rglob("*"):
            checked(path)
            if (path.is_file() and "__pycache__" not in path.parts
                    and not (path.parent == EVIDENCE and path.name in GENERATED)):
                entries.add(path)
    entries.update(checked(path) for path in (ROOT / "tests").glob("test_phase2*.py"))
    for relative in (
        "tests/__init__.py", "PHASE2_POLICY_UPDATE_PLAN.md", "PHASE2_POLICY_UPDATE_REPORT.md",
        "PHASE2_PREPARATION_REPORT.md", "PHASE_DEFINITIONS.md", "README.md", "AGENTS.md",
        "EXPERIMENT_PLAN.md", "DECISIONS.md", "requirements.lock", "requirements-build.lock",
        "upstreams.lock.json", "Dockerfile", "phase0.ps1", "pyproject.toml", ".dockerignore",
        "evidence/phase2-r010/phase2a-kit.zip", "evidence/phase2-r010/manifest.json",
        "evidence/phase2-r010/closeout.json", "evidence/phase2-r010/execution-start.json",
        "runs/phase2-r010/walkthrough-execution-complete.json",
        "evidence/phase2-r010/live-readiness.md", "specifications/archive/phase-definitions-0.12.md",
    ):
        entries.add(checked(relative))
    entries.add(verification_path)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(entries):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 10, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, checked(path).read_bytes())
    archive_path = EVIDENCE / "phase2-policy-kit.zip"
    preserve(archive_path, archive_bytes.getvalue())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(entries):
            raise RuntimeError("handoff archive CRC or entry count failure")
        for path in entries:
            if archive.read(path.relative_to(ROOT).as_posix()) != checked(path).read_bytes():
                raise RuntimeError("archive changed an artifact")
    existing_closeout = load(EVIDENCE / "closeout.json") if (EVIDENCE / "closeout.json").exists() else {}
    recorded = existing_closeout.get("recorded_at_utc", verification.get(
        "recorded_at_utc", dt.datetime.now(dt.UTC).isoformat()))
    closeout = {
        "schema_version": 1, "kind": "phase2-policy-offline-closeout",
        "status": "complete-with-live-admission-blocker", "execution_specification": "0.12",
        "recorded_at_utc": recorded, "study_sha256": study["study_sha256"],
        "historical_execution_study_sha256": ORIGINAL_STUDY,
        "checks": checks, "runtime_records": runtime_records, "preservation": preservation,
        "provider_calls": 0, "token_count_calls": 0, "human_ratings": 0,
        "experiment_api_spend_usd": 0, "human_collection_started": False,
        "phase2b_authorized": False, "live_ready": False, "crpo_activated": False,
        "route_h_started": False, "demonstration": {
            key: value for key, value in demonstration.items() if key != "commands"},
        "handoff_archive": {"path": archive_path.relative_to(ROOT).as_posix(),
                            "sha256": sha(archive_path), "bytes": archive_path.stat().st_size,
                            "entries": len(entries), "crc_and_bytes_verified": True},
        "remaining_live_prerequisites": study["remaining_live_prerequisites"],
        "decision": "Offline policy update complete; stop before separately scoped live-readiness work.",
        "archive_note": "Closeout and manifest are external to the ZIP to avoid recursive identities. The historical execution is included with its exact source archive.",
    }
    save(EVIDENCE / "closeout.json", closeout)
    manifest_paths = entries | {archive_path, EVIDENCE / "closeout.json"}
    manifest = {"schema_version": 1, "kind": "phase2-policy-handoff-manifest",
                "study_sha256": study["study_sha256"],
                "files": {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(manifest_paths)}}
    save(EVIDENCE / "manifest.json", manifest)
    print(json.dumps({"status": closeout["status"], "archive_entries": len(entries),
                      "archive_bytes": archive_path.stat().st_size,
                      "manifest_files": len(manifest["files"]),
                      "archive_sha256": closeout["handoff_archive"]["sha256"]}))


if __name__ == "__main__":
    main()
