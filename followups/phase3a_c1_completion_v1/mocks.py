"""Task-scoped copies of the frozen C1 SDK fixture, with one global wire log."""
from __future__ import annotations

import copy

from followups.phase3a_compat_c1_v1.mocks import SDKMock


class StudyMock(SDKMock):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_pilot: str | None = None
        self.pilot_proofs: dict[str, dict] = {}

    def __enter__(self):
        super().__enter__()
        self.transport.register_contract = self.register_pilot
        self.transport.records = self.records
        return self

    def register_pilot(self, pilot: str, label: str, prepared: dict) -> None:
        if self.active_pilot != pilot:
            if self.active_pilot is not None:
                self.pilot_proofs[self.active_pilot] = copy.deepcopy(self.c1_sessions)
            self.active_pilot = pilot
            self._registered.clear()
            self._registered_system.clear()
            self._c1.clear()
            self.c1_sessions.clear()
        super().register_contract(label, prepared)

    def proofs(self) -> dict:
        result = copy.deepcopy(self.pilot_proofs)
        if self.active_pilot is not None:
            result[self.active_pilot] = copy.deepcopy(self.c1_sessions)
        return result
