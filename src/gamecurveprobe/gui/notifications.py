from __future__ import annotations

from PySide6.QtWidgets import QStyle, QSystemTrayIcon


class DesktopNotifier:
    def __init__(self, backend=None) -> None:
        self._backend = backend

    def notify(self, title: str, message: str) -> None:
        if self._backend is None:
            return
        self._backend.show(title, message)


class QtSystemTrayBackend:
    def __init__(self, parent) -> None:
        icon = parent.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray_icon = QSystemTrayIcon(icon, parent)
        self._tray_icon.setToolTip("GameCurveProbe")
        self._tray_icon.show()

    def show(self, title: str, message: str) -> None:
        self._tray_icon.showMessage(title, message)

    def close(self) -> None:
        self._tray_icon.hide()
