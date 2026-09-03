from __future__ import annotations

import pytest

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.deadzone_probe_service import DeadzoneProbeService


class FakeClock:
    def __init__(self) -> None:
        self.time = 100.0

    def __call__(self) -> float:
        return self.time

    def advance(self, dt: float) -> None:
        self.time += dt


def test_expired_probe_is_neutralized() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    clock = FakeClock()
    service = DeadzoneProbeService(controller, clock=clock, lease_seconds=2.0)
    service.start(0.05, 0.005)
    clock.advance(2.01)
    service.expire_if_needed()
    assert backend.events[-1] == ("neutral",)


def test_probe_connects_controller_before_first_output() -> None:
    class StrictControllerBackend(StubControllerBackend):
        def set_right_stick(self, x: float, y: float) -> None:
            if not self.connected:
                raise RuntimeError("controller is not connected")
            super().set_right_stick(x, y)

    backend = StrictControllerBackend()
    service = DeadzoneProbeService(ControllerService(backend))

    service.start(0.05, 0.005)

    assert ("connect",) in backend.events
    service.close()


def test_controller_resource_rejects_probe_during_measurement() -> None:
    controller = ControllerService(StubControllerBackend())
    controller.acquire("measurement")
    service = DeadzoneProbeService(controller)

    try:
        with pytest.raises(Exception, match="resource"):
            service.start(0.05, 0.005)
    finally:
        controller.release("measurement")
        service.close()


def test_controller_resource_rejects_duplicate_owner_acquisition() -> None:
    controller = ControllerService(StubControllerBackend())
    controller.acquire("measurement")

    try:
        with pytest.raises(Exception, match="resource"):
            controller.acquire("measurement")
    finally:
        controller.release("measurement")
