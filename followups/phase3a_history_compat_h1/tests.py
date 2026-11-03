"""Adverse history checks must stop before another mocked admission."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v4.editor import _FALSE, relay

from . import runtime, verify
from .guard import HistoryGuard


class HistoryTests(unittest.TestCase):
    def test_inventory_private_files_and_directories_are_filtered_before_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "transform.ts"
            target.write_text("SYNTHETIC", encoding="utf-8")
            (root / "AUTH.JSON").write_text("SYNTHETIC DO NOT READ", encoding="utf-8")
            private_dir = root / "credentials.json"
            private_dir.mkdir()
            (private_dir / "hidden.txt").write_text("SYNTHETIC DO NOT READ", encoding="utf-8")
            (root / "public").mkdir()
            (root / "public/value.txt").write_text("SYNTHETIC PUBLIC", encoding="utf-8")
            (root / "public-link").symlink_to(root / "public", target_is_directory=True)
            real_stat, real_lstat, real_is_dir = Path.stat, Path.lstat, Path.is_dir
            real_listdir = runtime.os.listdir

            def check(path):
                if any(part.casefold() in runtime.PRIVATE for part in Path(path).parts):
                    self.fail("private metadata/content access occurred")
                if Path(path) == root / "public-link":
                    self.fail("public symlink traversal occurred")

            def guarded_stat(path, *args, **kwargs):
                if any(part.casefold() in runtime.PRIVATE for part in path.parts):
                    self.fail("private stat occurred")
                return real_stat(path, *args, **kwargs)

            def guarded_lstat(path, *args, **kwargs):
                if any(part.casefold() in runtime.PRIVATE for part in path.parts):
                    self.fail("private lstat occurred")
                return real_lstat(path, *args, **kwargs)

            def guarded_is_dir(path):
                check(path)
                return real_is_dir(path)

            def guarded_listdir(path):
                check(path)
                return real_listdir(path)

            with (
                mock.patch.object(Path, "stat", guarded_stat),
                mock.patch.object(Path, "lstat", guarded_lstat),
                mock.patch.object(Path, "is_dir", guarded_is_dir),
                mock.patch.object(runtime.os, "listdir", guarded_listdir),
            ):
                result = runtime.inventory(root, target)
            self.assertEqual(result["all_other_entry_count"], 3)
            self.assertEqual(len(result["excluded_private_names"]), 2)

    def start(self):
        content = [
            {"type": "thinking", "thinking": "", "signature": "SYNTHETIC"},
            {
                "type": "thinking",
                "thinking": "SYNTHETIC ONLY",
                "signature": "SYNTHETIC-2",
            },
            {"type": "redacted_thinking", "data": "SYNTHETIC-3"},
            {
                "type": "tool_use",
                "id": "read01",
                "name": "read",
                "input": {"filePath": "/tmp/fixture"},
                "caller": {"type": "direct"},
            },
        ]
        calls = []

        def delegate(slot, role, request):
            calls.append(slot)
            return {
                "status": "response",
                "response": {
                    "provider_response": {
                        "content": copy.deepcopy(content),
                        "stop_reason": "tool_use",
                    }
                },
            }

        guard = HistoryGuard(delegate, "fixture")
        initial: dict = {
            "model": "claude-opus-5",
            "messages": [{"role": "user", "content": "SYNTHETIC"}],
        }
        guard("fixture.t01", "editor", initial)
        next_request = copy.deepcopy(initial)
        next_request["messages"] += [
            {"role": "assistant", "content": copy.deepcopy(content)},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "read01",
                        "content": "SYNTHETIC RESULT",
                    }
                ],
            },
        ]
        return guard, calls, next_request

    def test_empty_visible_redacted_and_direct_caller_preserved(self):
        guard, calls, request = self.start()
        del request["messages"][1]["content"][-1]["caller"]
        guard("fixture.t02", "editor", request)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(a["history_restored"] for a in guard.audits))

    def test_all_history_tampering_stops_before_second_admission(self):
        for kind in (
            "drop",
            "change-signature",
            "change-visible",
            "duplicate",
            "reorder",
            "tool-input",
            "missing-tool",
            "prior-user",
            "tool-result-id",
            "tool-result-duplicate",
            "model",
            "cross-conversation",
            "incomplete-stream-history",
        ):
            with self.subTest(kind=kind):
                guard, calls, request = self.start()
                blocks = request["messages"][1]["content"]
                slot = "fixture.t02"
                if kind in {"drop", "incomplete-stream-history"}:
                    blocks.pop(0)
                elif kind == "change-signature":
                    blocks[0]["signature"] += "CHANGED"
                elif kind == "change-visible":
                    blocks[1]["thinking"] += "CHANGED"
                elif kind == "duplicate":
                    blocks.insert(0, copy.deepcopy(blocks[0]))
                elif kind == "reorder":
                    blocks[0], blocks[2] = blocks[2], blocks[0]
                elif kind == "tool-input":
                    blocks[-1]["input"]["filePath"] = "/tmp/other"
                elif kind == "missing-tool":
                    blocks.pop()
                elif kind == "prior-user":
                    request["messages"][0]["content"] = "CHANGED"
                elif kind == "tool-result-id":
                    request["messages"][-1]["content"][0]["tool_use_id"] = "other"
                elif kind == "tool-result-duplicate":
                    request["messages"][-1]["content"] *= 2
                elif kind == "model":
                    request["model"] = "other"
                elif kind == "cross-conversation":
                    slot = "foreign.t02"
                with self.assertRaises(ContractError):
                    guard(slot, "editor", request)
                self.assertEqual(len(calls), 1)

    def test_incomplete_provider_result_cannot_advance(self):
        calls = []

        def incomplete(*args):
            calls.append(True)
            return {
                "status": "response",
                "response": {"provider_response": {"content": []}},
            }

        guard = HistoryGuard(incomplete, "fixture")
        for _ in range(2):
            with self.assertRaises(ContractError):
                guard(
                    "fixture.t01",
                    "editor",
                    {"messages": [{"role": "user", "content": "SYNTHETIC"}]},
                )
        self.assertEqual(guard.responses, [])
        self.assertTrue(guard.stopped)
        self.assertEqual(len(calls), 1)

    def test_terminal_sixteen_is_outside_ordinary_guard(self):
        guard = HistoryGuard(lambda *args: self.fail("terminal dispatch forbidden"), "fixture")
        guard.responses = [[] for _ in range(15)]
        with self.assertRaises(ContractError):
            guard("fixture.t16", "editor", {"messages": [{"role": "user", "content": "SYNTHETIC"}]})

    def test_identical_local_request_replays_without_admission(self):
        calls = []

        def dispatch(*args):
            calls.append(True)
            return {
                "status": "response",
                "response": {
                    "provider_response": {
                        "id": "fixture",
                        "type": "message",
                        "role": "assistant",
                        "model": "claude-opus-5",
                        "content": [{"type": "text", "text": "SYNTHETIC"}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }
                },
            }

        raw = {
            "model": "claude-opus-5",
            "max_tokens": 16000,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
            "stream": True,
            "messages": [{"role": "user", "content": "SYNTHETIC"}],
        }
        record = {"fixture": True, "requests": []}
        with (
            tempfile.TemporaryDirectory() as directory,
            relay(
                Path(directory),
                HistoryGuard(dispatch, "fixture"),
                "fixture",
                record,
                lambda *a, **k: self.fail("unexpected relay halt"),
            ) as url,
        ):
            responses = []
            for _ in range(2):
                request = urllib.request.Request(
                    url + "/messages",
                    data=json.dumps(raw).encode(),
                    headers={"x-api-key": _FALSE},
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    responses.append(response.read())
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(len(calls), 1)
        self.assertEqual(record["local_response_replays"], 1)


class PreservationTests(unittest.TestCase):
    def study(self):
        return json.loads(
            (
                verify.ROOT / "runs/phase3a-c1-completion-v4/verification-v3/release/study.json"
            ).read_text(encoding="utf-8")
        )

    def test_unauthenticated_maps_cannot_touch_any_map_path(self):
        original = self.study()
        for kind in (
            "top-digest",
            "source-digest",
            "map-digest",
            "foreign-path",
            "private-path",
            "traversal-path",
            "wrong-count",
            "wrong-type",
        ):
            with self.subTest(kind=kind):
                study = copy.deepcopy(original)
                files = study["source"]["files"]
                name = next(iter(files))
                if kind == "top-digest":
                    study["source_sha256"] = "0" * 64
                elif kind == "source-digest":
                    study["source"]["sha256"] = "0" * 64
                elif kind == "map-digest":
                    files[name] = "0" * 64
                elif kind in {"foreign-path", "private-path", "traversal-path"}:
                    replacement = {
                        "foreign-path": "C:/SYNTHETIC-FOREIGN/source.py",
                        "private-path": "followups/AUTH.JSON",
                        "traversal-path": "../SYNTHETIC-FOREIGN/source.py",
                    }[kind]
                    files[replacement] = files.pop(name)
                elif kind == "wrong-count":
                    files.pop(name)
                elif kind == "wrong-type":
                    study["source"]["files"] = list(files)
                with (
                    mock.patch.object(Path, "read_text", return_value=json.dumps(study)),
                    mock.patch.object(
                        Path, "read_bytes", side_effect=AssertionError("map content accessed")
                    ),
                    mock.patch.object(Path, "open", side_effect=AssertionError("map file opened")),
                    mock.patch.object(
                        Path, "stat", side_effect=AssertionError("map stat accessed")
                    ),
                    mock.patch.object(
                        Path, "lstat", side_effect=AssertionError("map lstat accessed")
                    ),
                    mock.patch.object(
                        Path, "is_dir", side_effect=AssertionError("map type accessed")
                    ),
                    self.assertRaises(ValueError),
                ):
                    verify.preserved_r3()

    def test_authenticated_map_rejects_link_ancestor_before_leaf_access(self):
        import stat
        from types import SimpleNamespace

        study = self.study()
        name = next(iter(study["source"]["files"]))
        ancestor = verify.ROOT / Path(name).parts[0]
        for kind in ("symlink", "junction"):
            with self.subTest(kind=kind):
                visited = []

                def metadata(path):
                    visited.append(path)
                    if path == verify.ROOT:
                        return SimpleNamespace(st_mode=stat.S_IFDIR)
                    if path == ancestor:
                        return SimpleNamespace(
                            st_mode=stat.S_IFLNK if kind == "symlink" else stat.S_IFDIR,
                            st_file_attributes=0x400 if kind == "junction" else 0,
                        )
                    self.fail("accessed a descendant before rejecting its linked ancestor")

                with (
                    mock.patch.object(Path, "read_text", return_value=json.dumps(study)),
                    mock.patch.object(
                        Path, "read_bytes", side_effect=AssertionError("map content accessed")
                    ),
                    mock.patch.object(
                        Path, "stat", side_effect=AssertionError("following stat forbidden")
                    ),
                    mock.patch.object(Path, "lstat", metadata),
                    self.assertRaisesRegex(ValueError, "link or reparse"),
                ):
                    verify.preserved_r3()
                self.assertEqual(visited, [verify.ROOT, ancestor])


if __name__ == "__main__":
    unittest.main(verbosity=2)
