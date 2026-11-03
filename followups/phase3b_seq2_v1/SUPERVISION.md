# P3B-S2 startup and the dedicated keyless supervisor

The supervising agent must be dispatched and actually running **before** the
fresh key console opens. Give it the accepted study/runbook and exact public
run/evidence paths. Its responsibilities cover attachment, counted readiness,
the first-prompt engineering review, both bounded Inspect exports and owner-settled
closure. It must monitor independently of the parent chat receiving “keys entered.”
It receives no keys, provider transport or authority to alter grants or scores.

Pass its actual canonical agent handle to the new launcher:

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -File 'C:\Users\arvik\code\research\Buddha2\phase3b-seq2.ps1' -Action provider -Study 'phase3b-seq2-v1/VERIFICATION/release/study.json' -Grant 'phase3b-seq2-v1/VERIFICATION/release/live-grant.json' -SupervisorAgent '/root/ACTUAL_AGENT_HANDLE' -Stage all -Live
```

Replace the two explicit placeholders with accepted paths and the dispatched
handle; do not run this illustrative command against an unaccepted kit. The
contained operational rehearsal instead uses `-Action mock`, its fresh
`fixture_supervision_rehearsal=true` study and mock grant, and no `-Live`.
That mode accepts only the fixed fake keys. Production rejects rehearsal studies.

After the existing single hidden key entry, the controller publishes:

`runs/phase3b-seq2-v1/native/STUDY_SHA/{live|mock}/supervision/request.json`

The request binds all six release/grant hashes, fixture mode, actual inspected
container ID, controller PID, fresh launch nonce, supervisor handle and the
inspection seal. Its 1,800-second monotonic deadline is nonrenewable. No transport
construction, live claim, credential fingerprint binding or durable intent may
precede its consumed ACK. A timeout or cancellation stops this launch, clears key
references and requires existing exact-owned process/container cleanup.

## Publishing the trusted attachment ACK

The supervisor or parent must call **the actual `collaboration.list_agents` tool
now**, after the request appears, and use the named agent's new `running` entry.
An older status record, a guessed status or the fact that the agent was spawned
does not satisfy this step. If the new result is absent, idle or completed, do
not publish. Retain the actual tool observation/dispatch evidence in the final
operator audit. No file-based status-import option exists.

The trusted caller immediately constructs this observation from that result:

```json
{
  "kind": "phase3b-s2-supervisor-observation-v1",
  "tool": "collaboration.list_agents",
  "request_sha256": "EXACT_REQUEST_SHA256",
  "observed_at_utc": "ACTUAL_ISO_8601_UTC_OBSERVATION_TIME",
  "agent": {"agent_name": "/root/ACTUAL_AGENT_HANDLE", "agent_status": "running"}
}
```

Feed that fresh JSON directly on standard input to this keyless host command,
from the project root with the usual credential-free
environment and an explicit `PYTHONPATH` containing that root and its `src`:

```text
python -B -m followups.phase3b_seq2_v1.supervision --request C:\Users\arvik\code\research\Buddha2\runs\phase3b-seq2-v1\native\STUDY_SHA\live\supervision\request.json
```

Use `mock` for the actual fake-key rehearsal. The Python API is
`publish_ack(request_path, observation)`. Its default host owner observer checks
only `docker inspect --format '{{json .State.Running}}' EXACT_CID`; it does not
inspect the container environment or provider streams. The publisher rejects an
observation older than 30 seconds, one before request creation, wrong bindings,
an absent/foreign controller, a repeated ACK or an expired/closed request.

This is an explicit **trusted host attestation seam**: Python/container code
cannot query or cryptographically authenticate the collaboration orchestrator.
The trusted caller is responsible for using the actual immediate tool result.
The ACK records a point-in-time observation, never a guarantee of future agent
availability or an approval of scientific quality/readiness. Existing later
review/export deadlines govern lost supervision; no lease service is added.

The controller consumes the ACK once into `supervision/receipt.json`. Failure
is retained as `supervision/failure.json`; neither a new ACK nor a deadline
rewrite reopens it. Real SDK construction also requires this process's exact
consumed receipt; real and supervised-fixture workflow admission validates the
same bound receipt again. Ordinary direct offline matrix fixtures use no real
provider and remain separately labelled.

## Subsequent handoffs and proof

Service the existing public `barrier-readiness.json` and `barrier-first.json`
using substantive independent reviews, their exact evidence hashes and the
accepted runbook. Do not fabricate affirmative flags. Service first-pair and
closure `visibility/.../request.json` immediately in their original 600-second
windows with the separate keyless, network-disabled Inspect exporter. Keep all
provider calls, canonical writes and spending controls on the existing path.

The S13 acceptance evidence must come from a **fresh complete contained Windows
fake-key lifecycle**, with the real dedicated agent servicing attachment, both
reviews and both exports while the parent-chat acknowledgement is deliberately
delayed. A resumed main mock matrix, scripted positive unit payloads or a
running-agent snapshot alone cannot establish this operational acceptance.

The verifier prepares that separate mock-only study under
`VERIFICATION/operational-rehearsal/release/`, then writes its public
`operational-rehearsal/handoff.json` before starting Windows PowerShell. The
handoff supplies exact host paths for attachment, the two barriers, the two
visibility requests/outputs and the final service attestation. The mock runs
while the parent blocks on the launcher; the dedicated agent services those
paths independently. The main already-completed matrix is never resumed to
claim S13. Provider-configuration inspection continues using the main study and
never starts that configured container or prompts for real keys.

The two actual exporter outputs use the existing separate allowed namespace:
`runs/phase3b-seq2-v1/visibility-exports/REHEARSAL_STUDY_SHA/mock/CHECKPOINT/supervised`.
They are not written under the verification or native trees. Use the exact
`handoff.export_outputs` paths; the Inspect adapter's output boundary is unchanged.

For this supervised rehearsal, add `"supervisor_agent": "/root/ACTUAL_HANDLE"`
to each substantive `inspection-readiness.json` and `inspection-first.json`.
This identifies the trusted reviewer; it supplies no permission to invent its
affirmative checks. After both real Inspect exports finish, publish the exact
`service_path` named by the handoff with this schema:

```json
{
  "kind": "phase3b-s2-supervisor-service-v1",
  "study_sha256": "REHEARSAL_STUDY_HASH",
  "source_sha256": "EXACT_SOURCE_HASH",
  "runtime_sha256": "EXACT_RUNTIME_HASH",
  "policy_sha256": "EXACT_POLICY_HASH",
  "launcher_sha256": "EXACT_LAUNCHER_HASH",
  "supervisor_agent": "/root/ACTUAL_HANDLE",
  "handoff_sha256": "HANDOFF_SHA256_FIELD",
  "fixture": true,
  "provider_calls": 0,
  "parent_chat_ack_required": false,
  "references": {
    "attachment": {"path": "EXACT_HANDOFF_REFERENCE_PATH", "sha256": "RAW_FILE_SHA256"},
    "readiness": {"path": "EXACT_HANDOFF_REFERENCE_PATH", "sha256": "RAW_FILE_SHA256"},
    "first": {"path": "EXACT_HANDOFF_REFERENCE_PATH", "sha256": "RAW_FILE_SHA256"},
    "first-pair": {"path": "EXACT_HANDOFF_REFERENCE_PATH", "sha256": "RAW_FILE_SHA256"},
    "closure": {"path": "EXACT_HANDOFF_REFERENCE_PATH", "sha256": "RAW_FILE_SHA256"}
  }
}
```

Copy the five exact project-relative paths from `handoff.references` and hash
their actual bytes. They identify the consumed startup receipt, the two external
inspection records and the two exporter ACKs. The host allows up to60seconds
after the mock launcher settles for this final attestation. It then checks its
bindings, sealed controller/review records, both actual isolated exporter proofs
and cleanup, and fresh complete fixture coverage. It does not infer
orchestrator authenticity from the JSON: the actual agent dispatch and immediate
tool observation remain trusted, externally retained operator evidence.

The parent and supervisor must hand off or stop through existing bounded owner
controls before intentionally leaving a run that can still admit paid work.

P3B-S2 additionally requires both checkpoints c1/c2 and all twelve candidate assessments, four full fixed pools of twelve, normal native selectors on all four prompts, and complete information proofs on every normal author/selector path. First-prompt $55 total/$25 assessment limits remain binding after review; no review reopens them. A missing required candidate or checkpoint stops future admission. 
