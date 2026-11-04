"""Observed pinned Read page footer compatibility without incomplete delivery."""
from __future__ import annotations

import copy
import unittest

from buddha2.artifacts import ContractError

from .delivery import _read_result, audit_delivery, verify_delivery


def result(rows, footer):
    return {"type": "tool_result", "tool_use_id": "read-1", "content": (
        "<path>/fixture/source.md</path>\n<type>file</type>\n<content>\n"
        + "\n".join(rows + [footer]) + "\n</content>")}


class PagedReadTests(unittest.TestCase):
    def test_actual_footer_excludes_metadata_and_accepts_later_offset(self):
        path, rows = _read_result({"filePath": "/fixture/source.md", "offset": 129, "limit": 128},
            result([f"{n}: line {n}" for n in range(129, 257)],
                "(Showing lines 129-256 of 2317. Use offset=257 to continue.)"))
        self.assertEqual(path, "/fixture/source.md")
        self.assertEqual(rows, {n: f"line {n}" for n in range(129, 257)})

    def test_inconsistent_noncanonical_duplicate_or_mixed_footer_rejects(self):
        rows = ["1: one", "2: two"]
        good = "(Showing lines 1-2 of 3. Use offset=3 to continue.)"
        footers = [good.replace("1-2", "2-2"), good.replace("1-2", "1-3"),
            good.replace("of 3", "of 2"), good.replace("offset=3", "offset=4"),
            good.replace("1-2", "01-2"), good.replace("of 3", "of 03"),
            good.replace("offset=3", "offset=03"), good + "\n" + good,
            "(End of file - total 2 lines)\n" + good,
            good + "\n(End of file - total 2 lines)", good + "\n3: three"]
        for footer in footers:
            with self.subTest(footer=footer), self.assertRaises(ContractError):
                _read_result({"filePath": "/fixture/source.md", "limit": 2}, result(rows, footer))

    def test_duplicate_missing_noncanonical_and_undeclared_rows_reject(self):
        footer = "(Showing lines 1-3 of 4. Use offset=4 to continue.)"
        cases = [["1: one", "1: one", "2: two", "3: three"],
            ["1: one", "3: three"], ["01: one", "2: two", "3: three"],
            ["1: one", "2: two", "3: three", "4: four"]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ContractError):
                _read_result({"filePath": "/fixture/source.md", "limit": 3}, result(rows, footer))

    def test_valid_partial_page_cannot_satisfy_complete_source(self):
        path = "/fixture/source.md"
        tool = {"type": "tool_use", "id": "read-1", "name": "read", "caller": {"type": "direct"},
            "input": {"filePath": path, "offset": 1, "limit": 2}}
        block = result(["1: one", "2: two"], "(Showing lines 1-2 of 3. Use offset=3 to continue.)")
        body = {"messages": [{"role": "assistant", "content": [tool]}, {"role": "user", "content": [block]}]}
        with self.assertRaisesRegex(ContractError, "absent, stale or mismatched"):
            verify_delivery(body, {path: "one\ntwo\nthree\n"})
        body["messages"].extend([
            {"role": "assistant", "content": [{**tool, "id": "read-2", "input": {
                "filePath": path, "offset": 3, "limit": 2}}]},
            {"role": "user", "content": [{**result(["3: three"], "(End of file - total 3 lines)"),
                "tool_use_id": "read-2"}]}])
        self.assertTrue(verify_delivery(body, {path: "one\ntwo\nthree\n"})[path]["all_lines_model_visible"])

    def test_byte_capped_page_requires_complete_followup_and_bound_results(self):
        path = "/fixture/source.md"
        lines = ["x" * 2000] * 26
        tool = {"type": "tool_use", "id": "read-1", "name": "read", "caller": {"type": "direct"},
            "input": {"filePath": path, "offset": 1, "limit": 2000}}
        block = result([f"{n}: {text}" for n, text in enumerate(lines[:25], 1)],
            "(Output capped at 50 KB. Showing lines 1-25. Use offset=26 to continue.)")
        body = {"messages": [{"role": "assistant", "content": [tool]}, {"role": "user", "content": [block]}]}
        expected = {path: "\n".join(lines) + "\n"}
        with self.assertRaisesRegex(ContractError, "absent, stale or mismatched"):
            verify_delivery(body, expected)
        audit = audit_delivery(body, expected)
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["files"][path]["missing_ranges"], [[26, 26]])
        body["messages"].extend([
            {"role": "assistant", "content": [{**tool, "id": "read-2", "input": {
                "filePath": path, "offset": 26, "limit": 2000}}]},
            {"role": "user", "content": [{**result(["26: " + lines[-1]], "(End of file - total 26 lines)"),
                "tool_use_id": "read-2"}]}])
        self.assertTrue(verify_delivery(body, expected)[path]["all_lines_model_visible"])
        for field, value in (("tool_use_id", "foreign-read"), ("content", block["content"].replace(
                path, "/fixture/other.md"))):
            forged = copy.deepcopy(body)
            forged["messages"][1]["content"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                verify_delivery(forged, expected)
            with self.subTest(audit_field=field), self.assertRaises(ContractError):
                audit_delivery(forged, expected)

    def test_diagnostic_audit_enumerates_every_missing_conflicting_and_unparseable_target(self):
        path = "/fixture/source.md"
        body: dict = {"messages": []}
        pages = [("read-1", path, ["1: one", "2: two"],
            "(Showing lines 1-2 of 3. Use offset=3 to continue.)"),
            ("read-2", path, ["1: one", "2: DIFFERENT"],
            "(Showing lines 1-2 of 3. Use offset=3 to continue.)"),
            ("read-3", "/fixture/unknown.md", ["SYNTHETIC unsupported renderer"], "")]
        for identity, target, rows, footer in pages:
            tool = {"type": "tool_use", "id": identity, "name": "read", "caller": {"type": "direct"},
                "input": {"filePath": target, "offset": 1, "limit": 2}}
            block = result(rows, footer)
            block.update(tool_use_id=identity, content=block["content"].replace(path, target))
            body["messages"].extend([{"role": "assistant", "content": [tool]},
                {"role": "user", "content": [block]}])
        audit = audit_delivery(body, {path: "one\ntwo\nthree\n", "/fixture/unknown.md": "expected\n",
            "/fixture/unread.md": "first\nsecond\n"})
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["files"][path]["missing_ranges"], [[3, 3]])
        self.assertEqual(audit["files"][path]["conflicting_ranges"], [[2, 2]])
        self.assertEqual(audit["files"]["/fixture/unknown.md"]["parse_errors"], ["read-3"])
        self.assertEqual(audit["files"]["/fixture/unread.md"]["missing_ranges"], [[1, 2]])
        self.assertEqual(len(audit["parse_errors"]), 1)

    def test_diagnostic_audit_keeps_invalid_call_ranges_hard(self):
        path = "/fixture/source.md"
        tool = {"type": "tool_use", "id": "read-1", "name": "read", "caller": {"type": "direct"},
            "input": {"filePath": path, "offset": 0, "limit": 2}}
        body = {"messages": [{"role": "assistant", "content": [tool]},
            {"role": "user", "content": [result(["1: one"], "(End of file - total 1 lines)")]}]}
        with self.assertRaisesRegex(ContractError, "invalid declared read range"):
            audit_delivery(body, {path: "one\n"})

    def test_byte_cap_footer_rejects_forged_range_label_and_placement(self):
        good = "(Output capped at 50 KB. Showing lines 1-2. Use offset=3 to continue.)"
        ordinary = "(Showing lines 1-2 of 3. Use offset=3 to continue.)"
        footers = [good.replace("50 KB", "49 KB"), good.replace("1-2", "2-2"),
            good.replace("1-2", "1-3"), good.replace("offset=3", "offset=4"),
            good.replace("1-2", "01-2"), good.replace("offset=3", "offset=03"),
            good.replace("1-2.", "1-2 of 3."), good.replace("Output capped at 50 KB. ", ""),
            good + "\n" + good, good + "\n" + ordinary, ordinary + "\n" + good,
            "(End of file - total 2 lines)\n" + good, good + "\n(End of file - total 2 lines)",
            good + "\n3: three"]
        for footer in footers:
            with self.subTest(footer=footer), self.assertRaises(ContractError):
                _read_result({"filePath": "/fixture/source.md", "limit": 2000},
                    result(["1: one", "2: two"], footer))
        with self.assertRaises(ContractError):
            _read_result({"filePath": "/fixture/source.md", "limit": 2},
                result(["1: one", "2: two"], good))


if __name__ == "__main__":
    unittest.main()
