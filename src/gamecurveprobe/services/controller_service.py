from __future__ import annotations

import threading

from gamecurveprobe.backends.controller.base import VirtualControllerBackend
from gamecurveprobe.errors import DomainError


class ControllerService:
    def __init__(self, backend: VirtualControllerBackend) -> None:
        self._backend = backend
        self._lock = threading.RLock()
        self._owner: str | None = None
        self._enabled = True
        self._wake_timer: threading.Timer | None = None

    def connect(self) -> None:
        with self._lock:
            if getattr(self._backend, "connected", False):
                return
            if not self._backend.probe():
                raise DomainError("CONTROLLER_UNAVAILABLE", "Install vgamepad and ViGEmBus first.")
            self._backend.connect()

    def is_connected(self) -> bool:
        with self._lock:
            return bool(getattr(self._backend, "connected", False))

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> bool:
        with self._lock:
            if enabled:
                self._enabled = True
                self.connect()
                return True
            if self._owner is not None:
                raise DomainError(
                    "CONTROLLER_RESOURCE_BUSY",
                    f"Controller resource is currently owned by {self._owner}.",
                )
            self._backend.neutral()
            self._backend.disconnect()
            self._enabled = False
            return False

    def wake(self, input_name: str, duration_seconds: float = 0.5) -> None:
        with self._lock:
            if not self._enabled:
                return
            is_standalone = self._owner is None
            if is_standalone:
                self.acquire("wake")

            try:
                self._backend.press_wake_input(input_name)
            except Exception:
                if is_standalone:
                    self.release("wake")
                raise

            def release_cb():
                with self._lock:
                    try:
                        self._backend.release_wake_input(input_name)
                    finally:
                        self._wake_timer = None
                        if is_standalone:
                            self.release("wake")

            self._wake_timer = threading.Timer(duration_seconds, release_cb)
            self._wake_timer.daemon = True
            self._wake_timer.start()

    def acquire(self, owner: str) -> None:
        with self._lock:
            if self._owner is not None:
                raise DomainError(
                    "CONTROLLER_RESOURCE_BUSY",
                    f"Controller resource is currently owned by {self._owner}.",
                )
            if not self._enabled:
                raise DomainError("CONTROLLER_DISABLED", "Enable the ViGEmBus controller first.")
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
            if self._wake_timer is not None:
                self._wake_timer.cancel()
                self._wake_timer = None
            try:
                self._backend.neutral()
            finally:
                self._owner = None
                self._backend.disconnect()
                self._enabled = False

    def _release_wake(self, input_name: str) -> None:
        with self._lock:
            try:
                self._backend.release_wake_input(input_name)
            finally:
                self._wake_timer = None
                self.release("wake")
