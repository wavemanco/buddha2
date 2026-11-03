"""Hash and package the completed offline handoff; never access the old project."""

import datetime
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/phase2-r010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserve(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"preserve existing artifact: {path}")
    if not path.exists():
        path.write_bytes(data)


def save(path, value):
    preserve(path, (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


baseline = json.loads((EVIDENCE / "execution-start.json").read_text())
study = json.loads((ROOT / "runs/phase2-r010/frozen-study/study.json").read_text())
execution = json.loads((ROOT / "runs/phase2-r010/walkthrough-execution-complete.json").read_text())
allowed = {"src/buddha2/__main__.py", "README.md", "AGENTS.md", "EXPERIMENT_PLAN.md", "PHASE_DEFINITIONS.md"}
changed = [p for p, value in baseline["tracked_files"].items() if sha(ROOT / p) != value]
if set(changed) != allowed:
    raise RuntimeError(f"unexpected baseline changes: {changed}")
for relative, expected in baseline["existing_source_and_run_files"].items():
    if sha(ROOT / relative) != expected:
        raise RuntimeError(f"prior source/result changed: {relative}")
for name, source in baseline["upstream"].items():
    for relative, expected in source["tracked_files"].items():
        if sha(ROOT / ".upstream" / name / relative) != expected:
            raise RuntimeError(f"upstream changed: {name}/{relative}")
for relative, expected in study["package_files"].items():
    if sha(ROOT / "src/buddha2" / relative) != expected:
        raise RuntimeError(f"package changed after freeze: {relative}")
for relative, expected in execution["files"].items():
    if sha(ROOT / "runs/phase2-r010/walkthrough-complete" / relative) != expected:
        raise RuntimeError(f"walkthrough changed: {relative}")
first = ROOT / "runs/phase2-r010/walkthrough-complete/portfolios/p2-82276b972aa39c5491c83143.json"
if first.read_bytes() != (ROOT / "runs/phase2-r010/imported-first/portfolio.json").read_bytes():
    raise RuntimeError("CLI import changed the portfolio")

runtime_ids = {
    "prepare": "40915de212624ba59eb0735c3c9ae7c2",
    "full_tests": "16a587b3091b40889884c5e1edcf8b39",
    "inspect": "f2d4f24fdc1641b48067e1a4871fdb4d",
    "export": "1b60674e79df416884e7f41a5effbf6a",
    "import": "55375385480d43be9d5203c891b2277d",
    "replay": "4fb013f7044a47dcb1a6ad5f258288ff",
}
runtime_records = {}
for role, identifier in runtime_ids.items():
    source = ROOT / "runs/runtime" / (identifier + ".json")
    runtime = json.loads(source.read_text())
    if (runtime["ExitCode"] != 0 or runtime["NetworkMode"] != "none"
            or not runtime["ReadonlyRootfs"] or runtime["Image"] != study["runtime_image_id"]
            or any(re.search(r"(API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)$", item.split("=", 1)[0], re.I)
                   for item in runtime["Env"])):
        raise RuntimeError(f"runtime failed offline verification: {role}")
    for item in [source, *[source.with_name(runtime["Logs"][key]) for key in ("Stdout", "Stderr")]]:
        preserve(EVIDENCE / "runtime" / item.name, item.read_bytes())
    runtime_records[role] = f"evidence/phase2-r010/runtime/{source.name}"

entries = set()
for directory in ("src/buddha2", "strategies/fixed", "runs/phase2-r010/frozen-study",
                  "runs/phase2-r010/walkthrough-complete", "runs/phase2-r010/exported-first",
                  "runs/phase2-r010/imported-first", "evidence/phase2-r010/runtime"):
    entries.update(p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
entries.update(ROOT / relative for relative in (
    "PHASE2_PREPARATION_REPORT.md", "PHASE_DEFINITIONS.md", "README.md", "AGENTS.md", "EXPERIMENT_PLAN.md",
    "requirements.lock", "requirements-build.lock", "upstreams.lock.json", "Dockerfile", "phase0.ps1", "pyproject.toml",
    "specifications/archive/phase-definitions-0.10.md", "runs/phase2-r010/walkthrough-execution-complete.json",
    "evidence/phase2-r010/live-readiness.md", "evidence/phase2-r010/credential-readiness.json",
    "evidence/phase2-r010/walkthrough-runtime-complete.json", "evidence/phase2-r010/walkthrough-driver-complete.py",
))
entries.update((ROOT / "tests").glob("test_phase2*.py"))
archive_bytes = io.BytesIO()
with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(entries):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("handoff path escapes project")
        info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 10, 25, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, path.read_bytes())
archive_path = EVIDENCE / "phase2a-kit.zip"
preserve(archive_path, archive_bytes.getvalue())
with zipfile.ZipFile(archive_path) as archive:
    if archive.testzip() is not None:
        raise RuntimeError("handoff archive CRC failure")
    for path in entries:
        if archive.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
            raise RuntimeError("archive changed an artifact")

closeout = {
    "schema_version": 2, "kind": "phase2a-offline-closeout", "status": "complete-with-live-admission-blocker",
    "execution_specification": "0.10", "closure_revision": "0.11", "study_sha256": study["study_sha256"],
    "recorded_at_utc": json.loads((EVIDENCE / "closeout.json").read_text())["recorded_at_utc"]
    if (EVIDENCE / "closeout.json").exists() else datetime.datetime.now(datetime.UTC).isoformat(),
    "provider_calls": 0, "token_count_calls": 0, "human_ratings": 0, "experiment_api_spend_usd": 0,
    "live_ready": False, "phase2b_authorized": False, "crpo_activated": False, "route_h_started": False,
    "checks": {"project_tests": 175, "phase2_tests_included": 77, "upstream_harness2_tests": 5,
               "ruff": "pass", "mypy": "pass", "bandit_medium_high": "pass", "pip_check": "pass"},
    "walkthrough": {"orders": 72, "synthetic_dispatches": 960, "not_needed_nonhead_slots": 360,
                    "replayed_assessments": 72, "resume_new_dispatches": 0, "unchanged_files": len(execution["files"])},
    "runtime_records": runtime_records, "walkthrough_runtime": "evidence/phase2-r010/walkthrough-runtime-complete.json",
    "preservation": {"tracked_baseline_files": len(baseline["tracked_files"]), "changed_baseline_files": sorted(changed),
                     "prior_source_result_files_unchanged": len(baseline["existing_source_and_run_files"]),
                     "upstream_files_unchanged": {name: len(v["tracked_files"]) for name, v in baseline["upstream"].items()},
                     "original_folder_accessed": False, "no_original_mounts_or_working_directories": True},
    "handoff_archive": {"path": archive_path.relative_to(ROOT).as_posix(), "sha256": sha(archive_path),
                        "entries": len(entries), "bytes": archive_path.stat().st_size, "crc_and_bytes_verified": True},
    "remaining_live_prerequisites": study["remaining_live_prerequisites"],
    "decision": "Stop after 2A; resolve admission/billing, access/readers and applicable authorization before a counted 2B check.",
}
save(EVIDENCE / "closeout.json", closeout)
manifest_paths = set(entries) | {archive_path, EVIDENCE / "closeout.json"}
manifest_paths.update(p for p in EVIDENCE.rglob("*") if p.is_file() and p.name != "manifest.json")
manifest = {"schema_version": 2, "kind": "phase2a-handoff-manifest", "study_sha256": study["study_sha256"],
            "files": {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(manifest_paths)}}
save(EVIDENCE / "manifest.json", manifest)
print(json.dumps({"status": closeout["status"], "archive_entries": len(entries),
                  "archive_bytes": archive_path.stat().st_size, "manifest_files": len(manifest["files"])}))
