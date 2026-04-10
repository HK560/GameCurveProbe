from __future__ import annotations

import types

import pytest

from gamecurveprobe.backends.controller.vgamepad_backend import VgamepadControllerBackend


class FakePad:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float] | tuple[str, object]] = []

    def right_joystick_float(self, x_value_float: float, y_value_float: float) -> None:
        self.calls.append(("stick", x_value_float, y_value_float))

    def press_button(self, button) -> None:
        self.calls.append(("press", button))

    def release_button(self, button) -> None:
        self.calls.append(("release", button))

    def update(self) -> None:
        self.calls.append(("update",))


def test_probe_returns_false_when_vgamepad_is_missing() -> None:
    backend = VgamepadControllerBackend(module_loader=lambda: (_ for _ in ()).throw(ImportError("missing")))
    assert backend.probe() is False


def test_connect_and_set_right_stick_use_vgamepad() -> None:
    fake_pad = FakePad()
    fake_button = object()
    fake_module = types.SimpleNamespace(
        VX360Gamepad=lambda: fake_pad,
        XUSB_BUTTON=types.SimpleNamespace(XUSB_GAMEPAD_LEFT_THUMB=fake_button),
    )
    backend = VgamepadControllerBackend(module_loader=lambda: fake_module)

    backend.connect()
    backend.set_right_stick(0.25, -0.75)
    backend.press_left_stick()
    backend.release_left_stick()
    backend.neutral()
    backend.disconnect()

    assert fake_pad.calls == [
        ("stick", 0.25, -0.75),
        ("update",),
        ("press", fake_button),
        ("update",),
        ("release", fake_button),
        ("update",),
        ("stick", 0.0, 0.0),
        ("update",),
        ("stick", 0.0, 0.0),
        ("update",),
    ]


def test_connect_is_idempotent() -> None:
    pads: list[FakePad] = []

    def load_module() -> types.SimpleNamespace:
        return types.SimpleNamespace(VX360Gamepad=lambda: pads.append(FakePad()) or pads[-1])

    backend = VgamepadControllerBackend(module_loader=load_module)

    backend.connect()
    backend.connect()

    assert len(pads) == 1
    assert backend.connected is True


def test_set_right_stick_requires_connect() -> None:
    backend = VgamepadControllerBackend(
        module_loader=lambda: types.SimpleNamespace(
            VX360Gamepad=FakePad,
            XUSB_BUTTON=types.SimpleNamespace(XUSB_GAMEPAD_LEFT_THUMB=object()),
        )
    )
    with pytest.raises(RuntimeError, match="Controller backend is not connected"):
        backend.set_right_stick(0.1, 0.2)


@pytest.mark.parametrize("x, y", [(-1.0, 1.0), (1.0, -1.0), (0.0, 0.0)])
def test_set_right_stick_accepts_boundary_values(x: float, y: float) -> None:
    fake_pad = FakePad()
    backend = VgamepadControllerBackend(
        module_loader=lambda: types.SimpleNamespace(
            VX360Gamepad=lambda: fake_pad,
            XUSB_BUTTON=types.SimpleNamespace(XUSB_GAMEPAD_LEFT_THUMB=object()),
        )
    )

    backend.connect()
    backend.set_right_stick(x, y)

    assert fake_pad.calls == [("stick", x, y), ("update",)]


@pytest.mark.parametrize("x, y", [(-1.1, 0.0), (0.0, 1.1), (2.0, -2.0)])
def test_set_right_stick_rejects_out_of_range_values(x: float, y: float) -> None:
    fake_pad = FakePad()
    backend = VgamepadControllerBackend(
        module_loader=lambda: types.SimpleNamespace(
            VX360Gamepad=lambda: fake_pad,
            XUSB_BUTTON=types.SimpleNamespace(XUSB_GAMEPAD_LEFT_THUMB=object()),
        )
    )
    backend.connect()

    with pytest.raises(ValueError, match="Right stick values must be between -1.0 and 1.0"):
        backend.set_right_stick(x, y)
