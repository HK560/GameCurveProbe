from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from gamecurveprobe.errors import DomainError
from gamecurveprobe.services.controller_service import ControllerService


@dataclass(frozen=True, slots=True)
class ProbeSnapshot:
    active: bool
    output: float
    step: float
    direction: str = "x_positive"
    expires_in: float = 0.0


class DeadzoneProbeService:
    """Manages an interactive, leased controller probe for deadzone determination."""

    VALID_STEPS = {0.001, 0.005, 0.01}

    def __init__(
        self,
        controller: ControllerService,
        clock: Callable[[], float] | None = None,
        lease_seconds: float = 2.0,
    ) -> None:
        self._controller = controller
        self._clock = clock or time.monotonic
        self._lease_seconds = lease_seconds
        self._lock = threading.RLock()
        self._active = False
        self._output = 0.0
        self._step = 0.005
        self._deadline = 0.0
        self._cancel = threading.Event()
        self._closed = False

        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="gcp-probe-watchdog")
        self._watchdog_thread.start()

    def start(self, initial_output: float = 0.0, step: float = 0.005, direction: str = "x_positive") -> ProbeSnapshot:
        if direction != "x_positive":
            raise DomainError("INVALID_DIRECTION", "Only x_positive probe direction is supported.")
        if step not in self.VALID_STEPS:
            raise DomainError("INVALID_STEP", f"Step must be one of {self.VALID_STEPS}.")
        if not 0.0 <= initial_output <= 1.0:
            raise DomainError("INVALID_OUTPUT", "initial_output must be within [0, 1].")

        with self._lock:
            self._cancel.clear()
            self._controller.neutralize()
            if not self._controller.set_right_stick(initial_output, 0.0, self._cancel):
                raise DomainError("PROBE_START_FAILED", "Failed to engage controller stick.")
            self._active = True
            self._output = initial_output
            self._step = step
            self._deadline = self._clock() + self._lease_seconds
            return self.snapshot()

    def update(self, output: float) -> ProbeSnapshot:
        with self._lock:
            self._require_active()
            if not 0.0 <= output <= 1.0:
                raise DomainError("INVALID_PROBE_OUTPUT", "Probe output must be within [0, 1].")
            self._controller.set_right_stick(output, 0.0, self._cancel)
            self._output = output
            self._deadline = self._clock() + self._lease_seconds
            return self.snapshot()

    def stop(self) -> ProbeSnapshot:
        with self._lock:
            if self._active:
                self._controller.cancel_and_neutralize(self._cancel)
                self._active = False
                self._output = 0.0
                self._deadline = 0.0
            return self.snapshot()

    def expire_if_needed(self) -> bool:
        with self._lock:
            if self._active and self._clock() >= self._deadline:
                self.stop()
                return True
            return False

    def snapshot(self) -> ProbeSnapshot:
        with self._lock:
            now = self._clock()
            expires_in = max(0.0, round(self._deadline - now, 2)) if self._active else 0.0
            return ProbeSnapshot(
                active=self._active,
                output=self._output,
                step=self._step,
                direction="x_positive",
                expires_in=expires_in,
            )

    def close(self) -> None:
        self._closed = True
        self.stop()

    def _require_active(self) -> None:
        if not self._active:
            raise DomainError("PROBE_INACTIVE", "Deadzone probe is not currently active.")

    def _watchdog_loop(self) -> None:
        while not self._closed:
            self.expire_if_needed()
            time.sleep(0.1)
