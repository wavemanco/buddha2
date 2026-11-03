# Inspect display correction V2

The user requested correction of the closed pilot viewer's 1969 dates and an explanation of empty Models and Activity panes. This is a presentation-only repair of the reached closure checkpoint, not a new experiment phase.

- **Objective:** show real dated provenance and originating model configurations in Inspect, while preserving the closed native result.
- **Inputs:** the exact saved closure `.eval`, its frozen snapshot identity, the eight canonical report hashes, and explicitly authenticated public request audits/journal plus sanitized launcher records. No directory sweep or provider streams.
- **Work:** derive a bounded source-bound provenance supplement; project a new saved log with controller start/end, a separate API-activity envelope and import time; map declared originating model-role configurations; retain dated imported InfoEvents and export an audit CSV. Explain that Inspect Activity requires Model/Tool events, which this import does not fabricate.
- **Deliverables:** a fresh isolated viewer, reproducible projection/provenance helpers, meaningful offline checks, and an acceptance record binding input/output hashes and unchanged native semantics.
- **Exclusions:** model/provider calls, credentials, new scores or outputs, experiment-method changes, reconstructed conversations, fabricated tool/model events, changes to the original folder, frozen code, reports, snapshots or archives. This does not enable continuous live monitoring.
- **Completion:** October 31, 2026 timestamps survive saved-log read/write; imported Models configurations agree with the source; 256 request intervals and $7.882971 known cost reconcile; all native outcomes/attachments and historical holds remain exact; zero model/network attempts; verify Task and Models in the actual viewer, or report a concrete UI-control blocker.
- **Cost:** $0 API spend. Use the existing pinned Inspect image, with network disabled, explicit read-only inputs and one fresh output mount. No dependency installation or provider bridge.

The completed scientific attempt remains incomplete (two of eight primaries scored). After this display repair, the next scientific work is to define the bounded ranking-contract checkpoint before any implementation or paid repeat.

## Use

Open the [corrected viewer](http://127.0.0.1:8772/viewer/#/tasks/closure-v2.eval/task). Under Models, select **Roles**: the stock model-only view deduplicates by model ID and shows one role's profile, whereas Roles preserves all seven distinct configurations. Usage remains explicitly imported provenance; Inspect did not perform these calls.

The native request timeline is in Info/Transcript and [native-audit.csv](http://127.0.0.1:8772/native-audit.csv). Activity's graph does not consume InfoEvents. No ModelEvent, ToolEvent, missing timestamp or conversation was invented to fill it.

The static server can be restarted from the research checkout with:

```powershell
python -B -m http.server 8772 --bind 127.0.0.1 --directory 'C:\Users\arvik\code\research\Buddha2\runs\inspect-display-v2\verification-v2\export'
```

The durable saved log, provenance, CSV and evidence are retained under `evidence/inspect-display-v2`. The exact isolated export command and read-only mount inspection are in `export-run.json` and `export-container.json`. Reprojection requires the original closure log authenticated by the prior closed-attempt packet, the provenance file and a fresh output namespace; it does not rerun Harness² or the benchmark.
