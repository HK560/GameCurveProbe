from __future__ import annotations

import time
from typing import Any

import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame
from gamecurveprobe.models import CaptureHealth, CaptureInfo


class StubCaptureBackend(CaptureBackend):
    """Deterministic capture stub for tests and headless execution."""

    name = "stub"

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.window_id: int | None = None
        self.width = width
        self.height = height
        self._frame_counter = 0
        self._closed = False

    def attach(self, window_id: int, target_fps: int = 120) -> CaptureInfo:
        self.window_id = window_id
        self._closed = False
        return CaptureInfo(
            window_id=window_id,
            backend=self.name,
            width=self.width,
            height=self.height,
            target_fps=target_fps,
            title="Stub Window",
        )

    def read(self, timeout_ms: int = 100) -> Frame | None:
        if self._closed or self.window_id is None:
            return None
        self._frame_counter += 1
        now_ns = time.perf_counter_ns()
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[::20, :, 0] = 200
        img[:, ::20, 1] = 200
        img[0, 0, 2] = self._frame_counter % 255
        return Frame(
            image=img,
            monotonic_ns=now_ns,
            frame_id=self._frame_counter,
            is_duplicate=False,
        )

    def grab_frame(self) -> Any:
        return self.read(100)

    def health(self) -> CaptureHealth:
        return CaptureHealth(
            is_healthy=not self._closed and self.window_id is not None,
            fps=60.0,
            duplicate_ratio=0.0,
        )

    def close(self) -> None:
        self._closed = True
        self.window_id = None
