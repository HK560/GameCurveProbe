from __future__ import annotations

from typing import Any

from gamecurveprobe.backends.capture.base import CaptureBackend


class StubCaptureBackend(CaptureBackend):
    """Placeholder capture backend before DXcam integration."""

    def __init__(self) -> None:
        self.window_id: int | None = None

    def list_windows(self) -> list[dict[str, Any]]:
        return []

    def attach(self, window_id: int) -> None:
        self.window_id = window_id

    def grab_frame(self) -> Any:
        return None

    def close(self) -> None:
        self.window_id = None
