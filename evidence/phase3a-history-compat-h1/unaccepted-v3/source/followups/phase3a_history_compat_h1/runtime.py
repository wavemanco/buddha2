"""Exact, dependency-free OpenCode upstream backport and image-file witness."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

BASE_IMAGE = "sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2"
UPSTREAM_FIX = "4e14f79511728d04329da664b747dd0b359cf931"
ORDER_FIX = "59403040987137a367f259884766efc363725c39"
TARGET = "/opt/phase3a-opencode/packages/opencode/src/provider/transform.ts"
BEFORE_SHA = "13eeb2824f9455f216a6f948c1718e53d4a148a2108fc1d13fa32858fb63b462"
AFTER_SHA = "037e295c1905487293ebf99f660d889343eb4e675cd9223329df3febace72821"
BEFORE = (
    '          if (part.type === "text" || part.type === "reasoning") {\r\n'
    '            return part.text !== ""\r\n          }'
)
AFTER = (
    '          if (part.type === "text") {\r\n'
    '            return part.text !== ""\r\n          }\r\n'
    '          if (part.type === "reasoning") {\r\n'
    "            return (\r\n              part.text.trim().length > 0 ||\r\n"
    "              part.providerOptions?.anthropic?.signature != null ||\r\n"
    "              part.providerOptions?.anthropic?.redactedData != null\r\n"
    "            )\r\n          }"
)
ORDER_HUNK = """  if (["@ai-sdk/anthropic", "@ai-sdk/google-vertex/anthropic"].includes(model.api.npm)) {
    // Anthropic rejects assistant turns where tool_use blocks are followed by non-tool
    // content, e.g. [tool_use, tool_use, text], with:
    // `tool_use` ids were found without `tool_result` blocks immediately after...
    //
    // Reorder that invalid shape into [text] + [tool_use, tool_use]. Consecutive
    // assistant messages are later merged by the provider/SDK, so preserving the
    // original [tool_use...] then [text] order still produces the invalid payload.
    //
    // The root cause appears to be somewhere upstream where the stream is originally
    // processed. We were unable to locate an exact narrower reproduction elsewhere,
    // so we keep this transform in place for the time being.
    msgs = msgs.flatMap((msg) => {
      if (msg.role !== "assistant" || !Array.isArray(msg.content)) return [msg]

      const parts = msg.content
      const first = parts.findIndex((part) => part.type === "tool-call")
      if (first === -1) return [msg]
      if (!parts.slice(first).some((part) => part.type !== "tool-call")) return [msg]
      return [
        { ...msg, content: parts.filter((part) => part.type !== "tool-call") },
        { ...msg, content: parts.filter((part) => part.type === "tool-call") },
      ]
    })
  }
""".replace("\n", "\r\n")
PRIVATE = frozenset(
    {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch() -> dict:
    path = Path(TARGET)
    before = path.read_bytes()
    if sha(before) != BEFORE_SHA or before.count(BEFORE.encode()) != 1:
        raise ValueError("backport requires exact reviewed baseline and one Anthropic hunk")
    if before.count(ORDER_HUNK.encode()) != 1:
        raise ValueError("ordering backport requires its one exact reviewed hunk")
    after = before.replace(BEFORE.encode(), AFTER.encode(), 1).replace(ORDER_HUNK.encode(), b"", 1)
    if sha(after) != AFTER_SHA:
        raise ValueError("backport output differs from the exact reviewed hunk")
    path.write_bytes(after)
    return {
        "upstream_commit": UPSTREAM_FIX,
        "target": TARGET,
        "before_sha256": sha(before),
        "after_sha256": sha(after),
        "changed_hunks": 2,
        "order_fix_commit": ORDER_FIX,
    }


def inventory(root: Path = Path("/"), target: Path = Path(TARGET)) -> dict:
    """Hash every ordinary image file/link and ownership/mode, excluding Docker mounts."""
    mounts = {"/proc", "/sys", "/dev"}
    injected = {"/etc/hosts", "/etc/hostname", "/etc/resolv.conf"}
    entries, excluded = [], []
    pending = [root]
    while pending:
        directory = pending.pop()
        # listdir returns names only; scandir/os.walk can query entry type too early.
        for name in sorted(os.listdir(directory)):
            path = directory / name
            if name.casefold() in PRIVATE:
                excluded.append(str(path))
                continue
            if str(path) in mounts | injected or path == target:
                continue
            meta = path.lstat()
            row = [
                str(path),
                stat.S_IFMT(meta.st_mode),
                stat.S_IMODE(meta.st_mode),
                meta.st_uid,
                meta.st_gid,
            ]
            if stat.S_ISREG(meta.st_mode):
                with path.open("rb") as stream:
                    row += [
                        meta.st_size,
                        hashlib.file_digest(stream, "sha256").hexdigest(),
                    ]
            elif stat.S_ISLNK(meta.st_mode):
                row += [os.readlink(path)]
            elif stat.S_ISDIR(meta.st_mode):
                pending.append(path)
            else:
                raise ValueError("unexpected nonordinary image file")
            entries.append(row)
    entries.sort(key=lambda row: str(row[0]))
    meta = target.lstat()
    if not stat.S_ISREG(meta.st_mode):
        raise ValueError("runtime source target must be an ordinary file")
    return {
        "all_other_entries_sha256": sha(json.dumps(entries, separators=(",", ":")).encode()),
        "all_other_entry_count": len(entries),
        "excluded_private_names": sorted(excluded),
        "docker_virtual_mounts": sorted(mounts),
        "docker_injected_files": sorted(injected),
        "target_sha256": sha(target.read_bytes()),
        "target_mode_uid_gid": [stat.S_IMODE(meta.st_mode), meta.st_uid, meta.st_gid],
    }


if __name__ == "__main__":
    import sys

    operation = {"patch": patch, "inventory": inventory}.get(
        sys.argv[1] if len(sys.argv) == 2 else ""
    )
    if operation is None:
        raise SystemExit("expected patch or inventory")
    print(json.dumps(operation(), sort_keys=True))
