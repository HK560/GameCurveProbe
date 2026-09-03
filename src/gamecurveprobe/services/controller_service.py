from __future__ import annotations

import threading

from gamecurveprobe.backends.controller.base import VirtualControllerBackend
from gamecurveprobe.errors import DomainError


class ControllerService:
    def __init__(self, backend: VirtualControllerBackend) -> None:
        self._backend = backend
        self._lock = threading.RLock()
        self._owner: str | None = None

    def connect(self) -> None:
        with self._lock:
            if not self._backend.probe():
                raise DomainError("CONTROLLER_UNAVAILABLE", "Install vgamepad and ViGEmBus first.")
            self._backend.connect()

    def acquire(self, owner: str) -> None:
        with self._lock:
            if self._owner is not None:
                raise DomainError(
                    "CONTROLLER_RESOURCE_BUSY",
                    f"Controller resource is currently owned by {self._owner}.",
                )
            if self._owner is None:
                self.connect()
                self._owner = owner

    def is_available(self) -> bool:
        with self._lock:
            try:
                return bool(self._backend.probe())
            except Exception:
                return False

    def release(self, owner: str) -> None:
        with self._lock:
            if self._owner != owner:
                return
            try:
                self._backend.neutral()
            finally:
                self._owner = None

    def set_right_stick(self, x: float, y: float, cancel: threading.Event) -> bool:
        with self._lock:
            if cancel.is_set():
                return False
            self._backend.set_right_stick(x, y)
            return True

    def cancel_and_neutralize(self, cancel: threading.Event) -> None:
        cancel.set()
        self.neutralize()

    def neutralize(self) -> None:
        with self._lock:
            self._backend.neutral()

    def close(self) -> None:
        with self._lock:
            try:
                self._backend.neutral()
            finally:
                self._owner = None
                self._backend.disconnect()
