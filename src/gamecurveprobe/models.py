from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from gamecurveprobe.constants import PRESETS
from gamecurveprobe.errors import DomainError


class RangeMode(StrEnum):
    ACTIVE_RANGE = "active_range"
    FULL = "full"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELING = "canceling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in {self.COMPLETED, self.FAILED, self.CANCELED}


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
class ProbeConfig:
    capture_fps: int = 120
    point_count: int = 17
    repeats: int = 2
    settle_ms: int = 300
    sample_ms: int = 700
    range_mode: RangeMode = RangeMode.ACTIVE_RANGE
    inner_deadzone: float = 0.0
    outer_deadzone: float = 1.0

    @classmethod
    def from_preset(cls, name: str) -> "ProbeConfig":
        try:
            return cls(**PRESETS[name])
        except KeyError as exc:
            raise DomainError("INVALID_PRESET", f"Unknown preset: {name}") from exc

    def validate(self) -> None:
        if not 30 <= self.capture_fps <= 240:
            raise DomainError("INVALID_CONFIG", "capture_fps must be within [30, 240].")
        if self.point_count < 5 or self.repeats < 1 or self.settle_ms < 0 or self.sample_ms <= 0:
            raise DomainError("INVALID_CONFIG", "Measurement timing and count values are invalid.")
        if not 0.0 <= self.inner_deadzone < self.outer_deadzone <= 1.0:
            raise DomainError("INVALID_CONFIG", "outer_deadzone must be greater than inner_deadzone within [0, 1].")

    def point_values(self) -> list[float]:
        start, end = (
            (0.0, 1.0) if self.range_mode is RangeMode.FULL else (self.inner_deadzone, self.outer_deadzone)
        )
        values = {
            round(start + (end - start) * i / (self.point_count - 1), 4)
            for i in range(self.point_count)
        }
        if self.range_mode is RangeMode.FULL:
            values.update({self.inner_deadzone, self.outer_deadzone})
        return sorted(values)


@dataclass(frozen=True, slots=True)
class CaptureInfo:
    window_id: int
    backend: str
    width: int
    height: int
    target_fps: int
    attached_at: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class CaptureHealth:
    is_healthy: bool
    fps: float
    duplicate_ratio: float
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class MeasurementPoint:
    input: float
    velocity_px_s: float | None
    normalized_speed: float | None
    stability: float
    valid: bool
    attempts: int


@dataclass(frozen=True, slots=True)
class NoiseResult:
    floor_x: float
    floor_y: float
    valid_frames: int
    confidence: float


@dataclass(frozen=True, slots=True)
class RoiQuality:
    score: int
    level: str
    metrics: Mapping[str, float]
    suggestions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurveAnalysis:
    curve_type: str
    confidence: float
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SessionResult:
    points: tuple[MeasurementPoint, ...] = ()
    noise: NoiseResult | None = None
    analysis: CurveAnalysis | None = None
    schema_version: int = 1
    measured_at: str = ""


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    id: str
    kind: str
    state: JobState
    progress: Mapping[str, object] | None = None
    result: object | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    id: str
    config: ProbeConfig
    roi: RoiRect | None = None
    capture: CaptureInfo | None = None
    roi_quality: RoiQuality | None = None
    last_job: JobSnapshot | None = None
    active_job: JobSnapshot | None = None
    last_result: SessionResult | None = None
