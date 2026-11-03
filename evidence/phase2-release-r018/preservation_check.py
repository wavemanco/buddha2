"""Compare retained history to the pre-P2-R baseline, only in the new project."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = Path(r"C:\Users\arvik\code\research\Buddha2")
EVIDENCE = ROOT / "evidence/phase2-release-r018"
ALLOWED = {"AGENTS.md", "README.md", "EXPERIMENT_PLAN.md", "PHASE_DEFINITIONS.md",
           "PRE_PHASE2B_BLOCK.md", "src/buddha2/__main__.py"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if ROOT != EXPECTED or ROOT.is_symlink():
        raise RuntimeError("wrong project root")
    baseline = json.loads((EVIDENCE / "before.json").read_text(encoding="utf-8"))
    unchanged, allowed, missing, unexpected = [], {}, [], {}
    for name, expected in baseline["files"].items():
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError("baseline path escaped project")
        if not path.is_file():
            missing.append(name)
            continue
        actual = sha(path)
        if actual == expected:
            unchanged.append(name)
        elif name in ALLOWED:
            allowed[name] = {"before": expected, "after": actual}
        else:
            unexpected[name] = {"before": expected, "after": actual}
    record = {"kind": "p2r-historical-preservation-check", "baseline_sha256": sha(EVIDENCE / "before.json"),
              "baseline_files": len(baseline["files"]), "unchanged_files": len(unchanged),
              "intentional_current_changes": allowed, "missing": missing, "unexpected_changes": unexpected,
              "original_folder_accessed": False,
              "original_boundary_basis": "No enumeration/hash/read of protected original. All task commands and mounts confined to new project.",
              "status": "pass" if not missing and not unexpected else "fail"}
    target = EVIDENCE / "preservation.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(json.dumps(record))
    if record["status"] != "pass":
        raise RuntimeError("historical preservation failed")


if __name__ == "__main__":
    main()
