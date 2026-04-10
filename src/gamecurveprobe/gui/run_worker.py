from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class RunWorker(QObject):
    finished = Signal(object)
    failed = Signal(Exception)

    def __init__(self, session_service, session_id: str, action: str) -> None:
        super().__init__()
        self._session_service = session_service
        self._session_id = session_id
        self._action = action

    def run_sync(self):
        action = getattr(self._session_service, self._action)
        return action(self._session_id)

    def run(self) -> None:
        try:
            session = self.run_sync()
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.finished.emit(session)
