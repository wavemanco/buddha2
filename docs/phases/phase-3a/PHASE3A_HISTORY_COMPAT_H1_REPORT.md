# H1 — signed-history compatibility checkpoint

2026-10-30. **Complete offline; independent acceptance passed.** This is an offline engineering checkpoint, not a new Phase3A experiment. API/provider spend is $0; no credentials, live generation, scoring or held-out evaluation were used. 

## What changed

The actual Harness² engine and its source pin remain unchanged. A new isolated OpenCode runtime reuses two published changes in its provider-transform file:

- [PR26276](https://github.com/anomalyco/opencode/pull/26276), commit `4e14f79511728d04329da664b747dd0b359cf931`: retain empty visible reasoning when Anthropic signature or redacted-state metadata is present.
- [PR30483](https://github.com/anomalyco/opencode/pull/30483), commit `59403040987137a367f259884766efc363725c39`: remove the obsolete Anthropic/Vertex tool-reordering workaround.

These are selected hunks, not the full upstream commits or a general release upgrade. No dependencies were added or upgraded. The installed baseline's existing Opus4.8 and lockfile differences are retained; neither baseline nor derived client is mislabeled as a pristine newer release.

Parent image: `sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2`. Derived image: `sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800`. Only the authorized transform file changes among the measured ordinary image entries, to SHA `037e295c1905487293ebf99f660d889343eb4e675cd9223329df3febace72821`. Both images remain available. The original failed R3 study is not repaired or resumed.

A small injected `HistoryGuard` now checks the exact previous assistant blocks, complete prior message prefix, tool-result ownership, model/instruction/tool controls and conversation/turn identity before delegating admission. It never reconstructs or edits signed history. Errors, incomplete responses and delegate exceptions permanently stop that guard instance. The existing local relay cache serves an identical HTTP replay without another admission.

This component covers serialized ordinary tool conversations through15 requests. It is not a terminal16 implementation, durable resume system or accepted paid-launch kit; those integration boundaries need the next block's concrete definition and tests.

## Evidence

The actual installed SDK/OpenCode baseline reproduces the missing empty signed block. The first filter-only runtime fixes that loss but still reorders a valid thinking/tool/thinking/tool response; that intermediate failure and image are retained. The second published deletion resolves the ordering case without loosening the strict guard.

The corrected pipeline preserves empty signed, visible signed and redacted thinking through real SDK parsing, OpenCode storage/conversion, tool execution and the next mocked request. Valid within-response ordering ends with a tool; interleaving across tool-result turns is exercised separately. A fixture ending with reasoning is retained as an unsupported-shape diagnostic and rejection case, not evidence of normal provider support.

Actual native `Proposer.call` fixtures complete normal read/write/reread/final behavior: the changed case uses11 mocked requests and KEEP_BASE uses10. They run actual Harness²/OpenCode with SDK mock transport and local relay. Their scripted outputs prove software behavior only; they are not learned changes, live model judgments or quality results.

Guard checks include thirteen history-tampering variants, local replay, latched unknown/incomplete/exception failure, conversation controls and the ordinary-turn ceiling. Incomplete SDK-stream parsing and rejection of incomplete results are compositional checks; this is not a native end-to-end crash-recovery claim. Cryptographic validation by a live provider is not tested.

The strict private-first inventory compares393,039 ordinary entries in each image, including content, mode, ownership and link information. Two private names and declared dynamic Docker paths are excluded before metadata/content access. All other **scanned** entries match. Unchanged excluded private files follow from the retained base/layer and selected write target; their bytes were not read or hashed. The shared historical filter branch also covers other providers, but this checkpoint certifies only its tested Anthropic route, not Bedrock compatibility.

Ruff, Mypy and Bandit pass. A separate durable [DirEntry-level private-scan check](../../../evidence/phase3a-history-compat-h1/independent-private-scan-check.py) passes the actual scanner and rejects the deliberately bad walker, making the old ordering defect observable.

## Verification lineage

Unaccepted offline candidates remain preserved: an explicit disposable-cache static-check finding, the original walker's private-entry classification order, and the missing source-map authentication predicate. No former result is rewritten as accepted.

The complete `verification-v3` run passed runtime inventories, actual SDK/native fixtures, unit/adverse/replay checks and static checks. Final review then required authenticating the archived R3 source map before using its filenames. A narrow `verification-v4` preservation amendment adds pinned source/map validation and link guards, plus adverse tests that trap access to foreign/private paths. It reruns relevant static/unit/preservation checks and binds the earlier full run's unchanged runtime, guard, fixture, probe, Docker and definition bytes. It does not claim those expensive runtime/native checks were rerun under a different source identity.

Independent acceptance of that evidence composition **passed**. The [external receipt](../../../evidence/phase3a-history-compat-h1/independent-acceptance.json), SHA `a999c33b4584a6c1a94d0fda45078fca09db0e98b29f662eafd7396cdc7ff4f6`, binds current10-file source identity `0ab7775b63193b5de354f33ffa46ad8086e6a080bae6bd757090d0003769f813`,26 evidence hashes,161 retained full-run files,294 current plus294 retained R3 sources and974 R3 closure inputs. Both actual verifier invocations exited0. The machine summaries deliberately leave H1 completion false until external review; this receipt completes that condition without rewriting them.

## R3 and scientific status

[R3's accepted closure](../../../evidence/phase3a-c1-completion-v4/live-packet-acceptance.json), committed in `45c8a22`, retains73 known calls/$3.478993, zero new uncertainty, normal native execution and failed exact-history readiness. It has0/8 scored primaries and null aggregate/method selection. Historical held liability remains $22.88; cumulative known cost is $16.580264. H1 changes none of those outcomes or accounting figures.

Phase3A therefore remains scientifically incomplete. H1 supplies a compatibility correction and earlier stop condition; it does not show recursive adaptation outperforming the fixed planner, and supplies no held-out result.

## Use and research

From the project root, with the retained matching Docker images, the full offline verifier accepts a fresh unused output directory:

```powershell
python -B -m followups.phase3a_history_compat_h1.verify --output runs/phase3a-history-compat-h1/verification-new
```

It uses no provider credentials/calls and refuses an existing output root. The current host's retained images are verified; this is not a claim of bit-identical image reconstruction on a fresh machine.

The primary-source [research note](../../../evidence/phase3a-history-compat-h1/RESEARCH.md) is committed in `c635ff9`; the focused [Inspect AI fit review](../../../evidence/phase3a-history-compat-h1/INSPECT_AI_FIT.md) is committed in `83e5d5c`. Inspect already has relevant signed-thinking/interleaving tests. The proposed next infrastructure check is passive import/viewing of closed outputs in an isolated environment, retaining native engines, scoring and the financial ledger. Inspect was not installed or experimentally validated here.

The next experimental block must define integration of the new runtime/guard and one fresh pilot, with explicit settings, budgets, review/stop rules and completion criteria. H1 authorizes no paid repeat, expanded benchmark, platform migration, Phase3B or CrPO/human work.
