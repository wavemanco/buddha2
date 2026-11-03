"""Fresh contained actual-SDK/native HI fixtures; never a real-provider launcher."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from buddha2.artifacts import digest

from . import accounting, editor, workflow
from .mocks import StudyMock
from .support import path, publish, require, seal


class TerminalMock(StudyMock):
    """Delay later valid INV/DOM/AGG finals until the real terminal24 request."""
    def _unsigned_editor_content(self, body: dict, slot: str):
        match = re.search(r"\.editor\.((?:(?:inv[12]|dom[12]|c[12])\.a[12]|select\.seq2))\.t(\d+)$", slot)
        require(match is not None, "missing fixture editor identity")
        if match is None:
            raise ValueError("missing fixture match")
        label, turn = match.group(1), int(match.group(2))
        if self.active_pilot == "p3b-01" or label == "select.seq2":
            return super()._unsigned_editor_content(body, slot)
        natural_final = 5 if label == "select.seq2" else 10 if label.split(".")[0] in {"dom1", "dom2", "inv2", "c2"} else 11
        if turn == 24:
            require(editor._terminal_shape(body["messages"][-1]), "real native terminal control missing")
            return [{"type": "text", "text": self._c1[label]["notes"]}], "end_turn"
        if turn <= natural_final:
            content, stop = super()._unsigned_editor_content(body, slot)
            if stop != "end_turn":
                return content, stop
        state = self._c1[label]
        return self._tools([(f"hi_wait_terminal_{turn}", "read", {"filePath": str(state["cwd"] / "MISSION.md")})]), "tool_use"


def complete_fixture(output: Path, mode: str) -> dict:
    output = path(output)
    require(not output.exists() and mode in {"normal", "terminal-readiness", "terminal-later"},
            "fixture requires a fresh declared output")
    require({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "actual offline containment required")
    study = workflow.prepare(output / "release")
    study_path, grant_path = output / "release/study.json", output / "release/mock-grant.json"
    publish(grant_path, workflow.make_grant(study_path, True))
    mock_type = TerminalMock if mode == "terminal-later" else StudyMock
    with mock_type(fixture_mode="terminal" if mode == "terminal-readiness" else "normal") as mock:
        summary = workflow.run(study_path, grant_path, stage="all", transport=mock.transport)
        run, journal = workflow.paths(study, True)
        state = accounting.replay(journal)
        proofs = mock.proofs()
        if mode == "terminal-readiness":
            failure = workflow.read(run / "readiness-failure.json")
            editors = [slot for slot in state["results"] if ".editor." in slot]
            passed = (failure["reason"] == "forced_terminal_control_before_dispatch" and len(editors) == 23
                and not any(slot.endswith(".t24") for slot in state["intents"]))
            details = {"editor_sdk_calls": len(editors), "terminal24_preintent_rejection": passed}
        else:
            data = workflow.snapshot(study_path, grant_path, True)
            records = workflow.saved(study_path, study, state, True)
            later = [row for (pilot, arm), branch in records["branches"].items()
                     if pilot != "p3b-01" and arm == "adaptive"
                     for row in (branch.get("result") or {}).get("stage_dispositions", [])]
            terminal = [row for row in later if row["terminal_note_used"]]
            classifications = (any(row["effective_changed"] and row["authentic_eligible"] for row in terminal)
                and any(row["cap_limited_unchanged"] and not row["authentic_eligible"] for row in terminal))
            passed = summary["primary_scored"] == 8 and (mode == "normal" or classifications)
            details = {"primary_scored": summary["primary_scored"], "later_terminal_dispositions": terminal,
                       "terminal_changed_and_unchanged_classified": classifications,
                       "report_sha256": digest(data)}
        result = seal({"kind": "p3b-hi-native-fixture-v1", "mode": mode, "passed": passed,
            "study_sha256": study["study_sha256"], "source_sha256": study["source_sha256"],
            "runtime_sha256": study["runtime_sha256"], "policy_sha256": study["policy_sha256"],
            "launcher_sha256": study["launcher_sha256"], "fixture": True, "provider_calls": 0,
            "mock_http_calls": mock.http_calls, "reserved_micro_usd": state["reserved_micro_usd"],
            "summary": summary, **details})
        publish(output / "native-fixture.json", result)
        publish(output / "mock-proofs.json", proofs)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("normal", "terminal-readiness", "terminal-later"), required=True)
    args = parser.parse_args()
    result = complete_fixture(Path(args.output), args.mode)
    print({"mode": args.mode, "passed": result["passed"], "mock_http_calls": result["mock_http_calls"], "provider_calls": 0})
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
