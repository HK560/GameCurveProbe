from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from gamecurveprobe.constants import MIN_ROI_SIDE
from gamecurveprobe.models import (
    CaptureInfo,
    JobSnapshot,
    JobState,
    NoiseResult,
    ProbeConfig,
    RangeMode,
    RoiQuality,
    RoiRect,
    SessionResult,
)


class StrictDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaptureAttachRequest(StrictDto):
    window_id: int
    backend: Literal["auto", "wgc", "dxcam"] = "auto"
    target_fps: int = Field(default=120, ge=30, le=240)


class RoiRequest(StrictDto):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=MIN_ROI_SIDE)
    height: int = Field(ge=MIN_ROI_SIDE)


class ConfigUpdateRequest(StrictDto):
    capture_fps: int | None = Field(default=None, ge=30, le=240)
    point_count: int | None = Field(default=None, ge=5)
    repeats: int | None = Field(default=None, ge=1)
    settle_ms: int | None = Field(default=None, ge=0)
    sample_ms: int | None = Field(default=None, gt=0)
    range_mode: RangeMode | None = None
    inner_deadzone: float | None = Field(default=None, ge=0.0, le=1.0)
    outer_deadzone: float | None = Field(default=None, ge=0.0, le=1.0)
    hotkey_enabled: bool | None = None
    hotkey_start: str | None = None
    hotkey_stop: str | None = None
    hotkey_dz_inc: str | None = None
    hotkey_dz_dec: str | None = None
    dz_target: str | None = None
    dz_step: float | None = Field(default=None, ge=0.0001, le=0.5)
    sound_enabled: bool | None = None
    wake_input: str | None = None
    auto_wake: bool | None = None
    start_countdown_s: int | None = Field(default=None, ge=0, le=30)
    horizontal_fov_deg: float | None = Field(default=None, ge=30.0, le=180.0)
    bidirectional: bool | None = None


class DeadzoneRequest(StrictDto):
    inner_deadzone: float = Field(ge=0.0, le=1.0)
    outer_deadzone: float = Field(ge=0.0, le=1.0)


class ProbeStartRequest(StrictDto):
    initial_output: float = Field(default=0.0, ge=0.0, le=1.0)
    step: float = 0.005
    direction: Literal["x_positive"] = "x_positive"


class ProbeUpdateRequest(StrictDto):
    output: float = Field(ge=0.0, le=1.0)


class JobStartRequest(StrictDto):
    range_mode: RangeMode | None = None


class ControllerStateRequest(StrictDto):
    enabled: bool


class ControllerWakeRequest(StrictDto):
    input: Literal["right_stick", "x", "y", "a", "b", "left_bumper", "right_bumper", "left_trigger", "right_trigger"]


class AudioTestRequest(StrictDto):
    sound_type: Literal["start", "stop", "complete", "test"] = "test"


class WindowItem(BaseModel):
    id: int
    title: str
    pid: int | None = None
    width: int = 0
    height: int = 0


class WindowsListResponse(BaseModel):
    windows: list[WindowItem]


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    state: JobState
    progress: dict[str, Any] | None = None
    result: Any | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    config: ProbeConfig
    roi: RoiRect | None = None
    capture: CaptureInfo | None = None
    roi_quality: RoiQuality | None = None
    last_job: JobSnapshot | None = None
    active_job: JobSnapshot | None = None
    last_result: SessionResult | None = None
    noise: NoiseResult | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str = "ok"
    controller_ready: bool = True
    controller_enabled: bool = True
