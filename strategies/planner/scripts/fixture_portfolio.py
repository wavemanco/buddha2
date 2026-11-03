"""Known offline helper: consume staged instructions and emit synthetic responses."""

import hashlib
import json
import sys
from pathlib import Path

TASK = {
    "id": "phase0-reading-room",
    "prompt": "Give ten distinct ways to make a fictional public reading room welcoming without screens. Each answer should be a short actionable idea.",
    "domain": "creative-ideation",
    "fixture": True,
}

IDEAS = [
    "Place comfortable chairs in small conversation circles.",
    "Keep a low shelf of large-print books beside the entrance.",
    "Invite visitors to leave handwritten book recommendations.",
    "Offer a basket of washable lap blankets near the quiet seats.",
    "Set aside a low table where families can read picture books together.",
    "Arrange a volunteer welcome desk with a simple paper map.",
    "Reserve one window seat for readers who prefer a quiet corner.",
    "Host a short read-aloud gathering at a posted weekly time.",
    "Display a community noticeboard for local reading groups.",
    "Provide movable reading lamps with clearly labeled switches.",
]


def main():
    if len(sys.argv) != 3:
        raise ValueError("The fixture helper requires its staged harness and declared task")
    harness = Path(sys.argv[1]).resolve(strict=True)
    task = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    if task != TASK:
        raise ValueError("Only the exact declared fixture task is supported")
    paths = (
        "systemprompt.md",
        "guardrails.md",
        "LongTermMEMORY.md",
        "skills/planner/SKILL.md",
    )
    materialized = {name: (harness / name).read_bytes() for name in paths}
    text = {name: body.decode("utf-8") for name, body in materialized.items()}
    if "planner" not in text["systemprompt.md"] or "name: planner" not in text["skills/planner/SKILL.md"]:
        raise ValueError("The materialized planner instructions are missing")
    distinct = "<!-- fixture-angle-policy: distinct -->" in text["guardrails.md"]
    contextual = "<!-- fixture-domain-policy: reading-room -->" in text["LongTermMEMORY.md"]
    generations = list(IDEAS) if distinct else [IDEAS[0]] * 10
    if contextual:
        generations = [f"In the reading room, {idea[0].lower()}{idea[1:]}" for idea in generations]
    print(json.dumps({
        "fixture": True,
        "task": task,
        "generations": generations,
        "consumed_sha256": {name: hashlib.sha256(body).hexdigest() for name, body in materialized.items()},
        "fixture_policies": {"distinct": distinct, "reading_room": contextual},
        "provider_calls": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
