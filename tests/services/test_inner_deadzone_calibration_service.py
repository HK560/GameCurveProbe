from __future__ import annotations

import pytest

from gamecurveprobe.services.inner_deadzone_calibration_service import (
    DEADZONE_CALIBRATION_STEP,
    InnerDeadzoneCalibrationError,
    InnerDeadzoneCalibrationService,
)


class FakeController:
    def __init__(self) -> None:
        self.connected = False
        self.events: list[tuple[str, float, float] | tuple[str]] = []

    def probe(self) -> bool:
        return True

    def connect(self) -> None:
        self.connected = True
        self.events.append(("connect",))

    def set_right_stick(self, x: float, y: float) -> None:
        self.events.append(("stick", x, y))

    def neutral(self) -> None:
        self.events.append(("neutral",))


def test_service_enters_from_existing_deadzone_and_outputs_next_tick() -> None:
    controller = FakeController()
    service = InnerDeadzoneCalibrationService(controller)

    deadzone = service.enter(0.120)

    assert deadzone == pytest.approx(0.120)
    assert service.current_deadzone == pytest.approx(0.120)
    assert service.current_output == pytest.approx(0.125)
    assert service.is_active is True
    assert controller.events == [("connect",), ("stick", 0.125, 0.0)]


def test_service_increase_and_decrease_move_in_fixed_steps() -> None:
    controller = FakeController()
    service = InnerDeadzoneCalibrationService(controller)
    service.enter(0.000)

    assert service.increase() == pytest.approx(DEADZONE_CALIBRATION_STEP)
    assert service.current_output == pytest.approx(0.010)
    assert service.decrease() == pytest.approx(0.000)
    assert service.current_output == pytest.approx(0.005)


def test_service_clamps_at_bounds() -> None:
    controller = FakeController()
    service = InnerDeadzoneCalibrationService(controller)

    assert service.enter(1.0) == pytest.approx(0.995)
    assert service.current_output == pytest.approx(1.0)
    assert service.decrease() == pytest.approx(0.990)


def test_service_exit_neutralizes_controller_and_returns_value() -> None:
    controller = FakeController()
    service = InnerDeadzoneCalibrationService(controller)
    service.enter(0.235)

    result = service.exit()

    assert result == pytest.approx(0.235)
    assert service.is_active is False
    assert controller.events[-1] == ("neutral",)


def test_service_raises_when_probe_fails() -> None:
    controller = FakeController()
    controller.probe = lambda: False  # type: ignore[method-assign]
    service = InnerDeadzoneCalibrationService(controller)

    with pytest.raises(InnerDeadzoneCalibrationError, match="vgamepad"):
        service.enter(0.0)
