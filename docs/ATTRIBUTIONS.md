# Attribution and licenses

Reviewed November 2, 2026. Buddha2 integrates the projects below. Their authors retain their copyrights and their own license terms. This map identifies the versions used; it does not replace their license texts, bundled notices, dataset terms or model-service terms.

## Execution and assessment

| Project | Exact version used | License and primary source | Role in Buddha2 |
|---|---|---|---|
| [Google Research Harness²](https://github.com/google-research/harness2) | `1cfe254e8d25b15f37048c3730134686abe60335` | [Apache-2.0 at this commit](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/LICENSE) | The actual native proposal, probe, composition and selection engine. Buddha2 supplies external adapters; it does not claim this algorithm as its own. |
| [NoveltyBench](https://github.com/novelty-bench/novelty-bench), Yiming Zhang and contributors | `64a23be6b18ec1dacc298830aab276061b6e143c` | [MIT at this commit](https://github.com/novelty-bench/novelty-bench/blob/64a23be6b18ec1dacc298830aab276061b6e143c/LICENSE) | Native benchmark loading, v1.1 assessment and summary arithmetic. Its code license does not by itself settle every source dataset's terms. |
| [OpenCode](https://github.com/anomalyco/opencode) | Base `23fb5e0516c99ac04a1aa46c193efda2e1b9bb24` | [MIT at this commit](https://github.com/anomalyco/opencode/blob/23fb5e0516c99ac04a1aa46c193efda2e1b9bb24/LICENSE) | Tool-using execution substrate for the native authoring and selection sessions. The installed client includes declared compatibility changes described below. |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), UK AI Security Institute | `inspect-ai==0.3.286` | [MIT at tag `0.3.286`](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.286/LICENSE) | Separate passive saved-log import and viewer. It does not execute this study's models, judges or accounting. |
| [Bun](https://github.com/oven-sh/bun) | `1.3.11`; source image `oven/bun:1.3.11-slim@sha256:478281fdd196871c7e51ba6a820b7803a8ae97042ec86cdbc2e1c6b6626442d9` | [Bun's own code is MIT; linked components have additional terms](https://github.com/oven-sh/bun/blob/bun-v1.3.11/LICENSE.md) | Runs the pinned OpenCode workspace. The Bun binary is not wholly MIT code. |

Harness² and NoveltyBench source pins and file hashes are in [upstreams.lock.json](../upstreams.lock.json). Harness² also retains its own third-party notices and provenance; its Apache-2.0 license does not replace those notices.

The OpenCode baseline retains the declared Harness² compatibility patch and its recorded model/lockfile changes. H1 then backports two selected upstream hunks: [signed/redacted reasoning preservation, `4e14f79511728d04329da664b747dd0b359cf931`](https://github.com/anomalyco/opencode/commit/4e14f79511728d04329da664b747dd0b359cf931) and [removal of obsolete tool reordering, `59403040987137a367f259884766efc363725c39`](https://github.com/anomalyco/opencode/commit/59403040987137a367f259884766efc363725c39). Both upstream revisions retain MIT. These are scoped backports, not complete upgrades to those releases. See [runtime provenance](../evidence/phase3a-v1/runtime-provenance.json), the [H1 report](phases/phase-3a/PHASE3A_HISTORY_COMPAT_H1_REPORT.md) and the [exact patch implementation](../followups/phase3a_history_compat_h1/runtime.py).

The [current two-round definition](phases/phase-3b/PHASE3B_DEFINITION.md) binds H1 image `sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800` and the separate SDK-free Inspect image `sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d`. Inspect's exact wheel SHA256 is `f11c2afed84026507d902bbcc68e7a8ee95e8070786ba2914c880761e97a220f`, matching [official release metadata](https://pypi.org/pypi/inspect-ai/0.3.286/json) and the [retained wheel manifest](../evidence/inspect-visibility-i1/environment/wheel-manifest.json). Its embedded MIT notice was also checked, rather than inferred from a current branch.

## Direct Python dependencies

These are the exact native-benchmark subset declared in [requirements.in](../requirements.in), resolved with its transitive dependencies in [requirements.lock](../requirements.lock). The license column describes project source unless a broader distribution expression is stated; binary wheels retain additional notices.

| Dependency | Pin | License / primary source | Use |
|---|---|---|---|
| NumPy | `2.2.6` | [BSD-3-Clause source](https://github.com/numpy/numpy/blob/v2.2.6/LICENSE.txt); [binary distribution notices](https://pypi.org/pypi/numpy/2.2.6/json) | Native numerical operations/imports |
| pandas | `2.3.2` | [BSD-3-Clause](https://github.com/pandas-dev/pandas/blob/v2.3.2/LICENSE) | Native tabular loading and summaries |
| Pydantic | `2.11.7` | [MIT](https://github.com/pydantic/pydantic/blob/v2.11.7/LICENSE) | Native typed records |
| tqdm | `4.67.1` | [MIT and MPL-2.0-covered contributions](https://github.com/tqdm/tqdm/blob/v4.67.1/LICENCE) | Native progress reporting |
| OpenAI Python SDK | `1.107.0` | [Apache-2.0](https://github.com/openai/openai-python/blob/v1.107.0/LICENSE) | Explicit provider calls and offline SDK transport tests |
| Anthropic Python SDK | `1.4.0` | [MIT](https://github.com/anthropics/anthropic-sdk-python/blob/v1.4.0/LICENSE) | Explicit provider calls and offline SDK transport tests |
| SacreBLEU | `2.5.1` | [Apache-2.0 release license](https://pypi.org/pypi/sacrebleu/2.5.1/json) | Native text-scoring import dependency |
| ROUGE Score | `0.1.2` | [Apache license classification in release metadata](https://pypi.org/pypi/rouge-score/0.1.2/json) | Native text-scoring import dependency |
| Transformers | `5.20.2` | [Apache-2.0](https://github.com/huggingface/transformers/blob/v5.20.2/LICENSE) | Native benchmark import compatibility |
| PyTorch, official CPU build | `2.14.1+cpu` | [BSD-style upstream notice](https://github.com/pytorch/pytorch/blob/v2.14.1/LICENSE); [release expression](https://pypi.org/pypi/torch/2.14.1/json): Apache-2.0, Apache-2.0 WITH LLVM-exception, BSD-2-Clause, BSD-3-Clause, BSL-1.0 and MIT | Native CPU import compatibility; this does not imply a model-weight download |

The OpenCode workspace has a separate npm graph. Its pinned provider path includes Vercel's [`ai==6.0.168`](https://registry.npmjs.org/ai/6.0.168), [`@ai-sdk/anthropic==3.0.71`](https://registry.npmjs.org/@ai-sdk/anthropic/3.0.71), [`@ai-sdk/openai==3.0.53`](https://registry.npmjs.org/@ai-sdk/openai/3.0.53) and [`@ai-sdk/provider==3.0.8`](https://registry.npmjs.org/@ai-sdk/provider/3.0.8), each declared Apache-2.0 by its exact npm release metadata. These versions are distinct from the Python SDKs. The [retained workspace lock](../runs/phase3a-v1/runtime-src/opencode/bun.lock) records the complete graph and integrity hashes.

## Full inventories and material limits

The short tables above are an attribution guide, not a complete software bill of materials. Retained detailed records are:

- [Python dependency license metadata](../evidence/dependency-license-review.json), [installed packages and notice hashes](../evidence/environment.json), and [build-tool lock](../requirements-build.lock). The root lock also includes development checks; `mypy-extensions`' previously missing classification is resolved by its [exact-wheel MIT evidence](../evidence/mypy-extensions-license.json).
- [Inspect's separate 80-package license review](../evidence/inspect-visibility-i1/environment/license-review.json), [hash lock](../evidence/inspect-visibility-i1/environment/requirements.lock), and [wheel/notice manifest](../evidence/inspect-visibility-i1/environment/wheel-manifest.json).
- [OpenCode runtime package-license inventory](../runs/phase3a-v1/runtime-inventory.json) and [runtime provenance](../evidence/phase3a-v1/runtime-provenance.json). The inventory counts 8,467 installed workspace package occurrences, including repeated versions and tooling; it is not a claim that every package executes in the text-only pilot.

These environments contain components with licenses beyond permissive project-source licenses:

- `certifi==2026.10.23` is [MPL-2.0](https://github.com/certifi/python-certifi/blob/2026.10.23/LICENSE), as are `pathspec==1.1.1` [development-tool code](https://github.com/cpburnz/python-pathspec/blob/v1.1.1/LICENSE) and the identified contributions to tqdm. The existing unmodified local-use/notice-retention decisions are recorded in [DECISIONS.md](phases/phase-0/DECISIONS.md).
- Bun's tagged notice identifies JavaScriptCore/WebKit LGPL-2 and tinycc LGPL-2.1 components. OpenCode's installed workspace inventory also identifies `@img/sharp-libvips-*` under LGPL-3.0-or-later, MPL-2.0 packages including lightningcss, axe-core, loglevelnext and `@dot/log`, and packages with `UNKNOWN` metadata. Unknown is an unresolved metadata classification, not evidence of a permissive license. DOMPurify is listed with an MPL-2.0 **or** Apache-2.0 choice, rather than a mandatory MPL-only license.
- NumPy's published binary notices include libgfortran under GPL-3.0 with the GCC Runtime Library Exception and libquadmath under LGPL-2.1-or-later. Keep the exception and bundled notices with the applicable binaries; NumPy's BSD source license alone does not describe them.
- The Debian-based images and build tools include GPL/LGPL system components, as recorded in runtime provenance. The local research setup and its retained notices do not constitute a redistribution review of the entire image.

## Data used in the studies

**MuCE was actual historical input to Phases 1/1A.** Its [pinned card at `a02181e394c41602a95d0678b0ce9d880e994289`](https://huggingface.co/datasets/CNCL-Penn-State/MuCE/blob/a02181e394c41602a95d0678b0ce9d880e994289/README.md) declares `license: mit` and requests citation of *Creative Preference Optimization*, Ismayilzada et al. (2025). It does not declare a Creative Commons license. The public card matches the [retained capture](../evidence/phase1a-data-readiness-r07/references/assets/hf-muce-original-pinned-README.md). The [retained source review](../evidence/phase1a-data-readiness-r07/references/source-semantics.json) records that no separate LICENSE file was listed at that revision and that original donor permissions/participant conditions were not fully established. Historical use was the approved local train cache; no redistribution decision follows. The [data-readiness report](phases/phase-1a/PHASE1A_DATA_READINESS_REPORT.md) records exposure and use limits. MuCE is not the current Phase 3 benchmark.

**The current four development prompts come from NoveltyBench's curated set**, as mapped in the [Phase 3B definition](phases/phase-3b/PHASE3B_DEFINITION.md). Its [official dataset card, reviewed at `8d78adfc3896716724c6d8a8ad202bc77b8e3dff`](https://huggingface.co/datasets/yimingzhang/novelty-bench/blob/8d78adfc3896716724c6d8a8ad202bc77b8e3dff/README.md), describes 100 prompts written for the benchmark and a separate WildChat set, but supplies no dataset-license declaration. The pinned GitHub repository states MIT for the project; a separately scoped data grant was not established by this review. Retain benchmark attribution and consult its published data terms when sharing data rather than treating the software-license label as a complete donor-permissions review. This card review opened no corpus rows or new task contents.

## Research and design references

These references have a different role from the execution dependencies above. Attribution does not imply that their implementations or models are installed, reproduced or validated here.

| Reference | Actual relationship to this project |
|---|---|
| [Creative Preference Optimization (CrPO)](https://github.com/mismayil/creative-preference-optimization) and its [paper](https://arxiv.org/html/2505.14442v2) | Motivation for supplementary diversity, novelty, surprise and quality measurements. Further reproduction/training remains deferred. |
| [Lluminate](https://github.com/joel-simon/lluminate) | Reference for possible future creativity operators/evolution. These operator families are not part of the current comparison. |
| [DeepSeek Harness architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) | Design reference for replaceable boundaries and composition. DeepSeek Harness is not an additional execution engine here. |
| Lenny-derived procedures and other design ideas recorded in the [experiment plan](research/EXPERIMENT_PLAN.md#7-strategy-families-and-deferred-research) | Named future strategy candidates. The plan does not supply a verified primary Lenny publication URL; no unverified source or implemented contribution is asserted. |

Selected CrPO source/configuration captures used for the historical data-readiness review are retained at [revision `9c0d71438687255b355216481064b1ced471ceeb`](https://github.com/mismayil/creative-preference-optimization/tree/9c0d71438687255b355216481064b1ced471ceeb). They remain **MIT**, Copyright (c) 2025 Mete Ismayilzada, under the [retained notice](../evidence/phase1a-data-readiness-r07/references/assets/crpo-LICENSE.txt). Their reference role does not mean that CrPO training or its evaluator implementations run in the current experiment. Cached paper/model-card captures and direct human-row packets are local-only; see [publication notes](PUBLICATION.md).

## License for original Buddha2 code

**Apache-2.0 is adopted for original Buddha2 source and documentation**, under the [root license](../LICENSE) and [NOTICE](../NOTICE). It permits reuse, modification and redistribution, includes an express contributor patent grant, and aligns with the native Harness² engine's license. It is an [OSI-approved license](https://opensource.org/license/apache-2.0). Exact upstream MIT texts are retained for [Inspect AI](../third_party_licenses/INSPECT_AI.txt), [NoveltyBench](../third_party_licenses/NOVELTYBENCH.txt) and [OpenCode](../third_party_licenses/OPENCODE.txt).

Under the [Apache license text](https://www.apache.org/licenses/LICENSE-2.0), distributed copies retain the license and applicable notices, and modified files carry change notices. This project license does not relicense third-party code, datasets, model weights or the container contents listed above. Their own terms and any applicable source/relinking requirements remain separate.
