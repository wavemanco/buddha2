"""Fresh HI identities, strict public paths and accepted parent preservation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import stat
import sys
from pathlib import Path

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_compat_c1_v1.support import opencode_profile_sources
from followups.phase3a_history_compat_h1.verify import preserved_r3

ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "PHASE3A_H1_INTEGRATED_PILOT_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-h1-integrated-v1/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-h1-integrated-v1/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-h1-integrated.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-h1-integrated-v1"
NATIVE = BASE / "native"
IMAGE_ID = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
PRIVATE = frozenset({"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"})
H1_FILES = ("Dockerfile", "README.md", "__init__.py", "fixture.py", "guard.py", "probe.ts", "runtime.py", "tests.py", "verify.py")
I1_FILES = ("Dockerfile", "README.md", "__init__.py", "importer.py", "paths.py", "run.py", "setup.py", "tests.py")
CLOSED = {
    "evidence/phase3a-c1-completion-v4/live-outcome.json": "243c29222736d21624022e036f3a1f158725db3aa4d9fdeb4d76141aef0d3283",
    "evidence/phase3a-c1-completion-v4/live-outcome-v1.manifest.json": "555741b110d42f8282769144080fc5c976a5c4eb8bf6e5f9093b83475f88d91f",
    "evidence/phase3a-c1-completion-v4/live-packet-acceptance.json": "96e00d4179252ddf3370af34ca2cf30ff536e9198cc5b5e5279d431b839ee075",
    "evidence/phase3a-history-compat-h1/independent-acceptance.json": "a999c33b4584a6c1a94d0fda45078fca09db0e98b29f662eafd7396cdc7ff4f6",
    "evidence/inspect-visibility-i1/independent-acceptance.json": "61d4c90a441f8bf2b474add9203b1cf21c89d2b41fb3cc3e5c2a83f1ff929344",
}
CLOSED_ARCHIVE = "evidence/phase3a-c1-completion-v4/live-outcome-v1.zip"
CLOSED_ARCHIVE_SHA = "f1fb9bd222ff31d7addaef0fa1e6556522cb8d62470a68b89c4669bbe6d255e5"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def safe(value: Path, *, roots: tuple[Path, ...] | None = None) -> Path:
    """Lexical exclusions before top-down metadata; never walk descendants."""
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts
            and not any(p.casefold() in PRIVATE for p in value.parts), "foreign/private HI path")
    roots = roots or (ROOT, BASE)
    require(any(value == root or value.is_relative_to(root) for root in roots), "HI path outside explicit roots")
    current = Path(value.anchor)
    for part in value.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "linked HI input/output")
    return value


def read(value: Path) -> dict:
    target = safe(value)
    require(target.is_file() and target.stat().st_size <= 32_000_000, "missing/oversized HI artifact")
    def pairs(items):
        result = {}
        for key, item in items:
            require(key not in result, "duplicate HI JSON key")
            result[key] = item
        return result
    result = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite HI JSON")))
    require(isinstance(result, dict), "HI artifact must be an object")
    return result


def path(value: Path) -> Path:
    value = safe(value, roots=(BASE, ROOT / "runs/phase3a-h1-integrated-v1"))
    require(value not in (BASE, ROOT / "runs/phase3a-h1-integrated-v1"), "output requires a child namespace")
    return value


def file_hash(value: Path) -> str:
    return hashlib.sha256(safe(value).read_bytes()).hexdigest()


def runtime_identity() -> dict:
    files = {
        "/usr/local/bin/bun": "45598a2814020c231575487a560e47d397d6902355d7e08171a2e56221a6d675",
        "/opt/phase3a-opencode/bun.lock": "44e84b33709d5d74bbe17a67e2442d0f8f6ee06ff5415f302f59a4c54e360543",
        "/opt/phase3a-opencode/packages/opencode/src/provider/transform.ts": "037e295c1905487293ebf99f660d889343eb4e675cd9223329df3febace72821",
        "/opt/phase3a-opencode/packages/opencode/src/session/prompt/max-steps.txt": "dd27eb87f2347972e29af2187fea9fa8498fdd012044a60c23179083806b685f",
        "/opt/phase3a-opencode/packages/opencode/src/session/prompt.ts": "e4b95f17b6efd722fc4855c124c4dee302e6e3926302a1d4d83c828f0bc374a1",
    }
    require(all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha for name, sha in files.items()),
            "actual H1 runtime file differs")
    value = {"python": platform.python_version(), "anthropic": importlib.metadata.version("anthropic"),
             "openai": importlib.metadata.version("openai"), "image_id": IMAGE_ID,
             "harness2_commit": "1cfe254e8d25b15f37048c3730134686abe60335",
             "opencode_commit": "23fb5e0516c99ac04a1aa46c193efda2e1b9bb24", "bun": "1.3.11", "files": files,
             "c1_agent_prompt_sources": opencode_profile_sources(),
             "c1_agent_prompt_seam": "agent.build.prompt replaces provider default; environment remains appended"}
    require((value["python"], value["anthropic"], value["openai"]) == ("3.12.15", "1.4.0", "1.107.0"),
            "actual H1 runtime Python/SDK versions differ")
    return value


def runtime_guard() -> None:
    require(sys.platform == "linux" and tuple(sys.version_info[:3]) == (3, 12, 15)
            and os.environ.get("BUDDHA2_IMAGE_ID") == IMAGE_ID
            and importlib.metadata.version("anthropic") == "1.4.0"
            and importlib.metadata.version("openai") == "1.107.0"
            and os.environ.get("BUDDHA2_OUTPUT_ROOT") == "/results"
            and os.environ.get("PHASE3A_OPENCODE") == "/opt/phase3a-opencode"
            and os.environ.get("PHASE3A_BUN") == "/usr/local/bin/bun"
            and ROOT == Path("/workspace"), "live HI requires its actual H1 image and inspected mounts")


def source_identity() -> dict:
    parent = preserved_r3()
    files = dict(parent["files"])
    h1 = {"PHASE3A_HISTORY_COMPAT_H1_DEFINITION.md": file_hash(ROOT / "PHASE3A_HISTORY_COMPAT_H1_DEFINITION.md")}
    h1.update({f"followups/phase3a_history_compat_h1/{name}": file_hash(ROOT / "followups/phase3a_history_compat_h1" / name) for name in H1_FILES})
    require(digest(h1) == "0ab7775b63193b5de354f33ffa46ad8086e6a080bae6bd757090d0003769f813", "accepted H1 source changed")
    i1 = {name: file_hash(ROOT / "followups/inspect_visibility_i1" / name) for name in I1_FILES}
    require(digest(i1) == "cce047344d066a89f4980bdb593013fb48bc6d9a6c18c92fa8e576b475afab05", "accepted I1 source changed")
    files.update(h1)
    files.update({f"followups/inspect_visibility_i1/{name}": sha for name, sha in i1.items()})
    for name, expected in CLOSED.items():
        require(file_hash(ROOT / name) == expected, "accepted parent closure/receipt changed")
        files[name] = expected
    def collect(directory):
        directory = safe(directory)
        for name in sorted(os.listdir(directory)):
            if name.casefold() in PRIVATE or name.startswith("__pycache__"):
                continue
            candidate = safe(directory / name)
            info = candidate.lstat()
            if stat.S_ISDIR(info.st_mode):
                collect(candidate)
            elif stat.S_ISREG(info.st_mode) and candidate.suffix in {".py", ".json", ".md", ".ps1"}:
                files[candidate.relative_to(ROOT).as_posix()] = file_hash(candidate)
    collect(ROOT / "followups/phase3a_h1_integrated_v1")
    for source_path in [DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER, ROOT / "phase3a-h1-integrated-core.ps1",
                 ROOT / "evidence/phase3a-h1-integrated-v1/package_public.py"]:
        files[source_path.relative_to(ROOT).as_posix()] = file_hash(source_path)
    return {"kind": "phase3a-hi-source-v1", "parent_source_sha256": parent["source_sha256"],
            "H1_source_sha256": digest(h1), "I1_source_sha256": digest(i1), "files": files, "sha256": digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {"new_cap_micro_usd": 205860000, "first_cap_micro_usd": 50860000,
                "first_assessment_sublimit_micro_usd": 23700000, "readiness_included_micro_usd": 20000000,
                "historical_known_micro_usd": 16580264, "historical_reserved_micro_usd": 22880000,
                "historical_attempts": 977, "new_max_attempts": 775, "potential_request_slots": 967,
                "cumulative_max_exposure_micro_usd": 245320264, "cumulative_max_attempts": 1752}
    require(value.get("kind") == "phase3a-hi-authority-v1" and value.get("authorized") is True
            and all(type(value.get(k)) is int and value[k] == n for k, n in expected.items())
            and value.get("historical_liability_release_authorized") is False
            and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("definition_sha256") == file_hash(DEFINITION), "HI authority differs")
    return value


def preserve() -> dict:
    parent = preserved_r3()
    source_identity()
    require(file_hash(ROOT / CLOSED_ARCHIVE) == CLOSED_ARCHIVE_SHA, "closed R3 archive changed")
    return {"kind": "phase3a-hi-preservation-v1", "passed": True,
            "parent_source_sha256": parent["source_sha256"], "parent_source_files": len(parent["files"]),
            "closed_public_metadata": dict(CLOSED), "closed_R3_archive_sha256": CLOSED_ARCHIVE_SHA,
            "protected_original_accessed": False, "private_worktree_accessed": False}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "HI seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
