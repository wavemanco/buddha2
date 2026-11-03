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
from followups.phase3a_rc1_pilot_v1 import support as frozen_rp1

ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "PHASE3A_RP2_RECOVERY_DEFINITION.md"
AUTHORITY = ROOT / "evidence/phase3a-readiness-recovery-v1/authorization.json"
AM1_DEFINITION = ROOT / "PHASE3A_RP2_AM1_DEFINITION.md"
AM1_AUTHORITY = ROOT / "evidence/phase3a-readiness-recovery-v1/am1-authorization-v1.json"
AM1_CASES = ROOT / "evidence/phase3a-readiness-recovery-v1/am1-acceptance-supplement-v1.json"
AM1_AUTHORITY_SHA = "6a3231e8cd5036df0655f6432ca0a52b3db967ccb3aafa0db0710883b1d88a68"
AM1_CASES_SHA = "e2f7f5121a1c5e787d8fbb58b55a6b559353e08740cc087f0b8c81e0281a940b"
PROVIDERS = ROOT / "evidence/phase3a-readiness-recovery-v1/provider-documentation.json"
LAUNCHER = ROOT / "phase3a-readiness-recovery.ps1"
BASE = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "phase3a-readiness-recovery-v1"
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
    value = safe(value, roots=(BASE, ROOT / "runs/phase3a-readiness-recovery-v1"))
    require(value not in (BASE, ROOT / "runs/phase3a-readiness-recovery-v1"), "output requires a child namespace")
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

CHECKPOINTS.update({'P3A_RP1_LIVE_REPORT.md': '2e6233fcfa6edaf539a10cc78d43cbf2b1a004b74225be0365fda3be709c026b', 'evidence/phase3a-rc1-pilot-v1/independent-acceptance.json': '5d51331f9a8b411b48b22ed0fba7b0eb0337de9792b1c1ef3b6807b2bfe61cd2', 'evidence/phase3a-rc1-pilot-v1/offline-kit-v1.manifest.json': '39cc0734a6124313d31cf95b2cc9baa97750e99d0e53f0fc07817c37ba7401e7', 'evidence/phase3a-rc1-pilot-v1/packet-acceptance.json': '2a8ada4f165ff8a2dec8e898fe779f7320c56e7effd894e1287bed0e413bd206', 'evidence/phase3a-rc1-pilot-v1/live-outcome-v1.json': 'e07b6c8dfaf1e0cd92389265af87875a452e9f6b4c638448eb00c70db4de024a', 'evidence/phase3a-rc1-pilot-v1/live-outcome-v1.manifest.json': '4093c743835da6289dee23a37559425e65b552bcfef2ac4a2bd2e726da9a5cac', 'evidence/phase3a-rc1-pilot-v1/live-independent-acceptance-v1.json': 'bfc0afb1b0d360489cf64b1e162cc005229c402eb7ec5de418ae2f6e75949e34', 'evidence/phase3a-rc1-pilot-v1/live-packet-acceptance.json': '716b32f2d7bd8edcb0f68383d690ce88590eef9fe1bb24f38ef42cc2d8692f31'})

