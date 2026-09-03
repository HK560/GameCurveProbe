from __future__ import annotations

from gamecurveprobe.models import (
    CurveAnalysis,
    MeasurementPoint,
    NoiseResult,
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


def test_measurement_returns_202_job_snapshot(client, auth_headers) -> None:
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
