import threading
import time

import pytest

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.errors import DomainError
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


def test_controller_can_be_disabled_and_reenabled() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    service.connect()

    assert service.set_enabled(False) is False
    assert backend.connected is False
    with pytest.raises(DomainError, match="Enable the ViGEmBus controller first"):
        service.acquire("measurement")

    assert service.set_enabled(True) is True
    assert backend.connected is True


def test_wake_presses_then_releases_input() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)

    service.wake("a", duration_seconds=0.01)
    time.sleep(0.05)

    assert backend.events[-2:] == [("release_wake_input", "a"), ("neutral",)]

