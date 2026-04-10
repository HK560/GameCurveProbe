from __future__ import annotations

import ctypes

import gamecurveprobe.services.window_service as window_service_module
from gamecurveprobe.services.window_service import WindowService


class FakeUser32:
    def __init__(self) -> None:
        self.client_to_screen_calls: list[tuple[int, int]] = []

    def IsWindow(self, hwnd: int) -> bool:  # noqa: N802
        return hwnd == 123

    def GetClientRect(self, hwnd: int, rect) -> int:  # noqa: N802
        assert hwnd == 123
        target = rect._obj
        target.left = 0
        target.top = 0
        target.right = 640
        target.bottom = 480
        return 1

    def ClientToScreen(self, hwnd: int, point) -> int:  # noqa: N802
        assert hwnd == 123
        target = point._obj
        self.client_to_screen_calls.append((target.x, target.y))
        target.x += 100
        target.y += 200
        return 1


def test_get_client_rect_returns_client_area_in_screen_coordinates(monkeypatch) -> None:
    fake_user32 = FakeUser32()
    monkeypatch.setattr(window_service_module, "user32", fake_user32)

    rect = WindowService().get_client_rect(123)

    assert rect == (100, 200, 740, 680)
    assert fake_user32.client_to_screen_calls == [(0, 0), (640, 480)]


def test_get_client_rect_rejects_unknown_windows(monkeypatch) -> None:
    fake_user32 = FakeUser32()
    monkeypatch.setattr(window_service_module, "user32", fake_user32)

    try:
        WindowService().get_client_rect(999)
    except ValueError as exc:
        assert str(exc) == "Window 999 was not found."
    else:
        raise AssertionError("Expected ValueError for an unknown window.")
