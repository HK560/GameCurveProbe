from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from gamecurveprobe.services.window_service import WindowService

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


@dataclass(slots=True)
class CapturedFrame:
    frame: Any
    timestamp: float
    region: tuple[int, int, int, int]


class DxcamCaptureBackend:
    """Capture the selected window's client area rather than a desktop region."""

    def __init__(
        self,
        window_service: WindowService,
        target_fps: int = 60,
        capture_window: Callable[[int], Any | None] | None = None,
    ) -> None:
        self._window_service = window_service
        self._target_fps = target_fps
        self._window_id: int | None = None
        self._region: tuple[int, int, int, int] | None = None
        self._capture_window = capture_window or _capture_window_client_frame

    def list_windows(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._window_service.list_windows()]

    def attach(self, window_id: int) -> None:
        self._window_service.get_window(window_id)
        left, top, right, bottom = self._window_service.get_client_rect(window_id)
        if right <= left or bottom <= top:
            raise ValueError("Selected window is minimized or has an invalid size.")

        self._window_id = window_id
        self._region = (left, top, right, bottom)

    def set_target_fps(self, target_fps: int) -> None:
        self._target_fps = target_fps

    def grab_frame(self) -> CapturedFrame | None:
        if self._window_id is None or self._region is None:
            return None

        frame = self._capture_window(self._window_id)
        if frame is None:
            return None

        return CapturedFrame(frame=frame, timestamp=time.perf_counter(), region=self._region)

    def close(self) -> None:
        self._window_id = None
        self._region = None


def _capture_window_client_frame(window_id: int) -> np.ndarray | None:
    if not user32.IsWindow(window_id):
        return None

    rect = wintypes.RECT()
    if not user32.GetClientRect(window_id, ctypes.byref(rect)):
        return None

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None

    window_dc = user32.GetDC(window_id)
    if not window_dc:
        return None

    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    if not memory_dc:
        user32.ReleaseDC(window_id, window_dc)
        return None

    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    if not bitmap:
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(window_id, window_dc)
        return None

    previous_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        ok = user32.PrintWindow(window_id, memory_dc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
        if not ok:
            return None

        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB

        buffer = (ctypes.c_ubyte * (width * height * 4))()
        copied_rows = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(bitmap_info),
            DIB_RGB_COLORS,
        )
        if copied_rows != height:
            return None

        frame = np.ctypeslib.as_array(buffer).reshape((height, width, 4))
        return frame[:, :, :3].copy()
    finally:
        gdi32.SelectObject(memory_dc, previous_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(window_id, window_dc)
