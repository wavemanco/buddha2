"""Frozen MuCE source boundaries and deterministic preparation, using synthetic rows."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError, digest, read_json
from buddha2.muce import SOURCE, prepare_muce, select_population, validate_policy


def policy(**changes):
    value = {
        "schema_version": 1, "selection_revision": "phase1-muce-v1", **SOURCE,
        "construct": "creativity", "seed": 20261024, "min_margin": 5,
        "families": {"Metaphors": {"calibration": 1, "audit": 1}},
        "exposure_patterns": {"Metaphors": ["the hot tea is"]}, "aliases": {},
        "effective_prompt": "FullPrompt-or-Prompt",
        "population_authorization": "Synthetic unit-test population only.",
    }
    value.update(changes)
    return value


def rows(count=4):
    values = []
    for index in range(count):
        for number, score in enumerate((15.0, 25.0, 35.0)):
            values.append({
                "ID": "expected-reused-id", "Dataset": "synthetic-source",
                "Set": "Training", "DatasetsSplit": "synthetic-source", "Language": "english",
                "Prompt": f"Synthetic metaphor topic {index}", "RatingLabel": "creativity",
                "Response": f"Synthetic response {index}/{number}", "TasksNamesFull": "Metaphors",
                "TaskType": "Text", "facsco_grm_scaled": score,
                "FullPrompt": f"Give a metaphor for synthetic topic {index}.",
            })
    return values


class MucePreparationTests(unittest.TestCase):
    def test_source_identity_and_policy_are_frozen_before_selection(self):
        validate_policy(policy())
        for changes in (
            {"seed": 1}, {"min_margin": 0}, {"min_margin": True}, {"split": "test"},
            {"revision": "stale"}, {"construct": "quality"}, {"aliases": {"a": "b"}},
            {"families": {"Metaphors": {"calibration": True, "audit": 1}}},
            {"population_authorization": ""}, {"unexpected": "hidden-control"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                validate_policy(policy(**changes))

    def test_deterministic_separation_and_no_labels_in_critic_inputs(self):
        first = select_population(rows(), policy())
        second = select_population(list(reversed(rows())), policy())
        self.assertEqual(first["pairs"], second["pairs"])
        self.assertEqual(first["worklists"], second["worklists"])
        self.assertEqual(first["status"], "prepared")
        self.assertEqual(len(first["pairs"]), 2)
        work = first["worklists"]
        self.assertTrue(set(work["calibration"]["pair_ids"]).isdisjoint(work["audit"]["pair_ids"]))
        for stage in ("calibration", "audit"):
            self.assertEqual(len(work[stage]["presentations"]), 2)
            self.assertEqual(work[stage]["presentations"][0]["order"], list(reversed(work[stage]["presentations"][1]["order"])))
        raw = json.dumps({"pairs": first["pairs"], "worklists": work})
        for forbidden in ("preferred_response_id", "facsco_grm_scaled", "RatingLabel", "Dataset", "rating_context"):
            self.assertNotIn(forbidden, raw)
        self.assertEqual(len(first["labels"]["audit"]), 1)

    def test_quotas_fail_before_any_allocation_and_no_silent_construct_substitution(self):
        values = rows(1)
        result = select_population(values, policy())
        self.assertEqual(result["status"], "population_shortfall")
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["labels"], {"calibration": [], "audit": []})
        self.assertEqual(result["worklists"]["audit"]["pair_ids"], [])
        values = rows()
        for row in values:
            row["RatingLabel"] = "originality"
        result = select_population(values, policy())
        self.assertEqual(result["counts"]["Metaphors"]["eligible_prompt_groups"], 0)
        self.assertEqual(result["pairs"], [])

    def test_same_prompt_aliases_across_sources_are_one_independent_group(self):
        values = rows(1)
        aliases = copy.deepcopy(values)
        for row in aliases:
            row["Dataset"] = row["DatasetsSplit"] = "second-source"
            row["Prompt"] = "  SYNTHETIC\u00a0METAPHOR TOPIC 0 "
        result = select_population(values + aliases, policy())
        self.assertEqual(result["status"], "population_shortfall")
        self.assertEqual(result["counts"]["Metaphors"]["eligible_prompt_groups"], 1)
        self.assertEqual(result["counts"]["Metaphors"]["eligible_context_groups"], 2)

    def test_identical_effective_prompts_cannot_cross_the_split(self):
        values = rows(2)
        for row in values:
            row["FullPrompt"] = "The same effective task, with different source descriptors."
        result = select_population(values, policy())
        self.assertEqual(result["status"], "population_shortfall")
        self.assertEqual(result["counts"]["Metaphors"]["eligible_prompt_groups"], 1)
        self.assertEqual(result["pairs"], [])

    def test_blank_full_prompt_uses_raw_prompt_without_merging_distinct_groups(self):
        values = rows()
        for row in values:
            row["FullPrompt"] = "  \t "
        result = select_population(values, policy())
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["counts"]["Metaphors"]["eligible_prompt_groups"], 4)
        self.assertEqual(len({pair["prompt_group_sha256"] for pair in result["pairs"]}), 2)

    def test_exposed_group_removed_across_source_variants(self):
        values = rows()
        for row in values[:3]:
            row["Prompt"] = "The hot tea is..."
        result = select_population(values, policy(families={"Metaphors": {"calibration": 2, "audit": 2}}))
        self.assertEqual(result["status"], "population_shortfall")
        self.assertEqual(result["counts"]["Metaphors"]["exposed_prompt_groups"], 1)
        self.assertEqual(result["counts"]["Metaphors"]["eligible_prompt_groups"], 3)

    def test_score_gap_context_and_distinct_response_rules(self):
        for mutate in (
            lambda values: [row.update(facsco_grm_scaled=20.0) for row in values],
            lambda values: [row.update(Response="same response", ID=str(index)) for index, row in enumerate(values)],
            lambda values: [row.update(Dataset=str(index), DatasetsSplit=str(index)) for index, row in enumerate(values)],
        ):
            values = rows()
            mutate(values)
            self.assertEqual(select_population(values, policy())["status"], "population_shortfall")
        values = rows()
        for row in values:
            row["FullPrompt"] = None
        self.assertEqual(select_population(values, policy())["status"], "prepared")

    def test_expected_source_id_reuse_is_valid_but_conflicting_full_identity_fails(self):
        self.assertEqual(select_population(rows(), policy())["status"], "prepared")
        for mutate in (
            lambda row: row.update(facsco_grm_scaled=40.0),
            lambda row: None,
        ):
            values = rows()
            duplicate = copy.deepcopy(values[0])
            mutate(duplicate)
            with self.assertRaises(ContractError):
                select_population(values + [duplicate], policy())
        for value in (float("nan"), float("inf"), 51.0, True):
            values = rows()
            values[0]["facsco_grm_scaled"] = value
            with self.assertRaises(ContractError):
                select_population(values, policy())

    def test_source_hash_is_checked_before_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "untrusted.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ContractError):
                prepare_muce(path, {}, policy(), Path(temporary) / "out")
            self.assertFalse((Path(temporary) / "out").exists())

    def test_shortfall_publishes_only_aggregate_manifest_and_success_is_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.jsonl"
            source.write_text("synthetic loader fixture", encoding="utf-8")
            with patch("buddha2.muce._load_source", return_value=rows(1)):
                shortfall = prepare_muce(source, {}, policy(), root / "shortfall")
            self.assertEqual(shortfall["status"], "population_shortfall")
            self.assertEqual([p.name for p in (root / "shortfall").iterdir()], ["manifest.json"])
            with patch("buddha2.muce._load_source", return_value=rows()):
                prepared = prepare_muce(source, {}, policy(), root / "success")
                replay = prepare_muce(source, {}, policy(), root / "success")
            self.assertEqual(prepared, replay)
            self.assertEqual(read_json(root / "success" / "pairs.json")[0]["fixture"], False)
            for filename, identity in prepared["files"].items():
                self.assertEqual(len(identity["sha256"]), 64)
                self.assertTrue((root / "success" / filename).is_file())
            with patch("buddha2.muce._load_source", return_value=rows()), self.assertRaises(ContractError):
                prepare_muce(source, {}, policy(population_authorization="Changed population authority."), root / "success")
            self.assertNotEqual(digest(prepared), digest(shortfall))


if __name__ == "__main__":
    unittest.main()
