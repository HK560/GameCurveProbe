from __future__ import annotations

from gamecurveprobe.models import (
    CaptureInfo,
    CurveAnalysis,
    MeasurementPoint,
    NoiseResult,
    RoiRect,
    SessionResult,
)


def test_get_windows(client, auth_headers) -> None:
    response = client.get("/api/windows", headers=auth_headers)
    assert response.status_code == 200
    assert "windows" in response.json()


def test_session_config_update(client, auth_headers) -> None:
    response = client.put("/api/session/config", headers=auth_headers, json={"point_count": 33})
    assert response.status_code == 200
    assert response.json()["config"]["point_count"] == 33


def test_measurement_returns_202_job_snapshot(client, auth_headers, context) -> None:
    context.session.update_capture(context.capture.attach(1, "dxcam", 120))
    context.session.update_roi(RoiRect(0, 0, 100, 100))
    response = client.post("/api/jobs/measurement", headers=auth_headers, json={})
    assert response.status_code == 202
    data = response.json()
    assert data["state"] in {"queued", "running"}
    assert data["kind"] == "measurement"


def test_export_is_download_not_path_write(client, auth_headers, context) -> None:
    context.session.set_last_result(
        SessionResult(
            points=(
                MeasurementPoint(
                    input=0.0,
                    velocity_px_s=0.0,
                    normalized_speed=0.0,
                    stability=1.0,
                    valid=True,
                    attempts=1,
                ),
            ),
            noise=NoiseResult(floor_x=0.1, floor_y=0.1, valid_frames=10, confidence=0.8),
            analysis=CurveAnalysis(curve_type="linear", confidence=0.9),
            schema_version=1,
            measured_at="2026-09-03T15:00:00Z",
        )
    )
    response = client.get("/api/result/export?format=csv", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "Input,Velocity_px_s" in response.text


def test_import_does_not_replace_latest_measured_result(client, auth_headers, context) -> None:
    measured = SessionResult(
        points=(MeasurementPoint(0.5, 10.0, 1.0, 1.0, True, 1),),
        schema_version=1,
        measured_at="measured",
    )
    imported = SessionResult(
        points=(MeasurementPoint(0.5, 20.0, 1.0, 1.0, True, 1),),
        schema_version=1,
        measured_at="imported",
    )
    context.session.set_last_result(measured)

    response = client.post(
        "/api/result/import",
        headers=auth_headers,
        content=context.export.export_json(imported),
    )

    assert response.status_code == 200
    assert response.json()["result"]["measured_at"] == "imported"
    assert context.session.snapshot().last_result == measured


def test_design_contract_query_and_detach_routes(client, auth_headers, context) -> None:
    context.session.update_capture(CaptureInfo(1, "wgc", 640, 480, 120))

    assert client.get("/api/session/config", headers=auth_headers).status_code == 200
    assert client.put(
        "/api/session/deadzones",
        headers=auth_headers,
        json={"inner_deadzone": 0.1, "outer_deadzone": 0.9},
    ).status_code == 200
    assert client.post("/api/capture/detach", headers=auth_headers).status_code == 200
    assert context.session.snapshot().capture is None


def test_result_endpoint_returns_latest_measurement(client, auth_headers, context) -> None:
    result = SessionResult(schema_version=1, measured_at="measured")
    context.session.set_last_result(result)

    response = client.get("/api/result", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["measured_at"] == "measured"


def test_health_reports_real_controller_readiness(client, context, monkeypatch) -> None:
    monkeypatch.setattr(type(context.controller), "is_available", lambda self: False, raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["controller_ready"] is False


def test_quit_endpoint_accepts_an_authenticated_local_request(client, auth_headers, context) -> None:
    shutdown_requested = []
    context.shutdown_callback = lambda: shutdown_requested.append(True)

    response = client.post("/api/app/quit", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"status": "shutting_down"}
    assert shutdown_requested == [True]


def test_session_exposes_latest_idle_noise_calibration(client, auth_headers, context) -> None:
    context.session.set_noise(NoiseResult(1.0, 2.0, 20, 0.8))

    response = client.get("/api/session", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["noise"]["floor_x"] == 1.0
