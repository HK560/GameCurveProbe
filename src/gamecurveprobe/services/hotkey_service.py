from __future__ import annotations

import ctypes
import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Win32 Constants
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_START = 1001
HOTKEY_ID_STOP = 1002

VK_MAPPING: dict[str, int] = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "ESCAPE": 0x1B,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAUSE": 0x13,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "NUMPAD0": 0x60,
    "NUMPAD1": 0x61,
    "NUMPAD2": 0x62,
    "NUMPAD3": 0x63,
    "NUMPAD4": 0x64,
    "NUMPAD5": 0x65,
    "NUMPAD6": 0x66,
    "NUMPAD7": 0x67,
    "NUMPAD8": 0x68,
    "NUMPAD9": 0x69,
}

# Add 0-9 and A-Z
for i in range(10):
    VK_MAPPING[str(i)] = 0x30 + i
for char_code in range(ord("A"), ord("Z") + 1):
    VK_MAPPING[chr(char_code)] = char_code


def parse_hotkey_string(hotkey_str: str) -> tuple[int, int]:
    """Parse hotkey string like 'Ctrl+Alt+S' or 'F9' into (modifiers, vk_code)."""
    parts = [p.strip().upper() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        raise ValueError("Empty hotkey string")

    modifiers = MOD_NOREPEAT
    vk_code = 0

    for part in parts:
        if part in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif part == "ALT":
            modifiers |= MOD_ALT
        elif part == "SHIFT":
            modifiers |= MOD_SHIFT
        elif part in ("WIN", "WINDOWS", "SUPER"):
            modifiers |= MOD_WIN
        else:
            if part in VK_MAPPING:
                vk_code = VK_MAPPING[part]
            elif len(part) == 1 and part.isalnum():
                vk_code = ord(part)
            else:
                raise ValueError(f"Unknown hotkey key: {part}")

    if vk_code == 0:
        raise ValueError(f"No main key found in hotkey string: {hotkey_str}")

    return modifiers, vk_code


class HotkeyService:
    """Windows Global Hotkey Service using Win32 RegisterHotKey API."""

    def __init__(
        self,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self._enabled = False
        self._start_key = "F9"
        self._stop_key = "F10"

        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update_config(self, enabled: bool, start_key: str, stop_key: str) -> None:
        with self._lock:
            changed = (
                self._enabled != enabled or self._start_key != start_key or self._stop_key != stop_key
            )
            self._enabled = enabled
            self._start_key = start_key
            self._stop_key = stop_key

        if changed:
            self._restart_listener()

    def start(self, enabled: bool = True, start_key: str = "F9", stop_key: str = "F10") -> None:
        self.update_config(enabled, start_key, stop_key)

    def close(self) -> None:
        self._stop_listener()

    def _restart_listener(self) -> None:
        self._stop_listener()
        if self._enabled and sys.platform == "win32":
            self._start_listener()

    def _start_listener(self) -> None:
        self._thread = threading.Thread(target=self._msg_loop, daemon=True)
        self._thread.start()

    def _stop_listener(self) -> None:
        with self._lock:
            thread_id = self._thread_id
            thread = self._thread
            self._thread_id = None
            self._thread = None

        if thread_id and sys.platform == "win32":
            try:
                ctypes.windll.user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            except Exception as exc:
                logger.warning("Error posting WM_QUIT to hotkey thread: %s", exc)

        if thread and thread.is_alive():
            thread.join(timeout=1.0)

    def _msg_loop(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        with self._lock:
            self._thread_id = thread_id
            start_key = self._start_key
            stop_key = self._stop_key

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_void_p),
                ("lParam", ctypes.c_void_p),
                ("time", ctypes.c_ulong),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long),
            ]

        msg = MSG()
        # Force Windows to create a message queue for this worker thread
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        registered_start = False
        registered_stop = False

        try:
            # Register start hotkey
            try:
                mods, vk = parse_hotkey_string(start_key)
                if user32.RegisterHotKey(None, HOTKEY_ID_START, mods, vk):
                    registered_start = True
                    logger.info("Registered global hotkey START (%s)", start_key)
                else:
                    logger.warning("Failed to register global hotkey START (%s)", start_key)
            except Exception as exc:
                logger.warning("Invalid start hotkey configuration '%s': %s", start_key, exc)

            # Register stop hotkey
            try:
                mods, vk = parse_hotkey_string(stop_key)
                if user32.RegisterHotKey(None, HOTKEY_ID_STOP, mods, vk):
                    registered_stop = True
                    logger.info("Registered global hotkey STOP (%s)", stop_key)
                else:
                    logger.warning("Failed to register global hotkey STOP (%s)", stop_key)
            except Exception as exc:
                logger.warning("Invalid stop hotkey configuration '%s': %s", stop_key, exc)

            # Message Loop
            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p),
                    ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_ulong),
                    ("pt_x", ctypes.c_long),
                    ("pt_y", ctypes.c_long),
                ]

            msg = MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    if hotkey_id == HOTKEY_ID_START and self.on_start:
                        logger.info("Global hotkey START pressed")
                        try:
                            self.on_start()
                        except Exception as exc:
                            logger.error("Error executing start hotkey callback: %s", exc)
                    elif hotkey_id == HOTKEY_ID_STOP and self.on_stop:
                        logger.info("Global hotkey STOP pressed")
                        try:
                            self.on_stop()
                        except Exception as exc:
                            logger.error("Error executing stop hotkey callback: %s", exc)

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if registered_start:
                user32.UnregisterHotKey(None, HOTKEY_ID_START)
            if registered_stop:
                user32.UnregisterHotKey(None, HOTKEY_ID_STOP)
            with self._lock:
                self._thread_id = None
