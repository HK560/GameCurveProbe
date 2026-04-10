from __future__ import annotations

from PySide6.QtWidgets import QApplication

from gamecurveprobe.gui.run_worker import RunWorker
from gamecurveprobe.models import CurvePoint, JobState, SessionResult


class FakeSessionService:
    def __init__(self, result=None, error=None) -> None:
        self._result = result
        self._error = error
        self.calls: list[str] = []

    def run_steady(self, session_id: str):
        self.calls.append(session_id)
        if self._error is not None:
            raise self._error
        return self._result

    def calibrate_yaw360(self, session_id: str):
        self.calls.append(f"calibrate:{session_id}")
        if self._error is not None:
            raise self._error
        return self._result

    def calibrate_idle_noise(self, session_id: str):
        self.calls.append(f"idle:{session_id}")
        if self._error is not None:
            raise self._error
        return self._result


def test_run_worker_executes_selected_service_method_and_returns_session() -> None:
    session = type(
        "Session",
        (),
        {
            "status": type("Status", (), {"state": JobState.COMPLETED, "message": "done"})(),
            "result": SessionResult(x_curve=[CurvePoint("x", "positive", 0.5, 120.0, 1.0, 12.0)], y_curve=[]),
        },
    )()
    service = FakeSessionService(result=session)
    worker = RunWorker(session_service=service, session_id="abc123", action="run_steady")

    result = worker.run_sync()

    assert service.calls == ["abc123"]
    assert result.status.state is JobState.COMPLETED
    assert result.result.y_curve == []


def test_run_worker_supports_calibration_action() -> None:
    session = type(
        "Session",
        (),
        {
            "status": type("Status", (), {"state": JobState.READY, "message": "done"})(),
            "result": SessionResult(x_curve=[CurvePoint("x", "positive", 0.5, 120.0, 1.0, 180.0)], y_curve=[]),
        },
    )()
    service = FakeSessionService(result=session)
    worker = RunWorker(session_service=service, session_id="abc123", action="calibrate_yaw360")

    result = worker.run_sync()

    assert service.calls == ["calibrate:abc123"]
    assert result.result.x_curve[0].deg_per_sec == 180.0


def test_run_worker_supports_idle_noise_calibration_action() -> None:
    session = type(
        "Session",
        (),
        {
            "status": type("Status", (), {"state": JobState.READY, "message": "done"})(),
            "result": SessionResult(notes=["idle noise calibrated"]),
        },
    )()
    service = FakeSessionService(result=session)
    worker = RunWorker(session_service=service, session_id="abc123", action="calibrate_idle_noise")

    result = worker.run_sync()

    assert service.calls == ["idle:abc123"]
    assert result.result.notes == ["idle noise calibrated"]


def test_run_worker_propagates_exceptions() -> None:
    service = FakeSessionService(error=RuntimeError("boom"))
    worker = RunWorker(session_service=service, session_id="abc123", action="run_steady")

    try:
        worker.run_sync()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected RuntimeError to be raised")


def test_run_worker_emits_finished_signal() -> None:
    app = QApplication.instance() or QApplication([])
    session = type(
        "Session",
        (),
        {
            "status": type("Status", (), {"state": JobState.COMPLETED, "message": "done"})(),
            "result": SessionResult(x_curve=[CurvePoint("x", "positive", 0.5, 120.0, 1.0, 12.0)], y_curve=[]),
        },
    )()
    service = FakeSessionService(result=session)
    worker = RunWorker(session_service=service, session_id="abc123", action="run_steady")
    received: list[object] = []

    worker.finished.connect(received.append)
    worker.run()
    app.processEvents()

    assert received == [session]
