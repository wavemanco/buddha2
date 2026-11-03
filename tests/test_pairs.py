"""Two-response contracts and fixed-denominator evaluator analysis, without calls."""

import copy
import unittest

from buddha2.artifacts import ContractError, digest
from buddha2.pairs import (
    analyze_pairs,
    make_judgment,
    make_label,
    make_pair,
    make_presentation,
    validate_judgment,
    validate_label,
    validate_pair,
    validate_presentation,
    wilson_interval,
)


def pair(index=0, **overrides):
    values = {
        "prompt_id": f"p-{index}",
        "prompt": f"Imagine a helpful reading room improvement {index}.",
        "family": "synthetic-ideas",
        "responses": [
            {"id": f"r-{index}-short", "text": "Use comfortable chairs."},
            {"id": f"r-{index}-long", "text": "Use a movable book cart as a changing community display."},
        ],
        "fixture": True,
    }
    values.update(overrides)
    return make_pair(**values)


def presentations(item):
    ids = [response["id"] for response in item["responses"]]
    return [make_presentation(item, ids), make_presentation(item, list(reversed(ids)))]


def judgment(item, shown, selected=None, *, choice=None, status="ok", **changes):
    if choice is None and selected is not None:
        choice = "A" if shown["order"][0] == selected else "B"
    values = {
        "status": status,
        "choice": choice,
        "reason": "Synthetic contract check.",
        "model": {"requested": "fixture-critic", "returned": "fixture-critic-v1"},
        "rubric_sha256": "a" * 64,
        "settings_sha256": "b" * 64,
        "usage": {"input_tokens": 40, "output_tokens": 12},
        "cost_usd": 0.0002,
    }
    values.update(changes)
    return make_judgment(item, shown, **values)


def study(count=12):
    pairs, shown, labels, results = [], [], [], []
    for index in range(count):
        item = pair(index)
        orders = presentations(item)
        preferred = f"r-{index}-short"
        pairs.append(item)
        shown.extend(orders)
        labels.append(make_label(item, preferred, {"construct": "fixture-creativity"}))
        results.extend(judgment(item, order, preferred) for order in orders)
    return pairs, shown, results, labels


