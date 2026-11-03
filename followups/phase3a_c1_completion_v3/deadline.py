"""One nonrenewable completion window; cleanup has a separate finite bound."""
from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from buddha2.artifacts import ContractError


class KnownDeadlineStop(ContractError):
    """A known local deadline disposition; never permission to retry."""


class OwnerStopRequired(ContractError):
    """A committed hold requires termination of the owned controller."""


@dataclass(frozen=True)
class Policy:
    completion: float = 240.0
    cleanup: float = 60.0
    editor_margin: float = 30.0
    editor_minimum: float = 30.0
    connect: float = 10.0
    pool: float = 10.0
    write: float = 30.0
    read: float = 240.0

    def __post_init__(self) -> None:
        if any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ContractError("invalid finite deadline policy")


POLICY = Policy()


@dataclass(frozen=True)
class Budget:
    started_monotonic: float
    deadline_monotonic: float
    effective_seconds: float
    conversation_deadline: float | None
    started_utc: str
    policy: Policy

    @property
    def cleanup_deadline(self) -> float:
        return self.deadline_monotonic + self.policy.cleanup

    def record(self) -> dict:
        return asdict(self) | {"cleanup_deadline_monotonic": self.cleanup_deadline}


def budget(conversation_deadline: float | None = None, *, now: float | None = None,
           policy: Policy = POLICY) -> Budget:
    current = time.monotonic() if now is None else now
    if type(current) not in (int, float) or not math.isfinite(current):
        raise ContractError("invalid monotonic admission time")
    available = policy.completion
    if conversation_deadline is not None:
        if type(conversation_deadline) not in (int, float) or not math.isfinite(conversation_deadline):
            raise ContractError("invalid absolute conversation deadline")
        available = min(available, conversation_deadline - current - policy.editor_margin)
        if available < policy.editor_minimum:
            raise KnownDeadlineStop("insufficient post-lock conversation budget before intent")
    return Budget(current, current + available, available, conversation_deadline,
                  datetime.now(timezone.utc).isoformat(), policy)


def eligible(capture_monotonic: float, allocation: Budget) -> bool:
    return math.isfinite(capture_monotonic) and capture_monotonic <= allocation.deadline_monotonic
