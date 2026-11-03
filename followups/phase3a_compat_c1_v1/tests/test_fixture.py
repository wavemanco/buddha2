"""C1 delivery checks and the actual pinned native/OpenCode scripted composite."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from buddha2.artifacts import ContractError, digest
from followups.phase3a_compat_c1_v1.mocks import SDKMock, verify_delivery, visible_read_lines


def read_exchange(path: str, text: str, *, identity="read_1", offset=1, limit=2000):
    lines = text.splitlines()
    shown = "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1) if offset <= i < offset + limit)
    return [{"role": "assistant", "content": [{"type": "tool_use", "id": identity, "name": "read",
        "input": {"filePath": path, "offset": offset, "limit": limit}, "caller": {"type": "direct"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": identity,
          "content": f"<path>{path}</path>\n<type>file</type>\n<content>\n{shown}\n\n(End of file - total {len(lines)} lines)\n</content>"}]}]


class FixtureTests(unittest.TestCase):
    def test_full_visible_evidence_requires_results_not_issued_reads_or_a_summary(self):
        path, text = "/fixture/evidence.json", 'A literal <content> token.\nSecond line: 雪.\n\nLast line.\n'
        messages = read_exchange(path, text)
        proof = verify_delivery({"messages": messages}, {path: text})
        self.assertTrue(proof[path]["all_lines_model_visible"])
        self.assertEqual(proof[path]["source_lines"], 4)
        for bad in ({"messages": messages[:1]}, {"messages": [{"role": "user", "content": text}]},
                    {"messages": read_exchange(path, text, limit=2)}):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                verify_delivery(bad, {path: text})
        wrong = copy.deepcopy(messages)
        wrong[-1]["content"][0]["content"] = wrong[-1]["content"][0]["content"].replace('2: Second line', '2: Summary of second line')
        with self.assertRaises(ContractError):
            verify_delivery({"messages": wrong}, {path: text})

    def test_read_identity_caller_and_numbered_ranges_are_checked(self):
        messages = read_exchange("/fixture/a.txt", "One\nTwo\n")
        wrong = copy.deepcopy(messages)
        wrong[0]["content"][0]["caller"] = {"type": "code_execution_20250825", "tool_id": "bad"}
        with self.assertRaises(ContractError):
            visible_read_lines({"messages": wrong})
        wrong = copy.deepcopy(messages)
        wrong[1]["content"][0]["content"] = wrong[1]["content"][0]["content"].replace('/fixture/a.txt', '/fixture/b.txt')
        with self.assertRaises(ContractError):
            visible_read_lines({"messages": wrong})
        wrong = copy.deepcopy(messages)
        wrong[0]["content"][0]["input"]["limit"] = 1
        with self.assertRaises(ContractError):
            visible_read_lines({"messages": wrong})
        unknown = copy.deepcopy(messages)
        unknown[1]["content"][0]["tool_use_id"] = "unissued"
        with self.assertRaises(ContractError):
            verify_delivery({"messages": unknown}, {"/fixture/a.txt": "One\nTwo\n"})

    def test_frozen_lossless_view_detects_original_rewriting_and_missing_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            context = cwd / 'context'
            (context / 'harness').mkdir(parents=True)
            (context / 'C1_EVIDENCE').mkdir()
            current = {key: 'Synthetic ' + key for key in ('answer_system', 'plan_system', 'rank_system')}
            (context / 'harness/systemprompt.md').write_text(json.dumps(current), encoding='utf-8')
            original = 'A long literal evidence string: ' + '雪' * 9000
            data = original.encode('utf-8')
            (context / 'task.txt').write_bytes(data)
            view = {'source_path': 'task.txt', 'source_sha256': hashlib.sha256(data).hexdigest(),
                    'char_start': 0, 'char_end': len(original), 'text': [original]}
            view_data = (json.dumps(view) + '\n').encode()
            view_path = context / 'C1_EVIDENCE/000.json'
            view_path.write_bytes(view_data)
            entry: dict = {'path': 'task.txt', 'kind': 'synthetic-parser-unit-fixture', 'bytes': len(data),
                     'sha256': view['source_sha256'], 'chunks': [{'path': 'C1_EVIDENCE/000.json',
                        'bytes': len(view_data), 'sha256': hashlib.sha256(view_data).hexdigest(),
                        'offset': 1, 'limit': 1, 'char_start': 0, 'char_end': len(original)}]}
            mission = 'Synthetic unit-test C1 mission.\n'
            (cwd / 'MISSION.md').write_text(mission, encoding='utf-8')
            (context / 'C1_INDEX.md').write_text('Synthetic unit-test evidence index.\n', encoding='utf-8')
            system = 'BUDDHA2-C1-OPEN-CODE-SYSTEM-V1\n' + mission
            manifest = {'kind': 'phase3a-c1-evidence-v1', 'role': 'INV', 'label': 'inv1.a1',
                        'effective_mission_sha256': hashlib.sha256(mission.encode()).hexdigest(),
                        'required_evidence': [entry]}
            def publish():
                manifest['sha256'] = digest({k: v for k, v in manifest.items() if k != 'sha256'})
                (context / 'C1_MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            publish()
            mock = SDKMock()
            with self.assertRaises(ContractError):
                mock._start(cwd, 'inv1.a1')
            mock.register_contract('inv1.a1', {'manifest': manifest, 'authoring_system_text': system})
            state = mock._start(cwd, 'inv1.a1')
            self.assertTrue(state['source_proof'][str(context / 'task.txt')]['lossless_reconstruction'])
            body = {"system": [{"text": system + "\nWorking directory: " + str(cwd)}], "messages": []}
            first, _ = mock._editor_content(body, "p3a-01.adaptive.editor.inv1.a1.t01")
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0]["input"]["filePath"], str(cwd / "MISSION.md"))
            with self.assertRaises(ContractError):
                mock._editor_content(body, "p3a-01.adaptive.editor.inv1.a1.t02")
            self.assertFalse(mock.c1_sessions['inv1.a1']['mission_visible_before_evidence'])
            (cwd / 'MISSION.md').write_text('Wrong mission.', encoding='utf-8')
            with self.assertRaises(ContractError):
                mock._editor_content(body, "p3a-01.adaptive.editor.inv1.a1.t02")
            (cwd / 'MISSION.md').write_text(mission, encoding='utf-8')
            body['messages'] = read_exchange(str(cwd / 'MISSION.md'), mission)
            second, _ = mock._editor_content(body, "p3a-01.adaptive.editor.inv1.a1.t02")
            self.assertTrue(mock.c1_sessions['inv1.a1']['mission_visible_before_evidence'])
            self.assertTrue(any(call['input']['filePath'] == str(view_path) for call in second))
            without_profile = copy.deepcopy(body)
            without_profile['system'][0]['text'] = 'A generic unavailable-tool profile.\nWorking directory: ' + str(cwd)
            with self.assertRaises(ContractError):
                mock._editor_content(without_profile, "p3a-01.adaptive.editor.inv1.a1.t02")
            # A self-consistent view hash cannot authorize changed/missing original content.
            for changed in ('a rewritten summary', original[:-1]):
                with self.subTest(changed_length=len(changed)):
                    view['text'] = [changed]
                    view['char_end'] = len(changed)
                    view_data = (json.dumps(view) + '\n').encode()
                    view_path.write_bytes(view_data)
                    entry['chunks'][0].update(bytes=len(view_data), sha256=hashlib.sha256(view_data).hexdigest(),
                                               char_end=len(changed))
                    publish()
                    fresh = SDKMock()
                    fresh.register_contract('inv1.a1', {'manifest': manifest, 'authoring_system_text': system})
                    with self.assertRaises(ContractError):
                        fresh._start(cwd, 'inv1.a1')
            with self.assertRaises(ContractError):
                SDKMock._context_file(cwd, '../outside')


    @unittest.skipUnless(Path("/opt/phase3a-opencode").is_dir(), "requires actual pinned OpenCode")
    def test_real_native_composite_sees_complete_evidence_before_edits_and_keep_base(self):
        import os

        from followups.phase3a_compat_c1_v1.adapter import CompatibleProposer
        from followups.phase3a_v1 import accounting, native, strategy
        from followups.phase3a_v1.tests.test_strategy import STUDY, TASK

        output = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-compat-c1-v1"
        output.mkdir(parents=True, exist_ok=True)
        tools = json.loads((strategy.ROOT / "followups/phase3a_v1/editor-tools.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=output) as tmp, SDKMock() as mock:
            root = Path(tmp)
            seed = root / "seed"
            results: dict = {}
            holds: list = []
            strategy.materialize_seed(seed)

            def dispatch(slot, role, request):
                if slot in results:
                    self.assertEqual(results[slot]["request_sha256"], digest(request))
                    return copy.deepcopy(results[slot])
                accounting.validate_request(role, request, editor_tools=tools)
                mock.transport.select(role, slot)
                response = mock.transport.create(role, request)
                intent = {"slot_id": slot, "role": role, "cell": "p3a-01:adaptive", "pair": "p3a-01",
                    "study_sha256": STUDY, "fixture": True, "dispatch_id": "c1-fixture:" + slot,
                    "request": request, "request_sha256": digest(request),
                    "reservation": accounting._reservation(role)}
                result = accounting._result(intent, response)
                self.assertEqual(result["status"], "response")
                results[slot] = result
                return copy.deepcopy(result)

            def halt(*args, **kwargs):
                holds.append((args, kwargs))

            proposer = CompatibleProposer(pilot="p3a-01", study_sha256=STUDY, dispatch=dispatch,
                audit_dir=root / "adapt/editor-audit", fixture=True, halt=halt,
                register_contract=mock.register_contract)
            result = native.run_adaptation(TASK, seed, study_sha256=STUDY, run_root=root / "adapt",
                tag="c1-composite", dispatch=dispatch, fixture=True, prop=proposer,
                known_results={}, result_snapshot=lambda: results, halt=halt)
            self.assertEqual(holds, [], json.dumps({"fixture_errors": mock.c1_errors,
                "sessions": mock.c1_sessions, "editor": proposer.phase3a_evidence()}, ensure_ascii=False))
            self.assertEqual(result["status"], "complete", json.dumps({"native": result["native"],
                "editor": proposer.phase3a_evidence(), "c1": proposer.c1_evidence(),
                "mock_roles": [row["role"] for row in mock.records],
                "failures": [str(p) + ":" + p.read_text() for p in (root / "adapt").rglob("failure.json")]},
                ensure_ascii=False))
            self.assertFalse(result["authentic"])
            self.assertEqual(set(mock.c1_sessions), {"inv1.a1", "dom1.a1", "agg1.a1"})
            stages = {row["label"]: row for row in result["stage_dispositions"]}
            self.assertFalse(any(row["fell_back"] for row in stages.values()))
            self.assertTrue(stages["dom1"]["kept_base"])
            self.assertFalse(stages["inv1"]["kept_base"])
            self.assertTrue(all(row["authentic_eligible"] for row in stages.values()))
            self.assertEqual(mock.c1_sessions["dom1.a1"]["decision"], "KEEP_BASE")
            self.assertFalse(mock.c1_sessions["dom1.a1"]["effective_changed"])
            for evidence in mock.c1_sessions.values():
                self.assertTrue(evidence["decision_after_complete_evidence"])
                self.assertTrue(evidence["mission_visible_before_evidence"])
                self.assertTrue(evidence["configured_system_visible_before_mission"])
                self.assertTrue(evidence["verification_after_write"])
                self.assertTrue(evidence["normal_final"])
                self.assertTrue(evidence["notes_reread_model_visible"])
                self.assertFalse(evidence["terminal_note_used"])
                self.assertLessEqual(evidence["ordinary_rounds"], 7)
                self.assertTrue(evidence["source_evidence"])
                self.assertTrue(all(row["lossless_reconstruction"] for row in evidence["source_evidence"].values()))
            self.assertEqual(result["native"]["modes"]["agg"]["ledger"]["R"], 4)
            self.assertEqual(result["native"]["modes"]["agg"]["ledger"]["P"], 3)
            self.assertEqual(result["native"]["selections"]["agg"]["chosen_label"], "agg1")
            baseline = strategy.validate_harness(seed)["strategy"]
            fields = {label: strategy.validate_harness(root / "adapt/rollouts" / label / "harness")["strategy"]
                      for label in ("base1", "inv1", "dom1", "agg1")}
            wires = {row["slot_id"]: row["request"] for row in mock.records}
            for label, rollout in result["rollouts"].items():
                for response in rollout["requests"]:
                    field = {"plan": "plan_system", "answer": "answer_system", "rank": "rank_system"}[response["role"]]
                    serialized = wires[response["slot_id"]]["system"]
                    if isinstance(serialized, list):
                        serialized = "\n".join(part["text"] for part in serialized)
                    self.assertEqual(serialized, fields[label][field])
            self.assertNotEqual(fields["inv1"]["answer_system"], baseline["answer_system"])
            self.assertEqual(fields["dom1"], baseline)
            self.assertEqual(fields["agg1"]["answer_system"], fields["inv1"]["answer_system"])
            self.assertNotEqual(fields["agg1"]["rank_system"], baseline["rank_system"])
            self.assertEqual(mock.http_calls, len(results))


if __name__ == '__main__':
    unittest.main()