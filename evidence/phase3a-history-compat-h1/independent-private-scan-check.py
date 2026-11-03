"""Offline private-name denial regression, including the prior os.walk failure.

Uses fresh synthetic noncredential files only. No provider or SDK is imported.
Run with python -B to keep the frozen source tree free of bytecode writes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def check() -> dict:
    root = Path(__file__).resolve().parents[2]
    source = root / "followups/phase3a_history_compat_h1/runtime.py"
    spec = importlib.util.spec_from_file_location("h1_independent_runtime_review", source)
    if spec is None or spec.loader is None:
        raise AssertionError("runtime source is not importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    real_scandir, real_lstat = os.scandir, Path.lstat
    classifications: list[str] = []

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def __getattr__(self, name):
            return getattr(self.entry, name)

        def is_dir(self, *args, **kwargs):
            if self.entry.name.casefold() in module.PRIVATE:
                classifications.append(self.entry.name)
                raise AssertionError("PRIVATE_DIRENTRY_CLASSIFICATION")
            return self.entry.is_dir(*args, **kwargs)

    class Scan:
        def __init__(self, path):
            self.actual = real_scandir(path)

        def __iter__(self):
            return self

        def __next__(self):
            return Entry(next(self.actual))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.actual.close()

    def guarded_lstat(path, *args, **kwargs):
        if any(part.casefold() in module.PRIVATE for part in path.parts):
            raise AssertionError("PRIVATE_LSTAT")
        return real_lstat(path, *args, **kwargs)

    with tempfile.TemporaryDirectory(prefix="h1-independent-denial-") as temporary:
        directory = Path(temporary)
        if not directory.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise AssertionError("synthetic fixture escaped its temporary root")
        target = directory / "transform.ts"
        target.write_text("SYNTHETIC", encoding="utf-8")
        (directory / ".env").write_text("SYNTHETIC NONCREDENTIAL", encoding="utf-8")
        (directory / "AUTH.JSON").mkdir()
        (directory / "AUTH.JSON/hidden.txt").write_text("SYNTHETIC", encoding="utf-8")
        (directory / "public.txt").write_text("SYNTHETIC", encoding="utf-8")
        with patch.object(os, "scandir", Scan), patch.object(Path, "lstat", guarded_lstat):
            result = module.inventory(directory, target)
            if classifications or len(result["excluded_private_names"]) != 2:
                raise AssertionError("new scanner inspected a private entry")
            if result["all_other_entry_count"] != 1:
                raise AssertionError("new scanner did not retain exactly its public fixture")
            try:
                list(os.walk(directory))
            except AssertionError as error:
                if str(error) != "PRIVATE_DIRENTRY_CLASSIFICATION":
                    raise
            else:
                raise AssertionError("the known-bad classifier was not detected")
        if len(classifications) != 1:
            raise AssertionError("negative control did not identify its private classification")
    return {
        "passed": True,
        "fixture": True,
        "runtime_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "new_scanner_private_classifications": 0,
        "known_bad_os_walk_denied": True,
        "private_lstat_calls": 0,
        "private_content_reads": 0,
        "private_names_excluded": 2,
        "provider_calls": 0,
        "api_spend": 0,
        "independent_acceptance": False,
    }


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
