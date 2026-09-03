from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from gamecurveprobe.backends.controller.base import VirtualControllerBackend


def _load_vgamepad() -> ModuleType:
    import vgamepad

    return vgamepad


class VgamepadControllerBackend(VirtualControllerBackend):
    """Virtual Xbox 360 controller backend backed by vgamepad."""

    _BUTTONS = {
        "right_stick": "XUSB_GAMEPAD_RIGHT_THUMB",
        "x": "XUSB_GAMEPAD_X",
        "y": "XUSB_GAMEPAD_Y",
        "a": "XUSB_GAMEPAD_A",
        "b": "XUSB_GAMEPAD_B",
        "left_bumper": "XUSB_GAMEPAD_LEFT_SHOULDER",
        "right_bumper": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    }

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

    def press_wake_input(self, input_name: str) -> None:
        if self._gamepad is None:
            raise RuntimeError("Controller backend is not connected.")
        if input_name == "left_trigger":
            self._gamepad.left_trigger(value=255)
        elif input_name == "right_trigger":
            self._gamepad.right_trigger(value=255)
        else:
            self._gamepad.press_button(button=getattr(self._module_loader().XUSB_BUTTON, self._BUTTONS[input_name]))
        self._gamepad.update()

    def release_wake_input(self, input_name: str) -> None:
        if self._gamepad is None:
            return
        if input_name == "left_trigger":
            self._gamepad.left_trigger(value=0)
        elif input_name == "right_trigger":
            self._gamepad.right_trigger(value=0)
        else:
            self._gamepad.release_button(button=getattr(self._module_loader().XUSB_BUTTON, self._BUTTONS[input_name]))
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
