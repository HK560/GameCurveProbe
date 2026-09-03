from __future__ import annotations

import numpy as np
import pytest

from gamecurveprobe.backends.capture.base import Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo
from gamecurveprobe.services.capture_service import CaptureService


class HealthyBackend:
    name = "dxcam"

    def __init__(self, name: str = "dxcam", width: int = 800, height: int = 600) -> None:
        self.name = name
        self.width = width
        self.height = height
        self.closed = False
        self._frame_count = 0

    def attach(self, window_id: int, target_fps: int) -> CaptureInfo:
        return CaptureInfo(
            window_id=window_id,
            backend=self.name,
            width=self.width,
            height=self.height,
            target_fps=target_fps,
        )

    def read(self, timeout_ms: int) -> Frame | None:
        self._frame_count += 1
        # Create non-zero varied frame
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[0, 0, 0] = self._frame_count % 255
        img[10, 10, 1] = 120
        return Frame(
            image=img,
            monotonic_ns=self._frame_count * 10_000_000,
            frame_id=self._frame_count,
            is_duplicate=False,
        )

    def health(self) -> CaptureHealth:
        return CaptureHealth(is_healthy=True, fps=60.0, duplicate_ratio=0.0)

    def close(self) -> None:
        self.closed = True


class StalledBackend:
    name = "wgc"

    def __init__(self, name: str = "wgc") -> None:
        self.name = name
        self.closed = False

    def attach(self, window_id: int, target_fps: int) -> CaptureInfo:
        raise DomainError("CAPTURE_STALLED", f"{self.name} capture stalled during startup.")

    def read(self, timeout_ms: int) -> Frame | None:
        return None

    def health(self) -> CaptureHealth:
        return CaptureHealth(is_healthy=False, fps=0.0, duplicate_ratio=1.0)

    def close(self) -> None:
        self.closed = True


def test_auto_falls_back_when_wgc_stalls() -> None:
    service = CaptureService({"wgc": StalledBackend("wgc"), "dxcam": HealthyBackend("dxcam")})
    info = service.attach(42, "auto", 120)
    assert info.backend == "dxcam"


def test_forced_wgc_does_not_fallback() -> None:
    service = CaptureService({"wgc": StalledBackend("wgc"), "dxcam": HealthyBackend("dxcam")})
    with pytest.raises(DomainError) as exc:
        service.attach(42, "wgc", 120)
    assert exc.value.code == "CAPTURE_STALLED"


def test_capture_service_distributes_latest_frame() -> None:
    backend = HealthyBackend("dxcam", 400, 300)
    service = CaptureService({"dxcam": backend})
    service.attach(10, "dxcam", 60)
    frame = service.read_latest(timeout_ms=100)
    assert frame is not None
    assert frame.image.shape == (300, 400, 3)
    service.close()
    assert backend.closed is True
