"""Public artifact properties, independent of the native execution implementation."""

import copy
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import (
    ContractError,
    digest,
    export_native,
    import_native,
    read_json,
    tree_hashes,
    validate_portfolio,
    write_once,
)


def example_portfolio():
    return {
        "schema_version": 1,
        "fixture": True,
        "task": {"id": "example", "prompt": "Ten ideas", "domain": "creative", "fixture": True},
        "responses": [{"id": f"r{i}", "text": f"Idea {i}"} for i in range(10)],
        "provenance": {"model": "fixture-no-model"},
    }


class ArtifactTests(unittest.TestCase):
    def test_native_roundtrip_preserves_duplicate_text_and_order(self):
        portfolio = example_portfolio()
        portfolio["responses"][1]["text"] = portfolio["responses"][0]["text"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(portfolio, root)
            self.assertEqual(portfolio, import_native(root))

    def test_export_tampering_cannot_reuse_identity_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(example_portfolio(), root)
            path = root / "generations.jsonl"
            path.write_text(path.read_text().replace("Idea 0", "different"))
            with self.assertRaises(ContractError):
                import_native(root)

    def test_missing_identity_mapping_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(example_portfolio(), root)
            (root / "identities.json").unlink()
            with self.assertRaises(ContractError):
                import_native(root)

    def test_boolean_is_not_an_identity_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_native(example_portfolio(), root)
            identities = read_json(root / "identities.json")
            identities["schema_version"] = True
            import json

            (root / "identities.json").write_text(json.dumps(identities), encoding="utf-8")
            with self.assertRaises(ContractError):
                import_native(root)

    def test_invalid_records_are_rejected(self):
        bad_records = []
        for field, value in (("schema_version", True), ("fixture", False), ("responses", [])):
            item = example_portfolio()
            item[field] = value
            bad_records.append(item)
        duplicate_id = example_portfolio()
        duplicate_id["responses"][1]["id"] = duplicate_id["responses"][0]["id"]
        bad_records.append(duplicate_id)
        empty_text = example_portfolio()
        empty_text["responses"][0]["text"] = "  "
        bad_records.append(empty_text)
        for item in bad_records:
            with self.subTest(item=item), self.assertRaises(ContractError):
                validate_portfolio(item)

    def test_final_records_are_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            write_once(path, {"value": 1})
            original = path.read_bytes()
            write_once(path, {"value": 1})
            self.assertEqual(original, path.read_bytes())
            with self.assertRaises(ContractError):
                write_once(path, {"value": 2})
            self.assertEqual({"value": 1}, read_json(path))

    def test_markdown_and_python_both_change_tree_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompt.md").write_text("first")
            (root / "helper.py").write_text("VALUE = 1\n")
            first = digest(tree_hashes(root))
            (root / "prompt.md").write_text("second")
            second = digest(tree_hashes(root))
            (root / "helper.py").write_text("VALUE = 2\n")
            self.assertNotEqual(first, second)
            self.assertNotEqual(second, digest(tree_hashes(root)))

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "actual.md").write_text("source")
            (root / "linked.md").symlink_to(root / "actual.md")
            with self.assertRaises(ContractError):
                tree_hashes(root)

    def test_symlink_source_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            (root / "source/prompt.md").write_text("source")
            (root / "linked").symlink_to(root / "source", target_is_directory=True)
            with self.assertRaises(ContractError):
                tree_hashes(root / "linked")

    def test_identity_covers_order_not_just_response_set(self):
        first = example_portfolio()
        second = copy.deepcopy(first)
        second["responses"].reverse()
        self.assertNotEqual(digest(first), digest(second))


if __name__ == "__main__":
    unittest.main()
