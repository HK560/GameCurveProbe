from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame, to_bgr
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo


class WgcCaptureBackend(CaptureBackend):
    name = "wgc"

    def __init__(self, capture_impl: Any | None = None) -> None:
        self._capture_impl = capture_impl
        self._capture_control: Any | None = None
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._latest_frame: Frame | None = None
        self._frame_counter = 0
        self._duplicate_counter = 0
        self._closed = False
        self._width = 0
        self._height = 0
        self._window_id: int | None = None
        self._fps_tracker: list[float] = []

    def attach(self, window_id: int, target_fps: int = 120) -> CaptureInfo:
        self.close()
        with self._condition:
            self._closed = False
            self._window_id = window_id
            self._latest_frame = None

        if self._capture_impl is not None:
            self._capture_control = self._capture_impl(window_id, self._handle_raw_frame)
            frame = self.read(timeout_ms=500)
            width = frame.image.shape[1] if frame is not None else 1920
            height = frame.image.shape[0] if frame is not None else 1080
            self._width = width
            self._height = height
            return CaptureInfo(
                window_id=window_id,
                backend=self.name,
                width=width,
                height=height,
                target_fps=target_fps,
            )

        try:
            import windows_capture

            min_interval = max(1, int(1000 / target_fps)) if target_fps > 0 else None
            cap = windows_capture.WindowsCapture(
                cursor_capture=False,
                draw_border=False,
                minimum_update_interval=min_interval,
                window_hwnd=window_id,
            )

            @cap.event
            def on_frame_arrived(native_frame: Any, control: Any) -> None:
                if self._closed:
                    try:
                        control.stop()
                    except Exception:
                        pass
                    return
                raw = getattr(native_frame, "frame_buffer", native_frame)
                self._handle_raw_frame(raw)

            @cap.event
            def on_closed() -> None:
                self._closed = True

            self._capture_control = cap.start_free_threaded()
        except Exception as exc:
            raise DomainError("CAPTURE_ATTACH_FAILED", f"Failed to attach WGC to window {window_id}: {exc}") from exc

        frame = self.read(timeout_ms=1500)
        if frame is None:
            self.close()
            raise DomainError("CAPTURE_STALLED", f"WGC capture stalled during startup on window {window_id}.")

        self._width = frame.image.shape[1]
        self._height = frame.image.shape[0]

        return CaptureInfo(
            window_id=window_id,
            backend=self.name,
            width=self._width,
            height=self._height,
            target_fps=target_fps,
        )

    def _handle_raw_frame(self, raw_buffer: np.ndarray) -> None:
        try:
            bgr = to_bgr(raw_buffer)
        except Exception:
            return

        now_ns = time.perf_counter_ns()
        with self._condition:
            self._frame_counter += 1
            self._width = bgr.shape[1]
            self._height = bgr.shape[0]
            self._latest_frame = Frame(
                image=bgr,
                monotonic_ns=now_ns,
                frame_id=self._frame_counter,
                is_duplicate=False,
            )
            self._fps_tracker.append(now_ns / 1e9)
            if len(self._fps_tracker) > 60:
                self._fps_tracker.pop(0)
            self._condition.notify_all()

    def read(self, timeout_ms: int = 100) -> Frame | None:
        timeout_sec = timeout_ms / 1000.0
        with self._condition:
            if self._latest_frame is not None and timeout_ms <= 0:
                return self._latest_frame
            current_id = self._latest_frame.frame_id if self._latest_frame is not None else 0
            start = time.perf_counter()
            while not self._closed:
                if self._latest_frame is not None and self._latest_frame.frame_id > current_id:
                    return self._latest_frame
                remaining = timeout_sec - (time.perf_counter() - start)
                if remaining <= 0:
                    break
                self._condition.wait(min(0.05, remaining))
            return self._latest_frame

    def health(self) -> CaptureHealth:
        with self._lock:
            if len(self._fps_tracker) >= 2:
                dt = self._fps_tracker[-1] - self._fps_tracker[0]
                fps = round((len(self._fps_tracker) - 1) / dt, 1) if dt > 0 else 0.0
            else:
                fps = 0.0
            is_healthy = not self._closed and self._latest_frame is not None
            return CaptureHealth(
                is_healthy=is_healthy,
                fps=fps,
                duplicate_ratio=0.0,
            )

    def close(self) -> None:
        with self._condition:
            self._closed = True
            if self._capture_control is not None:
                try:
                    if hasattr(self._capture_control, "stop"):
                        self._capture_control.stop()
                except Exception:
                    pass
                self._capture_control = None
            self._condition.notify_all()
