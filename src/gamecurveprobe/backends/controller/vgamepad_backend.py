from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from gamecurveprobe.backends.controller.base import VirtualControllerBackend


def _load_vgamepad() -> ModuleType:
    import vgamepad

    return vgamepad


class VgamepadControllerBackend(VirtualControllerBackend):
    """Virtual Xbox 360 controller backend backed by vgamepad."""

    def __init__(self, module_loader: Callable[[], ModuleType] | None = None) -> None:
        self._module_loader = module_loader or _load_vgamepad
        self._gamepad = None
        self.connected = False

    def probe(self) -> bool:
        try:
            self._module_loader()
        except ImportError:
            return False
        return True

    def connect(self) -> None:
        if self.connected and self._gamepad is not None:
            return
        module = self._module_loader()
        self._gamepad = module.VX360Gamepad()
        self.connected = True

    def set_right_stick(self, x: float, y: float) -> None:
        if self._gamepad is None:
            raise RuntimeError("Controller backend is not connected.")
        self._validate_axis(x)
        self._validate_axis(y)
        self._gamepad.right_joystick_float(x_value_float=float(x), y_value_float=float(y))
        self._gamepad.update()

    def press_left_stick(self) -> None:
        if self._gamepad is None:
            raise RuntimeError("Controller backend is not connected.")
        module = self._module_loader()
        self._gamepad.press_button(button=module.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
        self._gamepad.update()

    def release_left_stick(self) -> None:
        if self._gamepad is None:
            raise RuntimeError("Controller backend is not connected.")
        module = self._module_loader()
        self._gamepad.release_button(button=module.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
        self._gamepad.update()

    def neutral(self) -> None:
        if self._gamepad is None:
            return
        self._gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
        self._gamepad.update()

    def disconnect(self) -> None:
        self.neutral()
        self._gamepad = None
        self.connected = False

    @staticmethod
    def _validate_axis(value: float) -> None:
        if not -1.0 <= value <= 1.0:
            raise ValueError("Right stick values must be between -1.0 and 1.0.")