COLD_DEPENDENCIES = {'.upstream/harness2/LICENSE': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30', '.upstream/harness2/harness2/__init__.py': 'de20a79ef3cf3974bf32cb6afdbb32608655676e749a466ffd6c7c173bb7e26a', '.upstream/harness2/harness2/benchmarks/__init__.py': '6c0fb1a1a69906258c5a0a7765aa7d0e862c71ac955707d938933f9c26f73fa8', '.upstream/harness2/harness2/benchmarks/jb_opencode_runner.py': 'aadfb0d1307b41da84900d353505c72d322937aef8f5400e2b95c7701ae9b768', '.upstream/harness2/harness2/benchmarks/jobbench.py': '446738c854a5fc1639c7a8a312aa90367d1f73bc7f1df1f00ccd2d243b2aeafb', '.upstream/harness2/harness2/benchmarks/lab.py': '95bfa213048e870f6c4e45f9040d881ef60f2282d25175b0f8fefe6ce9eb4e71', '.upstream/harness2/harness2/benchmarks/tasks.py': '368fa8d5f7596522a9e54c6c0cb9cd8feb12a3de110d29af05cdd7e6f74dabc7', '.upstream/harness2/harness2/benchmarks/wb_render.py': 'df516796e3f29842b2ee9efa0f9f7274fe062b6e1232be75fb83cf76a93c32b5', '.upstream/harness2/harness2/benchmarks/workbuddy.py': '1e08d17a9ad0b23a3b6dabc6da2d2e65a8110cba17d7882d5f113940f7dfeb91', '.upstream/harness2/harness2/cli/__init__.py': '8fd4345e5586666df552582be8e8d69adbb4daffae69088b08a773400c844b78', '.upstream/harness2/harness2/cli/_common.py': 'aba8393739a6ae343ce95ef005c7037b737466f444064aba63735f2ac5a22037', '.upstream/harness2/harness2/cli/bridge.py': '6092475dd656eccbd454067fd20166d2ca44948d91d3c574b4da2e3b28e2af7e', '.upstream/harness2/harness2/cli/check.py': '0c42509009b292613d46c7a87287036b5080116c14b0da4ead984896d108c2e0', '.upstream/harness2/harness2/cli/demo.py': 'f8ba578ff547d1f78666ee222d0ace3fea34d468405c9766d103b856c6272d25', '.upstream/harness2/harness2/cli/judge.py': '7dfb882266dd541100e5a1d4f7ac6cf728441e26c6850e420651bae8a4c7fb26', '.upstream/harness2/harness2/cli/report.py': '2cb4460658d982d9ef9921b4393b1adbb95d1909b07a967759167b97f78cf5d4', '.upstream/harness2/harness2/cli/run_sweep.py': '83998848662cdf3e101250ae13afbfbf82d9b88db4d9181ab973ae9fe32f8b0a', '.upstream/harness2/harness2/cli/setup.py': 'c0a5438fcbea074e61b749554198638777f393c48d0a686161699e298ee18d0b', '.upstream/harness2/harness2/config.py': '0db5ba0c42b87f5b14cbff2d11aaecddda1cd45500903c1d61741232bd1e0a88', '.upstream/harness2/harness2/core/__init__.py': 'ce487673e00fd8921139e3afb688c566fc43d9b07acba048d2102663a81f7151', '.upstream/harness2/harness2/core/context.py': '63dd482e5d9467d7e659d186a11289fc7861d08c8aed603244ff0cee92de91f3', '.upstream/harness2/harness2/core/judge.py': '0f8cd6f4ec659f5d5976bdad4ccdc432651f51486c3fbbee36be53a6d619fbba', '.upstream/harness2/harness2/core/ledger.py': '7059de5d90fc9fb8d4b3b799ff075f09d34f182ba0fdb56eb9d8b8383d0bbf55', '.upstream/harness2/harness2/core/library.py': '00219fda201a030f43b35b49c4e73ccf336aedc81164144c435b4b06a1256dd3', '.upstream/harness2/harness2/core/prompts.py': 'd1f4f8db4ab4cb4addcbca175b548db2270375499fda727ac95d271c63cc2504', '.upstream/harness2/harness2/core/proposer.py': '475ef49d72228e249d7172d793f8362913774412402dfd259ae6e01c6586e175', '.upstream/harness2/harness2/core/recursion.py': 'b299813b5334f2c0f89024a7f14162f0fdd5418ebd4413be93920b5334a204c1', '.upstream/harness2/harness2/core/report.py': '9d5b119ec93dc6b2c6341095130103ab4ba2f2dc6867c4b7ea759fca5de3cac9', '.upstream/harness2/harness2/core/runmark.py': '99a7c3f0b023623224c3376bc0390e985b8e6608f0928d34b821ffe6c36f9175', '.upstream/harness2/harness2/core/schedule.py': '6e46c5ab1e4ac111818ff3acd6b636e39d650898189ac0c21802a8233ad4cd38', '.upstream/harness2/harness2/core/selection.py': '2cb3353b2fd4ec72e6322f2c1f35db1ff2cdab88b0b50c8809d1841d235cb92f', '.upstream/harness2/harness2/core/spec.py': 'f245ec9e314778e2a1a51594b906584255b9eed8340c073b864a8a6f2c8dc400', '.upstream/harness2/harness2/core/tree.py': 'c2a15690b1b6b02156e922c5e0b1a215c5065d7bea5a3bae2e56b47309197552', '.upstream/harness2/harness2/demo.py': '8f338b3254922a8a48d66162f7796dde435d3ef65a7ccd441ef604c81a1d39d4', '.upstream/harness2/harness2/install.py': 'a75eaa452d405020a268864e1f047346ec10cb64b81c4045f6bda0f72bd152c4', '.upstream/harness2/harness2/preflight.py': '78b6a7bc81ced28987f6d9a47bb20e7e5c6d70ff89f2a70cc9a6d179363d6c53', '.upstream/harness2/harness2/substrate/__init__.py': '57f95d86cb0d4acfd60fddd52f2d140ffadcf0c318e28093532580339dc3f37d', '.upstream/harness2/harness2/substrate/base.py': '50a63f174e3772888af3882f3ffff3162cefba8d36e927b1a5de343c5806dd16', '.upstream/harness2/harness2/substrate/codex.py': '281a07271ebed72a617a671ced1b9137901aa8f5d1deffb56c706f44c295e416', '.upstream/harness2/harness2/substrate/opencode.py': 'dabc79953d164a0d38802125756379ffa6acdc7b553d2f9036475f8220166ff0', '.upstream/novelty-bench/LICENSE': '14e69e7fbb2f8fd0aa8ccf17d7d4ddd54665555c613a0336767f7a5fa477895c', '.upstream/novelty-bench/src/__init__.py': '91447944015cec709e8aa7655f7e9d64e1e4508e7023a57fe3746911c0fc6fed', '.upstream/novelty-bench/src/common.py': 'ba60bf0f2a409c3774d75880f305325a28ed34320610667542a4596c41f424af', '.upstream/novelty-bench/src/evaluation_io.py': '8a34e01308677469d984dd59e36412c2994baf2554fd3a5f026be9ef98a3a5c7', '.upstream/novelty-bench/src/judge.py': '4decf04790b90a03368eb792dfe29045435914a73ab83a52185d9dd0d1613902', '.upstream/novelty-bench/src/partition.py': '263970891ff3ee1cc8df369a33beefe5cb5de618b5dd146a5234536d97954aca', '.upstream/novelty-bench/src/score.py': '418985a40e9e159cfeffe9a43ab2c727010d7a7a29407f4e14cab3c81b77cbae', '.upstream/novelty-bench/src/summarize.py': '0a8bd1eb7f317584f579eaa827e580f9cefe4177a1abdc35b2cb06ef96eeea9e', 'runs/phase3a-c1-completion-v4/verification-v3/release/study.json': '80da9e8702941323e1abbb78df9ceaa568ed3462a4ea3c4c28522064d0b2c37e'}


def source_identity() -> dict:
    parent = frozen_rp1.source_identity()
    require(parent['sha256'] == '64b839d569e3ddefa3d56e06fc5b431760aef15cdfb3fd38256e04f8565f519a'
            and len(parent['files']) == 419, 'accepted RP1 source differs')
    files = dict(parent['files'])
    for name, expected in COLD_DEPENDENCIES.items():
        require(file_hash(ROOT / name) == expected, 'cold replay dependency changed: ' + name)
        files[name] = expected
    for name, expected in CHECKPOINTS.items():
        require(file_hash(ROOT / name) == expected, 'accepted checkpoint changed: ' + name)
        files[name] = expected
    directory = safe(ROOT / 'followups/phase3a_readiness_recovery_v1')
    for name in sorted(os.listdir(directory)):
        if name.casefold() in PRIVATE or 'stdout' in name.casefold() or 'stderr' in name.casefold() or name.casefold() in {
            '__pycache__', '.mypy_cache', '.ruff_cache', '.pytest_cache',
        }:
            continue
        target = safe(directory / name)
        info = target.lstat()
        require(stat.S_ISREG(info.st_mode), 'new source namespace contains an unexpected directory or file type')
        if target.suffix in {'.py', '.json', '.md', '.ps1'}:
            files[target.relative_to(ROOT).as_posix()] = file_hash(target)
    names = (DEFINITION, AUTHORITY, AM1_DEFINITION, AM1_AUTHORITY, AM1_CASES,
             PROVIDERS, LAUNCHER, ROOT / 'phase3a-readiness-recovery-core.ps1',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/package_public.py',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/provider-review.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/provider-review-v2.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/openai-pricing.md',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/acceptance-cases.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/preparation-preservation-v1.json',
             ROOT / 'PHASE3A_RP2_DELIVERY_CLARIFICATION.md',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/delivery-clarification-v1.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/delivery-supplemental-cases-v1.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/cold-dependency-review-v1.json',
             ROOT / 'P3A_RP2_OFFLINE_CHECKPOINT_REPORT.md',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/offline-checkpoint-v1.zip',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/offline-checkpoint-v1.manifest.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/offline-checkpoint-v1.validation.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/component-preparation-v1.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/component-preparation-v2.json',
             ROOT / 'evidence/phase3a-readiness-recovery-v1/component-preparation-v3.json')
    for target in names:
        files[target.relative_to(ROOT).as_posix()] = file_hash(target)
    return {'kind': 'phase3a-rp2-source-v1', 'parent_source_sha256': parent['sha256'],
            'H1_source_sha256': parent['H1_source_sha256'], 'I1_source_sha256': parent['I1_source_sha256'],
            'files': files, 'sha256': digest(files)}


def validate_authority() -> dict:
    value = read(AUTHORITY)
    expected = {"new_cap_micro_usd": 190000000, "first_cap_micro_usd": 50860000,
                "first_assessment_sublimit_micro_usd": 23700000, "readiness_included_micro_usd": 20000000,
                "historical_known_micro_usd": 29874161, "historical_reserved_micro_usd": 22880000,
                "historical_attempts": 1316, "new_max_attempts": 775, "potential_request_slots": 967,
                "cumulative_max_exposure_micro_usd": 242754161, "cumulative_max_attempts": 2091}
    require(value.get("kind") == "phase3a-rp2-authority-v1" and value.get("authorized") is True
            and all(type(value.get(k)) is int and value[k] == n for k, n in expected.items())
            and value.get("historical_liability_release_authorized") is False
            and value.get("old_results_reused") is False
            and value.get("models_and_billing_profile_unchanged") is True
            and value.get("calls_require_offline_gate_and_fresh_masked_keys") is True
            and value.get("definition_sha256") == file_hash(DEFINITION), "HI authority differs")
    require(file_hash(AM1_AUTHORITY) == AM1_AUTHORITY_SHA and file_hash(AM1_CASES) == AM1_CASES_SHA,
            "frozen AM1 authority/cases differ")
    amended, cases = read(AM1_AUTHORITY), read(AM1_CASES)
    require(amended.get("kind") == "phase3a-rp2-am1-authority-v1"
            and amended.get("authorized") is True
            and amended.get("parent_authority_sha256") == file_hash(AUTHORITY)
            and amended.get("definition_sha256") == file_hash(AM1_DEFINITION)
            and amended.get("fresh_cap_micro_usd") == value["new_cap_micro_usd"]
            and amended.get("cumulative_max_exposure_micro_usd") == value["cumulative_max_exposure_micro_usd"]
            and amended.get("new_max_attempts") == value["new_max_attempts"]
            and amended.get("cumulative_max_attempts") == value["cumulative_max_attempts"]
            and amended.get("additional_paid_repetition_authorized") is False
            and amended.get("mandatory_reads_unchanged") is True
            and amended.get("scientific_criteria_unchanged") is True
            and amended.get("fresh_keys_after_independent_acceptance") is True
            and amended.get("original_folder_access_authorized") is False
            and cases.get("authority_sha256") == AM1_AUTHORITY_SHA
            and cases.get("definition_sha256") == amended["definition_sha256"],
            "AM1 approval or unchanged RP2 authority differs")
    return {**value, "am1": amended}


def preserve() -> dict:
    parent = frozen_rp1.preserve()
    source_identity()
    archives = {}
    for stem in ('offline-kit-v1', 'live-outcome-v1'):
        manifest = read(ROOT / ('evidence/phase3a-rc1-pilot-v1/' + stem + '.manifest.json'))
        name = 'evidence/phase3a-rc1-pilot-v1/' + stem + '.zip'
        require(manifest.get('archive') == name and file_hash(ROOT / name) == manifest['archive_sha256'],
                'closed RP1 archive changed')
        archives[name] = manifest['archive_sha256']
    return {'kind': 'phase3a-rp2-preservation-v1', 'passed': True, 'closed_RP1_archives': archives,
            'RP1_preservation': parent, 'accepted_RP1_source_files': 419,
            'accepted_checkpoints': dict(CHECKPOINTS),
            'protected_original_accessed': False, 'private_worktree_accessed': False}


def seal(value: dict) -> dict:
    return {**value, "sha256": digest(value)}


def checked(value: dict) -> dict:
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}), "HI seal differs")
    return value


def publish(target: Path, value: dict) -> None:
    write_once(path(target), value)
