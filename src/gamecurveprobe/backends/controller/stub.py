from __future__ import annotations

from gamecurveprobe.backends.controller.base import VirtualControllerBackend


class StubControllerBackend(VirtualControllerBackend):
    """Stub controller backend for deterministic testing and headless execution."""

    def __init__(self, can_probe: bool = True) -> None:
        self.connected = False
        self.last_input = (0.0, 0.0)
        self.can_probe = can_probe
        self.events: list[tuple[object, ...]] = []

    def probe(self) -> bool:
        self.events.append(("probe",))
        return self.can_probe

    def connect(self) -> None:
        self.connected = True
        self.events.append(("connect",))

    def set_right_stick(self, x: float, y: float) -> None:
        self.last_input = (x, y)
        self.events.append(("set_right_stick", x, y))

    def press_left_stick(self) -> None:
        self.events.append(("press_left_stick",))

    def release_left_stick(self) -> None:
        self.events.append(("release_left_stick",))

    def press_wake_input(self, input_name: str) -> None:
        self.events.append(("press_wake_input", input_name))

    def release_wake_input(self, input_name: str) -> None:
        self.events.append(("release_wake_input", input_name))

    def neutral(self) -> None:
        self.last_input = (0.0, 0.0)
        self.events.append(("neutral",))

    def disconnect(self) -> None:
        self.connected = False
        self.events.append(("disconnect",))
