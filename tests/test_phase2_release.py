"""Frozen complete-release preparation and nonsending launch prerequisites."""

import contextlib
import copy
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, read_json, tree_hashes, write_once
from buddha2.phase2 import PROJECT
from buddha2.phase2_release import (
    BUDGET_POLICY,
    _live_readiness,
    _parent,
    cost_sheet,
    launch_preflight,
    load_release,
    main,
    prepare,
    validate_release,
)
from buddha2.phase2_release_journal import (
    AuthorityError,
    LiabilityError,
    ReleaseDispatcher,
    grant_template,
    initialize_journal,
    publish_grant,
    replay_journal,
)


class ReleasePreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-p2r-prep-",
            dir=Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", PROJECT / "runs")))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.prepared = self.root / "prepared"
        prepare(self.prepared)
        self.study_path = self.prepared / "study.json"
        self.study = read_json(self.study_path)
        self.run = self.root / "phase"

    def grant(self, fixture=True):
        return grant_template(self.study, fixture=fixture, stage="first", grant_id="test-explicit-first",
                              cumulative_cap_micro_usd=20_000_000, authorized=not fixture)

    def test_prepare_is_exact_idempotent_and_preserves_scientific_parent(self):
        original = tree_hashes(self.prepared)
        self.assertEqual(prepare(self.prepared)["study_sha256"], self.study["study_sha256"])
        self.assertEqual(original, tree_hashes(self.prepared))
        self.assertEqual(load_release(self.study_path), self.study)
        parent = _parent()
        for name in ("tasks", "worklist", "templates", "profiles", "procedure_hashes", "native_evaluator",
                     "shared_generator_settings_sha256", "human_check", "decision_policies", "failure_policy",
                     "source_audit", "exposure", "lockfiles", "upstream_pins"):
            self.assertEqual(self.study[name], parent[name], name)
        self.assertEqual(len(self.study["worklist"]["slots"]), 1320)
        self.assertEqual(self.study["budget_policy"], BUDGET_POLICY)
        self.assertFalse(read_json(self.prepared / "launch-packet.json")["authorized"])
        self.assertEqual(cost_sheet(self.study)["sum_first_envelopes_micro_usd"], 404086760)
        self.assertEqual(cost_sheet(self.study)["sum_full_envelopes_micro_usd"], 9698082240)

    def test_source_bundle_and_resealed_scientific_or_financial_changes_reject(self):
        for field in ("budget_policy", "tasks"):
            changed = copy.deepcopy(self.study)
            if field == "budget_policy":
                changed[field]["phase_max_micro_usd"] += 1
            else:
                changed[field][0]["prompt"] += " changed"
            changed["study_sha256"] = digest({k: v for k, v in changed.items() if k != "study_sha256"})
            with self.assertRaises(ContractError):
                validate_release(changed)
        first = next((self.prepared / "source").glob("*.py"))
        first.write_text("changed source", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "retained release source"):
            load_release(self.study_path)

    def test_preflight_validates_full_journal_without_publishing_authority_or_constructing_sdk(self):
        grant = self.root / "grant.json"
        write_once(grant, self.grant())
        with (patch("buddha2.phase2_release.canonical_run", return_value=self.run),
              patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=AssertionError("no SDK"))):
            checked = launch_preflight(self.study_path, grant, "first", True)
        self.assertEqual(checked["provider_calls"], 0)
        self.assertFalse(checked["credentials_read"])
        state = replay_journal(self.run / "journal")
        self.assertEqual(state["attempts"], 0)
        self.assertIsNone(state["authority_sha256"])
        self.assertEqual(len(read_json(self.run / "journal/manifest.json")["inputs"]["slots"]), 1320)

    def test_mismatched_mode_stage_and_missing_live_acceptance_fail_before_transport(self):
        for fixture, stage in ((True, "expansion"), (False, "first")):
            path = self.root / f"{fixture}.json"
            write_once(path, self.grant(fixture))
            with (patch("buddha2.phase2_release.canonical_run", return_value=self.run),
                  patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=AssertionError("no SDK"))):
                with self.assertRaises(ContractError):
                    launch_preflight(self.study_path, path, stage, fixture)
        self.assertFalse((self.run / "journal").exists())

    def test_an_existing_grant_cannot_reopen_unknown_liability_during_preflight(self):
        class Ambiguous:
            fixture = True

            def create(self, role, request):
                return {"model": request["model"], "usage": {"input_tokens": 1}}

        from buddha2.phase2 import render_request

        grant = self.grant()
        initialize_journal(self.run / "journal", self.study, fixture=True)
        publish_grant(self.run / "journal", self.study, grant)
        first = next(key for key, row in self.study["worklist"]["slots"].items()
                     if row == {"role": "answer", "checkpoint": "canary"})
        dispatcher = ReleaseDispatcher(self.run / "journal", study=self.study, transport=Ambiguous())
        dispatcher.dispatch(first, "answer", render_request("answer", self.study["tasks"][0]))
        path = self.root / "grant.json"
        write_once(path, grant)
        with patch("buddha2.phase2_release.canonical_run", return_value=self.run):
            with self.assertRaises(LiabilityError):
                launch_preflight(self.study_path, path, "first", True)
        self.assertEqual(replay_journal(self.run / "journal")["attempts"], 1)

    def test_incomplete_offline_gate_cannot_unlock_provider_launch(self):
        body = {"kind": "p2r-offline-release-acceptance", "study_sha256": self.study["study_sha256"],
                "source_sha256": digest(self.study["package_files"]),
                "launcher_sha256": self.study["launcher_sha256"],
                "control_policy_sha256": self.study["control_policy_sha256"],
                "requirements": {f"R-{i}": "pass" for i in range(1, 9)},
                "offline_gate_passed": True, "evidence": {}}
        write_once(self.prepared / "release-readiness.json", body | {"acceptance_sha256": digest(body)})
        with self.assertRaisesRegex(ContractError, "offline release gate"):
            _live_readiness(self.study, self.study_path)

    def test_historical_grant_cannot_misrepresent_active_launch_authority(self):
        initialize_journal(self.run / "journal", self.study, fixture=True)
        old = grant_template(self.study, fixture=True, stage="first", grant_id="old-first",
                             cumulative_cap_micro_usd=10_000_000)
        prior = publish_grant(self.run / "journal", self.study, old)
        current = grant_template(self.study, fixture=True, stage="first", grant_id="topup-first",
                                 cumulative_cap_micro_usd=20_000_000,
                                 previous_authority_sha256=prior["authority_sha256"])
        publish_grant(self.run / "journal", self.study, current)
        old_path, current_path = self.root / "old-grant.json", self.root / "current-grant.json"
        write_once(old_path, old)
        write_once(current_path, current)
        with patch("buddha2.phase2_release.canonical_run", return_value=self.run):
            with self.assertRaises(AuthorityError):
                launch_preflight(self.study_path, old_path, "first", True)
            self.assertEqual(launch_preflight(self.study_path, current_path, "first", True)["grant_sha256"],
                             current["grant_sha256"])

    def test_cli_bad_inputs_never_construct_transport(self):
        bad = self.root / "malformed.json"
        bad.write_text("not JSON", encoding="utf-8")
        with (contextlib.redirect_stderr(io.StringIO()),
              patch("buddha2.phase2_dispatch.DirectSDKTransport", side_effect=AssertionError("no SDK"))):
            self.assertEqual(main(["inspect", "--study", str(bad)]), 2)

    def test_fixture_grant_cannot_be_promoted_and_over_budget_template_is_rejected(self):
        for extra in (("--authorize-live", "--confirm-public-payg"),
                      ("--cap-micro-usd", "20000001")):
            with contextlib.redirect_stderr(io.StringIO()):
                result = main(["grant-template", "--study", str(self.study_path), "--fixture",
                               "--run", str(self.run), "--grant-id", "invalid-proposal",
                               "--output", str(self.root / "rejected"), *extra])
            self.assertEqual(result, 2)
        self.assertFalse((self.root / "rejected/grant.json").exists())


if __name__ == "__main__":
    unittest.main()
