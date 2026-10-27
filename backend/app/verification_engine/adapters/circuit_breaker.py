"""Manual circuit breaker state machine (closed / open / half-open).

Uses no third-party circuitbreaker library. Pair with tenacity for retries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _opened_at: float | None = None
    _half_open_probe_in_flight: bool = False

    @property
    def state(self) -> CircuitState:
        self._maybe_transition_to_half_open()
        return self._state

    def _maybe_transition_to_half_open(self) -> None:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return
        if time.monotonic() - self._opened_at >= self.cooldown_seconds:
            self._state = CircuitState.HALF_OPEN
            self._half_open_probe_in_flight = False

    def allow_request(self) -> bool:
        """Return True if a call may proceed; False if circuit is open."""
        self._maybe_transition_to_half_open()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return False
        # half-open: allow a single probe
        if self._half_open_probe_in_flight:
            return False
        self._half_open_probe_in_flight = True
        return True

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None
        self._half_open_probe_in_flight = False
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._half_open_probe_in_flight = False
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            return
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
