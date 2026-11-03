"""Independent offline assessments of already-saved fixture portfolios."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .nb_worker import canonical_hash, validate_grading, validate_portfolio


def evaluate_mechanical(portfolio: dict) -> dict:
    """Validate structure without generating, ranking, or judging response meaning."""
    validate_portfolio(portfolio)
    return {
        "evaluator": {"id": "mechanical-portfolio", "revision": 1},
        "portfolio_sha256": canonical_hash(portfolio),
        "task_id": portfolio["task"]["id"],
        "fixture": True,
        "checks": {
            "fixture": True,
            "schema": True,
            "count": True,
            "unique_ids": True,
            "nonempty_text": True,
        },
        "metrics": {"response_count": len(portfolio["responses"])},
    }


def evaluate_native(portfolio: dict, grading: dict, upstream: Path) -> dict:
    """Call unchanged native loading/arithmetic in a credential-free subprocess.

    Evidence binds the entire portfolio and must also match the trusted frozen
    grading profile, declared task and exact ordered synthetic response texts.
    This is fixture compatibility checking, not semantic judgment.
    OS-level network denial is the enclosing Phase 0 runtime's responsibility.
    """
    validate_portfolio(portfolio)
    validate_grading(portfolio, grading)
    upstream = Path(upstream).resolve(strict=True)
    for filename in ("partition.py", "score.py", "summarize.py"):
        source = (upstream / "src" / filename).resolve(strict=True)
        if not source.is_relative_to(upstream):
            raise ValueError("native source escapes the pinned upstream directory")
    request = json.dumps(
        {"portfolio": portfolio, "grading": grading},
        ensure_ascii=False,
        allow_nan=False,
    )
    if len(request.encode("utf-8")) > 2_000_000:
        raise ValueError("assessment input exceeds the offline fixture limit")

    with tempfile.TemporaryDirectory(prefix="buddha2-native-") as scratch:
        env = {
            "PATH": os.defpath,
            "PYTHONPATH": str(upstream),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "HOME": scratch,
            "TMPDIR": scratch,
            "TEMP": scratch,
            "TMP": scratch,
            "HF_HOME": scratch,
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "1",
        }
        for name in ("SYSTEMROOT", "WINDIR"):
            if name in os.environ:
                env[name] = os.environ[name]
        try:
            completed = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).with_name("nb_worker.py")), str(upstream)],
                input=request,
                text=True,
                encoding="utf-8",
                capture_output=True,
                cwd=scratch,
                env=env,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("native offline assessment timed out") from exc
        if completed.returncode:
            # Worker diagnostics contain type/category only, never response text.
            raise RuntimeError(f"native offline assessment failed: {completed.stderr[-1000:].strip()}")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("native assessment returned invalid JSON") from exc
    if not isinstance(result, dict) or result.get("portfolio_sha256") != canonical_hash(portfolio):
        raise RuntimeError("native assessment returned a mismatched portfolio identity")
    return result
