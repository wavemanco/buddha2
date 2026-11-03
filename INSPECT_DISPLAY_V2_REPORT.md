# Inspect display correction V2

The closed P3A-HI attempt is real provider-backed evidence. Its original viewer incorrectly showed 1969 because the adapter left `EvalStats.started_at` and `completed_at` empty. Inspect's pinned Task view evaluates those empty fields as Unix epoch zero, displayed locally as December 31, 1969. The original `eval.created` was a separate fixed import marker; it did not supply the Task dates.

The new presentation reads the original saved log and source-bound public provenance into a fresh export. No original snapshot, report, source, archive, score, failure or budget was modified. The original `C:\Users\arvik\code\buddha2` was not accessed or changed. API spend for this repair was **$0**.

## Dates and model information

The [actual corrected viewer](http://127.0.0.1:8772/viewer/#/tasks/closure-v2.eval/task) was checked on screen. Task now shows **October 31, 2026, 07:52:53–10:11:43 America/Los_Angeles**, with duration 2 hr 18 min 49 sec. These are the recorded controller bounds, including setup, key wait, reviews and display pauses. The separate recorded API-audit envelope is **08:40:21–10:08:51 local time**. Import time is stored separately; no date comes from file modification time or a guessed task-function/key-entry instant. Original nanosecond source strings remain in metadata even though Inspect normalizes its display fields to microseconds.

Models was empty because the first adapter set `model="none"` for passive import, with no typed model roles or Inspect usage. Model IDs/settings existed only in native metadata. V2 supplies labelled imported-origin model configurations:

| Native role | Originating model | Recorded requests |
|---|---|---:|
| Plan | claude-sonnet-5-5 | 14 |
| Answer | claude-sonnet-5-5 | 140 |
| Rank | claude-sonnet-5-5 | 14 |
| Editor | claude-opus-5 | 54 |
| Fixed selector | claude-opus-5 | 1 |
| Grouping | gpt-5.6-luna | 3 |
| Quality | claude-opus-5 | 30 |
| **Total** | | **256** |

Use **Models → Roles**, selected in the displayed page, to see every role's settings and omissions. The stock model-only view collapses duplicate model IDs and displays one role's configuration, so it is not a combined native usage report. Raw originating parameters preserve low/high effort, adaptive thinking, token limits, schema controls and tier/geography omissions as recorded. Inspect usage stays absent: the import did not execute any of these requests. The preserved `NO_MODEL_CALLS` import tag refers to the exporter, not the historical native run.

## Why Activity remains limited

The existing import used InfoEvents. This Inspect version's Activity chart renders model/tool execution events rather than InfoEvents. More dated InfoEvents do not create that chart. V2 explicitly discloses the limitation, without manufacturing model messages, tool invocations or tool-choice values.

All **256 genuine audit intervals** are now available as dated Info/Transcript records, native audit metadata and the [audit CSV](http://127.0.0.1:8772/native-audit.csv). Their timing runs from recorded admission through post-cleanup completion, not provider server latency or token-generation speed. Eleven diagnostic judge requests are identified separately from the two primary assessments. Their known cost reconciles to **$7.882971**; the export adds no spend, scores or primary samples.

## Verification and preserved evidence

Seven final offline unit methods passed, covering unchanged native evidence, separate timestamp meanings, role/configuration counts, no fabricated execution events, the diagnostic CSV and rejection of altered or malformed provenance. The provenance helper separately passed ten negative checks. Ruff, Mypy using the project's `check_untyped_defs` rule, and Bandit passed for all three new Python files. The exact saved-log projection ran in the existing pinned Inspect image with network disabled, a read-only root, explicit read-only inputs/source and one fresh output directory. Its owned container was removed.

The export proof records zero model-constructor or external-socket attempts, a successful semantic saved-log roundtrip, preservation of every original raw attachment value and resolved native output, and unchanged scientific completion status. The Task and seven-role Models view were checked through the actual browser. Source references, raw saved log, CSV, successful and failed preparation records, and final checks are indexed by [retained-evidence.json](evidence/inspect-display-v2/retained-evidence.json); [viewer-check.json](evidence/inspect-display-v2/viewer-check.json) records the UI observations. [Independent acceptance](evidence/inspect-display-v2/independent-acceptance.json) passed, including a separate isolated saved-reader check, all 272 source references and unchanged 356-file canonical source.

The first unit run expected literal nanosecond strings where Inspect normalizes date representation; the corrected test compares the same UTC instant and separately requires the original source strings to remain exact. Initial root static checks used the container image's unrelated configuration, followed by an incorrectly named mounted TOML file. The final checks use the existing project `pyproject.toml`, with explicit first-party namespace classification for the restricted source mounts. No project rule or scientific acceptance threshold was weakened. The failed records and exact predecessor source bytes remain retained.

This is a separate display repair, not another scientific attempt. P3A-HI remains **two of eight primary portfolios scored, scientifically incomplete**; historical holds and the original ranking failure remain unchanged.

**Next:** define a bounded offline ranking-contract checkpoint. It should reproduce the saved failure, freeze one prospective output contract shared by fixed and adaptive arms, and specify its mock acceptance checks before implementation or another paid pilot. Broader Activity instrumentation can remain optional; it need not block that scientific work.
