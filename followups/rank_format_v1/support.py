"""Small source, path and readiness guards for the P2B-N external adapter."""
from __future__ import annotations

import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, file_hash, read_json, write_once

__all__ = ["ContractError", "digest", "file_hash", "read_json", "write_once", "ROOT",
           "RESULTS", "IMAGE", "CAP", "POLICY", "DEFINITION", "PARENT", "EVIDENCE",
           "require", "checked_path", "source_identity", "validate_gate"]

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", str(ROOT / "runs"))).resolve()
IMAGE = "sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366"
CAP = 30_000_000
POLICY = {"id": "rank-format-N1", "max_utf8_bytes": 65536,
          "max_structural_depth": 2, "max_candidate_objects": 16}
DEFINITION = "PHASE2B_RANK_FORMAT_DEFINITION.md"
PARENT = ROOT / "evidence/phase2b-expansion/report"
EVIDENCE = ROOT / "evidence/phase2b-rank-format-v1"


def require(condition: object, message: str) -> None:
    if not condition:
        raise ContractError(message)


def checked_path(path: Path | str, *, output: bool = False) -> Path:
    path = Path(path)
    require(".." not in path.parts, "parent traversal is outside this follow-up")
    if not path.is_absolute():
        path = ROOT / path
    require(not any(p.is_symlink() for p in (path, *path.parents)), "follow-up paths cannot use links")
    resolved = path.resolve(strict=not output)
    require(resolved.is_relative_to(RESULTS) if output else
            resolved.is_relative_to(ROOT) or resolved.is_relative_to(RESULTS),
            "path is outside the new project/results boundary")
    return resolved


def source_identity() -> dict[str, str]:
    gate = read_json(ROOT / "runs/phase2-release-r018/release/release-readiness.json")
    parent = read_json(ROOT / "runs/phase2-release-r018/release/study.json")
    paths = dict(gate["evidence"])
    paths.update({"src/buddha2/" + name: value for name, value in parent["package_files"].items()})
    paths["phase2-release.ps1"] = parent["launcher_sha256"]
    require(all(file_hash(checked_path(ROOT / name)) == value for name, value in paths.items()),
            "frozen parent source/evidence changed")
    own = ROOT / "followups/rank_format_v1"
    names = [p.relative_to(ROOT).as_posix() for p in own.rglob("*")
             if p.is_file() and p.suffix in {".py", ".json", ".ps1"}]
    names += ["rank-format.ps1", DEFINITION,
              "evidence/phase2b-rank-format-v1/negative-fixtures-freeze.json",
              "evidence/phase2b-rank-format-v1/authorization.json"]
    require(all((ROOT / name).is_file() for name in names), "owned source/freeze record is incomplete")
    paths.update({name: file_hash(checked_path(ROOT / name)) for name in names})
    return dict(sorted(paths.items()))


def validate_gate(study_path: Path, study: dict) -> None:
    gate = read_json(checked_path(checked_path(study_path).parent / "readiness.json"))
    require(isinstance(gate, dict) and gate.get("kind") == "p2bn-offline-readiness-v1"
            and gate.get("passed") is True,
            "the completed offline gate is required before provider launch")
    for key in ("study_sha256", "source_sha256", "policy_sha256"):
        require(gate.get(key) == study.get(key), "readiness belongs to a different release")
    required = {"normalizer", "corpus_reuse", "sdk_mocks", "launcher", "static", "preservation"}
    require(isinstance(gate.get("checks"), dict) and set(gate["checks"]) == required
            and all(value is True for value in gate["checks"].values()),
            "readiness acceptance checks are incomplete")
    evidence = gate.get("evidence")
    require(isinstance(evidence, dict) and set(evidence) == required,
            "readiness must bind evidence for each required check group")
    for group, reference in evidence.items():
        require(isinstance(reference, dict) and set(reference) == {"path", "sha256"}
                and isinstance(reference["path"], str) and isinstance(reference["sha256"], str),
                "invalid check evidence reference")
        path = checked_path(reference["path"])
        require(file_hash(path) == reference["sha256"], "readiness evidence changed")
        record = read_json(path)
        require(isinstance(record, dict) and record.get("kind") == "p2bn-offline-check-v1"
                and record.get("group") == group and record.get("passed") is True,
                "readiness evidence does not record the required passed check")
        for key in ("study_sha256", "source_sha256", "policy_sha256"):
            require(record.get(key) == study.get(key), "check evidence belongs to another release")
