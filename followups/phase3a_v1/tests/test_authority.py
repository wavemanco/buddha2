"""R2 carries both stopped episodes and preserves the historical unknown."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError
from followups.phase3a_v1 import support, workflow


class R2AuthorityTests(unittest.TestCase):
    def test_accepted_repeat_cannot_reset_cumulative_caps(self):
        accepted = support.authorization()
        carry = accepted["prior_spent_micro_usd"] + accepted["prior_reserved_micro_usd"]
        self.assertEqual(carry, 14135297)
        self.assertEqual(219995297, carry + accepted["cap_micro_usd"])
        self.assertEqual(64995297, carry + accepted["canary_cap_micro_usd"])
        self.assertEqual(accepted["prior_requests"], 177)
        self.assertEqual(accepted["prior_known_requests"] + accepted["prior_unknown_requests"], 177)
        self.assertEqual(accepted["prior_requests"] + accepted["new_max_provider_attempts"], 952)

    def test_authority_cannot_discard_known_prior_spending(self):
        original = support.read_json
        altered = copy.deepcopy(support.authorization())
        altered["prior_spent_micro_usd"] = 0

        def read(path):
            return altered if Path(path) == support.AUTHORITY else original(path)

        with patch.object(support, "read_json", side_effect=read), self.assertRaises(ContractError):
            support.authorization()

    def test_changed_closed_archive_is_rejected(self):
        original = Path.read_bytes
        for directory in support.PRIORS:
            with self.subTest(episode=str(directory.relative_to(support.ROOT))):
                archive = directory / "archive.zip"
                touched: list[Path] = []

                def read(path):
                    raw = original(path)
                    if path == archive:
                        touched.append(path)
                        return raw + b"corrupted-after-closure"
                    return raw

                with (patch.object(Path, "read_bytes", autospec=True, side_effect=read),
                      self.assertRaisesRegex(ContractError, "prior stopped-run evidence changed")):
                    support.authorization()
                self.assertEqual(touched, [archive])

    def test_authority_cannot_zero_or_release_historical_reservation(self):
        original = support.read_json
        accepted = support.authorization()
        for field, value in (("prior_reserved_micro_usd", 0), ("prior_unknown_requests", 0),
                             ("prior_known_requests", 177), ("historical_unknown_release_authorized", True)):
            with self.subTest(field=field):
                altered = copy.deepcopy(accepted)
                altered[field] = value

                def read(path):
                    return altered if Path(path) == support.AUTHORITY else original(path)

                with patch.object(support, "read_json", side_effect=read), self.assertRaises(ContractError):
                    support.authorization()
        altered = copy.deepcopy(accepted)
        altered["prior_episodes"][1].update(reserved_micro_usd=0, unknown_requests=0, known_requests=91)
        with (patch.object(support, "read_json", side_effect=lambda path:
                altered if Path(path) == support.AUTHORITY else original(path)),
              self.assertRaisesRegex(ContractError, "cannot discard or settle historical")):
            support.authorization()

    def test_fixture_spending_is_never_added_to_real_prior_cost(self):
        study = {"study_sha256": "a" * 64,
                 "prior_live_episode": {"known_spent_micro_usd": 2695297, "reserved_micro_usd": 11440000,
                                        "provider_calls": 177, "known_requests": 176, "unknown_requests": 1}}
        state = {"results": {}, "intents": {}, "cells": {}, "fixture": True,
                 "spent_micro_usd": 355193, "reserved_micro_usd": 0, "provider_calls": 0}
        resource = workflow._resources(study, state)
        self.assertEqual(2695297, resource["prior_real_phase3a_spent_micro_usd"])
        self.assertEqual(11440000, resource["prior_real_phase3a_reserved_micro_usd"])
        self.assertEqual(177, resource["prior_real_phase3a_provider_calls"])
        self.assertEqual(176, resource["prior_real_phase3a_known_responses"])
        self.assertEqual(1, resource["prior_real_phase3a_unknown_responses"])
        for field in ("spent_micro_usd", "reserved_micro_usd", "max_exposure_micro_usd", "provider_calls"):
            self.assertIsNone(resource["cumulative_real_phase3a_" + field])
        self.assertFalse(resource["historical_accounting_settled"])
        self.assertFalse(resource["historical_unknown_released"])
        state.update(fixture=False, spent_micro_usd=123, reserved_micro_usd=456, provider_calls=2)
        resource = workflow._resources(study, state)
        self.assertEqual(2695420, resource["cumulative_real_phase3a_spent_micro_usd"])
        self.assertEqual(11440456, resource["cumulative_real_phase3a_reserved_micro_usd"])
        self.assertEqual(14135876, resource["cumulative_real_phase3a_max_exposure_micro_usd"])
        self.assertEqual(179, resource["cumulative_real_phase3a_provider_calls"])
        state["reserved_micro_usd"] = 0
        resource = workflow._resources(study, state)
        self.assertEqual(11440000, resource["cumulative_real_phase3a_reserved_micro_usd"])
        self.assertFalse(resource["historical_accounting_settled"])
        self.assertFalse(resource["historical_unknown_released"])


if __name__ == "__main__":
    unittest.main()
