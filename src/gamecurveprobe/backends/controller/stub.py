from __future__ import annotations

from gamecurveprobe.backends.controller.base import VirtualControllerBackend


class StubControllerBackend(VirtualControllerBackend):
    """Placeholder controller backend until the Windows backend is selected."""

    def __init__(self) -> None:
        self.connected = False
        self.last_input = (0.0, 0.0)

    def probe(self) -> bool:
        return False

    def connect(self) -> None:
        self.connected = True

    def set_right_stick(self, x: float, y: float) -> None:
        self.last_input = (x, y)

    def press_left_stick(self) -> None:
        return None

    def release_left_stick(self) -> None:
        return None

    def neutral(self) -> None:
        self.last_input = (0.0, 0.0)

    def disconnect(self) -> None:
        self.connected = False
