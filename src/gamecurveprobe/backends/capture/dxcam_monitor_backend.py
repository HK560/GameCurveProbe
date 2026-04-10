from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from gamecurveprobe.services.window_service import WindowService


@dataclass(slots=True)
class CapturedMonitorFrame:
    frame: Any
    timestamp: float
    frame_id: int
    is_duplicate: bool
    monitor_id: int
    window_rect: tuple[int, int, int, int]


class DxcamMonitorCaptureBackend:
    """Capture a target window by sampling its containing monitor via dxcam."""

    def __init__(
        self,
        window_service: WindowService,
        camera_factory: Callable[[int], object] | None = None,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self._window_service = window_service
        self._camera_factory = camera_factory or self._default_camera_factory
        self._time_source = time_source or time.perf_counter
        self._camera: object | None = None
        self._window_rect: tuple[int, int, int, int] | None = None
        self._monitor_rect: tuple[int, int, int, int] | None = None
        self._monitor_id: int | None = None
        self._frame_id = 0
        self._last_frame: np.ndarray | None = None

    def list_windows(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._window_service.list_windows()]

    def attach(self, window_id: int, capture_fps: int) -> None:
        self._window_service.get_window(window_id)
        window_rect = self._window_service.get_client_rect(window_id)
        monitor = self._window_service.get_monitor_for_rect(window_rect)
        if not bool(monitor["is_single_monitor"]):
            raise ValueError("Steady measurement requires the target window to stay on a single monitor.")

        self._monitor_id = int(monitor["monitor_index"])
        self._monitor_rect = tuple(monitor["monitor_rect"])
        self._window_rect = window_rect
        self._camera = self._camera_factory(self._monitor_id)
        self._camera.start(target_fps=int(capture_fps), video_mode=True)
        self._frame_id = 0
        self._last_frame = None

    def grab_frame(self) -> CapturedMonitorFrame | None:
        if self._camera is None or self._window_rect is None or self._monitor_rect is None or self._monitor_id is None:
            return None

        monitor_frame = self._camera.get_latest_frame()
        if monitor_frame is None:
            return None

        frame = self._crop_window_from_monitor_frame(np.asarray(monitor_frame))
        is_duplicate = self._last_frame is not None and np.array_equal(self._last_frame, frame)
        self._last_frame = frame
        self._frame_id += 1
        return CapturedMonitorFrame(
            frame=frame,
            timestamp=float(self._time_source()),
            frame_id=self._frame_id,
            is_duplicate=is_duplicate,
            monitor_id=self._monitor_id,
            window_rect=self._window_rect,
        )

    def close(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass
        self._camera = None
        self._window_rect = None
        self._monitor_rect = None
        self._monitor_id = None
        self._frame_id = 0
        self._last_frame = None

    def _crop_window_from_monitor_frame(self, frame: np.ndarray) -> np.ndarray:
        assert self._window_rect is not None
        assert self._monitor_rect is not None
        monitor_left, monitor_top, _, _ = self._monitor_rect
        window_left, window_top, window_right, window_bottom = self._window_rect
        crop_left = max(0, window_left - monitor_left)
        crop_top = max(0, window_top - monitor_top)
        crop_right = max(crop_left, window_right - monitor_left)
        crop_bottom = max(crop_top, window_bottom - monitor_top)
        return frame[crop_top:crop_bottom, crop_left:crop_right].copy()

    def _default_camera_factory(self, output_idx: int) -> object:
        import dxcam

        camera = dxcam.create(output_idx=output_idx)
        if camera is None:
            raise RuntimeError(f"dxcam could not create a capture device for output {output_idx}.")
        return camera
