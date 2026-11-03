"""A known invalid JSON proposal must use native a2, through real pinned OpenCode."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import digest
from followups.phase3a_v1 import accounting, editor, native, strategy
from followups.phase3a_v1.tests.test_strategy import STUDY, TASK, FakeDispatch


class EditorShapeTests(unittest.TestCase):
    @unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires pinned real OpenCode runtime")
    def test_native_invalid_first_shape_then_real_editor_repair_and_zero_call_resume(self):
        from followups.phase3a_v1.mocks import SDKMock

        output = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results"))
        with tempfile.TemporaryDirectory(dir=output) as temporary, SDKMock(editor_invalid_first=True) as mock:
            root = Path(temporary)
            seed = root / "seed"
            strategy.materialize_seed(seed)
            fake = FakeDispatch()
            holds: list = []
            tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))

            def dispatch(slot, role, request):
                if role != "editor":
                    return fake(slot, role, request)
                if slot in fake.results:
                    self.assertEqual(fake.results[slot]["request_sha256"], digest(request))
                    return fake.results[slot]
                accounting.validate_request(role, request, editor_tools=tools)
                mock.transport.select(role, slot)
                response = mock.transport.create(role, request)
                intent = {"slot_id": slot, "role": role, "cell": "p3a-01:adaptive", "pair": "p3a-01",
                    "study_sha256": STUDY, "fixture": True, "dispatch_id": "shape-fixture:" + slot,
                    "request": request, "request_sha256": digest(request),
                    "reservation": accounting._reservation(role)}
                result = accounting._result(intent, response)
                self.assertEqual(result["status"], "response")
                fake.results[slot] = result
                return result

            def halt(*args, **kwargs):
                holds.append((args, kwargs))

            prop = editor.AccountedProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=dispatch,
                audit_dir=root / "adapt/editor-audit", fixture=True, halt=halt)
            result = native.run_adaptation(TASK, seed, study_sha256=STUDY, run_root=root / "adapt",
                tag="shape-repair", dispatch=dispatch, fixture=True, prop=prop,
                known_results={}, result_snapshot=lambda: fake.results, halt=halt)
            self.assertEqual(holds, [])
            self.assertEqual(result["status"], "complete")
            self.assertFalse(result["authentic"])
            stages = {row["label"]: row for row in result["stage_dispositions"]}
            self.assertFalse(any(row["fell_back"] for row in stages.values()))
            self.assertEqual(stages["inv1"]["accepted_editor_sessions"], ["inv1.a2"])
            evidence = result["editor_evidence"]["sessions"]
            self.assertEqual(evidence["inv1.a1"]["status"], "invalid_harvest")
            self.assertEqual(evidence["inv1.a2"]["status"], "valid")
            self.assertTrue(evidence["inv1.a1"]["input_snapshot"]["strategy_valid"])
            self.assertFalse(evidence["inv1.a2"]["input_snapshot"]["strategy_valid"])
            self.assertIsNone(evidence["inv1.a2"]["input_effective_strategy_sha256"])
            self.assertTrue(evidence["inv1.a2"]["authentic_eligible"])
            self.assertEqual(mock.http_calls, 12)
            returned_tools = [block for record in mock.records for block in record["response"]["content"]
                              if block["type"] == "tool_use"]
            self.assertTrue(returned_tools)
            self.assertTrue(all(block["caller"] == {"type": "direct"} for block in returned_tools))
            self.assertEqual(len(fake.sent), 48)
            self.assertTrue(result["native"]["selections"]["agg"]["trivial"])
            before = mock.http_calls, len(fake.sent)
            self.assertEqual(native.validate_adaptation(result, TASK, seed, study_sha256=STUDY,
                run_root=root / "adapt", tag="shape-repair", fixture=True, results=fake.results), result)
            self.assertEqual(native.run_adaptation(TASK, seed, study_sha256=STUDY, run_root=root / "adapt",
                tag="shape-repair", dispatch=dispatch, fixture=True, prop=prop,
                known_results=fake.results, result_snapshot=lambda: fake.results, halt=halt), result)
            self.assertEqual((mock.http_calls, len(fake.sent)), before)


if __name__ == "__main__":
    unittest.main()
