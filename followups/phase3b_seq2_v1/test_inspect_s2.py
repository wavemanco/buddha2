"""Pure twelve-target projection, selected-alias and privacy acceptance checks."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from .inspect_projection import audit_csv
from .snapshot import (
    PILOTS,
    TARGETS,
    CanonicalIntegrityError,
    ProjectionError,
    build_snapshot,
    lexical,
    sha,
    validate_projection,
)


def fixture_records(*, first_only: bool = False, no_calls: bool = False) -> tuple[dict, dict, dict]:
    """Synthetic public values only, not provider-origin or scientific evidence."""
    identity = "a" * 64
    tasks = [{"pilot_id": p, "parent_task_id": "synthetic-" + p,
              "prompt": "SYNTHETIC request " + p} for p in PILOTS]
    rows, aliases, plan, branches, assessments = [], [], [], {}, {}
    for pilot in PILOTS:
        reached = not first_only or pilot == PILOTS[0]
        portfolios = {}
        prompt_rows = {}
        for target in TARGETS:
            arm = "fixed" if target == "fixed" else "adaptive"
            aid = f"fixture:{pilot}:{target}"
            plan.append({"id": aid, "pilot": pilot, "arm": arm, "target": target, "diagnostic": False})
            portfolio = {"fixture": True, "portfolio_id": f"{pilot}-{target}",
                "responses": [{"id": f"{pilot}-{target}-{i}", "text": f"SYNTHETIC ordered answer {i}\nUnicode: \u00f1"}
                              for i in range(10)]} if reached else None
            portfolios[target] = portfolio
            if reached:
                assessments[aid] = {"fixture": True, "status": "scored", "failure": None,
                    "portfolio_sha256": sha(portfolio), "metrics": {"utility": 0.0, "distinct": 1},
                    "native": {"fields": {"generation_scores": [1] + [None] * 9}},
                    "requests": [{"provider_blob": "excluded from projection"}]}
            row = {"pilot": pilot, "parent_task_id": "synthetic-" + pilot, "arm": arm, "target": target,
                "assessment_id": aid, "assessment_sha256": sha(assessments[aid]) if reached else None,
                "final_sha256": sha(portfolio) if reached else None,
                "status": "scored" if reached else "missing_final",
                "branch_status": "complete" if reached else "not_attempted",
                "metrics": {"utility": 0.0, "distinct": 1} if reached else None,
                "authentic": False, "first_answer_quality": 1 if reached else None}
            rows.append(row)
            prompt_rows[target] = row
        aliases.append(copy.deepcopy(prompt_rows["fixed"]))
        native_alias = copy.deepcopy(prompt_rows["c2"])
        native_alias.update(target="selected", selected_checkpoint="c2" if reached else None)
        if not reached:
            native_alias["assessment_id"] = None
        aliases.append(native_alias)
        if reached:
            for arm in ("fixed", "adaptive"):
                portfolio = portfolios["fixed" if arm == "fixed" else "c2"]
                result = {"portfolio": portfolio, "status": "complete"}
                if arm == "adaptive":
                    result.update(checkpoints={key: portfolios[key] for key in ("c1", "c2")}, selected_checkpoint="c2")
                branches[pilot, arm] = {"study_sha256": identity, "pilot": pilot, "arm": arm,
                    "fixture": True, "portfolio_sha256": sha(portfolio), "result": result}
    slots = {"fixture.plan": {"role": "plan", "pair": PILOTS[0], "cell": PILOTS[0] + ":adaptive"},
             "fixture.selector": {"role": "native_selector", "pair": PILOTS[0], "cell": PILOTS[0] + ":adaptive"}}
    requests = [{"slot_id": slot, "role": value["role"], "requested_parameters": {
        "model": "claude-sonnet-5-5" if value["role"] == "plan" else "claude-opus-5"},
        "status": "response", "spent_micro_usd": 0, "reserved_micro_usd": 0,
        "request_sha256": "d" * 64, "result_sha256": "e" * 64} for slot, value in slots.items()]
    if no_calls:
        slots, requests = {}, []
    study = {"study_sha256": identity, "tasks": tasks, "slots": slots, "assessment_plan": plan}
    summary = {"study_sha256": identity, "fixture": True, "scientific_complete": False,
        "complete_primary": not first_only, "first_assessments_closed": True,
        "engineering_review": {"approved": True}}
    report = {"rows": rows, "coverage": {"primary_rows": aliases, "assessment_targets": plan},
        "analysis": {"held_evidence_failure": None}, "summary": summary, "readiness": {"passed": True},
        "accounting": {"spent_micro_usd": 0, "reserved_micro_usd": 0},
        "protocol": {"study_sha256": identity, "source_sha256": "b" * 64,
                     "runtime_sha256": "c" * 64, "requests": requests}}
    saved = {"branches": branches, "assessments": assessments,
        "audit_intervals": {slot: {"started_at_utc": "2026-11-02T21:00:00+00:00",
            "finished_at_utc": "2026-11-02T21:00:01+00:00", "audit_file_sha256": "f" * 64,
            "input_tokens": 1, "output_tokens": 2} for slot in slots},
        "snapshot_observed_at_utc": "2026-11-02T21:00:02+00:00"}
    return study, report, saved


class S2SnapshotTests(unittest.TestCase):
    def test_twelve_targets_and_eight_existing_assessment_aliases(self):
        payload = build_snapshot(*fixture_records(), "closure")
        self.assertEqual((len(payload["rows"]), len(payload["finals"]), len(payload["selected_aliases"])), (12, 12, 8))
        self.assertEqual(len(payload["native_assessments"]), 12)
        self.assertTrue(all("requests" not in v for v in payload["native_assessments"].values()))
        validate_projection(payload)
        self.assertIn("native_selector", audit_csv(payload))
        self.assertIn("target", audit_csv(payload).splitlines()[0])

    def test_first_prompt_keeps_future_targets_absent(self):
        payload = build_snapshot(*fixture_records(first_only=True), "first-pair")
        self.assertEqual(sum(r["status"] == "scored" for r in payload["rows"]), 3)
        self.assertEqual(sum(f["portfolio"] is None for f in payload["finals"]), 9)
        self.assertEqual(len(payload["selected_aliases"]), 8)

    def test_alias_cannot_change_a_checkpoint_score_or_identity(self):
        payload = build_snapshot(*fixture_records(), "closure")
        for field, value in (("assessment_id", "forged"), ("final_sha256", "0" * 64),
                             ("metrics", {"utility": 10, "distinct": 10}), ("selected_checkpoint", "c1")):
            with self.subTest(field=field):
                changed = copy.deepcopy(payload)
                changed["selected_aliases"][1][field] = value
                with self.assertRaises(ProjectionError):
                    validate_projection(changed)

    def test_duplicate_checkpoint_and_unknown_model_role_reject(self):
        payload = build_snapshot(*fixture_records(), "closure")
        changed = copy.deepcopy(payload)
        changed["rows"][2]["target"] = "c1"
        with self.assertRaises(ProjectionError):
            validate_projection(changed)
        payload["requests"][0]["role"] = "undeclared"
        with self.assertRaises(ProjectionError):
            validate_projection(payload)

    def test_matching_other_checkpoint_cannot_replace_the_actual_selected_branch(self):
        study, report, saved = fixture_records()
        replacement = copy.deepcopy(report["rows"][1])
        replacement.update(target="selected", selected_checkpoint="c1")
        report["coverage"]["primary_rows"][1] = replacement
        with self.assertRaises(CanonicalIntegrityError):
            build_snapshot(study, report, saved, "closure")

    def test_no_interval_remains_absent_instead_of_epoch_or_fake_latency(self):
        payload = build_snapshot(*fixture_records(no_calls=True), "closure")
        self.assertEqual(payload["native_audit"]["requests"], [])
        self.assertEqual(payload["native_audit"]["observed_at_utc"], "2026-11-02T21:00:02+00:00")

    def test_private_and_stream_paths_reject_before_metadata(self):
        for value in ("/fixture/AUTH.JSON", "/fixture/.env", "/fixture/a.STDOUT.log",
                      "/fixture/nested/__pycache__/file", "/fixture/credentials.json"):
            with self.subTest(path=value), patch.object(Path, "lstat", side_effect=AssertionError("metadata forbidden")):
                with self.assertRaises(ValueError):
                    lexical(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
