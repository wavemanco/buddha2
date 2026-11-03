# I1 — passive Inspect visibility trial

2026-10-31. **Offline trial passed; limited adoption recommended for browsing saved evidence.** The usable result is a repeatable two-case importer and an actual Inspect viewer. This does not replace the financial ledger, native execution controls or experimental decisions. API spend was **$0**, with no provider bridge, keys, model execution or scientific scoring.

The [definition](INSPECT_VISIBILITY_I1_DEFINITION.md) bounded this as one engineering session of at most four hours. The user authorized it by accepting the passive Inspect recommendation. It closes that slice without starting another Phase3A pilot.

## What was tested

Exactly two retained H1 synthetic native-editor fixtures were imported through actual Inspect saved-log APIs. Harness² was not rerun. Both source expectation tests passed, but their native outcomes differ:

| Imported case | Preserved native outcome | Recorded activity | Assessment |
|---|---|---|---|
| `fixed-changed/inv1.a1` | Normal final return; scripted consumed-field EDIT completed | 11 mocked requests; synthetic 880 input/264 output tokens | No scientific score or eligibility |
| `baseline-loss/inv1.a1` | Editor stopped after history rejection; normal final absent | 1 admitted mocked request; rejected continuation retained separately; synthetic 80 input/24 output tokens | No scientific score or eligibility |

The baseline's `passed=true` remains the fixture expectation outcome. It is never mapped to native success, and its scripted EDIT intent is never promoted to a completed edit. Both cases made zero real provider calls and spent $0.

Two separate Inspect logs make success/error visible independently. `model="none"` identifies passive import; originating editor role, `claude-opus-5`, adaptive/high settings,16,000 output cap and exact field omissions remain imported provenance. Synthetic usage is separate from absent Inspect inference usage and known zero real spend.

Full original result/wire JSON is retained as metadata, exact UTF-8 attachments and sidecars. Opaque signatures, empty thinking, block order, tool ownership, omissions/null/zero and rejected relay requests remain intact. Imported records appear as labelled InfoEvents; the adapter does not invent Inspect model/tool execution or reconstruct a successful conversation. Only the successful case has final text. The native `end_turn` to display `stop` mapping is disclosed.

This uses Inspect's public [saved-log APIs](https://inspect.aisi.org.uk/reference/inspect_ai.log.html) and [viewer bundle](https://inspect.aisi.org.uk/log-viewer.html). It uses neither `eval()` nor the provider bridge and constructs no model.

## Verification and preservation

The final author run is `runs/inspect-visibility-i1/verification-v7`. An independent worker reran the public runner in `verification-review-v1` and, after the narrow setup correction, on final source in `verification-review-v2`. It checked all eight earlier saved logs across both pairs of imports directly with Inspect's reader against the four canonical inputs, then bound their identical semantics to the final runs. The [independent receipt](../../../evidence/inspect-visibility-i1/independent-acceptance.json) records the exact scope and hashes.

- Eight meaningful checks passed, including malformed/unknown inputs, status/configuration changes, private/escaped paths, real Linux links, deliberate model/socket/DNS rejection probes and explicit-file-only setup reuse.
- Both fresh imports preserve full semantic log fields and exact source attachment bytes; two replays agree. Event creation times and internal attachment-pool IDs are explicitly excluded, while event type/data/order, output, full errors, spec and provenance are compared.
- Actual import executions record zero attempted model construction or network operations. Deliberate containment probes are separate tests. Docker inspection verifies network-none, read-only root and four explicit read-only input files, one source mount and one writable fresh output mount.
- Ruff, Mypy and Bandit passed. Bandit's narrow documented non-credential/tmpfs exclusions remain visible in its retained output; this is not a broad production security certification.
- Before/after checks preserve H1's10-source identity, all294 authenticated frozen R3 source files and all four source case inputs. Closed outcomes and historical financial holds were not changed. 

The [actual browser check](../../../evidence/inspect-visibility-i1/viewer-check.json) confirms both cases can be opened. It used the retained v6 bundle; the final v7 changes only setup/tests, preserving importer, runtime image and semantic payload. The error tab shows the exact native failure and ContractError detail as a labelled imported summary, without invented traceback frames. The successful final notes are visible in sample Info metadata.

