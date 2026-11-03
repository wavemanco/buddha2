"""Native Harness²/OpenCode fixture using installed SDK MockTransport, never real HTTP."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from harness2 import config
from harness2.core.proposer import Proposer, ProposerError
from harness2.core.spec import ChannelSpec

from buddha2.artifacts import ContractError, digest, write_once
from followups.phase3a_c1_completion_v4 import contract, editor
from followups.phase3a_c1_completion_v4.mocks import SDKMock
from followups.phase3a_v1.accounting import validate_request

from .guard import HistoryGuard

ROOT = Path(__file__).resolve().parents[2]
R3 = (
    ROOT
    / "runs/phase3a-compat-c1-v1/completion-v4/080c6ec2bbc1477002a83f7bb91bf0c3f86799ffa1fddd693ced2bdbbccc4f34/live/search/p3a-01/adaptive"
)


class SignedMock(SDKMock):
    def __init__(self, *, within_response: bool = False, invalid_ending: bool = False):
        super().__init__()
        self.within_response = within_response
        self.invalid_ending = invalid_ending

    def _editor_content(self, body: dict, slot: str) -> tuple[list[dict], str]:
        content, stop = super()._editor_content(body, slot)
        if stop == "end_turn":
            return content, stop
        # Real R3 returned empty visible text with nonempty opaque signatures.
        # Include visible/redacted and interleaved blocks so all paths are exercised.
        marker = slot.rsplit(".", 1)[-1]
        opaque = [
            {
                "type": "thinking",
                "thinking": "",
                "signature": "synthetic-empty-" + marker,
            },
            {
                "type": "thinking",
                "thinking": "SYNTHETIC ONLY",
                "signature": "synthetic-visible-" + marker,
            },
            {"type": "redacted_thinking", "data": "synthetic-redacted-" + marker},
        ]
        if self.invalid_ending:
            return [opaque[0], *content[:1], *opaque[1:], *content[1:]], stop
        calls = [i for i, block in enumerate(content) if block["type"] == "tool_use"]
        if self.within_response and len(calls) >= 2:
            first = calls[0] + 1
            return [opaque[0], *content[:first], *opaque[1:], *content[first:]], stop
        return [*opaque, *content], stop


class NativeFixture(Proposer):
    """Use native call/materialization/harvest and the existing trusted relay unchanged."""

    def __init__(
        self,
        prepared: dict,
        output: Path,
        label: str,
        *,
        within_response: bool = False,
        invalid_ending: bool = False,
    ):
        super().__init__(
            ChannelSpec(
                kind="opencode",
                model="anthropic/claude-opus-5",
                effort="high",
                steps=16,
                timeout=600,
            ),
            audit_dir=output / "native-audit",
            attempts=1,
        )
        self.prepared, self.label = prepared, label
        self.mock = SignedMock(within_response=within_response, invalid_ending=invalid_ending)
        self.mock.register_contract(label, prepared)
        self.record: dict = {"fixture": True, "requests": []}
        self.guard = HistoryGuard(self.dispatch, "p3a-01.adaptive.editor." + label)
        self._local = threading.local()
        config.BUN, config.OPENCODE_DIR = (
            Path("/usr/local/bin/bun"),
            Path("/opt/phase3a-opencode"),
        )

    def env(self):
        # Reuse the accepted clean environment and supported native agent configuration.
        env = editor.frozen.AccountedProposer.env(self)
        cfg = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        cfg["agent"]["build"].update(steps=16, prompt=self.prepared["authoring_system_text"])
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(cfg, ensure_ascii=False)
        return env

    def dispatch(self, slot: str, role: str, request: dict) -> dict:
        import anthropic
        import httpx2

        tools = {tool["name"]: tool for tool in request.get("tools", [])}
        validate_request(role, request, editor_tools=tools)
        self.mock.select(role, slot)
        http = anthropic.DefaultHttpxClient(
            trust_env=False,
            follow_redirects=False,
            transport=httpx2.MockTransport(lambda req: self.mock._handle(req, http_module=httpx2)),
        )
        with anthropic.Anthropic(
            api_key="fixture-not-a-secret", max_retries=0, http_client=http
        ) as client:
            raw = client.messages.create(**request).model_dump(mode="json", exclude_none=True)
        return {
            "status": "response",
            "fixture": True,
            "response": {
                "provider_response": raw,
                "text": "".join(b["text"] for b in raw["content"] if b["type"] == "text"),
            },
        }

    def _opencode(self, cwd, mission, system, wall):
        self._local.home = str(cwd / ".phase3a-home")
        Path(self._local.home).mkdir()

        def halt(*args, **kwargs):
            self.record["halted"] = True

        with editor.relay(cwd, self.guard, self.guard.prefix, self.record, halt) as url:
            self._local.url = url
            return super()._opencode(cwd, mission, system, wall)


def native_case(
    output: Path,
    label: str,
    *,
    expect_loss: bool = False,
    within_response: bool = False,
    invalid_ending: bool = False,
    expected_mock_calls: int = 1,
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    context = output / "context"
    native_context = next((R3 / "native").glob("*/*/context")) / label.split(".")[0]
    shutil.copytree(
        native_context,
        context,
        ignore=lambda directory, names: [n for n in names if n.casefold() in editor.PRIVATE],
    )
    for relative in (
        "task.md",
        "rollouts/base1.md",
        "deliverables/base1/answers.json.txt",
        "deliverables/base1/INDEX.md",
    ):
        path = context / relative
        path.write_text(
            "SYNTHETIC fixture evidence: one valid answer; no quality or learning claim.\n",
            encoding="utf-8",
        )
    mission = (R3 / "editor-audit/c1-contracts" / label / "native-mission.md").read_text(
        encoding="utf-8"
    )
    prepared = contract.prepare_contract(mission, context, label)
    derived = dict(prepared["evidence_files"])
    derived[contract.INDEX_NAME] = prepared["index_text"]
    derived[contract.MANIFEST_NAME] = (
        json.dumps(prepared["manifest"], ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    for name, text in derived.items():
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    proposer = NativeFixture(
        prepared, output, label, within_response=within_response, invalid_ending=invalid_ending
    )
    failure = None
    try:
        reply = proposer.call(
            prepared["effective_mission"],
            context,
            label,
            max_attempts=1,
            harvest="context/harness",
        )
    except ProposerError:
        reply = None
        failure = "native editor stopped after rejected history"
    if reply is None or proposer.record.get("error"):
        write_once(
            output / "failure.json",
            {
                "fixture": True,
                "native_relay": proposer.record,
                "mock_records": proposer.mock.records,
                "mock_errors": proposer.mock.c1_errors,
                "guard_audits": proposer.guard.audits,
            },
        )
    if expect_loss:
        if (
            reply is not None
            or len(proposer.mock.records) != expected_mock_calls
            or not proposer.record.get("halted")
        ):
            raise ContractError("baseline did not reproduce pre-admission signed-history loss")
    else:
        if reply is None or not reply.ok or reply.workspace is None or proposer.record.get("error"):
            raise ContractError("fixed native fixture failed normal completion")
        stage = proposer.mock.c1_sessions[label]
        if not all(
            stage[k]
            for k in (
                "normal_final",
                "notes_reread_model_visible",
                "decision_after_complete_evidence",
            )
        ):
            raise ContractError("native fixture lacks completed delivery/verification")
        before = json.loads((context / "harness/systemprompt.md").read_text(encoding="utf-8"))
        after = json.loads((reply.workspace / "systemprompt.md").read_text(encoding="utf-8"))
        if (before != after) != label.startswith("inv"):
            raise ContractError("native changed/KEEP_BASE fixture differs")
    result = {
        "fixture": True,
        "label": label,
        "baseline_loss_expected": expect_loss,
        "within_response_interleaving": within_response,
        "invalid_ending_thinking": invalid_ending,
        "component_only_no_scientific_claim": True,
        "passed": True,
        "native_reply_ok": bool(reply),
        "failure": failure,
        "mock_http_calls": len(proposer.mock.records),
        "provider_calls": 0,
        "api_spend": 0,
        "history_guard_audits": proposer.guard.audits,
        "native_proof": proposer.mock.c1_sessions.get(label),
        "response_content_sha256": [
            digest(r["response"]["content"]) for r in proposer.mock.records
        ],
        "native_scope": "actual unchanged Harness2 Proposer.call/OpenCode; no scheduler matrix or scientific effect",
    }
    write_once(output / "result.json", result)
    write_once(
        output / "synthetic-wire.json",
        {
            "fixture": True,
            "records": proposer.mock.records,
            "native_relay": proposer.record,
        },
    )
    return result
