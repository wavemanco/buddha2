"""Frozen prospective independent cold worker: saved snapshot/report only, no generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from unittest.mock import patch

ROOT = Path("/workspace")
PREFIX = "phase3b-seq2-v1"
VERIFICATION = Path("/results") / PREFIX / "verification-v2"
OUTPUT = Path("/results") / PREFIX / "packet-review-output"
INDEX = ROOT / f"evidence/{PREFIX}/offline-kit-v1-index.json"
SOURCE = "0b154f40fd0418b5d86a218abf23050d9b0db26a2195dbad828a6c6a3f4073aa"
STUDY = "160fa663c793f3ac0878031f3ffaa9d6db57b4349069bc9460756e147b2b68ee"
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json", "__pycache__", ".cache", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".git"}
STREAMS = {f"evidence/phase2-release-r018/runtime/{stem}.{stream}.log" for stem in
           ("current-source-historical-rejected", "final-static-checks", "full-suite", "historical-am1-resume", "historical-r010-replay", "independent-full-rehearsal", "unreviewed-expansion-rejected") for stream in ("stdout", "stderr")}
attempts = []


def need(value, message):
    if not value:
        raise AssertionError(message)


def blocked(label):
    def fail(*args, **kwargs):
        attempts.append(label)
        raise AssertionError("forbidden cold-review external activity: " + label)
    return fail


def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind", "subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.exec", "pty.spawn"}:
        blocked("audit:" + event)()


def sha(path):
    state = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def verify_inputs(expected):
    checked = {}
    for name, wanted in expected.items():
        relative = PurePosixPath(name)
        need(relative.parts and not relative.is_absolute() and relative.as_posix() == name
             and "\\" not in name and ":" not in name and all(p not in {"", ".", ".."}
             and p.casefold() not in PRIVATE for p in relative.parts), "private/noncanonical archived input")
        if any("stdout" in p.casefold() or "stderr" in p.casefold() for p in relative.parts):
            need(name in STREAMS, "noncanonical stream input")
        target = ROOT
        for part in relative.parts:
            target /= part
            info = target.lstat()
            need(not stat.S_ISLNK(info.st_mode), "linked archived input")
        need(stat.S_ISREG(info.st_mode), "nonordinary archived input")
        checked[name] = sha(target)
        need(checked[name] == wanted, "archived input changed: " + name)
    return checked


def main(index_sha):
    need(Path(__file__).resolve().is_relative_to(ROOT), "cold script is not archive-extracted")
    need({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "network-none not observed")
    need(os.environ.get("BUDDHA2_OUTPUT_ROOT") == "/results" and not any(
        name.startswith(("ANTHROPIC_", "OPENAI_")) for name in os.environ), "provider environment present")
    need(sha(INDEX) == index_sha, "archived inventory index changed")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    need(index["source_sha256"] == SOURCE and index["study_sha256"] == STUDY, "foreign archived inventory")
    expected = dict(index["member_sha256"])
    expected[INDEX.relative_to(ROOT).as_posix()] = index_sha
    need({name for name in expected if any("stdout" in p.casefold() or "stderr" in p.casefold() for p in PurePosixPath(name).parts)} == STREAMS, "canonical14/zero-copy inventory mismatch")
    receipt_path = ROOT / "evidence/phase2-release-r018/independent-acceptance.json"
    need(sha(receipt_path) == "f8c729dbbb23ab98efacb4a66e67a73189d830a3c837c6acf347a77036703ea7", "canonical stream receipt changed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    need(receipt["independent_checks"]["real_provider_calls"] == 0 and all(expected[n] == receipt["evidence"][n] for n in STREAMS), "unclassified canonical streams")
    before = verify_inputs(expected)
    sys.addaudithook(audit)
    # Constructors, sockets and subprocesses are forbidden. Saved validators legitimately
    # reconstruct fixed_best12, so the strategy functions themselves are NOT trapped.
    with ExitStack() as stack:
        for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI",
                       "socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex", "socket.getaddrinfo",
                       "subprocess.Popen", "subprocess.run", "os.system"):
            stack.enter_context(patch(target, side_effect=blocked(target)))
        from followups.phase3b_seq2_v1 import workflow
        from followups.phase3b_seq2_v1.report import NAMES, write_report
        from buddha2 import phase2_native
        native_import_origins = {}
        original_import = phase2_native._native_modules
        def observe_native_import(upstream):
            modules = original_import(upstream)
            for name, module in modules.items():
                origin = Path(module.__file__).resolve()
                need(origin.is_relative_to(ROOT / ".upstream/novelty-bench/src"), "native benchmark import escaped extracted packet")
                native_import_origins[name] = str(origin)
            return modules
        stack.enter_context(patch.object(phase2_native, "_native_modules", side_effect=observe_native_import))
        study_path = VERIFICATION / "release/study.json"
        grant_path = VERIFICATION / "release/mock-grant.json"
        # This is the sole product entry point; never workflow.run or live transport.
        data = workflow.snapshot(study_path, grant_path, True)
        need(data["summary"]["study_sha256"] == STUDY and data["summary"]["fixture"] is True
             and data["summary"]["scientific_complete"] is False and data["summary"]["authentic_live_path"] is False
             and data["summary"]["primary_scored"] == 8 and data["summary"]["assessment_scored"] == 12
             and data["summary"]["reserved_micro_usd"] == 0, "cold fixture summary differs")
        write_report(data, OUTPUT / "reports")
        run = Path("/results") / PREFIX / "native" / STUDY / "mock"
        names = tuple(name + ".json" for name in NAMES) + ("PHASE3B_REPORT.md",)
        need(len(names) == 8, "canonical report count differs")
        report_hashes = {name:sha(OUTPUT / "reports" / name) for name in names}
        need(all(report_hashes[name] == sha(run / "reports/final" / name) for name in names), "cold saved reports are not byte-identical")
        origins = {}
        for name, module in tuple(sys.modules.items()):
            if name in {"buddha2", "followups", "harness2"} or name.startswith(("buddha2.", "followups.", "harness2.")):
                origin = getattr(module, "__file__", None)
                if origin:
                    need(Path(origin).resolve().is_relative_to(ROOT), "project/upstream import escaped extracted packet")
                    origins[name] = origin
    after = verify_inputs(expected)
    need(before == after and not attempts, "cold review mutated inputs or attempted external activity")
    record = {"kind":"phase3b-s2-independent-extracted-cold-review-v1", "reviewer":"/root/s2_a1_source_review",
              "observed_at_utc":datetime.now(timezone.utc).isoformat(), "passed":True,
              "source_sha256":SOURCE, "study_sha256":STUDY, "fixture":True, "provider_calls":0,
              "scientific_effectiveness_established":False, "real_credential_access":False,
              "working_checkout_mounted_or_imported":False, "project_import_origins":origins,
              "native_benchmark_import_origins":native_import_origins,
              "all_archived_input_files_verified_before_after":len(before), "all_inputs_unchanged":True,
              "canonical_original_streams_authenticated":14, "retained_stream_copies":0,
              "external_activity_attempts":attempts, "SDK_socket_process_traps_enabled":True,
              "canonical_report_sha256":report_hashes, "eight_reports_byte_identical":True,
              "final_packet_accepted":False, "owner_cleanup_still_required":True}
    with (OUTPUT / "cold-review.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key:record[key] for key in ("passed", "study_sha256", "all_inputs_unchanged", "eight_reports_byte_identical", "provider_calls")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-sha256", required=True)
    main(parser.parse_args().index_sha256)
