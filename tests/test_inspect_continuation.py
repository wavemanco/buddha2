"""Synthetic continuation projection only; saved-validator/ledger boundaries are injected."""
from __future__ import annotations

import copy
import importlib.util
import json
import socket
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, file_hash
from buddha2.phase2_contracts import make_portfolio
from followups.phase3b_seq2_v1.core_view import ForbiddenActivity
from followups.phase3b_seq2_v1.support import BASE
from followups.phase4_cm1_v1 import release, snapshot, workflow

spec = importlib.util.spec_from_file_location("passive_continuation", Path(__file__).parents[1] / "tools" / "inspect_continuation.py")
projector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projector)
SOURCE = "8c32d27ddfd4c81443c1dc3547845dd0fcfb79538988c75c819ae33d9c6de200"


class ContinuationProjectionTests(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="passive-test-", dir=BASE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "live"
        self.study_path, self.grant_path = self.root / "study.json", self.root / "grant.json"
        self.study = {"study_sha256": "f" * 64, "source_sha256": SOURCE, "source": {"sha256": SOURCE},
            "method_sha256": "9" * 64, "method": {"definition_sha256": "8" * 64},
            "continuation": {"original_method_sha256": "7" * 64, "children": []}}
        self.outcome = {"fixture": False, "status": "paused", "active_child": None,
            "closed_children": [], "attempts": 0, "spent_micro_usd": 0, "reserved_micro_usd": 0,
            "spent_by_allocation_micro_usd": dict.fromkeys(("dev", "inference", "assessment"), 0),
            "reserved_by_allocation_micro_usd": dict.fromkeys(("dev", "inference", "assessment"), 0),
            "historical_held_micro_usd": 22_880_000}
        self.ledgers, self.tasks = {}, {}
        for i in range(1, 25):
            self.tasks[f"p4-{i:02d}"] = {"id": f"synthetic-{i:02d}", "prompt": f"SYNTHETIC prompt {i}",
                "domain": "synthetic", "source_context": {"dataset": "synthetic", "revision": "1" * 40,
                    "source_sha256": "2" * 64, "source_task_id": f"synthetic-{i:02d}"}}
        manifest = {"frozen_method_sha256": "7" * 64, "selected": [{"source_task_id": task["id"],
                    "prompt_sha256": digest(task["prompt"])} for task in self.tasks.values()]}
        manifest["manifest_sha256"] = digest(manifest)
        self.save(self.run / "confirmation-manifest.json", manifest)
        self.save(self.root / "confirmation-manifest.json", manifest)
        self.save(self.grant_path, {"fixture": False})
        self.segment("origin", "dev", "dev02", "a" * 64, 10)
        self.segment("origin", "inference", "p4-01", "b" * 64, 100)
        self.segment("origin", "inference", "p4-02", "c" * 64, 200)
        self.segment("current", "inference", "p4-01", "d" * 64, 300, logical="b" * 64)
        self.segment("current", "assessment", "p4-02", "e" * 64, 400, generation="c" * 64)
        self.portfolios = {}
        for pair, logical in (("p4-01", "b" * 64), ("p4-02", "c" * 64)):
            portfolio = make_portfolio(self.tasks[pair], [{"id": f"answer-{i}", "text": f"Synthetic answer {i}",
                "status": "ok", "request_id": f"request-{i}"} for i in range(10)], method="A", repeat=1,
                model={"requested": "synthetic", "returned": "synthetic"}, settings_sha256="1" * 64,
                procedure_sha256="2" * 64, request_ids=[f"request-{i}" for i in range(10)], study_sha256=logical)
            self.portfolios[pair] = portfolio
            generation = {"pair": pair, "task": self.tasks[pair], "generation_study_sha256": logical,
                "adaptive": {"status": "complete"}, "fixed": {"portfolio": portfolio, "status": "complete"}}
            self.save(self.run / "generations" / (pair + ".json"), generation)
            if pair == "p4-02":
                entry = self.study["continuation"]["children"][-1]
                origin_result = Path(entry["open"]["path"]).parent / "result.json"
                self.save(origin_result, generation)
                entry["result"] = {"path": str(origin_result), "file_sha256": file_hash(origin_result)}
        bundle = {"kind": "phase4-cm1-target-assessment-v1", "fixture": False,
            "portfolio_sha256": digest(self.portfolios["p4-02"]), "official": {"fixture": False,
                "task_id": "synthetic-02", "portfolio_sha256": digest(self.portfolios["p4-02"]),
                "metrics": {"utility": 4.25, "distinct": 5}, "status": "scored"},
            "quality_scores": [8, 9], "quality_failures": [], "sensitivity": {"reverse": {"utility": 3.5}},
            "complete": True}
        bundle["sha256"] = digest(bundle)
        row = {"pair": "p4-02", "prompt_id": "synthetic-02", "selected_checkpoint": None,
               "targets": {"fixed": bundle, "c1": None, "c2": None}}
        assessment_folder = Path(self.outcome["closed_children"][-1]["path"])
        self.save(assessment_folder / "result.json", row)
        self.save(self.run / "combined-assessments.json", {"rows": [row]})
        self.save(self.run / "analysis.json", {"pairs": [{"prompt_id": "synthetic-02", "quality_mean": 8.5}],
                                               "scientific_complete": False})
        self.persist()

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def persist(self):
        self.save(self.study_path, self.study)
        self.save(self.run / "outcome.json", self.outcome)

    def segment(self, origin, kind, pair, child, cost, *, logical=None, generation=None):
        folder = (self.root / "original" if origin == "origin" else self.run / "children") / (kind + "-" + pair)
        profile = {"kind": kind, "pair": pair}
        if logical:
            profile["continuation"] = {"logical_study_sha256": logical}
        opened = {"child_sha256": child, "task": self.tasks.get(pair, self.tasks["p4-01"]),
                  "profile": {"phase4_child": profile}, "generation_study_sha256": generation}
        self.save(folder / "open.json", opened)
        if origin == "origin":
            self.study["continuation"]["children"].append({"kind": kind, "pair": pair,
                "open": {"path": str(folder / "open.json"), "file_sha256": file_hash(folder / "open.json")}})
        else:
            self.outcome["closed_children"].append({"kind": kind, "pair": pair, "path": str(folder)})
        request = {"model": "synthetic", "messages": [{"content": "RAW BODY MUST STAY PRIVATE"}]}
        intent = {"request": request, "role": "answer", "study_sha256": logical or child,
                  "request_sha256": digest(request), "reservation": {"micro_usd": cost}}
        result = {"status": "response", "input_tokens": 5, "output_tokens": 3, "spent_micro_usd": cost,
                  "response": {"model": "synthetic", "usage": {"input_tokens": 2, "output_tokens": 3,
                    "cache_read_input_tokens": 3}}}
        state = {"study_sha256": child, "intents": {child: intent}, "results": {child: result},
                 "attempts": 1, "spent_micro_usd": cost, "reserved_micro_usd": 0}
        audit = {"budget": {"started_utc": "2026-11-09T12:00:00Z"},
                 "finished_utc": "2026-11-09T12:00:01Z", "elapsed_seconds": 1}
        self.ledgers[child] = (folder, state, {"inputs": {"study_sha256": child, "fixture": False}}, {child: audit})
        self.outcome["attempts"] += 1
        self.outcome["spent_micro_usd"] += cost
        self.outcome["spent_by_allocation_micro_usd"][kind] += cost

    def build(self, *, report_error=None, source=None):
        def report(*_):
            with self.assertRaises(ForbiddenActivity):
                socket.create_connection(("invalid.example", 443))
            if report_error:
                raise report_error
            return copy.deepcopy(self.outcome)

        with ExitStack() as stack:
            stack.enter_context(patch.object(workflow, "load_study", return_value=copy.deepcopy(self.study)))
            validator = stack.enter_context(patch.object(workflow, "report", side_effect=report))
            stack.enter_context(patch.object(release, "paths", return_value=(self.run, None)))
            stack.enter_context(patch.object(release, "source_identity", return_value=source or self.study["source"]))
            ledger = stack.enter_context(patch.object(snapshot, "_ledger", side_effect=lambda opened, *_:
                                                     copy.deepcopy(self.ledgers[opened["child_sha256"]])))
            payload = projector.build_snapshot(self.study_path, self.grant_path)
            self.assertEqual(validator.call_count, 1)
            self.assertEqual(ledger.call_count, 5)
            return payload

    def test_segments_adoption_cost_scopes_missing_cases_and_metadata_survive_without_dispatch(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*.json")}
        self.study["continuation"]["children"].append(copy.deepcopy(self.study["continuation"]["children"][1]))
        self.persist()
        before[self.study_path] = self.study_path.read_bytes()
        value = self.build()
        first, adopted, missing = value["cases"][:3]
        self.assertEqual(len(value["cases"]), 24)
        self.assertEqual(len(value["physical_executions"]), 5)
        self.assertEqual(first["generation_study_sha256"], "b" * 64)
        self.assertEqual(first["events"][1]["data"]["request_study_sha256"], "b" * 64)
        self.assertEqual(first["events"][1]["data"]["child_sha256"], "d" * 64)
        self.assertAlmostEqual(first["model_usage"]["synthetic"]["total_cost"], 0.0004)
        self.assertIsNone(first["model_usage"]["synthetic"]["input_tokens_cache_write"])
        self.assertEqual(adopted["generation_study_sha256"], "c" * 64)
        self.assertEqual(adopted["metrics"]["targets"]["fixed"]["quality_scores"], [8, 9])
        self.assertEqual(adopted["metrics"]["targets"]["fixed"]["official"]["metrics"]["distinct"], 5)
        self.assertEqual(adopted["metrics"]["targets"]["fixed"]["sensitivity"]["reverse"]["utility"], 3.5)
        self.assertEqual(adopted["metrics"]["analysis_panel"]["quality_mean"], 8.5)
        self.assertIsNone(missing["outputs"])
        self.assertIsNone(missing["started_at"])
        self.assertEqual(value["accounting"]["spent_micro_usd"], 1010)
        self.assertAlmostEqual(value["qualification"]["model_usage"]["synthetic"]["total_cost"], 0.00001)
        self.assertEqual(value["original_frame_method_sha256"], "7" * 64)
        self.assertEqual(value["execution_method_sha256"], "9" * 64)
        self.assertNotIn("RAW BODY", json.dumps(value))
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*.json")})

    def test_saved_validator_and_source_guard_fail_closed(self):
        with self.assertRaisesRegex(ContractError, "saved validation failed"):
            self.build(report_error=ContractError("saved validation failed"))
        with self.assertRaisesRegex(ContractError, "artifacts changed"):
            self.build(source={"sha256": "0" * 64})
        self.outcome["spent_micro_usd"] += 1
        self.persist()
        with self.assertRaisesRegex(ContractError, "does not reconcile"):
            self.build()

    def test_completed_origin_output_survives_before_successor_publishes_adoption(self):
        (self.run / "generations" / "p4-02.json").unlink()
        adopted = self.build()["cases"][1]
        self.assertEqual(adopted["generation_study_sha256"], "c" * 64)
        self.assertEqual(adopted["outputs"]["fixed"], self.portfolios["p4-02"])
        self.assertEqual(adopted["metrics"]["targets"]["fixed"]["official"]["metrics"]["utility"], 4.25)

    def test_passive_files_are_outside_frozen_scientific_source(self):
        source = release.source_identity()
        self.assertNotIn("tools/inspect_continuation.py", source["files"])
        self.assertNotIn("tests/test_inspect_continuation.py", source["files"])


if __name__ == "__main__":
    unittest.main()
