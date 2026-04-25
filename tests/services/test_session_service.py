from __future__ import annotations

from collections.abc import Callable

from gamecurveprobe.models import CurvePoint, JobState, SessionResult
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError
from gamecurveprobe.services.window_service import WindowService


class FakeRunner:
    def __init__(
        self,
        result: SessionResult | None = None,
        error: Exception | None = None,
        on_run: Callable[[object, float | None], None] | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self._on_run = on_run
        self.calls: list[tuple[object, float | None]] = []

    def run(self, config, yaw_deg_per_px: float | None = None) -> SessionResult:
        self.calls.append((config, yaw_deg_per_px))
        if self._on_run is not None:
            self._on_run(config, yaw_deg_per_px)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class FakeCalibrationRunner:
    def __init__(self, result: SessionResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[object] = []

    def run(self, config) -> SessionResult:
        self.calls.append(config)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class FakeIdleNoiseRunner:
    def __init__(self, result: SessionResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[object] = []

    def run(self, config) -> SessionResult:
        self.calls.append(config)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


def test_calibrate_yaw360_replaces_result_with_measured_x_curve() -> None:
    calibration_runner = FakeCalibrationRunner(
        result=SessionResult(
            x_curve=[CurvePoint("x", "positive", 0.5, 120.0, 1.0, 180.0)],
            y_curve=[],
            notes=["yaw calibration complete"],
            yaw_deg_per_px=None,
            measurement_kind="yaw360_calibration",
            summary="Yaw 360 calibration measured 1 point.",
            metadata={"successful_points": 1, "failed_points": 0},
        )
    )
    service = SessionService(window_service=WindowService(), calibration_runner=calibration_runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})

    updated = service.calibrate_yaw360(session.status.session_id)

    assert updated.status.state is JobState.READY
    assert updated.status.message == "Yaw calibration complete."
    assert updated.result.x_curve[0].deg_per_sec == 180.0
    assert updated.result.notes == ["yaw calibration complete"]
    assert updated.result.measurement_kind == "yaw360_calibration"
    assert updated.result.summary == "Yaw 360 calibration measured 1 point."
    assert updated.result.metadata["successful_points"] == 1
    assert len(calibration_runner.calls) == 1


def test_calibrate_yaw360_maps_probe_failures_to_failed_state() -> None:
    calibration_runner = FakeCalibrationRunner(
        error=ProbeExecutionError("Select an ROI before running yaw calibration."),
    )
    service = SessionService(window_service=WindowService(), calibration_runner=calibration_runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})

    updated = service.calibrate_yaw360(session.status.session_id)

    assert updated.status.state is JobState.FAILED
    assert updated.status.message == "Select an ROI before running yaw calibration."
    assert updated.result.notes[-1] == "Select an ROI before running yaw calibration."


def test_calibrate_idle_noise_updates_noise_band_on_session_config() -> None:
    idle_runner = FakeIdleNoiseRunner(
        result=SessionResult(
            notes=["Idle noise band calibrated: vx +/-12.0px/s, vy +/-7.0px/s from 18 valid frames."],
            summary="Idle noise calibration complete.",
            measurement_kind="idle_noise_calibration",
            metadata={"idle_noise_floor_x": 12.0, "idle_noise_floor_y": 7.0, "valid_frames": 18},
        )
    )
    service = SessionService(window_service=WindowService(), idle_noise_calibration_runner=idle_runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})

    updated = service.calibrate_idle_noise(session.status.session_id)

    assert updated.status.state is JobState.READY
    assert updated.status.message == "Idle noise calibration complete."
    assert updated.config.idle_noise_floor_x == 12.0
    assert updated.config.idle_noise_floor_y == 7.0
    assert updated.result.notes[-1].startswith("Idle noise band calibrated:")
    assert len(idle_runner.calls) == 1


def test_run_steady_replaces_result_with_x_positive_only_runner_output() -> None:
    runner = FakeRunner(
        result=SessionResult(
            x_curve=[CurvePoint("x", "positive", 0.5, 120.0, 1.0, 12.0)],
            y_curve=[],
            notes=["real measurement"],
            yaw_deg_per_px=0.1,
            measurement_kind="steady_probe",
            summary="Steady probe measured 1 point.",
        )
    )
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})
    session.result.yaw_deg_per_px = 0.1

    updated = service.run_steady(session.status.session_id)

    assert updated.status.state is JobState.COMPLETED
    assert updated.result.notes == ["real measurement"]
    assert updated.result.measurement_kind == "steady_probe"
    assert updated.result.summary == "Steady probe measured 1 point."
    assert [point.axis for point in updated.result.x_curve] == ["x"]
    assert updated.result.y_curve == []
    assert updated.result.x_curve[0].px_per_sec == 120.0
    assert runner.calls
    assert runner.calls[0][1] == 0.1


def test_run_steady_snapshots_yaw_before_runner_execution() -> None:
    service: SessionService | None = None

    def mutate_session(_, __) -> None:
        assert service is not None
        session = service.get_session(session_id)
        session.result.yaw_deg_per_px = 0.5

    runner = FakeRunner(
        result=SessionResult(notes=["real measurement"], yaw_deg_per_px=0.1, y_curve=[]),
        on_run=mutate_session,
    )
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})
    session_id = session.status.session_id
    session.result.yaw_deg_per_px = 0.1

    service.run_steady(session_id)

    assert runner.calls[0][1] == 0.1


def test_run_steady_maps_probe_failures_to_failed_state() -> None:
    runner = FakeRunner(error=ProbeExecutionError("vgamepad is unavailable. Install vgamepad and ViGEmBus first."))
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})

    updated = service.run_steady(session.status.session_id)

    assert updated.status.state is JobState.FAILED
    assert "vgamepad is unavailable" in updated.status.message
    assert updated.result.notes[-1] == "vgamepad is unavailable. Install vgamepad and ViGEmBus first."


