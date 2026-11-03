# P2B-E operator entry

The user's subsequent **“proceed”** authorizes the unchanged [P2B-E definition](../../PHASE2B_REMAINDER_DEFINITION.md) with a **$125 cumulative ceiling**, including F1's $0.210174 accounted upper bound. [authorization.json](authorization.json) records that authority; the historical definition remains unchanged.

The new `live-expansion-001` grant was generated offline and passed the unchanged launcher's non-sending preflight. It references the existing first authority and approved first review. The canonical journal still contains only F1's 28 known requests, with zero liability. No new API calls or credential reads were made in preparing this entry.

Use the **same two API keys and unchanged direct public PAYG account settings** as F1. The confirmation below concerns those account facts, not another spending approval. F1 deliberately retained no keys. The unchanged launcher will validate its actual container/authority before requesting keys with `Read-Host -AsSecureString`; keys travel only through transient stdin and must match the existing fingerprints. Do not use the one-time F1 entry script.

Paste these three lines into a PowerShell window:

```powershell
$env:Path = 'C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell;' + $env:Path
if ((Read-Host 'Type YES to confirm the same accounts and unchanged public PAYG settings as F1') -cne 'YES') { throw 'Stopped before launch; account profile needs review' }
pwsh -NoProfile -File 'C:\Users\arvik\code\research\Buddha2\phase2-release.ps1' -Action provider -Live -Study 'phase2-release-r018/release/study.json' -Grant 'phase2-release-r018/grants/live-expansion-001/grant.json' -Stage expansion
```

The command works from a fresh window because the launcher resolves its fixed project root. PATH changes affect only that window. Enter keys only at the two masked prompts, never in chat or command text.

After entry, console silence is expected: provider streams are suppressed while the launcher waits. Leave the window open; do not start another copy while that run is active. Tell Codex **“Running”** or provide the resulting status/error text without keys. Codex will inspect the same live handle/journal, then produce and commit the actual complete or bounded-stop report. Original Buddha2 stays outside every access and mount path.

Scope remains the 23 frozen remaining blocks, zero retries/replacements/probes, and the approved cumulative ceiling including liabilities. Recursive adaptation, humans, new models/strategies, held-out evaluation and further spending remain excluded. Completing the fixed pilot does not automatically start Phase 3A.
