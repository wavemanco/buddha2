"""Independent physical review/extraction only. Never launches a container or accepts a kit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(r"C:\Users\arvik\code\research\Buddha2")
PREFIX = "phase3b-seq2-v1"
CANDIDATE = 0
VERIFICATION = ""
PACKET_STEM = ""
REVIEW = Path()
SOURCE = ""
SOURCE_COUNT = 0
STUDY = ""
H1 = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json", "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".git"}
RECEIPT = "evidence/phase2-release-r018/independent-acceptance.json"
RECEIPT_SHA = "f8c729dbbb23ab98efacb4a66e67a73189d830a3c837c6acf347a77036703ea7"
STREAMS = {f"evidence/phase2-release-r018/runtime/{stem}.{stream}.log" for stem in
           ("current-source-historical-rejected", "final-static-checks", "full-suite", "historical-am1-resume", "historical-r010-replay", "independent-full-rehearsal", "unreviewed-expansion-rejected") for stream in ("stdout", "stderr")}
GROUPS = {"static", "matrix", "replay", "tests", "windows-tests", "launcher", "inspect", "preservation", "regression", "native-fixtures", "semantics", "supervision"}
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("nonfinite JSON: " + value)
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    need(isinstance(value, dict), "record must be a JSON object")
    return value


def relative(name):
    need(isinstance(name, str), "member name is not text")
    path = PurePosixPath(name)
    need(path.parts and not path.is_absolute() and path.as_posix() == name and "\\" not in name
         and ":" not in name and "\0" not in name and all(part not in {"", ".", ".."}
         and part.casefold() not in PRIVATE for part in path.parts), "private/noncanonical packet member")
    if any("stdout" in part.casefold() or "stderr" in part.casefold() for part in path.parts):
        need(name in STREAMS, "unknown or retained-copy stream member")
    return path


def ordinary(path, *, missing=False):
    path = Path(path)
    need(path.is_absolute() and path.is_relative_to(ROOT) and path != ROOT, "host path outside new project")
    rel = path.relative_to(ROOT)
    need(not any(p.casefold() in PRIVATE or "stdout" in p.casefold() or "stderr" in p.casefold() for p in rel.parts), "private host path")
    current = ROOT
    for part in rel.parts:
        need(part not in {"", ".", ".."}, "host path traversal")
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing:
                return path
            raise
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "host linked/reparse path")
    return path


def file_sha(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def review():
    # Exact paths, no arbitrary file selection or original-checkout dependency.
    archive = ordinary(ROOT / f"evidence/{PREFIX}/{PACKET_STEM}.zip")
    manifest_path = ordinary(ROOT / f"evidence/{PREFIX}/{PACKET_STEM}.manifest.json")
    acceptance_path = ordinary(ROOT / f"evidence/phase3b-ra1-v1/candidate-{CANDIDATE}-independent-acceptance.json")
    manifest_bytes, acceptance_bytes = manifest_path.read_bytes(), acceptance_path.read_bytes()
    manifest, acceptance = parse(manifest_bytes), parse(acceptance_bytes)
    need(manifest.get("passed") is True and manifest.get("mode") == "offline"
         and manifest.get("source_sha256") == SOURCE and manifest.get("study_sha256") == STUDY
         and manifest.get("archive") == archive.relative_to(ROOT).as_posix(), "foreign/unaccepted manifest")
    archive_sha = file_sha(archive)
    need(archive_sha == manifest["archive_sha256"], "raw archive SHA mismatch")
    expected = manifest["member_sha256"]
    need(isinstance(expected, dict) and len(expected) == manifest["member_count"], "manifest inventory mismatch")
    for name, value in expected.items():
        relative(name)
        need(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "invalid member hash")
    index_name = f"evidence/{PREFIX}/{PACKET_STEM}-index.json"
    study_name = f"runs/{PREFIX}/{VERIFICATION}/release/study.json"
    gate_name = f"runs/{PREFIX}/{VERIFICATION}/release/offline-gate.json"
    acceptance_name = acceptance_path.relative_to(ROOT).as_posix()
    inventory = {}
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        names = [item.filename for item in infos]
        for name in names:
            relative(name)  # classify names BEFORE payload/entry attributes
        need(len(names) == len(set(names)) == len({n.casefold() for n in names}), "duplicate/case-fold-colliding members")
        need(set(names) == set(expected), "ZIP inventory differs from manifest")
        need({n for n in names if any("stdout" in p.casefold() or "stderr" in p.casefold() for p in PurePosixPath(n).parts)} == STREAMS, "canonical14/zero-copy stream inventory failed")
        receipt_bytes = zipped.read(RECEIPT)
        need(sha(receipt_bytes) == RECEIPT_SHA, "archived canonical classification receipt changed")
        receipt = parse(receipt_bytes)
        streams = {name: receipt["evidence"][name] for name in STREAMS}
        need(receipt["independent_checks"]["real_provider_calls"] == 0
             and manifest["authenticated_historical_offline_streams"] == streams
             and manifest["offline_classification_receipt_sha256"] == RECEIPT_SHA, "canonical stream classification not authenticated")
        # Authenticated canonical14 before any explicit stream entry metadata/CRC access.
        need(sum(i.file_size for i in infos) <= 8 * 1024 ** 3, "reviewer extraction bound exceeded; stop/review")
        for item in infos:
            mode = (item.external_attr >> 16) & 0o170000
            need(not item.is_dir() and mode in (0, stat.S_IFREG) and not item.flag_bits & 1
                 and item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "linked/nonordinary/encrypted packet entry")
        # All names classified; now inspect CRC and payload hashes, including canonical14 only.
        need(zipped.testzip() is None, "ZIP CRC failure")
        for item in infos:
            state = hashlib.sha256()
            with zipped.open(item) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    state.update(block)
            inventory[item.filename] = state.hexdigest()
            need(inventory[item.filename] == expected[item.filename], "member raw SHA mismatch")
        index, study, gate = (parse(zipped.read(n)) for n in (index_name, study_name, gate_name))
        need(index["member_sha256"] == {n:h for n,h in expected.items() if n != index_name}, "embedded index inventory differs")
        need(all(index.get(k) == manifest.get(k) == study.get(k) == acceptance.get(k) for k in BINDINGS), "source/study/acceptance binding mismatch")
        need(sha(canonical({k:v for k,v in study.items() if k != "study_sha256"})) == STUDY
             and sha(canonical(study["source"]["files"])) == SOURCE and len(study["source"]["files"]) == SOURCE_COUNT, "study/source seal mismatch")
        need(gate.get("passed") is True and set(gate["checks"]) == GROUPS
             and all(gate.get(k) == study.get(k) for k in BINDINGS)
             and sha(zipped.read(gate_name)) == manifest["offline_gate_file_sha256"] == acceptance["offline_gate_file_sha256"]
             and acceptance.get("passed") is True and zipped.read(acceptance_name) == acceptance_bytes, "full independent gate not accepted")
        for ref in gate["checks"].values():
            need(isinstance(ref["path"], str) and ref["path"].startswith(f"/results/{PREFIX}/{VERIFICATION}/"), "gate reference escaped current verification")
            name = "runs/" + ref["path"].removeprefix("/results/")
            record = parse(zipped.read(name))
            need(inventory[name] == ref["sha256"] and record.get("passed") is True
                 and all(record.get(k) == study.get(k) for k in BINDINGS), "stale or failed current gate group")
        policy = {"kind":"phase3b-s2-originals-only-source-snapshot-v1", "canonical_originals":streams,
                  "offline_classification_receipt":{"path":RECEIPT,"sha256":RECEIPT_SHA}}
        need(study["source_snapshot_policy"] == policy, "main snapshot policy mismatch")
        rehearsal_name = f"runs/{PREFIX}/{VERIFICATION}/operational-rehearsal/release/study.json"
        rehearsal = parse(zipped.read(rehearsal_name))
        need(rehearsal["source"] == study["source"] and rehearsal["source_snapshot_policy"] == policy
             and rehearsal["fixture_supervision_rehearsal"] is True, "rehearsal snapshot mismatch")
        for release in (study_name.removesuffix("study.json"), rehearsal_name.removesuffix("study.json")):
            for name, value in study["source"]["files"].items():
                need(inventory.get(name) == value, "canonical source missing/changed in packet")
                if name not in STREAMS:
                    need(inventory.get(release + "source/" + name) == value, "ordinary retained source missing/changed")
        extracted = ordinary(REVIEW / "extracted-ra1", missing=True)
        need(not extracted.exists(), "review extraction must be fresh")
        extracted.mkdir()
        for item in infos:
            rel = relative(item.filename)
            dest = extracted.joinpath(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(item) as source, dest.open("xb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
            need(file_sha(dest) == inventory[item.filename], "extracted raw hash differs")
    need(file_sha(archive) == archive_sha and manifest_path.read_bytes() == manifest_bytes
         and acceptance_path.read_bytes() == acceptance_bytes, "packet inputs changed during physical review")
    # This named empty mount point is reviewer setup, not an archived input file.
    mountpoint = extracted / f"runs/{PREFIX}/packet-review-output"
    need(not mountpoint.exists(), "review output mount point must be fresh")
    mountpoint.mkdir()
    output = ordinary(REVIEW / "cold-output-ra1", missing=True)
    need(not output.exists(), "cold output must be fresh")
    output.mkdir()
    script_name = f"runs/{PREFIX}/{VERIFICATION}/external-reviews/packet-review-ra1-c{CANDIDATE}/cold_replay_ra1.py"
    need(script_name in inventory, "frozen independent cold worker absent from archive")
    command = ["docker", "create", "--pull=never", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "4g", "--cpus", "2", "--entrypoint", "python",
               "--mount", f"type=bind,source={extracted},target=/workspace,readonly",
               "--mount", f"type=bind,source={extracted / 'runs'},target=/results,readonly",
               "--mount", f"type=bind,source={output},target=/results/{PREFIX}/packet-review-output",
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=1073741824,mode=1777", "--workdir", "/workspace",
               "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/workspace/src:/workspace/.upstream/harness2:/workspace",
               "-e", "BUDDHA2_OUTPUT_ROOT=/results", "-e", f"BUDDHA2_IMAGE_ID={H1}", "-e", "BUDDHA2_OFFLINE=1",
               "-e", "PHASE3A_OPENCODE=/opt/phase3a-opencode", "-e", "PHASE3A_BUN=/usr/local/bin/bun", H1,
               "-B", "/workspace/" + script_name, "--index-sha256", inventory[index_name], "--source-sha256", SOURCE, "--study-sha256", STUDY, "--candidate", str(CANDIDATE)]
    result = {"kind":"phase3b-s2-independent-physical-review-v2", "reviewer":"/root/ra1_path_review",
              "observed_at_utc":datetime.now(timezone.utc).isoformat(), "physical_review_passed":True,
              "final_packet_accepted":False, "cold_replay_executed":False, "archive":manifest["archive"],
              "archive_sha256":archive_sha, "manifest_sha256":sha(manifest_bytes),
              "independent_acceptance_sha256":sha(acceptance_bytes), "offline_gate_file_sha256":manifest["offline_gate_file_sha256"],
              **{k:study[k] for k in BINDINGS}, "member_sha256":inventory, "member_count":len(inventory),
              "canonical_original_stream_count":14, "retained_stream_copies":0,
              "extracted_root":str(extracted), "cold_output_root":str(output), "docker_create_argv":command,
              "working_checkout_mounted":False, "real_provider_calls":0, "original_folder_accessed":False}
    save(REVIEW / "physical-review-ra1.json", result)
    save(REVIEW / "cold-create-command-ra1.json", {"argv":command, "execute_only_after_independent_owner_review":True})
    print(json.dumps({k:result[k] for k in ("physical_review_passed", "final_packet_accepted", "archive_sha256", "member_count", "extracted_root")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-physical-review", action="store_true", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--study-sha256", required=True)
    parser.add_argument("--source-count", type=int, required=True)
    parser.add_argument("--candidate", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    SOURCE, STUDY, SOURCE_COUNT = args.source_sha256, args.study_sha256, args.source_count
    CANDIDATE = args.candidate
    VERIFICATION = "verification-ra1-v" + str(CANDIDATE)
    PACKET_STEM = "offline-kit-ra1-c" + str(CANDIDATE)
    REVIEW = ROOT / "runs" / PREFIX / VERIFICATION / "external-reviews" / ("packet-review-ra1-c" + str(CANDIDATE))
    need(all(len(value) == 64 and all(c in "0123456789abcdef" for c in value) for value in (SOURCE, STUDY))
         and SOURCE_COUNT > 0, "invalid prospective source/study binding")
    review()
