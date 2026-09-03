from __future__ import annotations

from gamecurveprobe.models import (
    CurveAnalysis,
    MeasurementPoint,
    NoiseResult,
    SessionResult,
)
from gamecurveprobe.services.export_service import ExportService

RESULT = SessionResult(
    points=(
        MeasurementPoint(
            input=0.0,
            velocity_px_s=0.0,
            normalized_speed=0.0,
            stability=1.0,
            valid=True,
            attempts=1,
        ),
        MeasurementPoint(
            input=0.5,
            velocity_px_s=50.0,
            normalized_speed=0.5,
            stability=0.9,
            valid=True,
            attempts=1,
        ),
        MeasurementPoint(
            input=1.0,
            velocity_px_s=100.0,
            normalized_speed=1.0,
            stability=0.95,
            valid=True,
            attempts=1,
        ),
    ),
    noise=NoiseResult(floor_x=0.5, floor_y=0.2, valid_frames=30, confidence=0.9),
    analysis=CurveAnalysis(curve_type="linear", confidence=0.98),
    schema_version=1,
    measured_at="2026-09-03T15:00:00Z",
)


def test_schema_one_round_trip_and_csv_header() -> None:
    service = ExportService()
    json_bytes = service.export_json(RESULT)
    restored = service.import_json(json_bytes)
    assert restored == RESULT
    csv_text = service.export_csv(RESULT)
    assert csv_text.splitlines()[0] == "Input,Velocity_px_s,Normalized_Ratio,Stability,Valid,Attempts"
