"""Black-box Phase 0 acceptance checks for the supported offline Linux runtime.

Run with the project's network-disabled launcher.  These checks deliberately use
the public CLI and pinned upstream artifacts, not project implementation helpers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
H2_PIN = "1cfe254e8d25b15f37048c3730134686abe60335"
NB_PIN = "64a23be6b18ec1dacc298830aab276061b6e143c"
EXPECTED_UTILITY = 4.346485261239209
CREDENTIAL_NAMES = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "AZURE_OPENAI_API_KEY",
    "DEEPSEEK_API_KEY", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACE_HUB_TOKEN", "ANTHROPIC_AUTH_TOKEN",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "GH_TOKEN",
)
FINAL_FILES = (
    "manifest.json", "portfolio.json", "grading.json",
    "native/generations.jsonl", "native/identities.json",
    "assessments/mechanical.json", "assessments/noveltybench-fixture.json",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def content_hash(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_snapshot(root: Path) -> dict[str, str]:
    """Detect source changes without requiring Git inside the runtime image."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(root).parts
        and "__pycache__" not in path.relative_to(root).parts
        and path.suffix != ".pyc"
    }


def values_named(value, name: str) -> list:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == name:
                found.append(child)
            found.extend(values_named(child, name))
    elif isinstance(value, list):
        for child in value:
            found.extend(values_named(child, name))
    return found


def replace_vector(value, expected: list, replacement: list) -> bool:
    """Change declared grading evidence without depending on wrapper field names."""
    if isinstance(value, dict):
        for key, child in value.items():
            if child == expected:
                value[key] = replacement
                return True
            if replace_vector(child, expected, replacement):
                return True
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if child == expected:
                value[index] = replacement
                return True
            if replace_vector(child, expected, replacement):
                return True
    return False


