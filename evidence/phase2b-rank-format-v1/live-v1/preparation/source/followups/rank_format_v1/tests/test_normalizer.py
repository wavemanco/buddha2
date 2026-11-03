"""N1 acceptance tests against fixtures committed before implementation."""

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.rank_format_v1.normalizer import normalize_rank

FIXTURES = Path(__file__).with_name("fixtures.json")
FIXTURE_SHA256 = "e4acded332abb48de58f92cdfaaa728027ae0d0e1dd0b0dca15ddadc97e91d2c"


class NormalizerTests(unittest.TestCase):
    fixture: dict
    cases: dict

    @classmethod
    def setUpClass(cls):
        raw = FIXTURES.read_bytes()
        if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
            raise AssertionError("prefrozen N1 fixtures changed")
        cls.fixture = json.loads(raw.decode("utf-8"))
        cls.cases = {row["id"]: row for row in cls.fixture["cases"]}

    def inputs(self, case):
        return case["text"], copy.deepcopy(case.get("parent_ids", self.fixture["default_parent_ids"]))

    def test_prefrozen_acceptance_and_rejection_cases(self):
        self.assertEqual(len(self.cases), 76)
        for name, case in self.cases.items():
            with self.subTest(case=name):
                text, parents = self.inputs(case)
                before = copy.deepcopy((text, parents))
                result = normalize_rank(text, parents)
                self.assertEqual(set(result), {"policy_id", "status", "order", "candidates", "reason"})
                self.assertEqual(result["policy_id"], "rank-format-N1")
                self.assertEqual(result["status"], case["expected_status"])
                self.assertEqual(result["reason"], case["expected_reason"])
                self.assertEqual(result["order"], case["expected_order"])
                self.assertEqual((text, parents), before)
                self.assertEqual(normalize_rank(text, parents), result)
                json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
                if result["status"] == "accepted":
                    self.assertTrue(result["candidates"])
                    for candidate in result["candidates"]:
                        self.assertEqual(candidate["order"], case["expected_order"])
                        self.assertEqual(json.loads(text[candidate["start"]:candidate["end"]]),
                                         {"order": case["expected_order"]})
                    if "expected_candidate_spans" in case:
                        self.assertEqual([[row["start"], row["end"]] for row in result["candidates"]],
                                         case["expected_candidate_spans"])
                else:
                    self.assertIsNone(result["order"])

    def test_encoding_size_and_depth_guards_precede_json_parsing(self):
        names = ("invalid-utf8-surrogate", "utf8-size-over-limit", "utf8-byte-not-character-limit",
                 "very-deep-input", "nested-wrapper-object", "nested-order-array")
        for name in names:
            with self.subTest(case=name):
                case = self.cases[name]
                with patch("followups.rank_format_v1.normalizer.json.loads",
                           side_effect=AssertionError("resource guard must precede JSON parsing")):
                    result = normalize_rank(*self.inputs(case))
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["reason"], case["expected_reason"])

    def test_seventeenth_candidate_is_not_parsed_or_selected(self):
        original = json.loads
        with patch("followups.rank_format_v1.normalizer.json.loads", wraps=original) as decoder:
            result = normalize_rank(*self.inputs(self.cases["seventeen-identical-objects"]))
        self.assertEqual(decoder.call_count, 16)
        self.assertEqual(result["reason"], "object_count_limit")
        self.assertIsNone(result["order"])

    def test_parent_order_cannot_choose_or_sort_the_proposed_order(self):
        text, parents = self.inputs(self.cases["reverse-order-preserved"])
        first = normalize_rank(text, parents)
        second = normalize_rank(text, parents[::-1])
        self.assertEqual(first, second)
        self.assertEqual(first["order"], self.cases["reverse-order-preserved"]["expected_order"])

    def test_returned_lists_do_not_alias_parent_or_each_other(self):
        text, parents = self.inputs(self.cases["identical-adjacent-objects"])
        before = parents.copy()
        result = normalize_rank(text, parents)
        result["order"][0] = "changed-by-caller"
        self.assertEqual(parents, before)
        self.assertEqual(result["candidates"][0]["order"], before)
        result["candidates"][0]["order"][0] = "another-change"
        self.assertEqual(result["candidates"][1]["order"], before)

    def test_normalization_performs_no_file_network_or_environment_lookup(self):
        text, parents = self.inputs(self.cases["identical-repeat-with-prose"])
        with patch("builtins.open", side_effect=AssertionError("no file access")), \
                patch("socket.socket", side_effect=AssertionError("no network access")), \
                patch("os.getenv", side_effect=AssertionError("no environment access")):
            result = normalize_rank(text, parents)
        self.assertEqual(result["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
