"""Metrology Supervisor: async state machine for coordinating acquisition."""

from __future__ import annotations

import asyncio
import enum
import logging
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)


class State(enum.Enum):
    IDLE = "idle"
    ACQUIRING = "acquiring"
    FITTING = "fitting"
    LOCKED = "locked"
    FAULT = "fault"


@dataclass
class SupervisorConfig:
    max_retries: int = 3
    interlock_volts: float = 9.5  # hard stop if |voltage| exceeds this


class MetrologySupervisor:
    """Async state machine that sequences trajectory → acquisition → fit."""

    def __init__(self, config: SupervisorConfig | None = None) -> None:
        self._config = config or SupervisorConfig()
        self._state = State.IDLE
        self._callbacks: list[Callable[[State], None]] = []

    @property
    def state(self) -> State:
        return self._state

    def on_state_change(self, cb: Callable[[State], None]) -> None:
        self._callbacks.append(cb)

    def _transition(self, new_state: State) -> None:
        log.debug("Supervisor %s → %s", self._state.value, new_state.value)
        self._state = new_state
        for cb in self._callbacks:
            cb(new_state)

    async def run_sweep(
        self,
        acquire_fn: Callable[[], tuple],
        fit_fn: Callable[[tuple], dict],
    ) -> dict:
        """Execute one acquire → fit cycle, returning fit results."""
        self._transition(State.ACQUIRING)
        try:
            raw = await asyncio.to_thread(acquire_fn)
        except Exception as exc:
            log.error("Acquisition failed: %s", exc)
            self._transition(State.FAULT)
            raise

        self._transition(State.FITTING)
        try:
            result = await asyncio.to_thread(fit_fn, raw)
        except Exception as exc:
            log.error("Fitting failed: %s", exc)
            self._transition(State.FAULT)
            raise

        self._transition(State.IDLE)
        return result
