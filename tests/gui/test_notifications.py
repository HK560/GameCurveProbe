from __future__ import annotations

from gamecurveprobe.gui.notifications import DesktopNotifier


class FakeBackend:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def show(self, title: str, message: str) -> None:
        self.messages.append((title, message))


def test_desktop_notifier_sends_message_to_backend() -> None:
    backend = FakeBackend()
    notifier = DesktopNotifier(backend=backend)

    notifier.notify("GameCurveProbe", "Steady probe started.")

    assert backend.messages == [("GameCurveProbe", "Steady probe started.")]