def test_run_steady_maps_unexpected_failures_to_failed_state() -> None:
    runner = FakeRunner(error=RuntimeError("capture backend exploded"))
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})

    updated = service.run_steady(session.status.session_id)

    assert updated.status.state is JobState.FAILED
    assert updated.status.message == "RuntimeError: capture backend exploded"
    assert updated.result.notes[-1] == "Unexpected steady probe failure (RuntimeError): capture backend exploded"


def test_run_steady_returns_pre_canceled_session_without_running_runner() -> None:
    runner = FakeRunner(
        result=SessionResult(notes=["real measurement"], yaw_deg_per_px=0.1, y_curve=[]),
    )
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})
    service.cancel(session.status.session_id)

    updated = service.run_steady(session.status.session_id)

    assert updated.status.state is JobState.CANCELED
    assert updated.status.message == "Session canceled."
    assert runner.calls == []


def test_run_steady_preserves_canceled_state_when_runner_finishes() -> None:
    service: SessionService | None = None

    def cancel_session(_, __) -> None:
        assert service is not None
        service.cancel(session_id)

    runner = FakeRunner(
        result=SessionResult(notes=["real measurement"], yaw_deg_per_px=0.1, y_curve=[]),
        on_run=cancel_session,
    )
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})
    session_id = session.status.session_id

    updated = service.run_steady(session_id)

    assert updated.status.state is JobState.CANCELED
    assert updated.status.message == "Session canceled."


def test_run_steady_preserves_canceled_state_when_runner_fails() -> None:
    service: SessionService | None = None

    def cancel_session(_, __) -> None:
        assert service is not None
        service.cancel(session_id)

    runner = FakeRunner(
        error=RuntimeError("capture backend exploded"),
        on_run=cancel_session,
    )
    service = SessionService(window_service=WindowService(), steady_probe_runner=runner)
    session = service.create_session({"window_id": 123, "roi": {"x": 1, "y": 2, "width": 80, "height": 80}})
    session_id = session.status.session_id

    updated = service.run_steady(session_id)

    assert updated.status.state is JobState.CANCELED
    assert updated.status.message == "Session canceled."


def test_export_session_writes_only_x_axis_rows(tmp_path) -> None:
    service = SessionService(window_service=WindowService())
    session = service.create_session({"window_id": 123})
    session.result = SessionResult(
        x_curve=[CurvePoint("x", "positive", 0.25, 100.0, 0.30, 10.0)],
        y_curve=[],
        notes=["measured"],
        yaw_deg_per_px=0.1,
        measurement_kind="yaw360_calibration",
        summary="Yaw 360 calibration measured 1 point.",
        metadata={"successful_points": 1, "failed_points": 0},
    )

    exported = service.export_session(session.status.session_id, str(tmp_path))

    import csv
    import json

    with open(exported["raw_samples_csv"], newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))
    with open(exported["session_meta_json"], encoding="utf-8") as handle:
        meta = json.load(handle)

    assert raw_rows == [
        {
            "axis": "x",
            "direction": "positive",
            "input_value": "0.25",
            "px_per_sec": "100.0",
            "normalized_speed": "0.3",
            "deg_per_sec": "10.0",
            "measurement_kind": "yaw360_calibration",
        }
    ]
    assert meta["result"]["y_curve"] == []
    assert meta["result"]["measurement_kind"] == "yaw360_calibration"
    assert meta["result"]["summary"] == "Yaw 360 calibration measured 1 point."
    assert meta["result"]["metadata"]["successful_points"] == 1


def test_export_session_writes_controllermeta_curve_json(tmp_path) -> None:
    service = SessionService(window_service=WindowService())
    session = service.create_session({"window_id": 123})
    session.result = SessionResult(
        x_curve=[
            CurvePoint("x", "positive", 0.25, 100.0, 0.30, 10.0),
            CurvePoint("x", "positive", 0.75, 250.0, 0.80, 20.0),
        ],
        y_curve=[],
        notes=["measured"],
        measurement_kind="steady_probe",
        summary="Steady probe measured 2 points.",
    )

    exported = service.export_session(session.status.session_id, str(tmp_path))

    import json

    with open(exported["controller_meta_curve_json"], encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["identifier"] == "ControllerMeta"
    assert payload["exportKind"] == "curve_transfer"
    assert payload["itemCount"] == 1
    assert payload["items"][0]["note"] == "Steady probe measured 2 points."

    curve = payload["items"][0]["curve"]
    assert curve["kind"] == "polyline"
    assert curve["sourceMeta"]["kind"] == "conversion"
    assert curve["points"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 25.0, "y": 37.5},
        {"x": 75.0, "y": 100.0},
        {"x": 100.0, "y": 100.0},
    ]
    assert curve["basePoints"] == curve["points"]


def test_export_session_writes_controllermeta_fallback_line_when_no_positive_x_curve(tmp_path) -> None:
    service = SessionService(window_service=WindowService())
    session = service.create_session({"window_id": 123})
    session.result = SessionResult(
        x_curve=[CurvePoint("x", "negative", 0.50, 120.0, 0.60, 12.0)],
        y_curve=[CurvePoint("y", "positive", 0.50, 80.0, 0.40, None)],
        measurement_kind="steady_probe",
        summary="Steady probe measured fallback.",
    )

    exported = service.export_session(session.status.session_id, str(tmp_path))

    import json

    with open(exported["controller_meta_curve_json"], encoding="utf-8") as handle:
        payload = json.load(handle)

    curve = payload["items"][0]["curve"]
    assert curve["points"] == [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 100.0}]
    assert curve["basePoints"] == curve["points"]
