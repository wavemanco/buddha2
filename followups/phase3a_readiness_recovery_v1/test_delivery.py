"""The sixteen frozen synthetic delivery cases; historical cases run separately."""
from __future__ import annotations

import copy
import unittest

from buddha2.artifacts import ContractError

from .delivery import verify_delivery

TARGET = "/workspace/context/harness/systemprompt.md"
NOTES = "/workspace/output/answer.md"
CASE_IDS = {
    "test_unrelated_revisions": "R02", "test_partial_reads": "R03", "test_missing": "R04",
    "test_truncated": "R05", "test_wrong_path": "R06", "test_failed_write": "R07",
    "test_stale_prewrite": "R08", "test_wrong_harvest": "R09", "test_wrong_final_notes": "R10",
    "test_same_epoch_conflict": "R11", "test_forged_owner": "R12A",
    "test_duplicate_result": "R12B", "test_missing_result": "R12C",
    "test_target_revisions": "R13", "test_keep_base": "R14", "test_unrelated_malformed": "R15",
}


def pair(identity: str, name: str, path: str, text: str, *, offset: int = 1,
         limit: int = 2000, error: bool = False) -> list[dict]:
    value: dict = {"filePath": path}
    if name == "read":
        value.update(offset=offset, limit=limit)
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(text.splitlines(), offset))
        content = f"<path>{path}</path>\n<content>\n{numbered}\n</content>"
    else:
        value["content"] = text
        content = "Write failed" if error else "Wrote file successfully"
    return [{"role": "assistant", "content": [{"type": "tool_use", "id": identity,
        "name": name, "input": value, "caller": {"type": "direct"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": identity,
                                       "content": content, "is_error": error}]}]


def body(*pairs: list[dict]) -> dict:
    return {"messages": [message for pair_ in pairs for message in pair_]}


class DeliveryCases(unittest.TestCase):
    def test_unrelated_revisions(self):
        value = body(pair("ws", "write", TARGET, "strategy"), pair("rs", "read", TARGET, "strategy"),
            pair("wn1", "write", NOTES, "draft"), pair("rn1", "read", NOTES, "draft"),
            pair("wn2", "write", NOTES, "final notes"), pair("rn2", "read", NOTES, "final notes"))
        before = copy.deepcopy(value)
        self.assertIn(TARGET, verify_delivery(value, {TARGET: "strategy"}, after="ws"))
        self.assertIn(NOTES, verify_delivery(value, {NOTES: "final notes"}, after="wn2"))
        self.assertEqual(value, before)

    def test_partial_reads(self):
        value = body(pair("r1", "read", TARGET, "first", offset=1, limit=1),
                     pair("r2", "read", TARGET, "second", offset=2, limit=1))
        self.assertEqual(verify_delivery(value, {TARGET: "first\nsecond"})[TARGET]["source_lines"], 2)

    def test_missing(self):
        with self.assertRaises(ContractError):
            verify_delivery(body(pair("r", "read", NOTES, "notes")), {TARGET: "strategy"})

    def test_truncated(self):
        with self.assertRaises(ContractError):
            verify_delivery(body(pair("r", "read", TARGET, "first")), {TARGET: "first\nsecond"})
        for extra in ("unexpected", ""):
            with self.subTest(extra=extra):
                value = body(pair("r", "read", TARGET, "expected\n" + extra + "\n"))
                with self.assertRaises(ContractError):
                    verify_delivery(value, {TARGET: "expected"})
        value = body(pair("r", "read", TARGET, "first\nsecond"))
        value["messages"][1]["content"][0]["content"] = value["messages"][1]["content"][0]["content"].replace("2: second", "3: second")
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "first\nsecond"})

    def test_wrong_path(self):
        value = body(pair("r", "read", TARGET, "strategy"))
        value["messages"][1]["content"][0]["content"] = value["messages"][1]["content"][0]["content"].replace(TARGET, NOTES)
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"})

    def test_failed_write(self):
        value = body(pair("w", "write", TARGET, "strategy", error=True), pair("r", "read", TARGET, "strategy"))
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"}, after="w")

    def test_stale_prewrite(self):
        value = body(pair("r", "read", TARGET, "strategy"), pair("w", "write", TARGET, "strategy"))
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"}, after="w")

    def test_wrong_harvest(self):
        value = body(pair("w", "write", TARGET, "changed"), pair("r", "read", TARGET, "changed"))
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "different harvest"}, after="w")

    def test_wrong_final_notes(self):
        value = body(pair("w", "write", NOTES, "draft"), pair("r", "read", NOTES, "draft"))
        with self.assertRaises(ContractError):
            verify_delivery(value, {NOTES: "different final"}, after="w")

    def test_same_epoch_conflict(self):
        value = body(pair("r1", "read", TARGET, "first"), pair("r2", "read", TARGET, "second"))
        with self.assertRaisesRegex(ContractError, "history conflicts"):
            verify_delivery(value, {TARGET: "second"})

    def test_forged_owner(self):
        value = body(pair("r", "read", TARGET, "strategy"))
        value["messages"][1]["content"][0]["tool_use_id"] = "foreign"
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"})

    def test_duplicate_result(self):
        value = body(pair("r", "read", TARGET, "strategy"))
        value["messages"].append(copy.deepcopy(value["messages"][1]))
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"})

    def test_missing_result(self):
        value = body(pair("r", "read", TARGET, "strategy"))
        value["messages"].pop()
        with self.assertRaises(ContractError):
            verify_delivery(value, {TARGET: "strategy"})

    def test_target_revisions(self):
        value = body(pair("w1", "write", TARGET, "first"), pair("r1", "read", TARGET, "first"),
                     pair("w2", "write", TARGET, "second"), pair("r2", "read", TARGET, "second"))
        self.assertIn(TARGET, verify_delivery(value, {TARGET: "second"}, after="w2"))
        with self.assertRaisesRegex(ContractError, "last successful"):
            verify_delivery(value, {TARGET: "second"}, after="w1")
        with self.assertRaisesRegex(ContractError, "history conflicts"):
            verify_delivery(value, {TARGET: "second"})

    def test_keep_base(self):
        self.assertIn(TARGET, verify_delivery(body(pair("r", "read", TARGET, "base")), {TARGET: "base"}))
        self.assertIn(TARGET, verify_delivery(body(pair("r", "read", TARGET, "base\n")), {TARGET: "base\n"}))

    def test_unrelated_malformed(self):
        value = body(pair("target", "read", TARGET, "strategy"),
                     pair("unrelated", "read", NOTES, "notes", offset=2, limit=1))
        value["messages"][-2]["content"][0]["input"]["offset"] = 1
        with self.assertRaisesRegex(ContractError, "undeclared line range"):
            verify_delivery(value, {TARGET: "strategy"})
        value = body(pair("target", "read", TARGET, "strategy"), pair("unrelated", "read", NOTES, "notes"))
        value["messages"][-2]["content"][0]["caller"] = {"type": "foreign"}
        with self.assertRaisesRegex(ContractError, "actual tool call"):
            verify_delivery(value, {TARGET: "strategy"})
        for number in (0, -1):
            with self.subTest(number=number):
                value = body(pair("target", "read", TARGET, "strategy"), pair("unrelated", "read", NOTES, "notes"))
                value["messages"][-1]["content"][0]["content"] = value["messages"][-1]["content"][0]["content"].replace("1: notes", f"{number}: notes")
                with self.assertRaises(ContractError):
                    verify_delivery(value, {TARGET: "strategy"})
        for offset in (0, -1, True):
            with self.subTest(offset=offset):
                value = body(pair("target", "read", TARGET, "strategy"), pair("unrelated", "read", NOTES, "notes", error=True))
                value["messages"][-2]["content"][0]["input"]["offset"] = offset
                with self.assertRaises(ContractError):
                    verify_delivery(value, {TARGET: "strategy"})


if __name__ == "__main__":
    unittest.main()
