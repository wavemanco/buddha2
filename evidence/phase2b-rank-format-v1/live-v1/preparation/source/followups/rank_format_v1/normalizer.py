"""Pure, bounded N1 derivation over visible rank text and exact parent IDs.

The caller validates the original settled rank role/model and parent provenance.
No source response is repaired or relabelled; this returns derived diagnostics.
"""

import json

POLICY_ID = "rank-format-N1"
MAX_UTF8_BYTES = 65_536
MAX_STRUCTURAL_DEPTH = 2
MAX_CANDIDATE_OBJECTS = 16


class _Rejected(ValueError):
    """A stable policy rejection, rather than an implementation exception."""


def _object_end(text: str, start: int) -> int:
    stack = ["}"]
    quoted = escaped = False
    for position in range(start + 1, len(text)):
        char = text[position]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
            if len(stack) > MAX_STRUCTURAL_DEPTH:
                raise _Rejected("depth_limit")
        elif char in "}]":
            if char != stack.pop():
                raise _Rejected("malformed_boundary")
            if not stack:
                return position + 1
    raise _Rejected("malformed_boundary")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _Rejected("duplicate_keys")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise _Rejected("nonfinite")


def normalize_rank(text: str, parent_ids: list[str]) -> dict:
    """Accept one unique valid tuple; any invalid/conflicting candidate vetoes it.

    Candidate offsets are code-point indices, with exclusive ``end``. Rejected
    results have no selected order; diagnostics may include the unparsed
    offending candidate with ``end``/``order`` set to None.
    """
    candidates: list[dict] = []

    def rejected(reason: str) -> dict:
        return {"policy_id": POLICY_ID, "status": "rejected", "order": None,
                "candidates": candidates, "reason": reason}

    if (type(parent_ids) is not list or len(parent_ids) != 10
            or any(type(value) is not str or not value for value in parent_ids)
            or len(set(parent_ids)) != 10):
        return rejected("invalid_parent_ids")
    try:
        for value in parent_ids:
            value.encode("utf-8", errors="strict")
    except UnicodeError:
        return rejected("invalid_parent_ids")
    if type(text) is not str:
        return rejected("invalid_input_type")
    # Every UTF-8 scalar needs at least one byte; reject oversized strings
    # before allocating their encoding. Encoding a remaining input is bounded.
    if len(text) > MAX_UTF8_BYTES:
        return rejected("size_limit")
    try:
        if len(text.encode("utf-8", errors="strict")) > MAX_UTF8_BYTES:
            return rejected("size_limit")
    except UnicodeError:
        return rejected("invalid_utf8")

    parent_set = set(parent_ids)
    unique_order: tuple[str, ...] | None = None
    position = 0
    while position < len(text):
        char = text[position]
        if char in "[]}":
            return rejected("outside_delimiter")
        if char != "{":
            position += 1
            continue
        candidate: dict = {"start": position, "end": None, "order": None}
        # Preserve one offending position diagnostically, but never parse a
        # seventeenth object or choose among a resource-overflowing response.
        if len(candidates) == MAX_CANDIDATE_OBJECTS:
            candidates.append(candidate)
            return rejected("object_count_limit")
        candidates.append(candidate)
        try:
            end = _object_end(text, position)
            candidate["end"] = end
            value = json.loads(text[position:end], object_pairs_hook=_unique_keys,
                               parse_constant=_nonfinite)
        except _Rejected as exc:
            return rejected(str(exc))
        except (ValueError, RecursionError):
            return rejected("malformed_json")
        if (type(value) is not dict or set(value) != {"order"}
                or type(value["order"]) is not list
                or any(type(item) is not str for item in value["order"])):
            return rejected("invalid_shape")
        order = value["order"]
        if len(order) != 10 or len(set(order)) != 10 or set(order) != parent_set:
            return rejected("invalid_ids")
        candidate["order"] = order
        current = tuple(order)
        if unique_order is not None and current != unique_order:
            return rejected("ambiguous_order")
        unique_order = current
        position = end
    if unique_order is None:
        return rejected("no_candidate")
    return {"policy_id": POLICY_ID, "status": "accepted", "order": list(unique_order),
            "candidates": candidates, "reason": None}
