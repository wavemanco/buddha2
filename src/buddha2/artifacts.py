"""Validated, content-addressed portfolios and native exchange using ordinary files."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .nb_worker import canonical_hash
from .nb_worker import validate_portfolio as _validate_portfolio


class ContractError(ValueError):
    """Input or existing evidence violates the declared artifact contract."""


def public_path_parts(parts: tuple[str, ...]) -> None:
    """Reject private and captured path names before any filesystem access."""
    private = {".git", ".writer.lock", "auth.json", "credentials.json",
               "credential-binding.json", "node_modules", ".venv", "venv"}
    for index, part in enumerate(parts):
        name = part.casefold()
        if (name in private or name.startswith(".env")
                or any(word in name for word in ("stdout", "stderr", "cache", "capture", "retained"))
                or (index < len(parts) - 1 and "source" in name)):
            raise ContractError("private or captured path is excluded")


def digest(value: Any) -> str:
    return canonical_hash(value)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, *, max_bytes: int = 2_000_000) -> Any:
    if type(max_bytes) is not int or not 0 < max_bytes <= 1_500_000_000:
        raise ContractError("invalid JSON artifact byte capacity")
    try:
        if path.stat().st_size > max_bytes:
            raise ContractError("JSON artifact exceeds the offline profile limit")
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raise ContractError("JSON artifact exceeds the offline profile limit")
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda value: _refuse(f"nonfinite JSON value: {value}"),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"unreadable JSON artifact: {path.name}") from exc


def _refuse(message: str) -> None:
    raise ContractError(message)


def validate_portfolio(value: Any) -> None:
    try:
        _validate_portfolio(value)
    except (ValueError, TypeError) as exc:
        raise ContractError(str(exc)) from exc


def write_once(path: Path, value: Any) -> None:
    """Publish an immutable final JSON record; identical replay is idempotent."""
    raw = (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")
    write_bytes_once(path, raw)


def write_bytes_once(path: Path, raw: bytes) -> None:
    if path.is_symlink():
        raise ContractError("refusing a symlink artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ContractError(f"immutable artifact already differs: {path.name}")
        return
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ContractError(f"concurrent artifact differs: {path.name}") from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def tree_hashes(root: Path) -> dict[str, str]:
    if root.is_symlink():
        raise ContractError("symlink source roots are not supported")
    root = root.resolve(strict=True)
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise ContractError("symlink source trees are not supported")
        if path.is_file():
            result[relative.as_posix()] = file_hash(path)
    return result


def export_native(portfolio: dict, destination: Path) -> None:
    validate_portfolio(portfolio)
    row = {
        "id": portfolio["task"]["id"],
        "prompt": portfolio["task"]["prompt"],
        "model": "fixture-no-model",
        "generations": [response["text"] for response in portfolio["responses"]],
    }
    identities = {
        "schema_version": 1,
        "fixture": True,
        "portfolio_sha256": digest(portfolio),
        "native_row_sha256": digest(row),
        "task": portfolio["task"],
        "provenance": portfolio["provenance"],
        "responses": [
            {
                "index": index,
                "id": response["id"],
                "text_sha256": hashlib.sha256(response["text"].encode("utf-8")).hexdigest(),
            }
            for index, response in enumerate(portfolio["responses"])
        ],
    }
    raw = json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    write_bytes_once(destination / "generations.jsonl", raw.encode("utf-8"))
    write_once(destination / "identities.json", identities)


def import_native(source: Path) -> dict:
    native_path = source / "generations.jsonl"
    try:
        if native_path.stat().st_size > 2_000_000 or native_path.is_symlink():
            raise ContractError("native generations exceed the supported profile")
        lines = native_path.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1:
            raise ContractError("this offline profile imports exactly one task")
        row = json.loads(lines[0])
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("unreadable native generations") from exc
    identities = read_json(source / "identities.json")
    if (
        not isinstance(row, dict)
        or not isinstance(identities, dict)
        or type(identities.get("schema_version")) is not int
        or identities["schema_version"] != 1
        or identities.get("fixture") is not True
        or identities.get("native_row_sha256") != digest(row)
        or row.get("model") != "fixture-no-model"
    ):
        raise ContractError("native generations and identity evidence are incompatible")
    texts, bindings = row.get("generations"), identities.get("responses")
    task = identities.get("task")
    if (
        not isinstance(texts, list)
        or len(texts) != 10
        or not isinstance(bindings, list)
        or len(bindings) != 10
        or not isinstance(task, dict)
        or task.get("id") != row.get("id")
        or task.get("prompt") != row.get("prompt")
    ):
        raise ContractError("native task or response mapping is incomplete")
    responses = []
    for index, (text, binding) in enumerate(zip(texts, bindings, strict=True)):
        if (
            not isinstance(text, str)
            or not isinstance(binding, dict)
            or type(binding.get("index")) is not int
            or binding["index"] != index
            or binding.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest()
        ):
            raise ContractError("response identity/order evidence does not match the native text")
        responses.append({"id": binding.get("id"), "text": text})
    portfolio = {
        "schema_version": 1,
        "fixture": True,
        "task": task,
        "responses": responses,
        "provenance": identities.get("provenance"),
    }
    validate_portfolio(portfolio)
    if digest(portfolio) != identities.get("portfolio_sha256"):
        raise ContractError("imported portfolio identity does not match its companion evidence")
    return portfolio
