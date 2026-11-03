"""Private-name-safe validation scope around unchanged fixed strategy functions."""
from __future__ import annotations

import inspect
import os
import re
import stat
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from buddha2.artifacts import file_hash
from followups.phase3a_v1 import strategy as frozen

from .support import BASE, PRIVATE, ROOT, read, require, safe

Dispatch = frozen.Dispatch
FIELDS, _integrity, _require, _path = frozen.FIELDS, frozen._integrity, frozen._require, frozen._path
seed_tree = frozen.seed_tree
_OWNED: ContextVar[bool] = ContextVar("hi_public_surface_scope", default=False)
_NATIVE_HARNESS: ContextVar[Path | None] = ContextVar("hi_owned_temporary_harness", default=None)


@contextmanager
def native_workspace(cwd: Path):
    """Trust only the current original Proposer's ordinary temporary workspace."""
    cwd = Path(cwd)
    require(cwd.is_absolute() and cwd.parent == Path("/tmp")  # nosec B108: exact native-created tmpfs workspace admission, not creation
            and re.fullmatch(r"harness2-prop-[A-Za-z0-9_-]{6,64}", cwd.name) is not None,
            "native temporary workspace identity differs")
    cwd = safe(cwd, roots=(cwd,))
    require(cwd.is_dir(), "native temporary workspace is not an ordinary directory")
    token = _NATIVE_HARNESS.set(cwd / "context/harness")
    try:
        yield
    finally:
        _NATIVE_HARNESS.reset(token)


def _harness_path(value: Path) -> Path:
    owned = _NATIVE_HARNESS.get()
    roots = (ROOT, BASE) if owned is None else (ROOT, BASE, owned)
    return safe(value, roots=roots)


def _public_surface():
    record = read(ROOT / "upstreams.lock.json")["upstreams"]["harness2"]
    code = {name: expected for name, expected in record["files"].items()
            if name.startswith("harness2/") and name.endswith(".py")}
    require(record["commit"] == "1cfe254e8d25b15f37048c3730134686abe60335" and bool(code)
            and all(file_hash(safe(ROOT / ".upstream/harness2" / name)) == expected
                    for name, expected in code.items()), "pinned public Harness2 source differs")
    from harness2.substrate import opencode
    require(safe(Path(opencode.__file__)).resolve(strict=True)
            == ROOT / ".upstream/harness2/harness2/substrate/opencode.py", "wrong public surface import")
    return opencode.OPENCODE_SURFACE


@contextmanager
def validation_scope(*, readonly: bool = False):
    require(type(readonly) is bool, "explicit readonly mode required")
    if _OWNED.get() and (not readonly or frozen._READONLY_CONTEXT.get() is not None):
        yield
        return
    surface = _public_surface()
    owned_token = _OWNED.set(True)
    surface_token = frozen._SURFACE_CONTEXT.set(surface)
    snapshot: dict[str, Any] | None = {"harnesses": {}, "aliases": {}, "templates": None} if readonly else None
    snapshot_token = frozen._READONLY_CONTEXT.set(snapshot) if snapshot is not None else None
    try:
        yield
    finally:
        try:
            if snapshot is not None:
                for path, expected in snapshot["harnesses"].items():
                    precheck_harness(path)
                    require(frozen._validate_harness_uncached(path) == expected,
                            "harness changed during readonly validation")
                if snapshot["templates"] is not None:
                    require(frozen._read_seed_templates() == snapshot["templates"], "templates changed during readonly validation")
        finally:
            if snapshot_token is not None:
                frozen._READONLY_CONTEXT.reset(snapshot_token)
            frozen._SURFACE_CONTEXT.reset(surface_token)
            _OWNED.reset(owned_token)
            _public_surface()


def precheck_harness(root: Path) -> None:
    root = _harness_path(root)
    if not root.exists():
        return
    allowed = {"systemprompt.md", *frozen.EMPTY_FILES, *frozen.compatibility_files()}
    directories = {p.as_posix() for name in allowed for p in Path(name).parents if str(p) != "."}
    pending = [root]
    while pending:
        directory = pending.pop()
        for name in sorted(os.listdir(directory)):
            require(name.casefold() not in PRIVATE, "private harness entry forbidden")
            target = directory / name
            relative = target.relative_to(root).as_posix()
            require(relative in allowed or relative in directories, "undeclared harness entry")
            target = _harness_path(target)
            info = target.lstat()
            if stat.S_ISDIR(info.st_mode):
                require(relative in directories, "undeclared harness directory")
                pending.append(target)
            else:
                require(stat.S_ISREG(info.st_mode) and relative in allowed, "undeclared harness file")


def _bound(function: Callable) -> Callable:
    signature = inspect.signature(function)
    @wraps(function)
    def call(*args, **kwargs):
        with validation_scope():
            arguments = signature.bind(*args, **kwargs).arguments
            harness = arguments.get("harness_dir")
            if function.__name__ in {"validate_harness", "validate_harness_inventory", "materialize_seed"}:
                harness = arguments.get("path")
            if harness is not None:
                precheck_harness(Path(harness))
            return function(*args, **kwargs)
    return call


materialize_seed = _bound(frozen.materialize_seed)
validate_harness = _bound(frozen.validate_harness)
validate_harness_inventory = _bound(frozen.validate_harness_inventory)
fixed_best6 = _bound(frozen.fixed_best6)
validate_fixed = _bound(frozen.validate_fixed)
validate_fixed_partial = _bound(frozen.validate_fixed_partial)

validate_partial = _bound(frozen.validate_partial)
validate_rollout = _bound(frozen.validate_rollout)

scoped = _bound