Two presentation limits remain: the Messages tab is empty because this adapter deliberately imports raw native events rather than a reconstructed conversation; the success header renders a NaN duration because native execution timing is missing. Missing timing was not filled with a fabricated zero. This trial does not test live progress, new outputs, general Harness² run schemas or provider compatibility.

Early setup/import attempts remain in their fresh namespaces. They exposed missing license metadata, CRLF lock parsing, optional-SDK availability probing, generated display IDs and the blank error pane. None is relabelled as the accepted final run. Independent reader development also retained its initial unresolved-attachment comparison failure before using the correct raw/resolved reader views; no production change was needed for that check. The first review receipt and its exact source snapshot were withdrawn and retained after review found that optional wheel reuse copied unlisted directory contents. Final reuse validates the explicit manifest/resolution leaves and copies only verified wheel bytes; a regression checks unlisted private/link files remain untouched. No actual private-file access was established.

## Environment and added work

Inspect `0.3.286` is pinned to released wheel SHA `f11c2afed84026507d902bbcc68e7a8ee95e8070786ba2914c880761e97a220f`. The isolated image is `sha256:25b07e51ef9ae948e7f3de5314b91b1ec4c120219ceebfde4b4064525c40a03d`. The final eight-file implementation identity is `cce047344d066a89f4980bdb593013fb48bc6d9a6c18c92fa8e576b475afab05`.

Setup retained80 hash-locked wheels, resolver evidence and license/notice hashes under `runs/inspect-visibility-i1/setup-v3`. Inspect is MIT; existing unmodified local certifi MPL use follows DECISIONS.md. ACP's absent metadata license was verified from its exact Apache2.0 wheel notice. No new copyleft package was enabled and no main-project/H1 dependency changed. The earlier research note's provider-SDK dependency statement was too broad: Anthropic/OpenAI requirements are optional development extras, absent from this passive image.

| Responsibility | Observed benefit or remaining work |
|---|---|
| Finding and opening the two outcomes | One standard Inspect listing with separate success/error records, then sample details; no custom viewer UI was written. |
| Reading raw evidence and failure detail | Inspect provides navigable events, metadata, JSON and a visible failure pane with source bytes retained. This substitutes for manually opening the four source JSON files for these cases; no timed usability comparison was performed. |
| Existing project modules removed | **Zero.** This is an additive fit trial. No production report, runner, journal or guard was removed. |
| Adapter/setup work added | Six Python files including tests, plus Dockerfile and README; eight files total. The isolated closure contains80 locked wheels. These are real maintenance costs. |
| Native assessment and scientific decision | Still external and unchanged. No NoveltyBench or generic Inspect scorer ran. |
| Financial admission, uncertain charges, history, ownership/deadlines | Still project responsibilities. Passive logs do not establish replacement or equivalent guarantees. |

**Decision:** retain this as a usable optional evidence viewer. Do not undertake a broad platform migration or provider-bridge integration on this evidence. The trial demonstrates faithful import of two known fixture schemas, not a general importer or net code reduction. If extended later, name the specific reporting module/operator step to remove and verify that replacement before declaring simplification.

## Use and next step

The prepared [viewer](http://127.0.0.1:8766/) was opened locally. Its reproducible start command from the research checkout is:

```powershell
python -B -m http.server 8766 --bind 127.0.0.1 --directory 'C:\Users\arvik\code\research\Buddha2\runs\inspect-visibility-i1\verification-v6\replay-1\viewer'
```

The [adapter README](../../../followups/inspect_visibility_i1/README.md) describes a fresh zero-call replay and isolated setup. Committed saved logs and environment/fidelity evidence are indexed in `evidence/inspect-visibility-i1`.

Phase3A remains incomplete. The next work toward the scientific goal is a concrete definition for integrating accepted H1 compatibility with terminal-turn/deadline/accounting policies and one fresh pilot. Keep optional passive visibility outside that provider path. This trial starts neither that implementation nor any paid repetition; CrPO, human collection, Phase3B and held-out work remain deferred.
