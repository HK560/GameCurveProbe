from __future__ import annotations

import pytest
from gamecurveprobe.services.hotkey_service import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    HotkeyService,
    parse_hotkey_string,
)


def test_parse_hotkey_string() -> None:
    # Single key
    mods, vk = parse_hotkey_string("F9")
    assert mods == MOD_NOREPEAT
    assert vk == 0x78

    mods, vk = parse_hotkey_string("F10")
    assert mods == MOD_NOREPEAT
    assert vk == 0x79

    # Combination: Ctrl+Alt+S
    mods, vk = parse_hotkey_string("Ctrl+Alt+S")
    assert mods == (MOD_NOREPEAT | MOD_CONTROL | MOD_ALT)
    assert vk == ord("S")

    # Shift+F9
    mods, vk = parse_hotkey_string("Shift+F9")
    assert mods == (MOD_NOREPEAT | MOD_SHIFT)
    assert vk == 0x78


def test_parse_hotkey_string_invalid() -> None:
    with pytest.raises(ValueError):
        parse_hotkey_string("")

    with pytest.raises(ValueError):
        parse_hotkey_string("InvalidKeyName123")


def test_hotkey_service_lifecycle() -> None:
    started = False
    stopped = False

    def on_start():
        nonlocal started
        started = True

    def on_stop():
        nonlocal stopped
        stopped = True

    service = HotkeyService(on_start=on_start, on_stop=on_stop)
    assert not service.enabled

    # Enable and update config
    service.update_config(enabled=True, start_key="F9", stop_key="F10")
    assert service.enabled

    # Disable
    service.update_config(enabled=False, start_key="F9", stop_key="F10")
    assert not service.enabled

    service.close()
