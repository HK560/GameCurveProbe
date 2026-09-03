from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import cv2
import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.events import PreviewFrame
from gamecurveprobe.models import CaptureHealth, CaptureInfo


class CaptureService:
    """Manages backend selection, health evaluation, and frame distribution."""

    def __init__(
        self,
        backends: Mapping[str, CaptureBackend],
        preview_callback: Callable[[PreviewFrame], None] | None = None,
    ) -> None:
        self._backends = dict(backends)
        self._preview_callback = preview_callback
        self._active_backend: CaptureBackend | None = None
        self._active_info: CaptureInfo | None = None
        self._lock = threading.RLock()
        self._latest_frame: Frame | None = None
        self._stop_preview = threading.Event()
        self._preview_thread: threading.Thread | None = None

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
                    self._start_preview_worker()
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

    def _start_preview_worker(self) -> None:
        self._stop_preview.clear()
        if self._preview_callback is not None:
            self._preview_thread = threading.Thread(
                target=self._preview_loop,
                daemon=True,
                name="CapturePreviewWorker",
            )
            self._preview_thread.start()

    def _preview_loop(self) -> None:
        seq = 0
        while not self._stop_preview.is_set():
            with self._lock:
                backend = self._active_backend
            if backend is None:
                time.sleep(0.05)
                continue

            frame = backend.read(timeout_ms=50)
            if frame is not None and frame.image is not None and self._preview_callback is not None:
                with self._lock:
                    self._latest_frame = frame
                try:
                    success, encoded = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if success:
                        preview = PreviewFrame(
                            seq=seq,
                            frame_id=frame.frame_id,
                            monotonic_ns=frame.monotonic_ns,
                            width=frame.image.shape[1],
                            height=frame.image.shape[0],
                            jpeg=encoded.tobytes(),
                        )
                        seq += 1
                        self._preview_callback(preview)
                except Exception:
                    pass

            time.sleep(0.033)

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
        self._stop_preview.set()
        if self._preview_thread is not None and self._preview_thread.is_alive():
            self._preview_thread.join(timeout=0.3)
            self._preview_thread = None

        with self._lock:
            if self._active_backend is not None:
                try:
                    self._active_backend.close()
                except Exception:
                    pass
                self._active_backend = None
                self._active_info = None
                self._latest_frame = None
