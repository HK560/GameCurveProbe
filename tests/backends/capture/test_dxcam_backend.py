from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gamecurveprobe.backends.capture.dxcam_backend import DxcamCaptureBackend
from gamecurveprobe.models import WindowInfo


@dataclass
class FakeWindowService:
    window: WindowInfo | None = None
    client_rect: tuple[int, int, int, int] | None = None

    def list_windows(self) -> list[WindowInfo]:
        return [self.window] if self.window is not None else []

    def get_window(self, window_id: int) -> WindowInfo:
        if self.window is None or self.window.window_id != window_id:
            raise ValueError(f"Window {window_id} was not found.")
        return self.window

    def get_client_rect(self, window_id: int) -> tuple[int, int, int, int]:
        self.get_window(window_id)
        assert self.client_rect is not None
        return self.client_rect


def test_grab_frame_captures_selected_window_content_instead_of_desktop_region() -> None:
    window_service = FakeWindowService(
        window=WindowInfo(window_id=321, title="Example", rect=(0, 0, 999, 999)),
        client_rect=(100, 200, 420, 440),
    )
    captured_calls: list[int] = []
    expected = np.zeros((240, 320, 3), dtype=np.uint8)

    def capture_window(window_id: int):
        captured_calls.append(window_id)
        return expected

    backend = DxcamCaptureBackend(window_service=window_service, capture_window=capture_window)
    backend.attach(321)

    frame = backend.grab_frame()

    assert captured_calls == [321]
    assert frame is not None
    assert frame.region == (100, 200, 420, 440)
    assert frame.frame is expected


def test_attach_uses_client_rect_not_outer_window_rect() -> None:
    window_service = FakeWindowService(
        window=WindowInfo(window_id=321, title="Example", rect=(10, 20, 900, 800)),
        client_rect=(100, 200, 420, 440),
    )
    backend = DxcamCaptureBackend(window_service=window_service, capture_window=lambda _: None)

    backend.attach(321)

    assert backend._region == (100, 200, 420, 440)
