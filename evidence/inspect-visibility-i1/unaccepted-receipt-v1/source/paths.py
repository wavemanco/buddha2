"""Small path boundary shared by I1's two host commands."""

import re
import stat
from pathlib import Path

PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}


def lexical(raw: str) -> None:
    if any(part in {".", ".."} or part.lower() in PRIVATE for part in re.split(r"[/\\]", raw)):
        raise ValueError("noncanonical or private path rejected before metadata")


def checked_path(raw: str | Path, root: Path, *, missing: bool = False) -> Path:
    lexical(str(raw))
    lexical(str(root))
    path = Path(raw)
    if not path.is_absolute() or not path.is_relative_to(root):
        raise ValueError("path outside declared research root")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing:
                return path
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked/reparse path rejected before following descendants")
    return path
