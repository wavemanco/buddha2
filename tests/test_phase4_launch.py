"""P4 uses the retained inspected/masked launcher, with an explicit lazy backend."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from buddha2.artifacts import ContractError, write_once
from followups import phase4_cm1_v1
from followups.phase3b_seq2_v1 import launch
from followups.phase3b_seq2_v1.support import BASE


class Phase4LaunchTests(unittest.TestCase):
    def setUp(self):
        parent = BASE / "phase4-launch-unit"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.study = Path(self.temp.name) / "study.json"
        self.grant = Path(self.temp.name) / "grant.json"
        write_once(self.study, {"kind": "buddha2-phase4-cm1-v1"})
        self.backend = SimpleNamespace(preflight=Mock(return_value={"fixture": False}),
            run=Mock(return_value={"synthetic": True}), claim=Mock())

    def test_preflight_routes_current_mode_and_supervisor_to_phase4_before_legacy(self):
        with patch.object(phase4_cm1_v1, "workflow", self.backend, create=True), \
                patch.object(launch.accounting, "runtime_guard"), \
                patch.object(launch, "_workflow_preflight") as legacy:
            result = launch.preflight(self.study, self.grant, "all", "provider",
                supervisor_agent="/root/phase4_launch")
        self.assertEqual(result, {"fixture": False})
        self.backend.preflight.assert_called_once_with(self.study, self.grant, "all", "provider",
            supervisor_agent="/root/phase4_launch")
        legacy.assert_not_called()

    def test_configuration_only_delegation_preserves_fixture_and_run_arguments(self):
        with patch.object(phase4_cm1_v1, "workflow", self.backend, create=True):
            value = launch._workflow_preflight(self.study, self.grant, False, "all", configuration_only=True)
            self.assertEqual(value, {"fixture": False})
            self.backend.preflight.assert_called_once_with(self.study, self.grant, "all", "provider-config")
            transport = object()
            self.assertEqual(launch._workflow_run(self.study, self.grant, "all", transport), {"synthetic": True})
            self.backend.run.assert_called_once_with(self.study, self.grant, stage="all", transport=transport)
            self.backend.preflight.return_value = {"fixture": True}
            with self.assertRaisesRegex(ContractError, "fixture differs"):
                launch._workflow_preflight(self.study, self.grant, False, "all")

    def test_claim_uses_only_declared_backend_and_preserves_legacy_route(self):
        checked = {"synthetic": "preflight identity"}
        with patch.object(phase4_cm1_v1, "workflow", self.backend, create=True), \
                patch.object(launch, "_live_study_claim") as legacy:
            launch._claim_study(self.study, checked)
            self.backend.claim.assert_called_once_with(checked)
            legacy.assert_not_called()
            old = Path(self.temp.name) / "legacy.json"
            write_once(old, {"kind": "buddha2-effective-seq2-study-v2"})
            launch._claim_study(old, checked)
            legacy.assert_called_once_with(checked, publish=True)
