# C1 offline compatibility kit

Work only from the project root. 

## One command

The host needs Python and the existing Docker runtime/image. The command verifies the pinned image locally; it does not download, rebuild, request credentials or expose a paid route.

```powershell
Set-Location 'C:\Users\arvik\code\research\Buddha2'
python -B -m followups.phase3a_compat_c1_v1.verify --output runs/phase3a-compat-c1-v1/operator-check-01
```

Use a fresh output name each time. Existing evidence is never overwritten. The command uses a read-only source mount, network denial, bounded temporary memory storage, fake-key SDK transports and one new export directory. Do not replace the image, enable networking, mount a home/credential directory or pass API keys.

The image must already be present:

`sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2`

The source checkout must retain the pinned upstream folders and unchanged R2 public reference artifacts. Missing or changed prerequisites fail closed. This is a usable command for this existing checkout, not a claim that the ZIP contains a replacement Docker installation or every upstream runtime dependency.

## What it emits

- Exact Docker arguments, host exit/time record, contained logs, static checks and affected regression results.
- Source and closed-public-evidence identities before/after; rendered contracts/manifests for all twelve exposed R2 contexts.
- One synthetic actual Harness²/OpenCode composite, including four C-N solver rollouts, original/effective authoring missions, context views, manifests, harvested strategies and editor decisions.
- Actual SDK mock requests/results, model-visible evidence reconstruction proofs, normal/terminal classifications, journal and identical ledger replay.
- `result.json` and `demo/report.json`, plus `demo/DEMO_REPORT.md`. An absent or failed final result is incomplete verification, not a pass.

For a direct contained demonstration, the wrapper exercises:

```text
python -B -m followups.phase3a_compat_c1_v1.cli demo --output /results/phase3a-compat-c1-v1/demo
```

That subcommand requires the fixed `/results` mount and Linux network denial. The outer command establishes those conditions and exports the otherwise temporary artifacts.

## Reading the result

The scripted native path makes an INV edit, normally keeps the base in DOM, and composes in AGG. It demonstrates exact evidence delivery, strategy rereading/validation, field consumption and ordinary completion. A valid unchanged decision remains eligible. Terminal unchanged outcomes remain ineligible; terminal changed outcomes retain the existing native classification.

The supported OpenCode agent-prompt setting supplies the same coherent SYSTEM role contract and factual index. The editor first reads `MISSION.md`, verifies its delivery, then batches the complete indexed evidence. The old generic system prompt and the configured/actual system identities are retained separately; unavailable TodoWrite/Task requirements are not active in this profile.

There are 68 synthetic HTTP calls in the demonstration: 48 solver and 20 editor, with editor rounds 7/6/7. These are fake-key SDK calls to local mock transports, not provider requests. The inherited strict ledger has 775 carrier slots; only one synthetic adaptive cell is admitted. The other 707 slots are unused mechanical metadata, not experiments or paid authority. Synthetic accounting is explicitly separate from real spending, which is zero.

The demonstration proves a possible mechanical route. It does not establish that an actual model will follow it, that any strategy improves creative quality, or that Phase 3A's scientific comparison is complete. No new live call follows automatically. See the separately proposed [actual-model readiness block](PHASE3A_POST_C1_LIVE_READINESS_DEFINITION.md).
