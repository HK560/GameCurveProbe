from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from collections.abc import Callable
from typing import Any

import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo
from gamecurveprobe.services.window_service import WindowService

user32 = getattr(ctypes.windll, "user32", None) if hasattr(ctypes, "windll") else None
gdi32 = getattr(ctypes.windll, "gdi32", None) if hasattr(ctypes, "windll") else None

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


class DxcamCaptureBackend(CaptureBackend):
    """Capture window client area using GDI / PrintWindow fallback or dxcam."""

    name = "dxcam"

    def __init__(
        self,
        window_service: WindowService | None = None,
        target_fps: int = 60,
        capture_window: Callable[[int], Any | None] | None = None,
    ) -> None:
        self._window_service = window_service
        self._target_fps = target_fps
        self._window_id: int | None = None
        self._region: tuple[int, int, int, int] | None = None
        self._capture_window = capture_window or _capture_window_client_frame
        self._frame_counter = 0
        self._lock = threading.Lock()
        self._closed = False
        self._fps_tracker: list[float] = []

    def attach(self, window_id: int, target_fps: int = 60) -> CaptureInfo:
        self._target_fps = target_fps
        if self._window_service is not None:
            self._window_service.get_window(window_id)
            left, top, right, bottom = self._window_service.get_client_rect(window_id)
            if right <= left or bottom <= top:
                raise DomainError("INVALID_WINDOW_SIZE", "Selected window is minimized or has an invalid size.")
            self._region = (left, top, right, bottom)
            width = right - left
            height = bottom - top
        else:
            self._region = (0, 0, 1920, 1080)
            width = 1920
            height = 1080

        self._window_id = window_id
        self._closed = False
        return CaptureInfo(
            window_id=window_id,
            backend=self.name,
            width=width,
            height=height,
            target_fps=target_fps,
        )

    def read(self, timeout_ms: int = 100) -> Frame | None:
        with self._lock:
            if self._closed or self._window_id is None:
                return None

            img = self._capture_window(self._window_id)
            if img is None:
                return None

            self._frame_counter += 1
            now_ns = time.perf_counter_ns()
            self._fps_tracker.append(now_ns / 1e9)
            if len(self._fps_tracker) > 60:
                self._fps_tracker.pop(0)

            return Frame(
                image=img,
                monotonic_ns=now_ns,
                frame_id=self._frame_counter,
                is_duplicate=False,
            )

    def grab_frame(self) -> Any | None:
        frame = self.read(100)
        if frame is None:
            return None
        from dataclasses import dataclass
        @dataclass(slots=True)
        class CapturedFrame:
            frame: Any
            timestamp: float
            region: tuple[int, int, int, int]
        return CapturedFrame(
            frame=frame.image,
            timestamp=frame.timestamp,
            region=self._region or (0, 0, frame.image.shape[1], frame.image.shape[0]),
        )

    def health(self) -> CaptureHealth:
        with self._lock:
            if len(self._fps_tracker) >= 2:
                dt = self._fps_tracker[-1] - self._fps_tracker[0]
                fps = round((len(self._fps_tracker) - 1) / dt, 1) if dt > 0 else 0.0
            else:
                fps = 0.0
            return CaptureHealth(
                is_healthy=not self._closed and self._window_id is not None,
                fps=fps,
                duplicate_ratio=0.0,
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._window_id = None
            self._region = None


def _capture_window_client_frame(window_id: int) -> np.ndarray | None:
    if user32 is None or gdi32 is None:
        return None
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
