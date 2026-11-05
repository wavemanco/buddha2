"""Exact target-scoped delivery proof over globally validated tool history."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v3.evidence import _after_mutation

READ_CONSUMPTION_POLICY_ID = "read-consumption-diagnostic-v1"


class ReadFormatError(ContractError):
    """A renderer cannot be interpreted; tool identity and ranges remain hard checks."""


def _format(value: bool, reason: str) -> None:
    if not value:
        raise ReadFormatError(reason)


def require(value: bool, reason: str) -> None:
    if not value:
        raise ContractError(reason)


def normalized_output(value: object) -> str:
    """Match native text-file reading without changing internal content."""
    if not isinstance(value, str):
        raise ContractError("returned output must be text")
    return value.replace("\r\n", "\n").strip()


def retain_operator_records(directory, relative_paths: list[str]) -> list[dict]:
    """Embed explicitly selected public S2 operator evidence losslessly at closure.

    The caller chooses the known public records; this helper never enumerates an
    operator directory or reads credential/stream files to decide eligibility.
    """
    import base64
    from pathlib import Path, PurePosixPath

    from .snapshot import checked_path, lexical
    from .support import BASE, ROOT

    directory = Path(directory)
    allowed = (ROOT / "runs/phase3b-seq2-v1/operator", BASE / "operator")
    require(directory in allowed, "operator evidence requires the exact S2 operator root")
    require(isinstance(relative_paths, list) and len(relative_paths) == len(set(relative_paths)),
            "operator paths must be an explicit unique list")
    records = []
    for name in relative_paths:
        require(isinstance(name, str) and bool(name), "operator relative path missing")
        lexical(name)
        parts = PurePosixPath(name)
        require(not parts.is_absolute() and bool(parts.parts) and "\\" not in name,
                "operator path must be canonical relative POSIX")
        target = checked_path(directory / Path(*parts.parts), directory)
        require(target.is_file() and target.stat().st_size <= 4_000_000,
                "operator evidence is missing, nonregular or oversized")
        raw = target.read_bytes()
        records.append({"path": "operator/" + name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "base64": base64.b64encode(raw).decode("ascii")})
    return records


def _read_result(call: dict, block: dict) -> tuple[str, dict[int, str]]:
    content = block.get("content", "")
    if isinstance(content, list):
        _format(all(isinstance(p, dict) and p.get("type") == "text"
                    and isinstance(p.get("text"), str) for p in content), "invalid read content blocks")
        content = "\n".join(p["text"] for p in content)
    _format(isinstance(content, str), "invalid read content")
    path = re.search(r"<path>([^\n]+)</path>", content)
    data = re.search(r"<content>\n(.*?)\n</content>", content, re.DOTALL)
    if path is None or data is None:
        raise ReadFormatError("numbered file read envelope missing")
    require(path.group(1) == call["filePath"], "read result names a different file")
    offset, limit = call.get("offset", 1), call.get("limit", 2000)
    require(type(offset) is int and type(limit) is int and offset >= 1 and limit >= 1,
            "invalid declared read range")
    lines: dict[int, str] = {}
    page: re.Match[str] | None = None
    other_footer = False
    for line in data.group(1).splitlines():
        _format(page is None or not line, "content follows paged read footer")
        if not line:
            continue
        footer = re.fullmatch(
            r"\((Output capped at 50 KB\. )?Showing lines ([1-9][0-9]*)-([1-9][0-9]*)"
            r"(?: of ([1-9][0-9]*))?\. Use offset=([1-9][0-9]*) to continue\.\)",
            line)
        if footer is not None:
            _format(page is None and not other_footer, "duplicate or mixed paged read footer")
            capped = footer[1] is not None
            start, end, following = map(int, footer.group(2, 3, 5))
            total = int(footer[4]) if footer[4] is not None else None
            _format(capped == (total is None), "unsupported read continuation footer")
            require(start == offset and start <= end and (total is None or end < total)
                    and (not capped or len(lines) < limit) and following == end + 1
                    and len(lines) == end - start + 1
                    and all(number == start + i for i, number in enumerate(lines)),
                    "paged read footer disagrees with declared range or numbered content")
            page = footer
            continue
        match = re.fullmatch(r"([1-9][0-9]*):(?: (.*))?", line)
        if match is None:
            _format(page is None, "content follows paged read footer")
            _format(not line or re.fullmatch(r"\(End of file - total \d+ lines\)", line) is not None
                    or re.fullmatch(r"\(File has more lines\..*\)", line) is not None,
                    "malformed numbered read content")
            other_footer = True
            continue
        number, text = int(match[1]), match[2] or ""
        require(offset <= number < offset + limit, "read returned undeclared line range")
        _format(number not in lines, "duplicate line in one read result")
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
    require(set(calls) == set(results), "actual tool call has no result")
    return calls, results


def _read_window(body: dict, calls: dict, results: dict, targets: set[str], after: str | None) -> dict:
    if after is not None:
        require(after in calls and calls[after]["name"] in {"write", "edit"}
                and calls[after]["input"]["filePath"] in targets, "mutation is not of the delivery target")
        for path in targets:
            mutations = [identity for identity, call in calls.items()
                         if call["name"] in {"write", "edit"} and call["input"]["filePath"] == path
                         and not results[identity].get("is_error")]
            require(bool(mutations) and mutations[-1] == after, "proof does not follow last successful target mutation")
        return _after_mutation(body, after)
    return body


def _collect(body: dict, targets: set[str], after: str | None = None) -> dict[str, dict[int, str]]:
    calls, results = _history(body)
    window = _read_window(body, calls, results, targets, after)
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


def _ranges(numbers: set[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for number in sorted(numbers):
        if result and number == result[-1][1] + 1:
            result[-1][1] = number
        else:
            result.append([number, number])
    return result


def audit_delivery(body: dict, expected: dict[str, str], *, after: str | None = None) -> dict:
    """Audit every target and read failure without making exhaustive consumption a gate."""
    require(isinstance(expected, dict) and bool(expected) and all(
        isinstance(p, str) and bool(p) and isinstance(t, str) for p, t in expected.items()),
        "invalid delivery targets")
    calls, results = _history(body)
    window = _read_window(body, calls, results, set(expected), after)
    delivered: dict[str, dict[int, str]] = {}
    conflicts: dict[str, set[int]] = {}
    read_errors: list[dict] = []
    parse_errors: list[dict] = []
    for message in window["messages"]:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if block.get("type") != "tool_result":
                continue
            identity = block["tool_use_id"]
            call = calls[identity]
            if call["name"] != "read":
                continue
            path = call["input"]["filePath"]
            if block.get("is_error"):
                read_errors.append({"tool_id": identity, "path": path})
                continue
            try:
                path, rows = _read_result(call["input"], block)
            except ReadFormatError as exc:
                parse_errors.append({"tool_id": identity, "path": path, "reason": str(exc)})
                continue
            if path not in expected:
                continue
            seen = delivered.setdefault(path, {})
            for number, text in rows.items():
                if number in seen and seen[number] != text:
                    conflicts.setdefault(path, set()).add(number)
                else:
                    seen[number] = text
    files = {}
    for path, text in expected.items():
        lines = text.splitlines()
        seen = delivered.get(path, {})
        wanted = set(range(1, len(lines) + 1))
        missing = wanted - set(seen)
        mismatch = {n for n in wanted & set(seen) if seen[n] != lines[n - 1]}
        unexpected = set(seen) - wanted
        conflicting = conflicts.get(path, set())
        failed = [r["tool_id"] for r in read_errors if r["path"] == path]
        unparsed = [r["tool_id"] for r in parse_errors if r["path"] == path]
        complete = path in delivered and not any((missing, mismatch, unexpected, conflicting, failed, unparsed))
        files[path] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_utf8_bytes": len(text.encode("utf-8")), "source_lines": len(lines),
            "observed_lines": len(seen), "missing_ranges": _ranges(missing),
            "mismatched_ranges": _ranges(mismatch), "conflicting_ranges": _ranges(conflicting),
            "unexpected_ranges": _ranges(unexpected), "read_errors": failed, "parse_errors": unparsed,
            "required": True, "complete": complete, "all_lines_model_visible": complete}
    return {"policy_id": READ_CONSUMPTION_POLICY_ID, "complete": all(v["complete"] for v in files.values())
            and not read_errors and not parse_errors, "files": files,
            "read_errors": read_errors, "parse_errors": parse_errors}


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


def _original_source(expected: dict[str, str], cwd: str, manifest: dict,
                     original: dict[str, str], views: dict[str, str]) -> tuple[dict, str, str, str]:
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
    return entry, text, source_hash, raw


def audit_original_strategy(body: dict, expected: dict[str, str], *, cwd: str,
                            manifest: dict, original: dict[str, str], views: dict[str, str]) -> tuple[dict, dict]:
    """Keep original input/source binding hard; report its observed consumption separately."""
    entry, text, source_hash, raw = _original_source(expected, cwd, manifest, original, views)
    audit = audit_delivery(body, expected)
    # The authenticated lossless strategy views remain an alternative to rereading its raw file.
    audit["files"][raw]["required"] = False
    audit["complete"] = all(v["complete"] for v in audit["files"].values() if v["required"])
    audit["complete"] = audit["complete"] and not audit["read_errors"] and not audit["parse_errors"]
    raw_complete = audit["files"][raw]["complete"]
    view_paths = [cwd + "/context/" + chunk["path"] for chunk in entry["chunks"]]
    views_complete = all(audit["files"][path]["complete"] for path in view_paths)
    return audit, {"source_path": "harness/systemprompt.md", "source_sha256": source_hash,
        "source_utf8_bytes": len(text.encode()), "raw_path": raw,
        "route": "raw" if raw_complete else "declared_lossless_view" if views_complete else "incomplete",
        "all_declared_views_model_visible_before_decision": views_complete,
        "read_consumption_policy": READ_CONSUMPTION_POLICY_ID}


def verify_original_strategy(body: dict, expected: dict[str, str], *, cwd: str,
                             manifest: dict, original: dict[str, str], views: dict[str, str]) -> tuple[dict, dict]:
    """Strict historical attestation; current live policy uses audit_original_strategy."""
    entry, text, source_hash, raw = _original_source(expected, cwd, manifest, original, views)
    source = "harness/systemprompt.md"
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