class PairContractTests(unittest.TestCase):
    def test_canonical_pair_and_display_order_have_separate_identities(self):
        item = pair()
        reversed_input = pair(responses=list(reversed(item["responses"])))
        self.assertEqual(item, reversed_input)
        first, second = presentations(item)
        self.assertEqual(first["pair_sha256"], digest(item))
        self.assertNotEqual(first["presentation_id"], second["presentation_id"])
        self.assertNotEqual(digest(first), digest(second))
        self.assertEqual(first["order"], list(reversed(second["order"])))

    def test_normalized_prompt_group_preserves_original_text(self):
        first = pair(prompt="  THE\u00a0Reading\nRoom ")
        second = pair(prompt="the reading room")
        self.assertEqual(first["prompt_group_sha256"], second["prompt_group_sha256"])
        self.assertNotEqual(first["pair_id"], second["pair_id"])
        self.assertEqual(first["prompt"], "  THE\u00a0Reading\nRoom ")

    def test_malformed_or_label_bearing_inputs_are_rejected(self):
        for mutate in (
            lambda item: item.update(schema_version=True),
            lambda item: item.update(fixture="yes"),
            lambda item: item.update(prompt=" "),
            lambda item: item.update(pair_id="stale"),
            lambda item: item.update(preferred_response_id="secret-label"),
            lambda item: item.update(provenance={"api_key": "must-not-propagate"}),
            lambda item: item["responses"][0].update(rating=50),
            lambda item: item["responses"][0].update(id=item["responses"][1]["id"]),
            lambda item: item["responses"][0].update(text=item["responses"][1]["text"]),
            lambda item: item["responses"].pop(),
        ):
            item = pair()
            mutate(item)
            with self.subTest(item=item), self.assertRaises(ContractError):
                validate_pair(item)

    def test_swapped_or_stale_order_and_label_evidence_are_rejected(self):
        item = pair()
        first, second = presentations(item)
        result = judgment(item, first, item["responses"][0]["id"])
        with self.assertRaises(ContractError):
            validate_judgment(item, second, result)
        for mutate in (
            lambda value: value["order"].reverse(),
            lambda value: value.update(order=["alien", "alien"]),
            lambda value: value.update(pair_sha256="0" * 64),
        ):
            value = copy.deepcopy(first)
            mutate(value)
            with self.assertRaises(ContractError):
                validate_presentation(item, value)
        label = make_label(item, item["responses"][0]["id"], {"construct": "fixture"})
        label["pair_sha256"] = "0" * 64
        with self.assertRaises(ContractError):
            validate_label(item, label)

    def test_judgments_enforce_status_choice_provenance_and_finite_accounting(self):
        item = pair()
        shown = presentations(item)[0]
        valid = judgment(item, shown, item["responses"][0]["id"])
        for mutate in (
            lambda value: value.update(status="invented-success"),
            lambda value: value.update(choice="C"),
            lambda value: value.update(status="transport_error"),
            lambda value: value.update(cost_usd=float("nan")),
            lambda value: value.update(cost_usd=-1),
            lambda value: value["usage"].update(input_tokens=True),
            lambda value: value.update(rubric_sha256="unversioned"),
            lambda value: value.update(api_key="unexpected-secret-field"),
        ):
            value = copy.deepcopy(valid)
            mutate(value)
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_judgment(item, shown, value)
        unknown = judgment(item, shown, status="unknown", usage=None, cost_usd=None)
        self.assertIsNone(unknown["cost_usd"])
        self.assertIsNone(unknown["usage"])

    def test_constructor_and_reference_type_errors_are_explicit_contract_failures(self):
        for arguments in (
            {"responses": [{"id": "one", "text": {"invalid": "object"}}]},
            {"prompt_id": {"invalid": "object"}},
            {"fixture": {"invalid": "object"}},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ContractError):
                pair(**arguments)
        with self.assertRaises(ContractError):
            make_presentation(pair(), None)
        data = list(study())
        data[1][0]["pair_id"] = []
        with self.assertRaises(ContractError):
            analyze_pairs(*data)


