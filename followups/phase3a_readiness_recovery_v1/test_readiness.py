"""Frozen D02-D15 cases exercise the real lossless decoder and original-input proof."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError

from . import contract
from .delivery import verify_delivery, verify_original_strategy
from .evidence import _sources
from .test_delivery import body, pair

CASE_IDS = {
    "test_raw_and_views": "D02", "test_wrong_source_path": "D03",
    "test_wrong_source_hash": "D04", "test_missing_chunk": "D05",
    "test_noncontiguous_or_reordered": "D06", "test_truncated_view": "D07",
    "test_view_after_decision": "D08", "test_original_cannot_prove_edit": "D09",
    "test_raw_contradiction": "D10", "test_undeclared_copy": "D11",
    "test_foreign_ownership": "D12", "test_unicode_character_ranges": "D13",
    "test_other_required_view": "D14", "test_keep_base": "D15",
}
CWD = "/workspace/contract-synthetic"
SOURCE = "harness/systemprompt.md"
RAW = CWD + "/context/" + SOURCE


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class OriginalInputCases(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.search = Path(self.temporary.name)
        self.prefix = "contract"
        self.manifest: dict = {"role": "INV", "required_evidence": [], "context_inventory": {}}
        self.strategy = json.dumps({"answer_system": "é漢🙂: inspect", "plan_system": "plan",
                                    "rank_system": "rank"}, ensure_ascii=False, indent=2) + "\n"
        for number, (path, kind) in enumerate(contract._layout("INV")[1]):
            text = self.strategy if path == SOURCE else "exact " + kind + "\n"
            entry: dict = {"path": path, "kind": kind, "sha256": sha(text.encode()),
                           "bytes": len(text.encode()), "chunks": []}
            self.manifest["context_inventory"][path] = {"sha256": entry["sha256"], "bytes": entry["bytes"]}
            # The first Unicode characters precede this boundary, distinguishing chars from UTF-8 bytes.
            cut = text.index("inspect") if path == SOURCE else len(text)
            pieces = [text[:cut], text[cut:]] if path == SOURCE else [text]
            cursor = 0
            for part, piece in enumerate(pieces):
                chunk = {"path": f"C1_EVIDENCE/{number:02}-{part:03}.json",
                         "char_start": cursor, "char_end": cursor + len(piece)}
                view = {"source_path": path, "source_sha256": entry["sha256"],
                        "char_start": chunk["char_start"], "char_end": chunk["char_end"], "text": [piece]}
                self.store(chunk, view)
                entry["chunks"].append(chunk)
                cursor += len(piece)
            self.manifest["required_evidence"].append(entry)
        self.entry = self.manifest["required_evidence"][1]

    def store(self, chunk: dict, view: dict) -> None:
        data = (json.dumps(view, ensure_ascii=False, indent=2) + "\n").encode()
        path = self.search / self.prefix / "context-view" / chunk["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        chunk.update(sha256=sha(data), bytes=len(data), offset=1, limit=len(data.decode().splitlines()))

    def change_view(self, index: int, **changes) -> None:
        chunk = self.entry["chunks"][index]
        path = self.search / self.prefix / "context-view" / chunk["path"]
        view = json.loads(path.read_text(encoding="utf-8"))
        view.update(changes)
        self.store(chunk, view)

    def decoded(self) -> tuple[dict, dict]:
        return _sources(self.search, self.prefix, self.manifest, {})

    def prepared(self) -> tuple[dict, dict, dict, dict]:
        original, views = self.decoded()
        expected = {CWD + "/context/" + path: text for path, text in views.items()}
        expected[RAW] = original[SOURCE]
        reads = body(*(pair("v" + str(i), "read", path, text)
                       for i, (path, text) in enumerate(expected.items()) if path != RAW))
        return original, views, expected, reads

    def verify(self, reads: dict, expected: dict, original: dict, views: dict) -> dict:
        return verify_original_strategy(reads, expected, cwd=CWD, manifest=self.manifest,
                                        original=original, views=views)[1]

    def test_raw_and_views(self):
        original, views, expected, reads = self.prepared()
        reads["messages"].extend(pair("raw", "read", RAW, self.strategy))
        self.assertEqual(self.verify(reads, expected, original, views)["route"], "raw")

    def test_wrong_source_path(self):
        self.change_view(0, source_path="harness/copy.md")
        with self.assertRaisesRegex(ContractError, "identity"):
            self.decoded()

    def test_wrong_source_hash(self):
        self.change_view(0, source_sha256="0" * 64)
        with self.assertRaisesRegex(ContractError, "identity"):
            self.decoded()

    def test_missing_chunk(self):
        self.entry["chunks"].pop()
        with self.assertRaisesRegex(ContractError, "omit/rewrite"):
            self.decoded()

    def test_noncontiguous_or_reordered(self):
        self.entry["chunks"].reverse()
        with self.assertRaisesRegex(ContractError, "identity"):
            self.decoded()
        self.entry["chunks"].reverse()
        self.entry["chunks"][1]["char_start"] += 1
        self.change_view(1, char_start=self.entry["chunks"][1]["char_start"])
        with self.assertRaisesRegex(ContractError, "identity"):
            self.decoded()

    def test_truncated_view(self):
        original, views, expected, reads = self.prepared()
        block = reads["messages"][3]["content"][0]
        lines = block["content"].splitlines()
        block["content"] = "\n".join(line for line in lines if not line.startswith("2:"))
        with self.assertRaises(ContractError):
            self.verify(reads, expected, original, views)

    def test_view_after_decision(self):
        original, views, expected, reads = self.prepared()
        decision = {"messages": reads["messages"][:4] + reads["messages"][6:]}
        # Actual evidence.py supplies the request before the first write/decision, excluding later reads.
        with self.assertRaises(ContractError):
            self.verify(decision, expected, original, views)

    def test_original_cannot_prove_edit(self):
        original, views, expected, reads = self.prepared()
        self.verify(reads, expected, original, views)
        value = body(pair("w", "write", RAW, "changed"))
        value["messages"].extend(reads["messages"])
        with self.assertRaises(ContractError):
            verify_delivery(value, {RAW: "changed"}, after="w")

    def test_raw_contradiction(self):
        original, views, expected, reads = self.prepared()
        reads["messages"].extend(pair("raw", "read", RAW, "contradictory"))
        with self.assertRaisesRegex(ContractError, "contradicts"):
            self.verify(reads, expected, original, views)
        reads["messages"][-2:] = pair("raw", "read", RAW, self.strategy.splitlines()[0], limit=1)
        self.assertEqual(self.verify(reads, expected, original, views)["route"], "declared_lossless_view")

    def test_undeclared_copy(self):
        original, views, expected, reads = self.prepared()
        path = list(views)[1]
        reads["messages"][2:4] = pair("copy", "read", CWD + "/context/undeclared-copy.json", views[path])
        with self.assertRaises(ContractError):
            self.verify(reads, expected, original, views)

    def test_foreign_ownership(self):
        original, views, expected, reads = self.prepared()
        reads["messages"][1]["content"][0]["tool_use_id"] = "foreign"
        with self.assertRaises(ContractError):
            self.verify(reads, expected, original, views)
        _, _, _, reads = self.prepared()
        reads["messages"][0]["content"][0]["caller"] = {"type": "foreign"}
        with self.assertRaises(ContractError):
            self.verify(reads, expected, original, views)

    def test_unicode_character_ranges(self):
        original, views, expected, reads = self.prepared()
        proof = self.verify(reads, expected, original, views)
        self.assertEqual(proof["source_utf8_bytes"], len(self.strategy.encode()))
        self.assertGreater(proof["source_utf8_bytes"], len(self.strategy))
        first = self.entry["chunks"][0]
        boundary = len(self.strategy[:first["char_end"]].encode())
        self.assertNotEqual(boundary, first["char_end"])
        first["char_end"] = boundary
        self.change_view(0, char_end=boundary)
        with self.assertRaisesRegex(ContractError, "range is incomplete"):
            self.decoded()

    def test_other_required_view(self):
        original, views, expected, reads = self.prepared()
        reads["messages"] = reads["messages"][2:]
        with self.assertRaises(ContractError):
            self.verify(reads, expected, original, views)

    def test_keep_base(self):
        original, views, expected, reads = self.prepared()
        before = copy.deepcopy(reads)
        self.assertEqual(self.verify(reads, expected, original, views)["route"], "declared_lossless_view")
        self.assertEqual(reads, before)
        self.assertFalse(any(b.get("name") in {"write", "edit"}
                             for m in reads["messages"] for b in m["content"]))


if __name__ == "__main__":
    unittest.main()
