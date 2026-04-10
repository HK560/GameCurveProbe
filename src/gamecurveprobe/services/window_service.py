from __future__ import annotations

import ctypes
from ctypes import wintypes

from gamecurveprobe.models import WindowInfo

user32 = ctypes.windll.user32


class WindowService:
    """Enumerate visible top-level windows on Windows."""

    def list_windows(self) -> list[WindowInfo]:
        windows: list[WindowInfo] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        @enum_windows_proc
        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True

            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length == 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
            title = title_buffer.value.strip()
            if not title:
                return True

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right <= rect.left or rect.bottom <= rect.top:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            windows.append(
                WindowInfo(
                    window_id=int(hwnd),
                    title=title,
                    process_id=int(pid.value),
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                )
            )
            return True

        user32.EnumWindows(callback, 0)
        windows.sort(key=lambda item: item.title.lower())
        return windows

    def get_window(self, window_id: int) -> WindowInfo:
        for window in self.list_windows():
            if window.window_id == window_id:
                return window
        raise ValueError(f"Window {window_id} was not found.")

    def get_client_rect(self, window_id: int) -> tuple[int, int, int, int]:
        if not user32.IsWindow(window_id):
            raise ValueError(f"Window {window_id} was not found.")

        rect = wintypes.RECT()
        if not user32.GetClientRect(window_id, ctypes.byref(rect)):
            raise ValueError(f"Window {window_id} has no valid client area.")

        top_left = wintypes.POINT(rect.left, rect.top)
        bottom_right = wintypes.POINT(rect.right, rect.bottom)
        if not user32.ClientToScreen(window_id, ctypes.byref(top_left)):
            raise ValueError(f"Window {window_id} client coordinates could not be resolved.")
        if not user32.ClientToScreen(window_id, ctypes.byref(bottom_right)):
            raise ValueError(f"Window {window_id} client coordinates could not be resolved.")

        return (top_left.x, top_left.y, bottom_right.x, bottom_right.y)

    def get_monitor_for_rect(self, rect: tuple[int, int, int, int]) -> dict[str, object]:
        monitors = self._list_monitors()
        containing_indices = [
            index
            for index, monitor_rect in enumerate(monitors)
            if self._rect_is_within(rect, monitor_rect)
        ]
        if containing_indices:
            index = containing_indices[0]
            return {
                "monitor_index": index,
                "monitor_rect": monitors[index],
                "is_single_monitor": len(containing_indices) == 1,
            }

        best_index = 0
        best_area = -1
        for index, monitor_rect in enumerate(monitors):
            area = self._intersection_area(rect, monitor_rect)
            if area > best_area:
                best_index = index
                best_area = area

        return {
            "monitor_index": best_index,
            "monitor_rect": monitors[best_index] if monitors else rect,
            "is_single_monitor": False,
        }

    def _list_monitors(self) -> list[tuple[int, int, int, int]]:
        monitors: list[tuple[int, int, int, int]] = []
        monitor_enum_proc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        @monitor_enum_proc
        def callback(_monitor: int, _hdc: int, rect_ptr, _lparam: int) -> bool:
            rect = rect_ptr.contents
            monitors.append((rect.left, rect.top, rect.right, rect.bottom))
            return True

        user32.EnumDisplayMonitors(0, 0, callback, 0)
        return monitors

    def _rect_is_within(
        self,
        inner: tuple[int, int, int, int],
        outer: tuple[int, int, int, int],
    ) -> bool:
        return (
            inner[0] >= outer[0]
            and inner[1] >= outer[1]
            and inner[2] <= outer[2]
            and inner[3] <= outer[3]
        )

    def _intersection_area(
        self,
        first: tuple[int, int, int, int],
        second: tuple[int, int, int, int],
    ) -> int:
        left = max(first[0], second[0])
        top = max(first[1], second[1])
        right = min(first[2], second[2])
        bottom = min(first[3], second[3])
        if right <= left or bottom <= top:
            return 0
        return (right - left) * (bottom - top)
