"""Circuit breaker — protect against cascading failures."""

from __future__ import annotations

import time
from enum import Enum


class State(Enum):
    CLOSED = "closed"          # normal
    OPEN = "open"              # rejecting
    HALF_OPEN = "half_open"    # probing


class CircuitBreaker:
    """Fail-fast when consecutive failures exceed threshold."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_ms: int = 30_000,
        half_open_max: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_ms = recovery_timeout_ms
        self.half_open_max = half_open_max

        self._state = State.CLOSED
        self._failures: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_attempts: int = 0

    @property
    def state(self) -> State:
        return self._state

    def allow(self) -> bool:
        if self._state == State.CLOSED:
            return True
        if self._state == State.OPEN:
            if (time.time() - self._last_failure_time) * 1000 >= self.recovery_timeout_ms:
                self._state = State.HALF_OPEN
                self._half_open_attempts = 0
                return True
            return False
        # HALF_OPEN — allow limited probes
        if self._half_open_attempts < self.half_open_max:
            self._half_open_attempts += 1
            return True
        return False

    def success(self) -> None:
        self._state = State.CLOSED
        self._failures = 0
        self._half_open_attempts = 0

    def failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.time()
        if self._state == State.HALF_OPEN:
            self._state = State.OPEN
        elif self._failures >= self.failure_threshold:
            self._state = State.OPEN


# ── Per-node-type breakers ──

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(node_type: str) -> CircuitBreaker:
    if node_type not in _breakers:
        _breakers[node_type] = CircuitBreaker(name=node_type)
    return _breakers[node_type]
