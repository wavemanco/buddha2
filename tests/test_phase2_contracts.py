"""Live-v2 exchange and permutation boundaries, without models or invented labels."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest, read_json
from buddha2.artifacts import validate_portfolio as validate_fixture
from buddha2.phase2_contracts import (
    export_native,
    import_native,
    make_portfolio,
    permute_portfolio,
    slot_prefix,
    validate_permutation,
    validate_portfolio,
)


def example(method="B", fixture=False):
    task = {
        "id": "curated-7", "prompt": "Suggest ways to explain a difficult idea.",
        "domain": "nb-curated-development",
        "source_context": {
            "dataset": "noveltybench/curated", "revision": "a" * 40,
            "source_sha256": "b" * 64, "source_task_id": "7",
        },
    }
    return make_portfolio(
        task,
        [{"id": f"answer-{i}", "text": f"Idea {i}", "status": "ok",
          "request_id": f"request-{i}"} for i in range(10)],
        method=method, repeat=1,
        model={"requested": "claude-sonnet-5-5", "returned": "claude-sonnet-5-5"},
        settings_sha256="c" * 64, procedure_sha256="d" * 64,
        study_sha256="e" * 64,
        request_ids=[f"request-{i}" for i in range(10)] + (
            ["request-plan"] if method == "B" else []
        ), fixture=fixture,
    )


class Phase2ContractTests(unittest.TestCase):
    def test_logical_slot_identity_is_stable_and_rejects_boolean_repeats(self):
        self.assertEqual(slot_prefix("task", "B", 1), "p2-" + digest(
            {"task_id": "task", "method": "B", "repeat": 1}
        )[:24])
        self.assertNotEqual(slot_prefix("task", "B", 1), slot_prefix("task", "B", 2))
        for arguments in (("task", "B", True), ("task", "D", 1), ("", "B", 1)):
            with self.assertRaises(ContractError):
                slot_prefix(*arguments)

    def test_duplicate_text_preserves_response_ids_and_native_roundtrip(self):
        portfolio = example()
        responses = copy.deepcopy(portfolio["responses"])
        responses[1]["text"] = responses[0]["text"]
        portfolio = make_portfolio(
            portfolio["task"], responses, **portfolio["provenance"], fixture=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(portfolio, root)
            self.assertEqual(portfolio, import_native(root))
            self.assertNotEqual(portfolio["responses"][0]["id"],
                                portfolio["responses"][1]["id"])
            self.assertFalse((root / "grading.json").exists())

    def test_live_and_walkthrough_kinds_cannot_be_relabeled_or_use_old_fixture_route(self):
        live, synthetic = example(), example(fixture=True)
        self.assertEqual(live["kind"], "phase2-portfolio-live-v2")
        self.assertEqual(synthetic["kind"], "phase2-portfolio-walkthrough-v2")
        for value in (live, synthetic):
            with self.assertRaises(ContractError):
                validate_fixture(value)
        for key, value in (("fixture", True), ("schema_version", True),
                           ("kind", "phase2-portfolio-walkthrough-v2")):
            changed = copy.deepcopy(live)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_portfolio(changed)

    def test_stale_content_identity_and_unknown_fields_are_rejected(self):
        for operation in (
            lambda p: p["responses"][0].update(text="changed"),
            lambda p: p["task"].update(prompt="changed"),
            lambda p: p["provenance"].update(repeat=True),
            lambda p: p["responses"][0].update(status="transport_error"),
            lambda p: p["task"]["source_context"].update(unknown="hidden"),
            lambda p: p.update(grading={"utility": 10}),
        ):
            changed = copy.deepcopy(example())
            operation(changed)
            with self.assertRaises(ContractError):
                validate_portfolio(changed)

    def test_constructors_validate_ids_sources_requests_and_types(self):
        baseline = example()
        for field, value in (("repeat", True), ("repeat", 0), ("method", []),
                             ("fixture", 1), ("request_ids", ["same"] * 11),
                             ("settings_sha256", "bad"),
                             ("study_sha256", "bad"),
                             ("parent_sha256", "e" * 64)):
            arguments = {**baseline["provenance"], "fixture": False, field: value}
            with self.subTest(field=field), self.assertRaises(ContractError):
                make_portfolio(baseline["task"], baseline["responses"], **arguments)
        for field in ("id", "request_id"):
            changed = copy.deepcopy(baseline["responses"])
            changed[1][field] = changed[0][field]
            with self.assertRaises(ContractError):
                make_portfolio(baseline["task"], changed, **baseline["provenance"])
        task = copy.deepcopy(baseline["task"])
        task["source_context"]["source_sha256"] = "unbound"
        with self.assertRaises(ContractError):
            make_portfolio(task, baseline["responses"], **baseline["provenance"])

    def test_order_only_transformation_preserves_every_response_field(self):
        parent = example()
        order = [row["id"] for row in reversed(parent["responses"])]
        child = permute_portfolio(
            parent, order, request_id="rank-request", settings_sha256="c" * 64,
            procedure_sha256="f" * 64,
        )
        validate_permutation(parent, child)
        self.assertEqual(child["responses"], list(reversed(parent["responses"])))
        self.assertEqual(child["provenance"]["parent_sha256"], digest(parent))
        self.assertEqual(child["provenance"]["request_ids"],
                         parent["provenance"]["request_ids"] + ["rank-request"])
        self.assertEqual(parent["provenance"]["method"], "B")
        self.assertNotEqual(digest(parent), digest(child))

    def test_identity_permutation_valid_but_rewrites_and_stale_parents_refused(self):
        parent = example()
        child = permute_portfolio(
            parent, [row["id"] for row in parent["responses"]], request_id="rank-request",
            settings_sha256="c" * 64, procedure_sha256="f" * 64,
        )
        validate_permutation(parent, child)
        responses = copy.deepcopy(child["responses"])
        responses[0]["text"] = "rewrite"
        rewritten = make_portfolio(child["task"], responses, **child["provenance"])
        with self.assertRaises(ContractError):
            validate_permutation(parent, rewritten)
        other = copy.deepcopy(parent)
        other["responses"][0]["text"] = "different parent response"
        other = make_portfolio(other["task"], other["responses"], **other["provenance"])
        with self.assertRaises(ContractError):
            validate_permutation(other, child)

    def test_malformed_orders_and_nonplanner_parent_refused(self):
        for parent, order in (
            (example(), ["answer-0"] * 10),
            (example(), [f"answer-{i}" for i in range(9)]),
            (example(), [f"answer-{i}" for i in range(9)] + ["new"]),
            (example("A"), [f"answer-{i}" for i in range(10)]),
        ):
            with self.assertRaises(ContractError):
                permute_portfolio(parent, order, request_id="rank-request",
                                  settings_sha256="c" * 64, procedure_sha256="f" * 64)

    def test_native_tampering_missing_companion_and_model_relabeling_refused(self):
        for mutation in ("text", "model", "mapping", "missing"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                export_native(example(), root)
                if mutation in ("text", "model"):
                    row = json.loads((root / "generations.jsonl").read_text())
                    if mutation == "text":
                        row["generations"][0] = "different"
                    else:
                        row["model"] = "another-model"
                    (root / "generations.jsonl").write_text(json.dumps(row) + "\n")
                elif mutation == "mapping":
                    identity = read_json(root / "identities.json")
                    identity["responses"][0]["id"] = "different"
                    (root / "identities.json").write_text(json.dumps(identity))
                else:
                    (root / "identities.json").unlink()
                with self.assertRaises(ContractError):
                    import_native(root)

    def test_export_replay_idempotent_and_different_order_does_not_overwrite(self):
        parent = example()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(parent, root)
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            export_native(parent, root)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})
            child = permute_portfolio(
                parent, [row["id"] for row in reversed(parent["responses"])],
                request_id="rank-request", settings_sha256="c" * 64,
                procedure_sha256="f" * 64,
            )
            with self.assertRaises(ContractError):
                export_native(child, root)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_constructor_copies_inputs_and_walkthrough_roundtrips_as_synthetic(self):
        portfolio = example(fixture=True)
        task, responses, provenance = (
            copy.deepcopy(portfolio[field]) for field in ("task", "responses", "provenance")
        )
        detached = make_portfolio(task, responses, **provenance, fixture=True)
        task["prompt"] = "mutated caller prompt"
        responses[0]["text"] = "mutated caller answer"
        provenance["model"]["returned"] = "mutated caller metadata"
        self.assertEqual(detached, portfolio)
        original = copy.deepcopy(portfolio)
        with tempfile.TemporaryDirectory() as directory:
            export_native(portfolio, Path(directory))
            restored = import_native(Path(directory))
            self.assertEqual(original, restored)
            row = json.loads((Path(directory) / "generations.jsonl").read_text())
            self.assertEqual(row["model"], "fixture-no-model")

    def test_nonfinite_native_json_fails_with_a_contract_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(example(), root)
            path = root / "generations.jsonl"
            path.write_text(path.read_text().replace('"curated-7"', "NaN"), encoding="utf-8")
            with self.assertRaises(ContractError):
                import_native(root)

    def test_reranking_cannot_silently_change_the_model_or_settings(self):
        parent = example()
        order = [row["id"] for row in parent["responses"]]
        for settings, model in (
            ("e" * 64, parent["provenance"]["model"]),
            ("c" * 64, {"requested": "different", "returned": "different"}),
            ("c" * 64, {"requested": "claude-sonnet-5-5", "returned": "other-snapshot"}),
        ):
            with self.subTest(settings=settings, model=model), self.assertRaises(ContractError):
                permute_portfolio(parent, order, request_id="rank-request",
                                  settings_sha256=settings, procedure_sha256="f" * 64,
                                  model=model)

    def test_permutation_cannot_be_rebound_to_a_different_study(self):
        parent = example()
        child = permute_portfolio(
            parent, [row["id"] for row in parent["responses"]], request_id="rank-request",
            settings_sha256="c" * 64, procedure_sha256="f" * 64,
        )
        self.assertEqual(child["provenance"]["study_sha256"], "e" * 64)
        provenance = child["provenance"] | {"study_sha256": "f" * 64}
        substituted = make_portfolio(child["task"], child["responses"], **provenance)
        with self.assertRaises(ContractError):
            validate_permutation(parent, substituted)


if __name__ == "__main__":
    unittest.main()
