from __future__ import annotations

from gamecurveprobe.backends.controller import VirtualControllerBackend


DEADZONE_CALIBRATION_STEP = 0.005
DEADZONE_TICK_SCALE = int(round(1.0 / DEADZONE_CALIBRATION_STEP))
MAX_CALIBRATED_DEADZONE_TICK = DEADZONE_TICK_SCALE - 1
MAX_CALIBRATED_DEADZONE = MAX_CALIBRATED_DEADZONE_TICK / DEADZONE_TICK_SCALE


class InnerDeadzoneCalibrationError(RuntimeError):
    """Raised when interactive inner deadzone calibration cannot proceed."""


class InnerDeadzoneCalibrationService:
    def __init__(self, controller: VirtualControllerBackend) -> None:
        self._controller = controller
        self._active = False
        self._current_deadzone_tick = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_deadzone(self) -> float:
        return self._tick_to_value(self._current_deadzone_tick)

    @property
    def current_output(self) -> float:
        output_tick = min(DEADZONE_TICK_SCALE, self._current_deadzone_tick + 1)
        return self._tick_to_value(output_tick)

    def enter(self, initial_deadzone: float) -> float:
        if not self._controller.probe():
            raise InnerDeadzoneCalibrationError("vgamepad is unavailable. Install vgamepad and ViGEmBus first.")
        try:
            self._controller.connect()
            self._active = True
            self._current_deadzone_tick = self._value_to_tick(initial_deadzone)
            self._apply_output()
        except Exception as exc:
            self._active = False
            self._safe_neutral()
            raise InnerDeadzoneCalibrationError(str(exc)) from exc
        return self.current_deadzone

    def increase(self) -> float:
        self._require_active()
        self._current_deadzone_tick = min(MAX_CALIBRATED_DEADZONE_TICK, self._current_deadzone_tick + 1)
        self._apply_output()
        return self.current_deadzone

    def decrease(self) -> float:
        self._require_active()
        self._current_deadzone_tick = max(0, self._current_deadzone_tick - 1)
        self._apply_output()
        return self.current_deadzone

    def exit(self) -> float:
        result = self.current_deadzone
        self._safe_neutral()
        self._active = False
        return result

    def _apply_output(self) -> None:
        try:
            self._controller.set_right_stick(self.current_output, 0.0)
        except Exception as exc:
            self._safe_neutral()
            self._active = False
            raise InnerDeadzoneCalibrationError(str(exc)) from exc

    def _safe_neutral(self) -> None:
        try:
            self._controller.neutral()
        except Exception:
            pass

    def _require_active(self) -> None:
        if not self._active:
            raise InnerDeadzoneCalibrationError("Inner deadzone calibration is not active.")

    @staticmethod
    def _tick_to_value(tick: int) -> float:
        return tick / DEADZONE_TICK_SCALE

    @staticmethod
    def _value_to_tick(value: float) -> int:
        tick = int(round(value * DEADZONE_TICK_SCALE))
        return max(0, min(MAX_CALIBRATED_DEADZONE_TICK, tick))
