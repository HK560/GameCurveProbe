import threading

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.services.controller_service import ControllerService


def test_cancel_neutralizes_and_blocks_later_writes() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    cancel = threading.Event()
    service.set_right_stick(0.5, 0.0, cancel)
    cancel.set()
    service.cancel_and_neutralize(cancel)
    assert backend.events[-1] == ("neutral",)
    assert service.set_right_stick(0.8, 0.0, cancel) is False


def test_close_neutralizes_before_disconnect() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    service.connect()
    service.close()
    assert backend.events[-2:] == [("neutral",), ("disconnect",)]


def test_controller_connect_is_idempotent() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    service.connect()
    assert backend.connected is True
    connect_event_count = sum(1 for ev in backend.events if ev[0] == "connect")
    assert connect_event_count == 1
    # Second connect should be a no-op
    service.connect()
    assert sum(1 for ev in backend.events if ev[0] == "connect") == 1

