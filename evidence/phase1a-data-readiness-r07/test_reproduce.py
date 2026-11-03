"""Boundary oracles for the bounded data inspection; never call a model."""

import unittest

from reproduce import choose, compatible, orientation, stratum


class InspectionRules(unittest.TestCase):
    def test_score_floor_and_margin_are_inclusive(self):
        self.assertEqual(stratum(10, 19), "both_below20")
        self.assertEqual(stratum(15, 20), "straddling20")
        self.assertEqual(stratum(20, 25), "both_at_least20")
        self.assertTrue(compatible("first", 15, "second", 20))
        self.assertFalse(compatible("first", 15, "second", 19))
        self.assertFalse(compatible(" Same  words ", 10, "same words", 30))

    def test_global_rank_unique_groups_and_no_quota_redistribution(self):
        def candidate(rank, group, band):
            return {"rank": rank, "group_id": group, "stratum": band,
                    "response_ids": [rank + "a", rank + "b"]}

        values = [candidate("1", "g1", "high"), candidate("2", "g1", "low"),
                  candidate("3", "g2", "low"), candidate("4", "g3", "high"),
                  candidate("5", "g4", "mixed")]
        selected = choose(list(reversed(values)), {"high": 1, "low": 2, "mixed": 1})
        self.assertEqual([value["rank"] for value in selected], ["1", "3", "5"])
        self.assertEqual(len({value["group_id"] for value in selected}), 3)
        self.assertEqual(choose(values, {"high": 0, "low": 0, "mixed": 0}), [])

    def test_orientation_alternates_canonical_ids_without_scores(self):
        self.assertEqual(orientation(["z", "a"], 0), ["a", "z"])
        self.assertEqual(orientation(["z", "a"], 1), ["z", "a"])


if __name__ == "__main__":
    unittest.main()
