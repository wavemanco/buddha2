"""Process boundary for unchanged NoveltyBench functions; no native import at startup."""

import contextlib
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

UPSTREAM_COMMIT = "64a23be6b18ec1dacc298830aab276061b6e143c"


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_portfolio(portfolio: dict) -> None:
    if not isinstance(portfolio, dict) or type(portfolio.get("schema_version")) is not int or portfolio["schema_version"] != 1:
        raise ValueError("unsupported portfolio schema")
    if portfolio.get("fixture") is not True:
        raise ValueError("only fixture portfolios are authorized")
    task = portfolio.get("task")
    if not isinstance(task, dict) or task.get("fixture") is not True:
        raise ValueError("fixture task evidence is required")
    if any(not _text(task.get(key)) for key in ("id", "prompt", "domain")):
        raise ValueError("task id, prompt and domain must be nonempty text")
    if not isinstance(portfolio.get("provenance"), dict):
        raise ValueError("portfolio provenance is required")
    responses = portfolio.get("responses")
    if not isinstance(responses, list) or len(responses) != 10:
        raise ValueError("the offline protocol requires ten responses")
    if any(not isinstance(row, dict) or not _text(row.get("id")) or not _text(row.get("text")) for row in responses):
        raise ValueError("response ids and text must be nonempty strings")
    if len({row["id"] for row in responses}) != len(responses):
        raise ValueError("response ids must be unique")
    canonical_hash(portfolio)  # Reject non-JSON and nonfinite provenance values too.


def validate_grading(portfolio: dict, grading: dict) -> None:
    if not isinstance(grading, dict) or type(grading.get("schema_version")) is not int or grading["schema_version"] != 1:
        raise ValueError("unsupported grading evidence schema")
    if grading.get("fixture") is not True or grading.get("version") != "1.1":
        raise ValueError("synthetic NoveltyBench v1.1 evidence is required")
    if grading.get("task_id") != portfolio["task"]["id"] or grading["task_id"] != "phase0-reading-room":
        raise ValueError("grading task identity is incompatible")
    if grading.get("portfolio_sha256") != canonical_hash(portfolio):
        raise ValueError("grading evidence does not match this portfolio")
    patience = grading.get("patience")
    if isinstance(patience, bool) or not isinstance(patience, (int, float)) or not math.isfinite(patience) or patience != 0.8:
        raise ValueError("the declared protocol requires finite patience 0.8")
    partition, scores = grading.get("partition"), grading.get("head_scores")
    if not isinstance(partition, list) or not isinstance(scores, list) or len(partition) != 10 or len(scores) != 10:
        raise ValueError("partition and head scores must match ten responses")
    if any(type(group) is not int or group < 0 or group >= 10 for group in partition):
        raise ValueError("partition labels must be nonnegative integer class ids")
    seen = set()
    for group, score in zip(partition, scores, strict=True):
        if group not in seen:
            if type(score) is not int or not 1 <= score <= 10:
                raise ValueError("every class head requires an integer score from 1 to 10")
            seen.add(group)
        elif score is not None:
            raise ValueError("non-head scores must be null")
    canonical_hash(grading)
    # Synthetic labels apply only to this frozen example, never to arbitrary
    # compatible text. The trusted template is mounted read-only by the launcher.
    template_path = Path(__file__).resolve().parents[2] / "fixtures" / "grading.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    declared_profile = {key: value for key, value in grading.items() if key != "portfolio_sha256"}
    if not isinstance(template, dict) or canonical_hash(declared_profile) != canonical_hash(template):
        raise ValueError("grading does not match the frozen fixture profile")
    if canonical_hash(portfolio["task"]) != template.get("task_sha256"):
        raise ValueError("task does not match the declared fixture evidence")
    if canonical_hash([response["text"] for response in portfolio["responses"]]) != template.get("response_texts_sha256"):
        raise ValueError("ordered response texts do not match the declared fixture evidence")


def _native_assessment(portfolio: dict, grading: dict, upstream: Path) -> dict:
    validate_portfolio(portfolio)
    validate_grading(portfolio, grading)
    upstream = upstream.resolve(strict=True)
    modules = {name: importlib.import_module(f"src.{name}") for name in ("partition", "score", "summarize")}
    imports = {}
    for name, module in modules.items():
        if not isinstance(module.__file__, str):
            raise ValueError("native module has no inspectable source file")
        source = Path(module.__file__).resolve(strict=True)
        if source != upstream / "src" / f"{name}.py":
            raise ValueError("native module resolved outside the declared upstream")
        imports[name] = {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    import pandas as pd

    generation = {
        "id": portfolio["task"]["id"],
        "prompt": portfolio["task"]["prompt"],
        "model": "fixture-no-model",
        "generations": [row["text"] for row in portfolio["responses"]],
    }
    # The parent assigned a new isolated scratch working directory.
    eval_dir = Path.cwd() / "native-evaluation"
    eval_dir.mkdir()
    (eval_dir / "generations.jsonl").write_text(json.dumps(generation, ensure_ascii=False) + "\n", encoding="utf-8")
    loaded = modules["partition"].load_instances(str(eval_dir))
    if loaded != [generation]:
        raise ValueError("native generation loading did not preserve the exported row")
    fields = modules["score"].utility_fields(grading["head_scores"], grading["partition"], grading["patience"])
    fields["utility"] = float(fields["utility"])
    summary = modules["summarize"].summarize(pd.DataFrame([{**generation, **fields}]), grading["version"])
    return {
        "evaluator": {"id": "noveltybench-native-fixture", "revision": 1, "version": grading["version"], "patience": grading["patience"], "upstream_commit": UPSTREAM_COMMIT},
        "portfolio_sha256": canonical_hash(portfolio),
        "grading_sha256": canonical_hash(grading),
        "task_id": portfolio["task"]["id"],
        "fixture": True,
        "metrics": {"distinct": fields["distinct"], "utility": fields["utility"]},
        "native": {"generation_row": loaded[0], "fields": fields, "summary": summary, "imports": imports},
    }


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ValueError("expected one pinned upstream path")
        raw = sys.stdin.buffer.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("assessment input exceeds the offline fixture limit")
        request = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON input")))
        if not isinstance(request, dict) or set(request) != {"portfolio", "grading"}:
            raise ValueError("assessment request schema is invalid")
        with contextlib.redirect_stdout(sys.stderr):
            result = _native_assessment(request["portfolio"], request["grading"], Path(sys.argv[1]))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, ImportError) as exc:
        print(f"{type(exc).__name__}: native fixture assessment refused or unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
