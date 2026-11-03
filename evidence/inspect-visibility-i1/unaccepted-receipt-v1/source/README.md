# I1: passive Inspect visibility

This imports **two closed synthetic H1 fixtures**, without running Harness², a model,
an evaluator or Inspect's provider bridge. The original evidence remains authoritative.
It creates two viewable Inspect saved logs: `fixed-changed/inv1.a1` returned normally;
`baseline-loss/inv1.a1` failed native history preservation. Both expectation tests passed,
which does **not** turn the failed native case into a success.

## Run

From `C:\Users\arvik\code\research\Buddha2`, using a fresh absolute output path:

```powershell
python -B -m followups.inspect_visibility_i1.run --output 'C:\Users\arvik\code\research\Buddha2\runs\inspect-visibility-i1\verification-new'
```

The prepared image is `buddha2-inspect-i1:0.3.286`. The command records its immutable
ID, actual Docker network/read-only/mount settings, seven boundary/containment checks,
two independent imports, full semantic saved-log round trips and before/after input hashes.
Inputs are four individually whitelisted read-only files. Only the fresh output directory
is writable, plus a bounded disposable container tmpfs. No host environment is passed.

Each `replay-N/viewer` directory is a standard, static Inspect viewer bundle. Serve it
on loopback with a local static HTTP server; no provider route is involved. A browser
usually cannot load the bundle directly from a `file:` URL. The root trial report records
the actual viewer check and the selected local viewing command.

## What the view means

- `model=none` identifies the passive import, while originating role/model/configuration
  are retained in native metadata. No model is selected or constructed.
- Native calls appear as **InfoEvents**, containing exact recorded wire JSON, rather than
  invented Inspect ModelEvents/ToolEvents or a reconstructed successful conversation.
- Actual final text appears only for the normal return. The failed case has an empty output,
  absent scores/results and its exact native failure message. Its error pane contains a
  labelled imported error summary, not fabricated Python traceback frames.
- Original UTF-8 bytes are preserved in both log attachments and `sources/` sidecars.
  Full metadata preserves raw request/response fields, opaque signatures, order, missing
  values, explicit nulls and zeros. No normalization is applied to that evidence.
- Native `end_turn` is displayed as Inspect `stop` only for the normal final text; the raw
  value remains in the wire. Synthetic fixture usage remains separately labelled;
  Inspect/native real-provider requests and real spend are zero. No quality scores exist.
- Fixed import IDs/timestamp are display-only, never native execution times. Event creation
  timestamps and internal attachment pooling IDs are excluded from semantic comparison;
  event type/data/order, output, full errors, spec, source bytes and metadata are compared.

The importer rejects changed hashes, unsupported cases/status/role/model/configuration,
noncanonical/private/escaped paths and links before opening them. It blocks socket/DNS
operations and Inspect Model/ModelAPI construction. Optional Anthropic/OpenAI SDKs must be
absent. A separate unit test deliberately probes these blocks; each actual import must
record zero attempts.

## Isolated environment

Inspect is MIT. `inspect-ai==0.3.286` is pinned to the public wheel SHA256
`f11c2afed84026507d902bbcc68e7a8ee95e8070786ba2914c880761e97a220f`.
The exact Linux/Python3.12 dependency closure is retained under
`runs/inspect-visibility-i1/setup-v3`: resolver report, pre-install license decision,
80 wheel hashes/notices, hash-required lock, installation record and image identity.
The missing ACP metadata license was checked against the exact wheel's Apache2.0 notice.
Unmodified certifi MPL use follows the existing local-use decision in `DECISIONS.md`.
No new copyleft package was enabled. Provider SDKs are optional development extras;
the passive image does not install them or change existing project/H1 dependencies.

Fresh setup requires registry access solely for package preparation:

```powershell
python -B -m followups.inspect_visibility_i1.setup --output 'C:\Users\arvik\code\research\Buddha2\runs\inspect-visibility-i1\setup-new'
```

That resolves then pins a fresh closure, so its identity may differ from the retained
accepted environment. The frozen wheel closure can be rebuilt into a fresh setup directory
with `--reuse-reviewed` pointing at its retained setup directory; every wheel is rehashed
and checked against the resolver record. Runtime always has `--network none`.

This is a visibility adapter, not a paid-launch kit, financial ledger replacement,
scientific comparison, reliable arbitrary-process recovery system or platform migration.
