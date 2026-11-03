"""Observed pinned Read page footer compatibility without incomplete delivery."""
from __future__ import annotations

import unittest

from buddha2.artifacts import ContractError

from .delivery import _read_result, verify_delivery


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


if __name__ == "__main__":
    unittest.main()
