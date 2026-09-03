from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo


class CaptureService:
    """Manages backend selection, health evaluation, and frame distribution."""

    def __init__(self, backends: Mapping[str, CaptureBackend]) -> None:
        self._backends = dict(backends)
        self._active_backend: CaptureBackend | None = None
        self._active_info: CaptureInfo | None = None
        self._lock = threading.RLock()
        self._latest_frame: Frame | None = None

    @property
    def active_backend_name(self) -> str | None:
        with self._lock:
            return self._active_backend.name if self._active_backend is not None else None

    @property
    def active_info(self) -> CaptureInfo | None:
        with self._lock:
            return self._active_info

    def attach(self, window_id: int, requested: str = "auto", fps: int = 120) -> CaptureInfo:
        candidates = ("wgc", "dxcam") if requested == "auto" else (requested,)
        failures: list[DomainError] = []

        with self._lock:
            self.close()
            for name in candidates:
                if name not in self._backends:
                    continue
                backend = self._backends[name]
                try:
                    info = self._attach_and_validate(backend, window_id, fps)
                    self._active_backend = backend
                    self._active_info = info
                    return info
                except DomainError as exc:
                    failures.append(exc)
                    backend.close()
                except Exception as exc:
                    failures.append(DomainError("CAPTURE_FAILED", f"{name} failed: {exc}"))
                    backend.close()

            if failures:
                raise failures[-1]
            raise DomainError("BACKEND_NOT_FOUND", f"No suitable capture backend found for {requested}.")

    def _attach_and_validate(self, backend: CaptureBackend, window_id: int, fps: int) -> CaptureInfo:
        info = backend.attach(window_id, fps)
        # Read a test frame to ensure backend is not stalled
        frame = backend.read(timeout_ms=500)
        if frame is None:
            raise DomainError("CAPTURE_STALLED", f"{backend.name} capture stalled during startup.")
        self._latest_frame = frame
        return info

    def read_latest(self, timeout_ms: int = 100) -> Frame | None:
        with self._lock:
            if self._active_backend is None:
                return None
            frame = self._active_backend.read(timeout_ms)
            if frame is not None:
                self._latest_frame = frame
            return self._latest_frame

    def health(self) -> CaptureHealth:
        with self._lock:
            if self._active_backend is None:
                return CaptureHealth(is_healthy=False, fps=0.0, duplicate_ratio=1.0)
            return self._active_backend.health()

    def close(self) -> None:
        with self._lock:
            if self._active_backend is not None:
                try:
                    self._active_backend.close()
                except Exception:
                    pass
                self._active_backend = None
                self._active_info = None
                self._latest_frame = None
