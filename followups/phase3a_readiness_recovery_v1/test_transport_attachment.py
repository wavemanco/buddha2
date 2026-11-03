"""S14: exercise the actual constructor boundary without creating SDK clients."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from buddha2.artifacts import ContractError

from . import transport


class TransportAttachmentTests(unittest.TestCase):
    def test_live_constructor_without_attachment_never_reaches_parent(self):
        receipts: tuple[dict | None, ...] = (None, {})
        for receipt in receipts:
            with self.subTest(receipt=receipt), patch.object(
                transport.parent.Transport, "__init__",
                side_effect=AssertionError("unattached construction reached parent"),
            ) as parent_constructor:
                with self.assertRaises(ContractError):
                    transport.Transport(
                        anthropic_api_key="fixture-not-a-secret",
                        openai_api_key="fixture-not-a-secret",
                        startup_attachment=receipt,
                    )
                parent_constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
