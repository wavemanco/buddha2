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
from followups.phase3a_h1_integrated_v1 import support as frozen_hi

ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "PHASE3A_RC1_PILOT_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-rc1-pilot-v1/authorization.json"
PROVIDERS = ROOT / "evidence/phase3a-rc1-pilot-v1/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-rc1-pilot.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-rc1-pilot-v1"
NATIVE = BASE / "native"
IMAGE_ID = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
PRIVATE = frozenset({"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def safe(value: Path, *, roots: tuple[Path, ...] | None = None) -> Path:
    """Lexical exclusions before top-down metadata; never walk descendants."""
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts
            and not any(p.casefold() in PRIVATE or 'stdout' in p.casefold() or 'stderr' in p.casefold() for p in value.parts), "foreign/private HI path")
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
    value = safe(value, roots=(BASE, ROOT / "runs/phase3a-rc1-pilot-v1"))
    require(value not in (BASE, ROOT / "runs/phase3a-rc1-pilot-v1"), "output requires a child namespace")
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


CHECKPOINTS = {'INSPECT_DISPLAY_V2_REPORT.md': '0d11af8935057da9e41651041e4eeb50ebff4ca72efca7eb192d4a47e1df06b2',
 'P3A_HI_LIVE_REPORT.md': '4b37b06108bcd132b4f99e9060997a6649d9b6c9425f0d1996505eb288f43011',
 'PHASE3A_RANKING_CONTRACT_DEFINITION.md': 'd317a6b60adc5d2b36b89c278080124955c1efbbd3548520e0c8199f4aa9da79',
 'PHASE3A_RC1_REPORT.md': 'cada390053c69480a765283dd67ece7aa72248ff07157a0578cb1fab5db60d2f',
 'evidence/inspect-display-v2/independent-acceptance.json': '88880867100e947aba87fa524855b198cce639dd185c15dce6a71a32b57769b2',
 'evidence/inspect-display-v2/retained-evidence.json': 'fa7806922ec475f09f41f0f509ed2fb0518f085004c57e4d83cdcbfa5fe81e09',
 'evidence/phase3a-h1-integrated-v1/live-outcome-v1.manifest.json': 'e2ce7e6f38a19e499dc43f8d407f0a1261bae296a01489a740bb8a634d5519bc',
 'evidence/phase3a-h1-integrated-v1/live-outcome-v1.zip': '50e69c125f2ff9b514aa959bc8be1731050f8e9566ebf69748aadeb37026345f',
 'evidence/phase3a-h1-integrated-v1/live-packet-acceptance.json': '60f462480e14ab00e6e74f9253bdae2e64f8b0502d2f276a3b946867268037a2',
 'evidence/phase3a-rank-contract-v1/closeout.json': '8db7ea491ce81795332a474afdc2209203fbf0a0438dabaafb2649cfe623f3d2',
 'evidence/phase3a-rank-contract-v1/independent-acceptance.json': '14bcab2c9bb9b3627e0cee194336f9bfecfd6f02d76cf068c33910addd129253',
 'evidence/phase3a-rank-contract-v1/retained-artifacts.json': '1ea477ecf6e88c709c212a1aa3e3e715a9e81e2491a2c974c8b4a75393716b24',
 'followups/inspect_display_v2/display.py': '7b7f1bfc6ced0ae7d4137ade03e47ae30068bfb1737c9f75fc6f70726ceed963',
 'followups/inspect_display_v2/provenance.py': '1a2194b16c5a3945989f9ba817afec482ef01466b3ae20dfd3d440dd6e06c2a9',
 'followups/inspect_display_v2/test_display.py': '77ba4055d6a5c9e0bced2ee0daa24550de5e5fe3c14579a841b50d03cc6f5320',
 'followups/phase3a_rank_contract_v1/adapter.py': 'be7088f564acafe49387f10fbf1cbc5f1171960dd54bd3eceb0762c9a79d911d',
 'followups/phase3a_rank_contract_v1/test_adapter.py': '8fb5caaef950e8fbc61d4965e96f080e81a0d6a48492e138953a7e1cee1ab9a5',
 'followups/phase3a_rank_contract_v1/verify.py': '6f7ac23c7c6c970de3f62133970baaedbe8385b99ae19ecdcaf471bfae356935'}


def source_identity() -> dict:
    parent = frozen_hi.source_identity()
    require(parent['sha256'] == '2440535e5274c106a44efb28cf9533308b7dbea8fd8768649a089145cbc150a3'
            and len(parent['files']) == 356, 'accepted HI source differs')
    files = dict(parent['files'])
    for name, expected in CHECKPOINTS.items():
        require(file_hash(ROOT / name) == expected, 'accepted checkpoint changed: ' + name)
        files[name] = expected
    directory = safe(ROOT / 'followups/phase3a_rc1_pilot_v1')
    for name in sorted(os.listdir(directory)):
        if name.casefold() in PRIVATE or 'stdout' in name.casefold() or 'stderr' in name.casefold() or name == '__pycache__':
            continue
        target = safe(directory / name)
        info = target.lstat()
        require(stat.S_ISREG(info.st_mode), 'new source namespace contains an unexpected directory or file type')
        if target.suffix in {'.py', '.json', '.md', '.ps1'}:
            files[target.relative_to(ROOT).as_posix()] = file_hash(target)
    names = (DEFINITION, AUTHORITY, PROVIDERS, LAUNCHER, ROOT / 'phase3a-rc1-pilot-core.ps1',
             ROOT / 'evidence/phase3a-rc1-pilot-v1/package_public.py',
             ROOT / 'evidence/phase3a-rc1-pilot-v1/provider-review.json',
             ROOT / 'evidence/phase3a-rc1-pilot-v1/openai-pricing.md')
    for target in names:
        files[target.relative_to(ROOT).as_posix()] = file_hash(target)
    return {'kind': 'phase3a-rp1-source-v1', 'parent_source_sha256': parent['sha256'],
            'H1_source_sha256': parent['H1_source_sha256'], 'I1_source_sha256': parent['I1_source_sha256'],
            'files': files, 'sha256': digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {"new_cap_micro_usd": 200000000, "first_cap_micro_usd": 50860000,
                "first_assessment_sublimit_micro_usd": 23700000, "readiness_included_micro_usd": 20000000,
                "historical_known_micro_usd": 24463235, "historical_reserved_micro_usd": 22880000,
                "historical_attempts": 1233, "new_max_attempts": 775, "potential_request_slots": 967,
                "cumulative_max_exposure_micro_usd": 247343235, "cumulative_max_attempts": 2008}
    require(value.get("kind") == "phase3a-rp1-authority-v1" and value.get("authorized") is True
            and all(type(value.get(k)) is int and value[k] == n for k, n in expected.items())
            and value.get("historical_liability_release_authorized") is False
            and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("definition_sha256") == file_hash(DEFINITION), "HI authority differs")
    return value


def preserve() -> dict:
    parent = frozen_hi.preserve()
    source_identity()
    return {'kind': 'phase3a-rp1-preservation-v1', 'passed': True,
            'HI_preservation': parent, 'accepted_HI_source_files': 356,
            'accepted_checkpoints': dict(CHECKPOINTS),
            'protected_original_accessed': False, 'private_worktree_accessed': False}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "HI seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
