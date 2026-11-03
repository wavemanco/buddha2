"""Additive Phase 3A identities; closed studies and their source remain untouched."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from buddha2.artifacts import ContractError, digest, read_json, write_once

__all__ = ["ContractError", "ROOT", "RESULTS", "SPEC", "DEFINITION", "LAUNCHER", "AUTHORITY",
           "canonical", "json_sha", "error", "require", "checked_path", "source_identity",
           "runtime_identity", "validate_gate", "authorization", "read_json", "write_once"]

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-r2-v1"
SPEC = ROOT / "specifications/phase3a-r2-v1.json"
DEFINITION = ROOT / "PHASE3A_RECOVERY_DEFINITION.md"
LAUNCHER = ROOT / "phase3a-r2.ps1"
AUTHORITY = ROOT / "evidence/phase3a-r2-v1/authorization.json"
PRIORS = (ROOT / "evidence/phase3a-v1/live-stop-v1", ROOT / "evidence/phase3a-r1-v1/live-stop-v1")
json_sha = digest
error = ContractError


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def authorization() -> dict:
    """Bind one accepted recovery to both immutable episodes and the unreleased liability."""
    from .accounting import POLICY

    value = read_json(AUTHORITY)
    origin = read_json(ROOT / "evidence/phase3a-v1/authorization.json")
    require(value.get("kind") == "phase3a-r2-user-authority-v1" and value.get("authorized") is True
            and value.get("definition_sha256") == hashlib.sha256(DEFINITION.read_bytes()).hexdigest()
            and origin.get("authorized") is True, "accepted R2 authority is missing or differs")
    episodes = value.get("prior_episodes")
    require(isinstance(episodes, list) and len(episodes) == 2, "both stopped episodes are required")
    totals = dict.fromkeys(("known_spent_micro_usd", "reserved_micro_usd", "provider_calls",
                           "known_requests", "unknown_requests"), 0)
    expected_counts = ((86, 86, 1293437, 0, 0), (91, 90, 1401860, 11440000, 1))
    for directory, episode, expected in zip(PRIORS, episodes, expected_counts, strict=True):
        require(isinstance(episode, dict) and episode.get("evidence_directory") == directory.relative_to(ROOT).as_posix(),
                "prior episode path differs")
        for name, field in (("manifest.json", "manifest_sha256"), ("cost-audit.json", "cost_audit_sha256"),
                            ("closeout.json", "closeout_sha256"), ("archive.zip", "archive_sha256")):
            require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == episode.get(field),
                    "prior stopped-run evidence changed")
        audit, manifest = read_json(directory / "cost-audit.json"), read_json(directory / "manifest.json")
        calls, known, spent, reserved, unknown = expected
        require(audit.get("passed") is True and audit.get("known_requests") == episode.get("known_requests") == known
                and audit.get("spent_micro_usd") == episode.get("known_spent_micro_usd") == spent
                and audit.get("pending") == 0 and audit.get("unknown") == episode.get("unknown_requests") == unknown
                and audit.get("reserved_micro_usd") == episode.get("reserved_micro_usd") == reserved
                and episode.get("provider_calls") == calls
                and audit.get("study_sha256") == episode.get("study_sha256")
                and manifest.get("archive_sha256") == episode.get("archive_sha256"),
                "R2 cannot discard or settle historical spending/liability")
        for key in totals:
            totals[key] += episode[key]
    require(value.get("original_phase_cap_micro_usd") == origin.get("cap_micro_usd") == 220000000
            and value.get("original_included_checkpoint_micro_usd") == origin.get("canary_cap_micro_usd") == 65000000
            and value.get("prior_spent_micro_usd") == totals["known_spent_micro_usd"] == 2695297
            and value.get("prior_reserved_micro_usd") == totals["reserved_micro_usd"] == 11440000
            and value.get("prior_requests") == totals["provider_calls"] == 177
            and value.get("prior_known_requests") == totals["known_requests"] == 176
            and value.get("prior_unknown_requests") == totals["unknown_requests"] == 1
            and value.get("cap_micro_usd") == POLICY["phase_micro_usd"] == 205860000
            and value.get("canary_cap_micro_usd") == POLICY["first_micro_usd"] == 50860000
            and value["prior_spent_micro_usd"] + value["prior_reserved_micro_usd"] + value["cap_micro_usd"]
                <= value["original_phase_cap_micro_usd"]
            and value["prior_spent_micro_usd"] + value["prior_reserved_micro_usd"] + value["canary_cap_micro_usd"]
                <= value["original_included_checkpoint_micro_usd"]
            and value.get("new_max_provider_attempts") == 775
            and value.get("cumulative_max_provider_attempts") == 952
            and value.get("historical_unknown_release_authorized") is False
            and value.get("scientific_completion_with_disclosed_historical_uncertainty_authorized") is True
            and value.get("new_study_requires_fresh_arms") is True
            and value.get("prior_results_reused_or_retagged") is False,
            "R2 authority exceeds its accepted scope or cumulative envelope")
    return value


def checked_path(path: Path | str, root: Path = RESULTS) -> Path:
    candidate = Path(path)
    require(".." not in candidate.parts and not any(p.is_symlink() for p in (candidate, *candidate.parents)),
            "Phase 3A paths cannot traverse links or parent components")
    value, boundary = candidate.resolve(), root.resolve()
    require(value.is_relative_to(boundary) and value != boundary,
            "Phase 3A output must be below its declared result boundary")
    return value


def source_identity() -> dict:
    from followups.rank_format_v1.support import source_identity as parent_source_identity
    authorization()
    files = parent_source_identity()
    paths = sorted(p for p in (ROOT / "followups/phase3a_v1").rglob("*")
                   if p.is_file() and p.suffix in {".py", ".json"})
    paths += [SPEC, DEFINITION, ROOT / "PHASE3A_DEFINITION.md", ROOT / "upstreams.lock.json",
              ROOT / "requirements.lock", ROOT / "requirements-build.lock",
              ROOT / "strategies/fixed/phase2.json"]
    paths += [p for p in (LAUNCHER, ROOT / "followups/phase3a_v1/Dockerfile")
              if p.is_file()]
    paths += [AUTHORITY, ROOT / "evidence/phase3a-v1/authorization.json",
              ROOT / "evidence/phase3a-v1/runtime-provenance.json",
              ROOT / "evidence/phase3a-v1/caller-regression-v1/candidate-direct-caller.json"]
    paths += [directory / name for directory in PRIORS for name in ("manifest.json", "cost-audit.json", "closeout.json")]
    paths += [ROOT / "evidence/phase3a-recovery-v1" / name for name in
              ("request-shape-audit.json", "runtime-source-audit.json", "proposal-audit.json")]
    files.update({p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in paths})
    return {"schema": "phase3a-source-v1", "files": files, "sha256": digest(files)}


def runtime_identity() -> dict:
    import importlib.metadata
    import platform
    files = {"/usr/local/bin/bun": "45598a2814020c231575487a560e47d397d6902355d7e08171a2e56221a6d675",
             "/opt/phase3a-opencode/bun.lock": "44e84b33709d5d74bbe17a67e2442d0f8f6ee06ff5415f302f59a4c54e360543",
             "/opt/phase3a-opencode/packages/opencode/src/provider/transform.ts":
             "13eeb2824f9455f216a6f948c1718e53d4a148a2108fc1d13fa32858fb63b462",
             "/opt/phase3a-opencode/packages/opencode/src/session/prompt/max-steps.txt":
             "dd27eb87f2347972e29af2187fea9fa8498fdd012044a60c23179083806b685f",
             "/opt/phase3a-opencode/packages/opencode/src/session/prompt.ts":
             "e4b95f17b6efd722fc4855c124c4dee302e6e3926302a1d4d83c828f0bc374a1"}
    for name, expected in files.items():
        require(Path(name).is_file() and hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected,
                "actual editor runtime differs from its reviewed source/binary")
    return {"python": platform.python_version(),
            "anthropic": importlib.metadata.version("anthropic"),
            "openai": importlib.metadata.version("openai"),
            "harness2_commit": "1cfe254e8d25b15f37048c3730134686abe60335",
            "opencode_commit": "23fb5e0516c99ac04a1aa46c193efda2e1b9bb24",
            "bun": "1.3.11", "files": files,
            "image_id": "sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2"}


def validate_gate(study_path: Path, study: dict) -> None:
    gate_path = checked_path(Path(study_path).parent / "readiness.json")
    gate = read_json(gate_path)
    require(isinstance(gate, dict) and gate.get("kind") == "phase3a-offline-readiness-v1"
            and gate.get("passed") is True, "Phase 3A requires its completed offline acceptance")
    bindings = ("study_sha256", "source_sha256", "policy_sha256", "runtime_sha256", "launcher_sha256")
    require(all(gate.get(key) == study.get(key) for key in bindings), "offline gate belongs to another study")
    groups = {"conformance", "native_path", "editor_containment", "accounting", "full_rehearsal",
              "resume", "launcher", "static", "preservation"}
    require(isinstance(gate.get("checks"), dict) and set(gate["checks"]) == groups
            and all(value is True for value in gate["checks"].values()), "offline gate checks are incomplete")
    refs = gate.get("evidence")
    require(isinstance(refs, dict) and set(refs) == groups, "offline gate evidence groups differ")
    for group, ref in refs.items():
        require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "offline evidence reference differs")
        path = checked_path(ref["path"])
        require(hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"], "offline evidence changed")
        record = read_json(path)
        require(record.get("kind") == "phase3a-offline-check-v1" and record.get("group") == group
                and record.get("passed") is True and all(record.get(k) == study.get(k) for k in bindings),
                "offline check does not attest this exact study")
        require(isinstance(record.get("artifacts"), dict) and record["artifacts"],
                "offline check must retain its actual artifacts")
        for name, sha in record["artifacts"].items():
            artifact = checked_path(name)
            require(hashlib.sha256(artifact.read_bytes()).hexdigest() == sha, "offline check artifact changed")
