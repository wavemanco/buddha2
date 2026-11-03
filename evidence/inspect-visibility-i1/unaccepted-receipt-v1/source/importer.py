"""Import two frozen synthetic H1 cases into Inspect logs without model execution."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import stat
import sys
from pathlib import Path, PurePosixPath

from .paths import checked_path, lexical

CASES = {
    "fixed-changed": {
        "result.json": "e8fe7baeea34943fccd1e45c3a57b13f527f128c0cda705ef4250453f6401b6f",
        "synthetic-wire.json": "b296dd8a889c8560ea215d0b36192e39adc3dd3028455625cdf1e7659125e91f",
    },
    "baseline-loss": {
        "result.json": "5f8386074c8841179a9c56282cf7ff1e1eb15920b369885e55b6ab9ec6ab47d7",
        "synthetic-wire.json": "de748c8de154f463bbd3e866e619617daef033f4edb85c85b78896ccb75ef342",
    },
}
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
STAMP = "2026-10-31T00:00:00Z"  # Display-only import identity; never a native execution timestamp.


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def safe_read(root: Path, relative: str) -> bytes:
    lexical(str(root))
    lexical(relative)
    name = PurePosixPath(relative)
    # Lexical checks precede even lstat: no private path is followed or classified.
    if (not relative or str(name) != relative or "\\" in relative or name.is_absolute() or ":" in relative
            or any(p in {".", ".."} or p.lower() in PRIVATE for p in name.parts)):
        raise ValueError("unsupported, escaped or private path")
    checked_path(root, root)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("linked or non-directory input root")
    current = root
    for part in name.parts:
        current /= part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("linked input path")
        if current != root / name and not stat.S_ISDIR(mode):
            raise ValueError("input ancestor is not a directory")
    if not stat.S_ISREG(mode):
        raise ValueError("input is not a regular file")
    return current.read_bytes()


def decode(raw: bytes) -> object:
    def no_duplicate(items: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError(f"nonfinite JSON value: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate, parse_constant=reject)


def validate_case(case: str, result: object, wire: object) -> None:
    if case not in CASES or not isinstance(result, dict) or not isinstance(wire, dict):
        raise ValueError("unknown case or malformed records")
    expected_ok = case == "fixed-changed"
    required = {"fixture": True, "passed": True, "native_reply_ok": expected_ok,
                "provider_calls": 0, "api_spend": 0, "label": "inv1.a1",
                "baseline_loss_expected": not expected_ok,
                "component_only_no_scientific_claim": True}
    for key, expected in required.items():
        if key not in result or type(result[key]) is not type(expected) or result[key] != expected:
            raise ValueError(f"unsupported native status {case}:{key}")
    if result.get("failure") != (None if expected_ok else "native editor stopped after rejected history"):
        raise ValueError("unsupported native failure")
    records = wire.get("records")
    if wire.get("fixture") is not True or not isinstance(records, list) or len(records) != (11 if expected_ok else 1):
        raise ValueError("unsupported synthetic wire shape")
    if result.get("mock_http_calls") != len(records):
        raise ValueError("native call count mismatch")
    for number, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("model") != "claude-opus-5" or record.get("role") != "editor":
            raise ValueError("unknown originating role/model")
        if record.get("slot_id") != f"p3a-01.adaptive.editor.inv1.a1.t{number:02d}":
            raise ValueError("unsupported originating slot")
        request, response = record.get("request"), record.get("response")
        if not isinstance(request, dict) or not isinstance(response, dict):
            raise ValueError("malformed request/response")
        if (request.get("model") != "claude-opus-5" or request.get("max_tokens") != 16000
                or request.get("thinking") != {"type": "adaptive"}
                or request.get("output_config") != {"effort": "high"}
                or request.get("service_tier") != "standard_only" or request.get("inference_geo") != "global"):
            raise ValueError("unsupported originating generation configuration")
        if not isinstance(request.get("messages"), list) or not isinstance(response.get("content"), list):
            raise ValueError("malformed messages/content")


def read_cases(root: Path, names: list[str]) -> list[dict]:
    if len(names) != len(set(names)) or set(names) != set(CASES):
        raise ValueError("exactly the two declared cases are required")
    cases = []
    for case in names:
        raw = {}
        for filename, digest in CASES[case].items():
            data = safe_read(root, f"{case}/{filename}")
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"frozen input hash differs: {case}/{filename}")
            raw[filename] = data
        result, wire = decode(raw["result.json"]), decode(raw["synthetic-wire.json"])
        validate_case(case, result, wire)
        cases.append({"case": case, "raw": raw, "result": result, "wire": wire})
    return cases


def block_execution() -> dict:
    counts: dict = {"external_socket_attempts": [], "model_constructor_attempts": []}
    # These optional SDKs are deliberately absent from the core-only isolated image.
    if any(importlib.util.find_spec(name) is not None for name in ("anthropic", "openai")):
        raise RuntimeError("provider SDK unexpectedly installed in passive image")

    def audit(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request"}:
            counts["external_socket_attempts"].append(event)
            raise RuntimeError("network forbidden in passive trial")

    sys.addaudithook(audit)
    # Inspect is imported only after process-level network/SDK blocks are active.
    from inspect_ai.model import Model, ModelAPI

    def forbidden(*args: object, **kwargs: object) -> None:
        counts["model_constructor_attempts"].append("Model/ModelAPI")
        raise RuntimeError("model construction forbidden in passive trial")

    Model.__init__ = forbidden
    ModelAPI.__init__ = forbidden
    return counts


def project(case: dict) -> dict:
    result, wire = case["result"], case["wire"]
    final = wire["records"][-1]["response"]
    final_text = None
    if result["native_reply_ok"]:
        if final.get("stop_reason") != "end_turn":
            raise ValueError("successful case lacks normal native final")
        final_text = "".join(b["text"] for b in final["content"] if b.get("type") == "text")
        if not final_text:
            raise ValueError("successful native final text is missing")
    return {
        "case_id": case["case"], "origin_label": result["label"],
        "qualified_id": f"{case['case']}/{result['label']}",
        "synthetic_fixture": True, "fixture_expectation_passed": result["passed"],
        "native_reply_ok": result["native_reply_ok"], "native_error": result["failure"],
        "origin_model": "claude-opus-5", "origin_role": "editor",
        "native_result": result, "native_wire": wire,
        "native_final_text": final_text,
        "display_mapping": "InfoEvents contain exact imported native wire, not reconstructed ModelEvents; successful end_turn displayed as stop; failed final absent",
        "assessment_presence": "absent", "scientific_eligibility": False,
        "accounting": {"real_provider_calls": result["provider_calls"], "real_api_spend": result["api_spend"],
                       "synthetic_mock_calls": result["mock_http_calls"],
                       "recorded_synthetic_usage": [r["response"].get("usage", {"field_absent": True}) for r in wire["records"]],
                       "inspect_served_calls": 0, "inspect_token_usage": None},  # nosec B105 - usage missingness, not a credential
        "source_artifacts": [{"path": f"runs/phase3a-history-compat-h1/verification-v3/{case['case']}/{n}",
                              "sha256": CASES[case["case"]][n], "sidecar": f"sources/{case['case']}/{n}"}
                             for n in CASES[case["case"]]],
    }


def import_logs(cases: list[dict], out: Path) -> dict:
    from inspect_ai.event import InfoEvent
    from inspect_ai.log import (
        EvalConfig,
        EvalDataset,
        EvalError,
        EvalLog,
        EvalSample,
        EvalSpec,
        bundle_log_dir,
        read_eval_log,
        write_eval_log,
    )
    from inspect_ai.model import ModelOutput

    expected = [project(case) for case in cases]
    if out.exists():
        raise ValueError("output must be fresh")
    out.mkdir()
    logs = out / "logs"
    logs.mkdir()
    recovered = []
    def semantic_view(log: EvalLog, source_attachments: dict) -> dict:
        sample = log.samples[0]
        return {"log_status": log.status, "log_error": log.error.model_dump() if log.error else None,
                "eval_spec": log.eval.model_dump(), "results": log.results,
                "sample": {"id": sample.id, "epoch": sample.epoch, "input": sample.input,
                           "target": sample.target, "description": sample.description,
                           "output": sample.output.model_dump(), "scores": sample.scores,
                           "error": sample.error.model_dump() if sample.error else None,
                           "metadata": sample.metadata, "source_attachments": source_attachments,
                           "events": [{"event": e.event, "data": e.data} for e in sample.events],
                           "model_usage": sample.model_usage, "role_usage": sample.role_usage}}

    for case, payload in zip(cases, expected, strict=True):
        name = case["case"]
        source_dir = out / "sources" / name
        source_dir.mkdir(parents=True)
        for filename, data in case["raw"].items():
            (source_dir / filename).write_bytes(data)
        attachments = {f"{name}/{filename}": data.decode("utf-8") for filename, data in case["raw"].items()}
        relay = case["wire"]["native_relay"]
        displayed_failure = (
            "Imported native failure summary (not a recorded Python stack trace):\n"
            f"native result: {payload['native_error']}\n"
            f"native relay error: {relay.get('error')}\n"
            f"native relay detail: {relay.get('offline_error_detail')}"
        )
        error = None if payload["native_reply_ok"] else EvalError(
            message=payload["native_error"], traceback=displayed_failure,
            traceback_ansi=displayed_failure)
        # InfoEvents are explicitly imported native wire records, not invented ModelEvents.
        events = [InfoEvent(data={"imported_synthetic_native_call": record,
                                 "qualified_slot_id": f"{name}/{record['slot_id']}"})
                  for record in case["wire"]["records"]]
        output = ModelOutput() if payload["native_final_text"] is None else ModelOutput.from_content(
            model="recorded-synthetic/claude-opus-5", content=payload["native_final_text"])
        if output.choices:
            output.choices[0].message.id = f"i1-{name}-display-final"
        sample = EvalSample(id=payload["qualified_id"], epoch=1,
                            input="SYNTHETIC retained Harness² editor fixture. No new model execution.",
                            target=[], description=f"SYNTHETIC {name}: {'normal native return' if error is None else 'native history failure'}",
                            output=output, scores=None, error=error, metadata=payload,
                            attachments=attachments, events=events)
        log = EvalLog(status="success" if error is None else "error", error=error,
                      eval=EvalSpec(created=STAMP, task="synthetic_h1_passive_import", task_version="I1-1.0",
                                    task_id=f"i1-{name}", eval_id=f"i1-{name}", run_id="i1-retained-import",
                                    model="none", dataset=EvalDataset(name="H1 closed synthetic fixtures", samples=1,
                                    sample_ids=[payload["qualified_id"]]), config=EvalConfig(),
                                    tags=["SYNTHETIC", "IMPORTED", "NO_MODEL_CALLS"],
                                    metadata={"origin": "external unchanged Harness2 Proposer.call/OpenCode",
                                              "import_only": True, "native_timestamps": "not supplied",
                                              "display_timestamp_is_not_native": True}),
                      samples=[sample], results=None)
        path = logs / f"{name}.eval"
        expected_view = semantic_view(log, attachments)
        write_eval_log(log, path)
        raw_saved = read_eval_log(path, resolve_attachments=False)
        saved = read_eval_log(path, resolve_attachments=True)
        restored = saved.samples[0]
        if restored.metadata != payload or restored.scores is not None or saved.results is not None:
            raise AssertionError("Inspect changed imported semantics or invented scores")
        if bool(restored.error) != (not payload["native_reply_ok"]) or saved.status != log.status:
            raise AssertionError("Inspect changed failure classification")
        for filename, data in case["raw"].items():
            if raw_saved.samples[0].attachments[f"{name}/{filename}"].encode("utf-8") != data:
                raise AssertionError("Inspect changed source attachment bytes")
            if (source_dir / filename).read_bytes() != data:
                raise AssertionError("source sidecar differs")
        saved_view = semantic_view(saved, {key: raw_saved.samples[0].attachments[key] for key in attachments})
        if saved_view != expected_view:
            raise AssertionError("Inspect changed viewer-facing semantic fields")
        recovered.append(saved_view)
    bundle_log_dir(log_dir=str(logs), output_dir=str(out / "viewer"), overwrite=False)
    semantic = canonical(recovered)
    (out / "semantic.json").write_bytes(semantic + b"\n")
    proof = {"all_fields_equal": True,
             "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
             "source_bytes_preserved": True, "case_count": len(cases),
             "native_successes": 1, "native_failures": 1, "scientific_scores": 0,
             "real_provider_calls": 0, "api_spend": 0,
             "timing_policy": "fixed display-only timestamp; no imported native timing invented",
             "fidelity": ["full native result", "full native request/response wire", "opaque history",
                          "original UTF8 bytes", "omissions/null/zero", "native final text or absence",
                          "exact error", "case-qualified identifiers", "synthetic usage versus real zero"]}
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    args = parser.parse_args()
    lexical(args.inputs)
    lexical(args.output)
    inputs, output = Path(args.inputs), Path(args.output)
    if inputs != Path("/inputs"):
        raise ValueError("inputs must be the explicit /inputs whitelist mounts")
    if not output.is_absolute() or output.parent != Path("/out"):
        raise ValueError("output must be a direct fresh child of mounted /out")
    counts = block_execution()
    cases = read_cases(inputs, args.cases)
    proof = import_logs(cases, output)
    proof["execution_blocks"] = counts
    if any(counts.values()):
        raise AssertionError("execution containment was invoked")
    (output / "fidelity.json").write_bytes(canonical(proof) + b"\n")
    print(json.dumps({"output": str(output), "semantic_sha256": proof["semantic_sha256"], "provider_calls": 0}))


if __name__ == "__main__":
    main()
