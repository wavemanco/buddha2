"""Run the configured local checks in the network-disabled Phase 0 image."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    reports = Path(os.environ.get("BUDDHA2_OUTPUT_ROOT", "/results")) / "checks"
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="buddha2-checks-") as temporary:
        commands = [
            [sys.executable, "-m", "ruff", "check", "--no-cache", "src", "tests", "tools", "strategies"],
            [sys.executable, "-m", "mypy", "--cache-dir", str(Path(temporary) / "mypy"), "src/buddha2"],
            [
                sys.executable, "-m", "bandit", "-r", "src", "tools", "strategies", "-ll", "-ii",
                "-f", "json", "-o", str(reports / "bandit.json"),
            ],
            [sys.executable, "-m", "pip", "check"],
            [
                sys.executable, "-m", "unittest", "discover", "-s",
                str(Path(__file__).resolve().parents[1] / ".upstream/harness2/tests"), "-v",
            ],
        ]
        failed = False
        for command in commands:
            print("CHECK:", " ".join(command), flush=True)
            result = subprocess.run(command, check=False, timeout=180)
            failed = failed or result.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
