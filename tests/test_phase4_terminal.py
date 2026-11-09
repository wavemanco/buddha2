"""Settled P4 refusals/truncations close a cell; unknown or changed history still stops."""
from __future__ import annotations

import copy
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlparse

from harness2.core.proposer import Proposer
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest
from followups.phase3b_seq2_v1 import adapter, editor, native
from followups.phase3b_seq2_v1.history import HistoryGuard, KnownProviderTerminalStop
from followups.phase3b_seq2_v1.support import BASE
from tests.test_phase4_policy import profile_for


def request():
    return {"model": "claude-opus-5", "max_tokens": 16000, "stream": True,
        "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
        "system": [{"type": "text", "text": "Synthetic fixture instructions."}],
        "messages": [{"role": "user", "content": "Synthetic fixture invocation."}]}


def result(slot, role, body, reason):
    return {"slot_id": slot, "role": role, "status": "response", "fixture": True,
        "request_sha256": digest(body), "spent_micro_usd": 42, "reserved_micro_usd": 0,
        "response": {"provider_response": {"stop_reason": reason,
            "content": [{"type": "text", "text": "Synthetic incomplete response."}]}}}


class Phase4TerminalTests(unittest.TestCase):
    def test_only_settled_p4_terminal_outcomes_have_cell_failure_disposition(self):
        body = editor.effective_request(request(), turn=1)
        for role in ("editor", "native_selector"):
            label = "select.seq2" if role == "native_selector" else "c2.a1"
            prefix = "p4-01.adaptive.editor." + label
            slot = prefix + ".t01"
            for reason in ("refusal", "max_tokens"):
                with self.subTest(role=role, reason=reason):
                    response = result(slot, role, body, reason)
                    delegate = Mock(return_value=response)
                    guard = HistoryGuard(delegate, prefix, known_terminal=True)
                    with self.assertRaises(KnownProviderTerminalStop) as stopped:
                        guard(slot, role, body)
                    self.assertEqual(stopped.exception.evidence, {"slot_id": slot, "role": role,
                        "stop_reason": reason, "result_sha256": digest(response)})
                    with self.assertRaises(ContractError):
                        guard(prefix + ".t02", role, body)
                    self.assertEqual(delegate.call_count, 1)
                    for changed in (response | {"status": "unknown"}, response | {"reserved_micro_usd": 11_440_000}):
                        with self.assertRaises(ContractError) as unknown:
                            HistoryGuard(lambda *a: changed, prefix, known_terminal=True)(slot, role, body)
                        self.assertNotIsInstance(unknown.exception, KnownProviderTerminalStop)
                    with self.assertRaises(ContractError) as legacy:
                        HistoryGuard(lambda *a: response, prefix)(slot, role, body)
                    self.assertNotIsInstance(legacy.exception, KnownProviderTerminalStop)
        delegate = Mock()
        with self.assertRaises(ContractError):
            HistoryGuard(delegate, "p4-01.adaptive.editor.c2.a1", known_terminal=True)(
                "wrong.t01", "editor", body)
        delegate.assert_not_called()

    def test_actual_local_relay_retains_terminal_slot_and_never_resends_or_global_halts(self):
        """Real loopback HTTP only; this method is separate from socket-blocked pure checks."""
        BASE.mkdir(parents=True, exist_ok=True)
        profile, _ = profile_for()
        for reason in ("refusal", "max_tokens"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory(prefix="p4-terminal-", dir=BASE) as temporary:
                body = request()
                prefix = "p4-01.adaptive.editor.c2.a1"
                dispatch = Mock(side_effect=lambda slot, role, value: result(slot, role, value, reason))
                halt = Mock()
                record = {"fixture": True, "requests": [], "terminal_note_used": False}
                with editor.relay(Path(temporary), dispatch, prefix, record, halt,
                                  prepared={}, request_policy=profile) as (url, _):
                    address = urlparse(url)
                    for _ in range(2):
                        connection = http.client.HTTPConnection(address.hostname, address.port, timeout=10)
                        try:
                            connection.request("POST", address.path + "/messages", json.dumps(body),
                                {"content-type": "application/json", "x-api-key": editor._FALSE})
                            response = connection.getresponse()
                            response.read()
                            self.assertEqual(response.status, 403)
                        finally:
                            connection.close()
                self.assertEqual(dispatch.call_count, 1)
                self.assertEqual(len(record["requests"]), 1)
                self.assertEqual(record["known_provider_terminal"]["stop_reason"], reason)
                self.assertEqual(record["requests"][0]["result_sha256"],
                                 record["known_provider_terminal"]["result_sha256"])
                self.assertNotIn("error", record)
                halt.assert_not_called()

    def test_native_dispatch_backstop_survives_a_swallowed_proposer_failure(self):
        profile, _ = profile_for()
        prop = object.__new__(Proposer)
        prop.spec = ChannelSpec("opencode", "anthropic/claude-opus-5", effort="high",
                                steps=editor.MAX_STEPS, timeout=native.NATIVE_TIMEOUT)
        prop.attempts, prop._known_provider_terminal = 1, None
        terminal = {"slot_id": "p4-01.adaptive.editor.c2.a1.t01", "role": "editor",
                    "stop_reason": "refusal", "result_sha256": "a" * 64}
        waiting = object.__new__(adapter.CompatibleProposer)
        waiting._known_provider_terminal = terminal
        with patch.object(editor.AccountedProposer, "_opencode") as handoff, \
                self.assertRaises(KnownProviderTerminalStop):
            waiting._opencode(None, "synthetic", "synthetic", 1)
        handoff.assert_not_called()
        dispatch = Mock()
        captured = {}

        def make_adapter(*a, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(spec=SimpleNamespace(runs_root=Path("/results/synthetic")),
                                   optional_probe_failures=lambda label: {})

        def swallowed(*a, **kwargs):
            prop._known_provider_terminal = copy.deepcopy(terminal)
            with self.assertRaises(KnownProviderTerminalStop):
                captured["dispatch"]("synthetic-next-slot", "answer", {})
            return None

        BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="p4-terminal-native-", dir=BASE) as temporary:
            modules = native._modules()
            with patch.object(native, "PortfolioAdapter", side_effect=make_adapter), \
                    patch.object(modules["schedule"], "run_task", side_effect=swallowed), \
                    self.assertRaises(KnownProviderTerminalStop):
                native._run_adaptation({"id": "synthetic"}, Path(temporary), study_sha256="a" * 64,
                    run_root=Path(temporary) / "native", tag="synthetic", dispatch=dispatch,
                    fixture=True, prop=prop, request_policy=profile)
        dispatch.assert_not_called()
