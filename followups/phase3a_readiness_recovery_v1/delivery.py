"""Exact target-scoped delivery proof over globally validated tool history."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v3.evidence import _after_mutation


def require(value: bool, reason: str) -> None:
    if not value:
        raise ContractError(reason)


def _read_result(call: dict, block: dict) -> tuple[str, dict[int, str]]:
    content = block.get("content", "")
    if isinstance(content, list):
        require(all(isinstance(p, dict) and p.get("type") == "text"
                    and isinstance(p.get("text"), str) for p in content), "invalid read content blocks")
        content = "\n".join(p["text"] for p in content)
    require(isinstance(content, str), "invalid read content")
    path = re.search(r"<path>([^\n]+)</path>", content)
    data = re.search(r"<content>\n(.*?)\n</content>", content, re.DOTALL)
    if path is None or data is None:
        raise ContractError("numbered file read envelope missing")
    require(path.group(1) == call["filePath"], "read result names a different file")
    offset, limit = call.get("offset", 1), call.get("limit", 2000)
    require(type(offset) is int and type(limit) is int and offset >= 1 and limit >= 1,
            "invalid declared read range")
    lines: dict[int, str] = {}
    for line in data.group(1).splitlines():
        match = re.fullmatch(r"(\d+):(?: (.*))?", line)
        if match is None:
            require(not line or re.fullmatch(r"\(End of file - total \d+ lines\)", line) is not None
                    or re.fullmatch(r"\(File has more lines\..*\)", line) is not None,
                    "malformed numbered read content")
            continue
        number, text = int(match[1]), match[2] or ""
        require(offset <= number < offset + limit, "read returned undeclared line range")
        require(number not in lines, "duplicate line in one read result")
        lines[number] = text
    return path.group(1), lines


def _history(body: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Validate every tool, including tools unrelated to the requested target."""
    require(isinstance(body, dict) and isinstance(body.get("messages"), list), "tool history missing")
    calls: dict[str, dict] = {}
    results: dict[str, dict] = {}
    for message in body["messages"]:
        require(isinstance(message, dict), "malformed message")
        blocks = message.get("content", [])
        if not isinstance(blocks, list):
            require(isinstance(blocks, str), "malformed message content")
            continue
        for block in blocks:
            require(isinstance(block, dict), "malformed content block")
            if block.get("type") == "tool_use":
                identity, name, value = block.get("id"), block.get("name"), block.get("input")
                require(message.get("role") == "assistant" and isinstance(identity, str) and bool(identity)
                        and identity not in calls and name in {"read", "write", "edit"}
                        and block.get("caller") == {"type": "direct"} and isinstance(value, dict)
                        and isinstance(value.get("filePath"), str) and bool(value["filePath"]),
                        "invalid or duplicate actual tool call")
                if name == "read":
                    offset, limit = value.get("offset", 1), value.get("limit", 2000)
                    require(type(offset) is int and type(limit) is int and offset >= 1 and limit >= 1,
                            "invalid declared read range")
                calls[identity] = block
            elif block.get("type") == "tool_result":
                identity = block.get("tool_use_id")
                require(message.get("role") == "user" and isinstance(identity, str)
                        and identity in calls and identity not in results
                        and type(block.get("is_error", False)) is bool,
                        "forged, duplicate or malformed tool-result ownership")
                results[identity] = block
                if calls[identity]["name"] == "read" and not block.get("is_error"):
                    _read_result(calls[identity]["input"], block)
    require(set(calls) == set(results), "actual tool call has no result")
    return calls, results


