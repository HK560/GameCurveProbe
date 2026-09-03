from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import (
    CurveAnalysis,
    MeasurementPoint,
    NoiseResult,
    SessionResult,
)


class MeasurementPointDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: float = Field(ge=0.0, le=1.0)
    velocity_px_s: float | None = None
    normalized_speed: float | None = None
    stability: float = Field(ge=0.0, le=1.0)
    valid: bool
    attempts: int = Field(ge=1)


class NoiseResultDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    floor_x: float
    floor_y: float
    valid_frames: int
    confidence: float


class CurveAnalysisDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    curve_type: str
    confidence: float
    metrics: dict[str, float] = Field(default_factory=dict)


class ResultDocumentDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    measured_at: str = ""
    points: list[MeasurementPointDto]
    noise: NoiseResultDto | None = None
    analysis: CurveAnalysisDto | None = None


class ExportService:
    """Serialize and validate session results for JSON and CSV."""

    def export_json(self, result: SessionResult) -> bytes:
        data = {
            "schema_version": result.schema_version,
            "measured_at": result.measured_at,
            "points": [
                {
                    "input": p.input,
                    "velocity_px_s": p.velocity_px_s,
                    "normalized_speed": p.normalized_speed,
                    "stability": p.stability,
                    "valid": p.valid,
                    "attempts": p.attempts,
                }
                for p in result.points
            ],
            "noise": (
                {
                    "floor_x": result.noise.floor_x,
                    "floor_y": result.noise.floor_y,
                    "valid_frames": result.noise.valid_frames,
                    "confidence": result.noise.confidence,
                }
                if result.noise is not None
                else None
            ),
            "analysis": (
                {
                    "curve_type": result.analysis.curve_type,
                    "confidence": result.analysis.confidence,
                    "metrics": dict(result.analysis.metrics),
                }
                if result.analysis is not None
                else None
            ),
        }
        return json.dumps(data, indent=2).encode("utf-8")

    def import_json(self, payload: bytes) -> SessionResult:
        if len(payload) > 5 * 1024 * 1024:
            raise DomainError("IMPORT_TOO_LARGE", "Result JSON exceeds 5 MiB.")

        try:
            raw = json.loads(payload)
        except Exception as exc:
            raise DomainError("INVALID_JSON", f"Invalid JSON format: {exc}") from exc

        schema_version = raw.get("schema_version")
        if schema_version != 1:
            raise DomainError("UNSUPPORTED_SCHEMA_VERSION", f"Unsupported schema version: {schema_version}. Only version 1 is supported.")

        try:
            doc = ResultDocumentDto.model_validate(raw)
        except Exception as exc:
            raise DomainError("INVALID_RESULT_SCHEMA", f"Invalid result schema: {exc}") from exc

        points = tuple(
            MeasurementPoint(
                input=p.input,
                velocity_px_s=p.velocity_px_s,
                normalized_speed=p.normalized_speed,
                stability=p.stability,
                valid=p.valid,
                attempts=p.attempts,
            )
            for p in doc.points
        )

        noise = (
            NoiseResult(
                floor_x=doc.noise.floor_x,
                floor_y=doc.noise.floor_y,
                valid_frames=doc.noise.valid_frames,
                confidence=doc.noise.confidence,
            )
            if doc.noise is not None
            else None
        )

        analysis = (
            CurveAnalysis(
                curve_type=doc.analysis.curve_type,
                confidence=doc.analysis.confidence,
                metrics=doc.analysis.metrics,
            )
            if doc.analysis is not None
            else None
        )

        return SessionResult(
            points=points,
            noise=noise,
            analysis=analysis,
            schema_version=doc.schema_version,
            measured_at=doc.measured_at,
        )

    def export_csv(self, result: SessionResult) -> str:
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["Input", "Velocity_px_s", "Normalized_Ratio", "Stability", "Valid", "Attempts"])

        for p in result.points:
            writer.writerow([
                p.input,
                p.velocity_px_s if p.velocity_px_s is not None else "",
                p.normalized_speed if p.normalized_speed is not None else "",
                p.stability,
                p.valid,
                p.attempts,
            ])

        return output.getvalue()
