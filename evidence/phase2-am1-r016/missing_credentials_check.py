"""Contained acceptance check: absent explicit keys never construct SDK clients."""

import json
from unittest.mock import patch

from buddha2.artifacts import ContractError
from buddha2.phase2_am1_controls import CONTROL_POLICY
from buddha2.phase2_dispatch import DirectSDKTransport

cases = (("", "fixture-not-a-secret"), ("fixture-not-a-secret", ""), ("", ""),
         ("   ", "fixture-not-a-secret"))
rejected = 0
with patch("anthropic.Anthropic", side_effect=AssertionError("SDK construction is forbidden")) as anthro, \
        patch("openai.OpenAI", side_effect=AssertionError("SDK construction is forbidden")) as openai:
    for anthropic_key, openai_key in cases:
        try:
            DirectSDKTransport(anthropic_api_key=anthropic_key, openai_api_key=openai_key,
                               control_policy=CONTROL_POLICY)
        except ContractError as exc:
            assert str(exc) == "explicit keys for both providers are required"
            rejected += 1
        else:
            raise AssertionError("absent key was accepted")
    assert anthro.call_count == openai.call_count == 0
assert rejected == len(cases)
print(json.dumps({"kind": "am1-missing-credential-check", "status": "pass",
                  "cases": rejected, "sdk_clients_constructed": 0, "provider_calls": 0,
                  "real_credentials_accessed": False}))
