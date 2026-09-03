from __future__ import annotations

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
