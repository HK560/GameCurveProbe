from __future__ import annotations

from gamecurveprobe.backends.capture.dxcam_backend import DxcamCaptureBackend
from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend
from gamecurveprobe import app


class FakeUser32:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def SetProcessDPIAware(self) -> int:  # noqa: N802
        self.calls.append("SetProcessDPIAware")
        return 1


class FakeShcore:
    def __init__(self, result: int = 0) -> None:
        self.result = result
        self.calls: list[int] = []

    def SetProcessDpiAwareness(self, awareness: int) -> int:  # noqa: N802
        self.calls.append(awareness)
        return self.result


def test_enable_windows_dpi_awareness_prefers_per_monitor_mode() -> None:
    user32 = FakeUser32()
    shcore = FakeShcore(result=0)

    app._enable_windows_dpi_awareness(user32=user32, shcore=shcore)

    assert shcore.calls == [2]
    assert user32.calls == []


def test_enable_windows_dpi_awareness_falls_back_to_system_dpi_aware() -> None:
    user32 = FakeUser32()
    shcore = FakeShcore(result=5)

    app._enable_windows_dpi_awareness(user32=user32, shcore=shcore)

    assert shcore.calls == [2]
    assert user32.calls == ["SetProcessDPIAware"]


def test_build_steady_capture_backend_factory_uses_monitor_backend() -> None:
    class FakeWindowService:
        pass

    backend = app._build_steady_capture_backend_factory(FakeWindowService())()

    assert isinstance(backend, DxcamMonitorCaptureBackend)


def test_build_preview_capture_backend_factory_uses_window_backend() -> None:
    class FakeWindowService:
        pass

    backend = app._build_preview_capture_backend_factory(FakeWindowService())()

    assert isinstance(backend, DxcamCaptureBackend)