def _collect(body: dict, targets: set[str], after: str | None = None) -> dict[str, dict[int, str]]:
    calls, results = _history(body)
    window = body
    if after is not None:
        require(after in calls and calls[after]["name"] in {"write", "edit"}
                and calls[after]["input"]["filePath"] in targets, "mutation is not of the delivery target")
        for path in targets:
            mutations = [identity for identity, call in calls.items()
                         if call["name"] in {"write", "edit"} and call["input"]["filePath"] == path
                         and not results[identity].get("is_error")]
            require(bool(mutations) and mutations[-1] == after, "proof does not follow last successful target mutation")
        window = _after_mutation(body, after)
    delivered: dict[str, dict[int, str]] = {}
    for message in window["messages"]:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if block.get("type") != "tool_result":
                continue
            call = calls[block["tool_use_id"]]
            if call["name"] != "read" or block.get("is_error"):
                continue
            path, rows = _read_result(call["input"], block)
            if path not in targets:
                continue
            target = delivered.setdefault(path, {})
            for number, text in rows.items():
                require(number not in target or target[number] == text, "target read history conflicts")
                target[number] = text
    return delivered


def verify_delivery(body: dict, expected: dict[str, str], *, after: str | None = None) -> dict:
    """Collect only requested paths, with no conflict swallowing or content selection."""
    require(isinstance(expected, dict) and bool(expected) and all(
        isinstance(p, str) and bool(p) and isinstance(t, str) for p, t in expected.items()),
        "invalid delivery targets")
    delivered = _collect(body, set(expected), after)
    proof: dict[str, Any] = {}
    for path, text in expected.items():
        lines = text.splitlines()
        # The pinned Read format omits a terminal newline separator; it does not add a numbered row.
        require(path in delivered and set(delivered[path]) == set(range(1, len(lines) + 1))
                and all(delivered[path][i] == line for i, line in enumerate(lines, 1)),
                "required complete target content is absent, stale or mismatched: " + path)
        proof[path] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       "source_lines": len(lines), "all_lines_model_visible": True}
    return proof


def verify_original_strategy(body: dict, expected: dict[str, str], *, cwd: str,
                             manifest: dict, original: dict[str, str], views: dict[str, str]) -> tuple[dict, dict]:
    """Only the original input may use lossless sources already authenticated by _sources."""
    source = "harness/systemprompt.md"
    matches = [entry for entry in manifest["required_evidence"] if entry["kind"] == "current_strategy"]
    require(len(matches) == 1 and matches[0]["path"] == source, "original strategy source path differs")
    entry = matches[0]
    require(source in original, "authenticated original strategy missing")
    text = original[source]
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    require(entry["sha256"] == source_hash and entry["bytes"] == len(text.encode("utf-8")),
            "original strategy source bytes/hash differ")
    raw = cwd + "/context/" + source
    require(expected.get(raw) == text, "original strategy proof is not for the original bytes")
    declared = [chunk["path"] for item in manifest["required_evidence"] for chunk in item["chunks"]]
    require(len(declared) == len(set(declared)) and set(declared) == set(views)
            and all(expected.get(cwd + "/context/" + path) == views[path] for path in declared),
            "required lossless view proof was omitted or substituted")
    # Every required view remains mandatory, including the original strategy's complete views.
    proof = verify_delivery(body, {path: value for path, value in expected.items() if path != raw})
    collected = _collect(body, {raw})
    seen = collected.get(raw, {})
    lines = text.splitlines()
    require(all(1 <= n <= len(lines) and lines[n - 1] == value for n, value in seen.items()),
            "raw original strategy contradicts its authenticated source")
    route = "raw" if raw in collected and set(seen) == set(range(1, len(lines) + 1)) else "declared_lossless_view"
    view_hashes = {chunk["path"]: hashlib.sha256(views[chunk["path"]].encode("utf-8")).hexdigest()
                   for chunk in entry["chunks"]}
    source_proof = {"route": route, "source_path": source, "raw_path": raw,
                    "source_sha256": source_hash, "source_utf8_bytes": len(text.encode("utf-8")),
                    "view_sha256": view_hashes,
                    "view_numbered_lines": {path: len(views[path].splitlines()) for path in view_hashes},
                    "all_declared_views_model_visible_before_decision": True,
                    "partial_raw_lines_checked_for_contradiction": len(seen)}
    proof[raw] = {"sha256": source_hash, "source_lines": len(lines),
                  "all_lines_model_visible": True, "original_source_route": route}
    return proof, source_proof