@unittest.skipUnless(sys.platform == "linux", "Phase 0 supports Linux only")
class OfflineAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("BUDDHA2_OFFLINE") != "1":
            raise RuntimeError("Use the network-disabled Phase 0 test launcher")
        present = [name for name in CREDENTIAL_NAMES if os.environ.get(name)]
        if present:
            raise RuntimeError(f"Provider/host credentials present: {present}")
        root = Path(os.environ.get("BUDDHA2_TEST_OUTPUT_ROOT", "/runs/acceptance"))
        root.mkdir(parents=True, exist_ok=True)
        cls.scratch = tempfile.TemporaryDirectory(prefix="acceptance-", dir=root)
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.work = Path(cls.scratch.name)
        cls.upstreams = (
            Path(os.environ.get("HARNESS2_ROOT", PROJECT / ".upstream/harness2")),
            Path(os.environ.get("NOVELTYBENCH_ROOT", PROJECT / ".upstream/novelty-bench")),
        )
        for source in cls.upstreams:
            if not source.is_dir():
                raise RuntimeError(f"Pinned source unavailable: {source}")
        cls.before_sources = {str(p): source_snapshot(p) for p in cls.upstreams}
        cls.addClassCleanup(cls.check_source_integrity)
        cls.baseline = cls.work / "baseline"
        cls.cli("demo", "--output", cls.baseline)

    @classmethod
    def check_source_integrity(cls) -> None:
        for source in cls.upstreams:
            if source_snapshot(source) != cls.before_sources[str(source)]:
                raise AssertionError(f"Acceptance commands modified upstream: {source}")

    @classmethod
    def cli(cls, *args, success: bool = True) -> subprocess.CompletedProcess:
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run(
            [sys.executable, "-m", "buddha2", *map(str, args)], cwd=PROJECT,
            env=environment, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=180, check=False,
        )
        if (process.returncode == 0) != success:
            raise AssertionError(
                f"CLI exit {process.returncode}: {args}\n"
                f"{process.stdout[-5000:]}\n{process.stderr[-5000:]}"
            )
        return process

    def fresh(self, name: str) -> Path:
        return self.work / f"{self._testMethodName}-{name}"

    def test_usable_demo_inspection_and_required_artifacts(self) -> None:
        for relative in (*FINAL_FILES, "report.md", "engine/engine.json"):
            self.assertTrue((self.baseline / relative).is_file(), relative)
        portfolio = read_json(self.baseline / "portfolio.json")
        self.assertEqual(portfolio["schema_version"], 1)
        self.assertIs(portfolio["fixture"], True)
        self.assertIs(portfolio["task"]["fixture"], True)
        self.assertEqual(len(portfolio["responses"]), 10)
        self.assertEqual(len({r["id"] for r in portfolio["responses"]}), 10)
        self.assertIsInstance(portfolio["provenance"], dict)
        provenance = json.dumps(read_json(self.baseline / "manifest.json"))
        self.assertIn(H2_PIN, provenance)
        self.assertIn(NB_PIN, provenance)
        self.assertTrue(self.cli("inspect", "--run", self.baseline).stdout.strip())

    def test_native_scheduler_materialization_and_trivial_selection(self) -> None:
        engine = self.baseline / "engine"
        evidence = read_json(engine / "engine.json")
        native = evidence["native_source"]
        self.assertEqual(native["expected_commit"], H2_PIN)
        scheduler = Path(native["scheduler"])
        self.assertTrue(scheduler.is_relative_to(self.upstreams[0]))
        self.assertEqual(
            hashlib.sha256(scheduler.read_bytes()).hexdigest(),
            native["scheduler_sha256"],
        )
        outputs = list((engine / "executions").glob("*/*/*/portfolio.json"))
        self.assertEqual({p.parent.name for p in outputs}, {"base1", "inv1", "dom1", "agg1"})
        self.assertEqual(len(outputs), 4)
        generations = {}
        for path in outputs:
            generations[path.parent.name] = read_json(path)["generations"]
            staged = read_json(path.parent / "materialization.json")
            for relative, expected in staged["materialized_sha256"].items():
                materialized = path.parent / "harness" / relative
                self.assertEqual(hashlib.sha256(materialized.read_bytes()).hexdigest(), expected)
        self.assertNotEqual(generations["base1"], generations["inv1"])
        self.assertNotEqual(generations["dom1"], generations["agg1"])
        summaries = list((engine / "adapt").glob("*/*/summary.json"))
        self.assertEqual(len(summaries), 1)
        summary = read_json(summaries[0])
        self.assertIs(summary["selections"]["agg"]["trivial"], True)
        ledger = summary["modes"]["agg"]["ledger"]
        self.assertEqual((ledger["R"], ledger["P"]), (4, 3))
        self.assertEqual(set(ledger["sessions"]), {"inv1", "dom1", "agg1"})
        edits = list((engine / "proposer").glob("*/edit.json"))
        self.assertEqual(len(edits), 3)
        attempts = set()
        for path in edits:
            edit = read_json(path)
            self.assertEqual(edit["label"], path.parent.name)
            self.assertIs(edit["fixture"], True)
            self.assertEqual(edit["provider_calls"], 0)
            attempts.add(edit["label"])
        self.assertEqual(attempts, {"inv1.a1", "dom1.a1", "agg1.a1"})

    def test_native_arithmetic_and_separate_output_bound_assessments(self) -> None:
        portfolio = read_json(self.baseline / "portfolio.json")
        output_hash = content_hash(portfolio)
        native = read_json(self.baseline / "assessments/noveltybench-fixture.json")
        mechanical = read_json(self.baseline / "assessments/mechanical.json")
        for assessment in (native, mechanical):
            self.assertIn(output_hash, json.dumps(assessment))
        utilities = values_named(native, "utility")
        self.assertTrue(utilities, "Native per-task utility must be preserved")
        for utility in utilities:
            self.assertAlmostEqual(utility, EXPECTED_UTILITY, places=12)
        self.assertIn(5, values_named(native, "distinct"))
        self.assertIn(5, values_named(native, "mean_distinct"))
        for utility in values_named(native, "mean_utility"):
            self.assertAlmostEqual(utility, EXPECTED_UTILITY, places=12)

    def test_export_import_roundtrip_and_duplicate_text(self) -> None:
        source = read_json(self.baseline / "portfolio.json")
        # Duplicate text is allowed; identity must be positional, never text-keyed.
        source["responses"][1]["text"] = source["responses"][0]["text"]
        portfolio = self.fresh("portfolio.json")
        write_json(portfolio, source)
        exported, imported = self.fresh("export"), self.fresh("import")
        self.cli("export", "--portfolio", portfolio, "--output", exported)
        rows = [json.loads(line) for line in (exported / "generations.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], source["task"]["id"])
        self.assertEqual(rows[0]["prompt"], source["task"]["prompt"])
        self.assertEqual(rows[0]["model"], "fixture-no-model")
        self.assertEqual(rows[0]["generations"], [r["text"] for r in source["responses"]])
        self.cli("import", "--source", exported, "--output", imported)
        restored = read_json(imported / "portfolio.json")
        self.assertEqual(restored["task"], source["task"])
        self.assertEqual(restored["responses"], source["responses"])

    def test_reassessment_from_copied_artifacts_does_not_generate(self) -> None:
        copied = self.fresh("copied")
        copied.mkdir()
        for name in ("portfolio.json", "grading.json"):
            shutil.copyfile(self.baseline / name, copied / name)
        before_output = (copied / "portfolio.json").read_bytes()
        before_engine = source_snapshot(self.baseline / "engine")
        destination = self.fresh("assessment")
        self.cli(
            "assess", "--portfolio", copied / "portfolio.json", "--output", destination,
            "--grading", copied / "grading.json", "--noveltybench", self.upstreams[1],
        )
        self.assertEqual((copied / "portfolio.json").read_bytes(), before_output)
        self.assertEqual(source_snapshot(self.baseline / "engine"), before_engine)
        self.assertFalse((destination / "engine").exists())
        for name in ("mechanical.json", "noveltybench-fixture.json"):
            self.assertTrue((destination / "assessments" / name).is_file())

    def test_invalid_portfolios_fail_explicitly(self) -> None:
        original = read_json(self.baseline / "portfolio.json")
        invalid = {"not-an-object": [], "unsupported-schema": dict(original, schema_version=2)}
        short = copy.deepcopy(original)
        short["responses"].pop()
        invalid["short-portfolio"] = short
        duplicate = copy.deepcopy(original)
        duplicate["responses"][1]["id"] = duplicate["responses"][0]["id"]
        invalid["duplicate-id"] = duplicate
        nontext = copy.deepcopy(original)
        nontext["responses"][0]["text"] = 17
        invalid["nontext"] = nontext
        for label, value in invalid.items():
            with self.subTest(case=label):
                source, output = self.fresh(f"{label}.json"), self.fresh(label)
                write_json(source, value)
                self.cli("export", "--portfolio", source, "--output", output, success=False)

    def test_missing_or_tampered_native_identity_mapping_fails(self) -> None:
        for kind in ("missing", "malformed", "changed-text"):
            with self.subTest(case=kind):
                source = self.fresh(kind)
                shutil.copytree(self.baseline / "native", source)
                if kind == "missing":
                    (source / "identities.json").unlink()
                elif kind == "malformed":
                    write_json(source / "identities.json", [])
                else:
                    row = json.loads((source / "generations.jsonl").read_text().strip())
                    row["generations"][0] += " tampered"
                    (source / "generations.jsonl").write_text(json.dumps(row) + "\n")
                self.cli("import", "--source", source, "--output", self.fresh(f"out-{kind}"), success=False)

    def test_grading_requires_matching_finite_complete_evidence(self) -> None:
        original = read_json(self.baseline / "grading.json")
        scores = [9, None, 8, None, 7, None, 6, None, 5, None]
        for label, replacement in (
            ("missing-head", [None, *scores[1:]]),
            ("nonfinite-head", [float("nan"), *scores[1:]]),
            ("out-of-range-head", [11, *scores[1:]]),
            ("short-scores", scores[:-1]),
        ):
            with self.subTest(case=label):
                grading = copy.deepcopy(original)
                self.assertTrue(replace_vector(grading, scores, replacement))
                path, output = self.fresh(f"{label}.json"), self.fresh(label)
                write_json(path, grading)
                self.cli(
                    "assess", "--portfolio", self.baseline / "portfolio.json",
                    "--output", output, "--grading", path,
                    "--noveltybench", self.upstreams[1], success=False,
                )
                self.assertFalse((output / "assessments/noveltybench-fixture.json").exists())
        wrong = read_json(self.baseline / "portfolio.json")
        wrong["responses"].reverse()
        path = self.fresh("reordered.json")
        write_json(path, wrong)
        self.cli(
            "assess", "--portfolio", path, "--output", self.fresh("wrong-order"),
            "--grading", self.baseline / "grading.json",
            "--noveltybench", self.upstreams[1], success=False,
        )

    def test_declared_checkpoint_resume_is_idempotent_and_rejects_tampering(self) -> None:
        run = self.fresh("checkpoint")
        process = subprocess.run(
            [sys.executable, "-m", "buddha2", "demo", "--output", str(run), "--stop-after-output"],
            cwd=PROJECT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180, check=False,
        )
        self.assertGreaterEqual(process.returncode, 0)
        self.assertTrue((run / "portfolio.json").is_file(), process.stderr)
        self.assertFalse((run / "assessments/noveltybench-fixture.json").exists())
        retained = {name: (run / name).read_bytes() for name in (
            "portfolio.json", "native/generations.jsonl", "native/identities.json",
        )}
        self.cli("demo", "--output", run, "--resume")
        for name, value in retained.items():
            self.assertEqual((run / name).read_bytes(), value)
        finalized = {name: (run / name).read_bytes() for name in FINAL_FILES}
        self.cli("demo", "--output", run, "--resume")
        for name, value in finalized.items():
            self.assertEqual((run / name).read_bytes(), value, name)
        changed = read_json(run / "portfolio.json")
        changed["responses"][0]["text"] += " corrupt saved output"
        write_json(run / "portfolio.json", changed)
        self.cli("demo", "--output", run, "--resume", success=False)

    def test_completed_run_rejects_missing_report_without_repair(self) -> None:
        run = self.fresh("completed")
        shutil.copytree(self.baseline, run)
        report = run / "report.md"
        original = report.read_bytes()
        report.unlink()
        try:
            for command in ("inspect", "resume"):
                with self.subTest(command=command):
                    before = source_snapshot(run)
                    arguments = ("inspect", "--run", run) if command == "inspect" else (
                        "demo", "--output", run, "--resume",
                    )
                    try:
                        self.cli(*arguments, success=False)
                    finally:
                        self.assertEqual(source_snapshot(run), before)
                    self.assertFalse(report.exists())
        finally:
            report.write_bytes(original)

    def test_completed_run_requires_exact_completion_record(self) -> None:
        run = self.fresh("completed")
        shutil.copytree(self.baseline, run)
        path = run / "completion.json"
        original_bytes = path.read_bytes()
        original = read_json(self.baseline / "completion.json")
        cases = {"not-object": []}
        for field, value in (
            ("schema_version", True), ("fixture", False), ("status", "checkpoint"),
            ("run_id", "0" * 64), ("portfolio_sha256", "0" * 64),
            ("provider_calls", False), ("report_sha256", "0" * 64),
            ("assessments", {"mechanical": "0" * 64}),
        ):
            cases[field] = dict(original, **{field: value})
        cases["extra-field"] = dict(original, unrecorded="extra")
        changed_digest = copy.deepcopy(original)
        changed_digest["assessments"]["mechanical"] = "0" * 64
        cases["assessment-digest"] = changed_digest
        for label, record in cases.items():
            write_json(path, record)
            try:
                for command in ("inspect", "resume"):
                    with self.subTest(case=label, command=command):
                        before = source_snapshot(run)
                        arguments = ("inspect", "--run", run) if command == "inspect" else (
                            "demo", "--output", run, "--resume",
                        )
                        try:
                            self.cli(*arguments, success=False)
                        finally:
                            self.assertEqual(source_snapshot(run), before)
            finally:
                path.write_bytes(original_bytes)

    def test_completed_run_rejects_missing_corrupt_or_symlinked_evidence(self) -> None:
        run = self.fresh("completed")
        shutil.copytree(self.baseline, run)
        cases = (
            ("report.md", "corrupt"),
            ("report.md", "symlink"),
            ("assessments/mechanical.json", "missing"),
            ("assessments/mechanical.json", "corrupt"),
            ("assessments/noveltybench-fixture.json", "missing"),
            ("assessments/noveltybench-fixture.json", "corrupt"),
            ("assessments/noveltybench-fixture.json", "symlink"),
            ("completion.json", "symlink"),
            ("completion.json", "dangling-symlink"),
            ("output.json", "missing"),
        )
        for index, (relative, change) in enumerate(cases):
            path = run / relative
            original_bytes = path.read_bytes()
            target = self.fresh(f"symlink-target-{index}")
            try:
                if change == "corrupt":
                    if path.suffix == ".json":
                        record = read_json(path)
                        record["fixture"] = False
                        write_json(path, record)
                    else:
                        path.write_text("altered completed report\n", encoding="utf-8")
                elif change == "missing":
                    path.unlink()
                else:
                    if change == "symlink":
                        target.write_bytes(original_bytes)
                    path.unlink()
                    path.symlink_to(target)
                for command in ("inspect", "resume"):
                    with self.subTest(artifact=relative, change=change, command=command):
                        before = source_snapshot(run)
                        arguments = ("inspect", "--run", run) if command == "inspect" else (
                            "demo", "--output", run, "--resume",
                        )
                        try:
                            self.cli(*arguments, success=False)
                        finally:
                            self.assertEqual(source_snapshot(run), before)
                        if "symlink" in change:
                            self.assertTrue(path.is_symlink())
            finally:
                if path.is_symlink():
                    path.unlink()
                path.write_bytes(original_bytes)
                target.unlink(missing_ok=True)

    def test_parent_and_subprocess_have_no_network_or_credentials(self) -> None:
        self.assertEqual(sorted(p.name for p in Path("/sys/class/net").iterdir()), ["lo"])
        active_defaults = [
            line for line in Path("/proc/net/route").read_text().splitlines()[1:]
            if (fields := line.split())[1] == "00000000" and int(fields[3], 16) & 1
        ]
        self.assertEqual(active_defaults, [])
        probe = subprocess.run(
            [sys.executable, "-c", (
                "import json,pathlib; "
                "print(json.dumps(sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir())))"
            )], capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertEqual(json.loads(probe.stdout), ["lo"])
        self.assertFalse([name for name in CREDENTIAL_NAMES if os.environ.get(name)])

    def test_nonfixture_mode_refuses_before_dispatch(self) -> None:
        output = self.fresh("live-refusal")
        self.cli("demo", "--output", output, "--mode", "live", success=False)
        self.assertFalse((output / "engine").exists())


if __name__ == "__main__":
    unittest.main()
