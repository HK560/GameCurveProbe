from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from gamecurveprobe.models import WindowInfo


@dataclass
class FakeWindowService:
    window: WindowInfo
    client_rect: tuple[int, int, int, int]
    monitor: dict[str, object]

    def get_window(self, window_id: int) -> WindowInfo:
        if self.window.window_id != window_id:
            raise ValueError(f"Window {window_id} was not found.")
        return self.window

    def get_client_rect(self, window_id: int) -> tuple[int, int, int, int]:
        self.get_window(window_id)
        return self.client_rect

    def get_monitor_for_rect(self, rect: tuple[int, int, int, int]) -> dict[str, object]:
        assert rect == self.client_rect
        return self.monitor


class FakeCamera:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame
        self.started_with: tuple[int, bool] | None = None
        self.stop_calls = 0

    def start(self, target_fps: int, video_mode: bool = True) -> None:
        self.started_with = (target_fps, video_mode)

    def get_latest_frame(self) -> np.ndarray:
        return self._frame

    def stop(self) -> None:
        self.stop_calls += 1


def test_attach_maps_window_client_rect_onto_monitor_capture_region() -> None:
    from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend

    source = np.arange(400 * 400 * 3, dtype=np.uint8).reshape((400, 400, 3))
    camera = FakeCamera(source)
    window_service = FakeWindowService(
        window=WindowInfo(window_id=321, title="Example"),
        client_rect=(110, 120, 210, 220),
        monitor={
            "monitor_index": 1,
            "monitor_rect": (100, 100, 500, 500),
            "is_single_monitor": True,
        },
    )
    backend = DxcamMonitorCaptureBackend(
        window_service=window_service,
        camera_factory=lambda output_idx: camera,
        time_source=lambda: 12.5,
    )

    backend.attach(321, capture_fps=144)
    frame = backend.grab_frame()

    assert camera.started_with == (144, True)
    assert frame is not None
    assert frame.timestamp == 12.5
    assert frame.frame_id == 1
    assert frame.is_duplicate is False
    assert frame.monitor_id == 1
    assert frame.window_rect == (110, 120, 210, 220)
    assert frame.frame.shape == (100, 100, 3)
    np.testing.assert_array_equal(frame.frame, source[20:120, 10:110])


def test_attach_rejects_windows_spanning_multiple_monitors() -> None:
    from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend

    window_service = FakeWindowService(
        window=WindowInfo(window_id=321, title="Example"),
        client_rect=(110, 120, 210, 220),
        monitor={
            "monitor_index": 1,
            "monitor_rect": (100, 100, 500, 500),
            "is_single_monitor": False,
        },
    )
    backend = DxcamMonitorCaptureBackend(
        window_service=window_service,
        camera_factory=lambda output_idx: FakeCamera(np.zeros((400, 400, 3), dtype=np.uint8)),
    )

    with pytest.raises(ValueError, match="single monitor"):
        backend.attach(321, capture_fps=120)
