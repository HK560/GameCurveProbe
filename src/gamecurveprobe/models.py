from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class JobState(StrEnum):
    IDLE = "idle"
    READY = "ready"
    CALIBRATING = "calibrating"
    RUNNING_STEADY = "running_steady"
    RUNNING_DYNAMIC = "running_dynamic"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(slots=True)
class WindowInfo:
    window_id: int
    title: str
    process_id: int | None = None
    process_name: str | None = None
    rect: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RoiRect:
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class ProbeSessionConfig:
    window_id: int | None = None
    capture_fps: int = 120
    roi: RoiRect | None = None
    axes: list[str] = field(default_factory=lambda: ["x"])
    point_count_per_half_axis: int = 17
    settle_ms: int = 300
    steady_sample_ms: int = 700
    yaw360_timeout_ms: int = 4000
    repeats: int = 2
    dynamic_enabled: bool = True
    step_levels: list[float] = field(default_factory=lambda: [0.25, 0.5, 0.75, 1.0])
    ramp_ms: int = 250
    inner_deadzone_marker: float = 0.0
    outer_saturation_marker: float = 1.0
    live_smoothing_factor: float = 0.65
    motion_min_tracked_points: int = 8
    motion_min_confidence: float = 0.35
    idle_noise_sample_ms: int = 1200
    idle_noise_floor_x: float = 0.0
    idle_noise_floor_y: float = 0.0
    idle_noise_band_percentile: float = 0.9
    push_live_preview_during_run: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ProbeSessionConfig":
        payload = payload or {}
        roi_payload = payload.get("roi")
        roi = RoiRect(**roi_payload) if roi_payload else None
        legacy_sample_ms = payload.get("sample_ms")
        return cls(
            window_id=payload.get("window_id"),
            capture_fps=payload.get("capture_fps", 120),
            roi=roi,
            axes=list(payload.get("axes", ["x"])),
            point_count_per_half_axis=payload.get("point_count_per_half_axis", 17),
            settle_ms=payload.get("settle_ms", 300),
            steady_sample_ms=payload.get("steady_sample_ms", legacy_sample_ms if legacy_sample_ms is not None else 700),
            yaw360_timeout_ms=payload.get(
                "yaw360_timeout_ms", legacy_sample_ms if legacy_sample_ms is not None else 4000
            ),
            repeats=payload.get("repeats", 2),
            dynamic_enabled=payload.get("dynamic_enabled", True),
            step_levels=list(payload.get("step_levels", [0.25, 0.5, 0.75, 1.0])),
            ramp_ms=payload.get("ramp_ms", 250),
            inner_deadzone_marker=payload.get("inner_deadzone_marker", 0.0),
            outer_saturation_marker=payload.get("outer_saturation_marker", 1.0),
            live_smoothing_factor=payload.get("live_smoothing_factor", 0.65),
            motion_min_tracked_points=payload.get("motion_min_tracked_points", 8),
            motion_min_confidence=payload.get("motion_min_confidence", 0.35),
            idle_noise_sample_ms=payload.get("idle_noise_sample_ms", 1200),
            idle_noise_floor_x=payload.get("idle_noise_floor_x", 0.0),
            idle_noise_floor_y=payload.get("idle_noise_floor_y", 0.0),
            idle_noise_band_percentile=payload.get("idle_noise_band_percentile", 0.9),
            push_live_preview_during_run=payload.get("push_live_preview_during_run", False),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.roi is not None:
            data["roi"] = self.roi.to_dict()
        return data


@dataclass(slots=True)
class CurvePoint:
    axis: str
    direction: str
    input_value: float
    px_per_sec: float
    normalized_speed: float
    deg_per_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionResult:
    x_curve: list[CurvePoint] = field(default_factory=list)
    y_curve: list[CurvePoint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    yaw_deg_per_px: float | None = None
    measurement_kind: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_curve": [point.to_dict() for point in self.x_curve],
            "y_curve": [point.to_dict() for point in self.y_curve],
            "notes": self.notes,
            "yaw_deg_per_px": self.yaw_deg_per_px,
            "measurement_kind": self.measurement_kind,
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class SessionStatus:
    session_id: str
    state: JobState = JobState.IDLE
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    message: str = "Waiting for configuration."

    def touch(self, state: JobState | None = None, message: str | None = None) -> None:
        self.updated_at = datetime.now(UTC).isoformat()
        if state is not None:
            self.state = state
        if message is not None:
            self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message": self.message,
        }


@dataclass(slots=True)
class ProbeSession:
    config: ProbeSessionConfig = field(default_factory=ProbeSessionConfig)
    status: SessionStatus = field(default_factory=lambda: SessionStatus(session_id=new_session_id()))
    result: SessionResult = field(default_factory=SessionResult)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "status": self.status.to_dict(),
            "result": self.result.to_dict(),
        }


def new_session_id() -> str:
    return uuid4().hex[:10]
