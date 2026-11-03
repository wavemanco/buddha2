"""A declared authoring-policy adapter around the actual native proposer."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from pathlib import Path, PurePosixPath
from typing import Callable

from harness2.core.proposer import ProposerError

from buddha2.artifacts import digest, file_hash, write_bytes_once, write_once
from buddha2.phase2_dispatch import _publish
from followups.phase3a_compat_c1_v1.support import OPENCODE_FILES, PRIVATE, opencode_profile_sources
from followups.phase3a_v1 import strategy

from . import contract, editor


class CompatibleProposer(editor.AccountedProposer):
    """Preserve native execution/harvest and replace only its authoring contract."""

    def __init__(self, *, pilot: str, study_sha256: str, dispatch: Callable,
                 audit_dir: Path, fixture: bool, halt: Callable,
                 register_contract: Callable | None = None, source_sha256: str | None = None,
                 register_deadline: Callable | None = None):
        try:
            audit_dir = Path(audit_dir)
            roots = (strategy.ROOT / "runs/phase3a-compat-c1-v1/completion-v4", Path("/results/phase3a-compat-c1-v1/completion-v4"))
            valid = (audit_dir.is_absolute() and ".." not in audit_dir.parts
                     and not any(part.lower() in PRIVATE for part in audit_dir.parts)
                     and any(audit_dir.is_relative_to(root) and audit_dir != root for root in roots))
            if valid:
                valid = not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                                for p in (audit_dir, *audit_dir.parents))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            halt("c1_audit_boundary_violation")
            raise ProposerError("C1 audit must be below its own checkpoint output root")
        super().__init__(pilot=pilot, study_sha256=study_sha256, dispatch=dispatch,
                         audit_dir=audit_dir, fixture=fixture, halt=halt)
        self._register_contract = register_contract
        self._register_deadline = register_deadline
        self._conversation_deadlines: dict[str, dict] = {}
        self._c1_sessions: dict[str, dict] = {}
        self._c1_contracts: dict[str, dict] = {}
        self._c1_binding = {
            "adapter_sha256": file_hash(Path(__file__)),
            "contract_sha256": file_hash(contract.IMPLEMENTATION_PATH),
            "definition_sha256": file_hash(strategy.ROOT / "PHASE3A_C1_COMPLETION_R3_DEFINITION.md"),
            "parent_boundary_sha256": file_hash(Path(editor.frozen.__file__)),
            "editor_sha256": file_hash(Path(editor.__file__)),
        }
        self._c1_source = source_sha256 or digest(self._c1_binding)

    def _opencode(self, cwd, mission, system, wall):
        # Waiting for the other native editor never consumes this conversation's clock.
        with editor._SERIAL:
            label = self._local.label
            if not callable(self._register_deadline):
                self.halt("editor_deadline_registration_missing")
                raise ProposerError("editor lacks its owned absolute deadline registration")
            if label not in self._conversation_deadlines:
                started = time.monotonic()
                identity = f"{self.pilot}:adaptive:{label}"
                record = {"kind": "phase3a-r3-conversation-admission-clock-v1", "study_sha256": self.study_sha256,
                    "source_sha256": self._c1_source, "pilot": self.pilot, "label": label,
                    "conversation_id": identity, "started_monotonic": started, "deadline_monotonic": started + 600,
                    "seconds": 600, "native_subprocess_cap_seconds": 600, "OpenCode_fetch_cap_seconds": 590,
                    "anchor": "inside editor._SERIAL before native _opencode boundary setup and CLI invocation",
                    "scope_limit": "Native context preparation/copy precede this hook; relay setup/subprocess/drain are distinct from the subprocess cap.",
                    "renewable": False, "fixture": self.fixture, "editor_profile_sha256": digest(editor.profile())}
                self._register_deadline(identity, record["deadline_monotonic"])
                record["sha256"] = digest(record)
                _publish(Path(self.audit_dir) / "conversation-deadlines" / (label + ".json"), record)
                self._conversation_deadlines[label] = record
            return super()._opencode(cwd, mission, system, wall)

    def call(self, mission, context_dir=None, label="", **kwargs):
        try:
            context = Path(context_dir)
            root = Path(self.audit_dir).parent.resolve(strict=True)
            valid = (isinstance(label, str) and re.fullmatch(r"(?:inv1|dom1|agg1)\.a[12]", label)
                     and context.is_absolute() and context.is_relative_to(root)
                     and ".." not in context.parts
                     and not any(part.lower() in PRIVATE for part in context.parts)
                     and not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                                 for p in (context, *context.parents))
                     and context.resolve(strict=True).is_relative_to(root))
        except (OSError, TypeError, ValueError):
            valid = False
        if not valid:
            self.halt("c1_context_boundary_violation")
            raise ProposerError("C1 stage/context is outside its own native workspace")
        if label in self._c1_sessions:
            raise ProposerError("C1 logical authoring session has already been attempted")
        try:
            prepared = contract.prepare_contract(mission, context, label)
        except (contract.ContractError, OSError, TypeError, ValueError) as exc:
            self.halt("c1_contract_input_violation")
            raise ProposerError("C1 contract rejected its native input") from exc
        manifest = prepared["manifest"]
        self._c1_contracts[label] = prepared
        audit = Path(self.audit_dir) / "c1-contracts" / label
        record = {
            "kind": "phase3a-c1-authoring-call-v1", "fixture": self.fixture,
            "study_sha256": self.study_sha256, "source_sha256": self._c1_source,
            "binding": self._c1_binding, "label": label, "manifest_sha256": manifest["sha256"],
            "raw_mission_sha256": manifest["raw_mission_sha256"],
            "effective_mission_sha256": manifest["effective_mission_sha256"],
            "context_inventory_sha256": manifest["context_inventory_sha256"],
            "authoring_system_sha256": hashlib.sha256(prepared["authoring_system_text"].encode()).hexdigest(),
            "default_provider_prompt_sha256": OPENCODE_FILES["session/prompt/anthropic.txt"],
            "status": "started", "auxiliary_removed": False,
        }
        self._c1_sessions[label] = record
        write_bytes_once(audit / "native-mission.md", mission.encode("utf-8"))
        write_bytes_once(audit / "effective-mission.md", prepared["effective_mission"].encode("utf-8"))
        write_bytes_once(audit / "configured-agent-prompt.md", prepared["authoring_system_text"].encode("utf-8"))
        write_once(audit / "manifest.json", manifest)
        write_once(audit / "binding.json", record)
        derived = dict(prepared["evidence_files"])
        derived[contract.INDEX_NAME] = prepared["index_text"]
        # Match the ordinary immutable artifact serializer used by the fixture.
        derived[contract.MANIFEST_NAME] = json.dumps(manifest, ensure_ascii=False,
            sort_keys=True, indent=2, allow_nan=False) + "\n"
        installed: list[tuple[Path, str]] = []
        try:
            for name, text in derived.items():
                relative = PurePosixPath(name)
                if (relative.is_absolute() or ".." in relative.parts or ":" in name
                        or not (name in (contract.MANIFEST_NAME, contract.INDEX_NAME)
                                or relative.parts[0] == contract.EVIDENCE_DIR)):
                    raise contract.ContractError("undeclared derived context path")
                path = context.joinpath(*relative.parts)
                data = text.encode("utf-8")
                write_bytes_once(path, data)
                installed.append((path, hashlib.sha256(data).hexdigest()))
                write_bytes_once(audit / "context-view" / name, data)
            if self._register_contract is not None:
                self._register_contract(label, copy.deepcopy(prepared))
            reply = super().call(prepared["effective_mission"], context, label, **kwargs)
            record.update(status="returned", native_reply_ok=reply.ok)
            return reply
        except Exception:
            record["status"] = "failed"
            raise
        finally:
            for path, expected in reversed(installed):
                if path.is_symlink() or not path.is_file() or file_hash(path) != expected:
                    self.halt("c1_derived_context_tampered")
                    raise ProposerError("C1 derived context changed during authoring")
                path.unlink()
            directory = context / contract.EVIDENCE_DIR
            if directory.exists():
                directory.rmdir()  # Only the known empty operational directory; never recursive.
            record["auxiliary_removed"] = True
            record["sha256"] = digest(record)
            write_once(audit / "result.json", record)

    def env(self):
        env = super().env()
        label = self._local.label
        prepared = self._c1_contracts[label]
        sources = opencode_profile_sources()
        config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        config["agent"]["build"]["prompt"] = prepared["authoring_system_text"]
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False, allow_nan=False)
        audit = Path(self.audit_dir) / "c1-contracts" / label
        default = Path("/opt/phase3a-opencode/packages/opencode/src/session/prompt/anthropic.txt")
        write_bytes_once(audit / "original-provider-prompt.md", default.read_bytes())
        write_once(audit / "system-profile.json", {"kind": "phase3a-c1-system-profile-v1",
            "profile": contract.SYSTEM_ID, "policy_id": contract.POLICY_ID, "sources": sources,
            "configured_agent_prompt_sha256": hashlib.sha256(prepared["authoring_system_text"].encode()).hexdigest(),
            "default_provider_prompt_sha256": sources["session/prompt/anthropic.txt"],
            "seam": "supported agent.build.prompt; no upstream or provider-request mutation",
            "steps": config["agent"]["build"]["steps"], "editor_profile_sha256": digest(editor.profile()), "permissions": config["agent"]["build"]["permission"]})
        return env

    def c1_evidence(self) -> dict:
        return copy.deepcopy({"kind": "phase3a-c1-authoring-evidence-v1", "fixture": self.fixture,
            "study_sha256": self.study_sha256, "source_sha256": self._c1_source,
            "binding": self._c1_binding, "sessions": self._c1_sessions,
            "live_readiness_established": False})
