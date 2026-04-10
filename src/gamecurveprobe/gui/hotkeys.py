from __future__ import annotations

import ctypes
from dataclasses import dataclass


@dataclass(slots=True)
class HotkeyRegistrationResult:
    failures: list[str]


class Win32HotkeyRegistrar:
    MOD_NOREPEAT = 0x4000

    def register(self, hwnd: int, hotkey_id: int, virtual_key: int) -> bool:
        user32 = ctypes.windll.user32
        return bool(user32.RegisterHotKey(hwnd, hotkey_id, self.MOD_NOREPEAT, virtual_key))

    def unregister(self, hotkey_id: int) -> None:
        ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)


class GlobalHotkeyManager:
    def __init__(self, registrar=None) -> None:
        self._registrar = registrar or Win32HotkeyRegistrar()
        self._hotkeys = [(1, "F8", 0x77), (2, "F9", 0x78), (3, "F10", 0x79)]

    def register_defaults(self, hwnd: int) -> HotkeyRegistrationResult:
        failures: list[str] = []
        for hotkey_id, label, virtual_key in self._hotkeys:
            if not self._registrar.register(hwnd, hotkey_id, virtual_key):
                failures.append(label)
        return HotkeyRegistrationResult(failures=failures)

    def unregister_all(self) -> None:
        for hotkey_id, _, _ in self._hotkeys:
            self._registrar.unregister(hotkey_id)

    def hotkey_label(self, hotkey_id: int) -> str | None:
        for registered_id, label, _ in self._hotkeys:
            if registered_id == hotkey_id:
                return label
        return None
