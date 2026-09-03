from __future__ import annotations

import numpy as np
import pytest
import threading
import time

from gamecurveprobe.backends.capture.base import Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo, RoiRect, WindowState
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
            monotonic_ns=time.perf_counter_ns(),
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


def test_auto_does_not_fallback_when_wgc_stalls() -> None:
    dxcam = HealthyBackend("dxcam")
    service = CaptureService({"wgc": StalledBackend("wgc"), "dxcam": dxcam})

    with pytest.raises(DomainError) as exc:
        service.attach(42, "auto", 120)

    assert exc.value.code == "CAPTURE_STALLED"
    assert dxcam._frame_count == 0


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


def test_capture_service_implements_frame_provider_contract() -> None:
    backend = HealthyBackend("dxcam", 400, 300)
    service = CaptureService({"dxcam": backend})
    service.attach(10, "dxcam", 60)

    frame = service.read(100)

    assert frame is not None
    assert frame.image.shape == (300, 400, 3)
    service.close()


def test_auto_accepts_static_wgc_pixels_when_frame_ids_advance() -> None:
    class FrozenBackend(HealthyBackend):
        def read(self, timeout_ms: int) -> Frame | None:
            frame = super().read(timeout_ms)
            assert frame is not None
            frame.image.fill(40)
            return frame

    wgc = FrozenBackend("wgc")
    dxcam = HealthyBackend("dxcam")
    service = CaptureService({"wgc": wgc, "dxcam": dxcam})

    info = service.attach(42, "auto", 120)

    assert info.backend == "wgc"
    assert dxcam._frame_count == 0
    service.close()


def test_auto_accepts_wgc_after_one_initial_frame_without_constant_updates() -> None:
    class InitialFrameBackend(HealthyBackend):
        def read(self, timeout_ms: int) -> Frame | None:
            if self._frame_count:
                return None
            frame = super().read(timeout_ms)
            assert frame is not None
            frame.image.fill(40)
            return frame

    service = CaptureService({"wgc": InitialFrameBackend("wgc")})

    info = service.attach(42, "auto", 120)

    assert info.backend == "wgc"
    service.close()


def test_static_wgc_capture_is_not_faulted_only_because_no_update_arrived() -> None:
    class InitialFrameBackend(HealthyBackend):
        def read(self, timeout_ms: int) -> Frame | None:
            if self._frame_count:
                return None
            frame = super().read(timeout_ms)
            assert frame is not None
            frame.image.fill(40)
            return frame

    service = CaptureService({"wgc": InitialFrameBackend("wgc")})
    service._STALL_AFTER_MS = 5
    service.attach(42, "auto", 120)
    time.sleep(0.03)

    service.assert_ready(RoiRect(0, 0, 100, 100))
    service.close()


def test_auto_reports_ten_consecutive_black_wgc_frames() -> None:
    class BlackBackend(HealthyBackend):
        def read(self, timeout_ms: int) -> Frame | None:
            frame = super().read(timeout_ms)
            assert frame is not None
            frame.image.fill(0)
            return frame

    service = CaptureService({"wgc": BlackBackend("wgc")})

    with pytest.raises(DomainError) as exc:
        service.attach(42, "auto", 120)

    assert exc.value.code == "CAPTURE_BLACK_FRAME"


def test_frame_consumers_do_not_read_backend_concurrently() -> None:
    class ThreadRecordingBackend(HealthyBackend):
        def __init__(self) -> None:
            super().__init__()
            self.reader_threads: list[str] = []

        def read(self, timeout_ms: int) -> Frame | None:
            self.reader_threads.append(threading.current_thread().name)
            return super().read(timeout_ms)

    backend = ThreadRecordingBackend()
    service = CaptureService({"dxcam": backend}, preview_callback=lambda _: None)
    service.attach(42, "dxcam", 120)

    assert service.read(250) is not None
    assert threading.current_thread().name not in backend.reader_threads[1:]
    service.close()


def test_capture_rejects_minimized_window_and_prompts_user() -> None:
    class MinimizedWindows:
        def inspect_window(self, window_id: int) -> WindowState:
            return WindowState(exists=True, minimized=True)

    service = CaptureService(
        {"wgc": HealthyBackend("wgc")},
        window_service=MinimizedWindows(),  # type: ignore[arg-type]
    )

    with pytest.raises(DomainError) as exc:
        service.attach(42, "auto", 120)

    assert exc.value.code == "WINDOW_MINIMIZED"
    assert "不要最小化" in exc.value.message


def test_assert_ready_rejects_roi_outside_current_frame() -> None:
    service = CaptureService({"dxcam": HealthyBackend("dxcam", 400, 300)})
    service.attach(42, "dxcam", 120)

    with pytest.raises(DomainError) as exc:
        service.assert_ready(RoiRect(350, 250, 100, 100))

    assert exc.value.code == "ROI_INVALIDATED"
    service.close()