class PairAnalysisTests(unittest.TestCase):
    def test_audit_thresholds_count_prompts_not_presentations(self):
        pairs, shown, results, labels = study()
        # Three consistently wrong prompts: 9/12 agreement, 12/12 consistency.
        for index in range(9, 12):
            for order_index in range(2):
                position = index * 2 + order_index
                results[position] = judgment(pairs[index], shown[position], f"r-{index}-long")
        report = analyze_pairs(pairs, shown, results, labels)
        self.assertEqual(report["outcome"], "pass")
        self.assertEqual(report["human_agreement"]["successes"], 9)
        self.assertEqual(report["order_consistency"]["successes"], 12)
        self.assertEqual(report["independent_prompts"], 12)
        self.assertEqual(report["presentations"], 24)
        self.assertEqual(report["length_diagnostics"]["wrong_longer_choices"], 6)
        self.assertEqual(report["families"]["synthetic-ideas"]["prompts"], 12)

    def test_exact_integer_consistency_floor_and_both_orders_requirement(self):
        pairs, shown, results, labels = study()
        for index in (10, 11):
            position = 2 * index + 1
            results[position] = judgment(pairs[index], shown[position], f"r-{index}-long")
        report = analyze_pairs(pairs, shown, results, labels)
        self.assertEqual(report["human_agreement"]["successes"], 10)
        self.assertEqual(report["order_consistency"]["successes"], 10)
        self.assertEqual(report["outcome"], "diagnostic-only")
        results[23] = judgment(pairs[11], shown[23], "r-11-short")
        self.assertEqual(analyze_pairs(pairs, shown, results, labels)["outcome"], "pass")

    def test_ties_abstentions_refusals_and_missing_do_not_earn_consistency(self):
        pairs, shown, results, labels = study()
        for index, (choice, status) in enumerate((
            ("tie", "ok"), ("abstain", "ok"), (None, "refused"), (None, "malformed")
        )):
            for order_index in range(2):
                position = index * 2 + order_index
                results[position] = judgment(pairs[index], shown[position], choice=choice, status=status)
        results.pop()  # Fifth prompt fails because one scheduled presentation is missing.
        report = analyze_pairs(pairs, shown, results, labels)
        self.assertEqual(report["human_agreement"]["successes"], 7)
        self.assertEqual(report["order_consistency"]["successes"], 7)
        self.assertEqual(report["statuses"]["missing"], 1)
        self.assertEqual(report["coverage"]["decisive_presentations"], 15)
        self.assertEqual(report["cost"]["unreported_presentations"], 1)
        self.assertIsNone(report["cost"]["complete_total_usd"])

    def test_small_descriptive_report_cannot_claim_screen_pass(self):
        args = study(2)
        report = analyze_pairs(*args)
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertEqual(report["human_agreement"]["denominator"], 12)
        self.assertEqual(report["human_agreement"]["successes"], 2)

    def test_duplicates_stale_labels_or_mixed_evaluator_revisions_refuse(self):
        for mutate in (
            lambda data: data[0].append(data[0][0]),
            lambda data: data[1].append(data[1][0]),
            lambda data: data[2].append(data[2][0]),
            lambda data: data[3].pop(),
            lambda data: data[3][0].update(pair_sha256="0" * 64),
            lambda data: data[2][0].update(rubric_sha256="c" * 64),
        ):
            data = list(study())
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ContractError):
                analyze_pairs(*data)

    def test_same_normalized_question_under_another_id_is_not_independent(self):
        pairs, shown, results, labels = study(1)
        item = pair(42, prompt="  IMAGINE a helpful reading room improvement 0. ")
        extra_shown = presentations(item)
        pairs.append(item)
        shown.extend(extra_shown)
        labels.append(make_label(item, "r-42-short", {"construct": "fixture"}))
        results.extend(judgment(item, order, "r-42-short") for order in extra_shown)
        with self.assertRaisesRegex(ContractError, "prompt"):
            analyze_pairs(pairs, shown, results, labels)

    def test_unknown_accounting_or_broken_transport_is_inconclusive_not_bad_critic(self):
        for changes in (
            {"cost_usd": None}, {"usage": None},
            {"status": "unknown", "choice": None},
            {"status": "transport_error", "choice": None},
        ):
            data = list(study())
            data[2][0].update(changes)
            self.assertEqual(analyze_pairs(*data)["outcome"], "inconclusive")

    def test_real_and_fixture_observations_cannot_be_pooled(self):
        pairs, shown, results, labels = study(1)
        item = pair(42, fixture=False)
        extra_shown = presentations(item)
        pairs.append(item)
        shown.extend(extra_shown)
        labels.append(make_label(item, "r-42-short", {"construct": "fixture"}))
        results.extend(judgment(item, order, "r-42-short") for order in extra_shown)
        with self.assertRaisesRegex(ContractError, "fixture"):
            analyze_pairs(pairs, shown, results, labels)

    def test_wilson_interval_has_independent_known_values_and_validates_denominator(self):
        low, high = wilson_interval(9, 12)
        self.assertAlmostEqual(low, 0.46769466506643426, places=12)
        self.assertAlmostEqual(high, 0.9110583316059453, places=12)
        self.assertEqual(wilson_interval(0, 0), [None, None])
        for successes, total in ((-1, 12), (13, 12), (1, True)):
            with self.assertRaises(ContractError):
                wilson_interval(successes, total)


if __name__ == "__main__":
    unittest.main()
