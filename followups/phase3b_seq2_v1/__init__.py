"""Native seq2 integration; deny private dotenv before importing pinned Harness2."""
from __future__ import annotations

import importlib
import io
import os

IMPORT_PRIVACY = {"dotenv_open_denials": 0, "harness2_config_imported": False}


def _import_config():
    original_open = io.open
    def public_open(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            lexical = os.fsdecode(os.fspath(file)).replace("\\", "/")
            if any(part.casefold() == ".env" for part in lexical.split("/")):
                IMPORT_PRIVACY["dotenv_open_denials"] += 1
                raise PermissionError("Private environment access is disabled during the pinned import")
        return original_open(file, *args, **kwargs)
    io.open = public_open
    try:
        importlib.import_module("harness2.config")
        IMPORT_PRIVACY["harness2_config_imported"] = True
    except ModuleNotFoundError as exc:
        if exc.name not in {"harness2", "harness2.config"}:
            raise
        # Inspect's separate pure-export image deliberately has no Harness2.
    finally:
        io.open = original_open


_import_config()
