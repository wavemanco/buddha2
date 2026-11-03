# H1 offline compatibility component

Run from `C:\Users\arvik\code\research\Buddha2`, with Docker Desktop running:

```powershell
python -B -m followups.phase3a_history_compat_h1.verify --output runs/phase3a-history-compat-h1/verification-v1
```

Choose a fresh output directory each time. The command requires the retained baseline,
filter-only image and final derived image; it performs no dependency installation or live
provider operation. All actual SDK HTTP responses are synthetic MockTransport responses.
Containers have networking disabled, with local relay HTTP only.

`HistoryGuard(delegate, prefix)` wraps an existing admission callback. It accepts one
ordinary tool conversation, turns1–15, preserves all provider blocks and prior messages,
and stops permanently after any invalid or unresolved outcome. It does not restore state,
authorize calls, replace resource accounting, support terminal16, or resume interrupted
conversations. Identical local HTTP replay is handled by the reused frozen relay.

The runtime applies only two official OpenCode hunks to the retained baseline bytes.
`runtime.py` pins their exact input/output hashes. Existing Harness², NoveltyBench,
SDKs, lockfile, Bun binary and every other ordinary image file remain unchanged.
This is a scoped upstream backport, not a pristine upstream release.

Fixtures establish software compatibility only. They do not validate real opaque
signatures, provider accounts, live completion, creativity, or adaptation effectiveness.
