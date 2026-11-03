"""R3 changes the declared native channel, never bypassing profile validation."""
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.core.proposer import Proposer
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v4 import native


class NativeProfileTests(unittest.TestCase):
    def test_old_eight_step_native_profile_is_rejected_before_execution(self):
        prop = Proposer(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=8, timeout=600))
        with self.assertRaises(ContractError):
            native.run_adaptation({"id": "SYNTHETIC"}, Path("/not-read"), study_sha256="a" * 64,
                run_root=Path("/not-created"), tag="SYNTHETIC", dispatch=lambda *a: self.fail("dispatch forbidden"),
                fixture=True, prop=prop)

    def test_saved_native_result_without_r3_binding_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "profile/source"):
            native.validate_adaptation({}, {"id": "SYNTHETIC"}, Path("/not-read"), study_sha256="a" * 64,
                run_root=Path("/not-read"), tag="SYNTHETIC", fixture=True, results={})

    def test_sixteen_profile_reaches_native_adapter_with_exact_channel(self):
        prop = Proposer(ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high", steps=16, timeout=600))
        class ReachedAdapter(RuntimeError):
            pass
        with patch.object(native, "PortfolioAdapter", side_effect=ReachedAdapter) as adapter, \
                patch.object(native.strategy, "_path", return_value=Path("/tmp/synthetic-native-r3")):
            with self.assertRaises(ReachedAdapter):
                native.run_adaptation({"id": "SYNTHETIC"}, Path("/not-read"), study_sha256="a" * 64,
                    run_root=Path("/not-created"), tag="SYNTHETIC", dispatch=lambda *a: self.fail("dispatch forbidden"),
                    fixture=True, prop=prop)
        self.assertEqual(adapter.call_args.kwargs["channel"], prop.spec)
