from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gamecurveprobe.models import CurvePoint, ProbeSessionConfig, SessionResult
from gamecurveprobe.services.motion_sampler import MotionSampler

if TYPE_CHECKING:
    from gamecurveprobe.vision.motion_estimator import MotionEstimator


class ProbeExecutionError(RuntimeError):
    """Raised when the steady probe cannot be executed."""


@dataclass(slots=True)
class PointMeasurement:
    axis: str
    direction: str
    input_value: float
    px_per_sec: float
    valid_frames: int = 0
    duplicate_frames: int = 0
    sample_duration_ms: int = 0
    stability_score: float = 0.0
    quality_label: str = "good"
    retry_used: bool = False


class SteadyProbeRunner:
    """Run the real steady-state probe loop for the selected session config."""

    _PRE_MEASUREMENT_DELAY_SECONDS = 1.0
    _LEFT_STICK_PRESS_SECONDS = 0.05
    _LEFT_STICK_RELEASE_SECONDS = 0.05
    _LEFT_STICK_PRESS_COUNT = 3
    _MIN_STABILITY_SCORE = 0.75

    def __init__(
        self,
        controller_backend_factory: Callable[[], object],
        capture_backend_factory: Callable[[], object],
        motion_sampler: MotionSampler,
        motion_estimator_factory: Callable[[], object] | None = None,
        sleep: Callable[[float], None] | None = None,
        point_values: Sequence[float] | None = None,
        disconnect_controller_on_finish: bool = True,
    ) -> None:
        self._controller_backend_factory = controller_backend_factory
        self._capture_backend_factory = capture_backend_factory
        self._motion_sampler = motion_sampler
        self._motion_estimator_factory = motion_estimator_factory or self._default_motion_estimator_factory
        self._sleep = sleep or time.sleep
        self._point_values = list(point_values) if point_values is not None else []
        self._disconnect_controller_on_finish = disconnect_controller_on_finish
        if any(value < 0.0 or value > 1.0 for value in self._point_values):
            raise ProbeExecutionError("Steady probe point_values override must stay within [0.0, 1.0].")

    def run(self, config: ProbeSessionConfig, yaw_deg_per_px: float | None = None) -> SessionResult:
        if config.window_id is None:
            raise ProbeExecutionError("Select a target window before running the steady probe.")
        if config.roi is None:
            raise ProbeExecutionError("Select an ROI before running the steady probe.")
        self._validate_config(config)

        controller = self._controller_backend_factory()
        if not controller.probe():
            raise ProbeExecutionError("vgamepad is unavailable. Install vgamepad and ViGEmBus first.")

        capture = None
        estimator = None
        notes: list[str] = []
        measurements: list[PointMeasurement] = []
        connect_attempted = False

        try:
            capture = self._capture_backend_factory()
            estimator = self._motion_estimator_factory()
            connect_attempted = True
            controller.connect()
            self._attach_capture(capture, config)
            self._prepare_measurement_start(controller)
            for axis, direction, sign in self._iter_axes(config):
                for input_value in self._resolve_point_values(config):
                    x_value = sign * input_value if axis == "x" else 0.0
                    y_value = sign * input_value if axis == "y" else 0.0
                    controller.set_right_stick(x_value, y_value)
                    self._sleep(config.settle_ms / 1000.0)

                    repeat_values: list[float] = []
                    point_samples = []
                    retry_used = False
                    for repeat_index in range(config.repeats):
                        estimator.reset()
                        sample = self._sample_motion(capture, estimator, config)
                        if sample.valid_frames > 0 and self._needs_retry(sample):
                            retry_used = True
                            estimator.reset()
                            sample = self._sample_motion(capture, estimator, config)
                        point_samples.append(sample)
                        target = self._apply_noise_floor(sample, axis, config)
                        if sample.valid_frames == 0:
                            notes.append(
                                f"{axis}/{direction} input {input_value:.4f} repeat {repeat_index + 1} had no valid frames."
                            )
                            continue
                        repeat_values.append(target)

                    px_per_sec = statistics.median(repeat_values) if repeat_values else 0.0
                    if not repeat_values:
                        notes.append(f"{axis}/{direction} input {input_value:.4f} fell back to 0.0 px/s.")
                    measurements.append(self._build_measurement(axis, direction, input_value, float(px_per_sec), point_samples, retry_used))
        finally:
            if connect_attempted:
                self._safe_cleanup(controller.neutral)
                if self._disconnect_controller_on_finish:
                    self._safe_cleanup(controller.disconnect)
            if capture is not None:
                self._safe_cleanup(capture.close)

        x_curve = self._build_curve([item for item in measurements if item.axis == "x"], yaw_deg_per_px)
        y_curve = self._build_curve([item for item in measurements if item.axis == "y"], None)
        return SessionResult(
            x_curve=x_curve,
            y_curve=y_curve,
            notes=notes,
            yaw_deg_per_px=yaw_deg_per_px,
            measurement_kind="steady_probe",
            summary=f"Steady probe measured {len(x_curve)} point{'s' if len(x_curve) != 1 else ''}.",
            metadata={
                "capture_fps_requested": config.capture_fps,
                "successful_points": sum(1 for point in x_curve if point.px_per_sec > 0.0),
                "failed_points": sum(1 for point in x_curve if point.px_per_sec <= 0.0),
                "retry_used_points": sum(1 for point in x_curve if point.input_value in {
                    item.input_value for item in measurements if item.axis == "x" and item.retry_used
                }),
                "point_diagnostics": {
                    "x": [self._measurement_diagnostic(item) for item in measurements if item.axis == "x"],
                    "y": [self._measurement_diagnostic(item) for item in measurements if item.axis == "y"],
                },
            },
        )

    def _default_motion_estimator_factory(self) -> object:
        from gamecurveprobe.vision.motion_estimator import MotionEstimator

        return MotionEstimator()

    def _iter_axes(self, config: ProbeSessionConfig) -> list[tuple[str, str, float]]:
        if "x" not in config.axes:
            return []
        return [("x", "positive", 1.0)]

    def _resolve_point_values(self, config: ProbeSessionConfig) -> list[float]:
        if self._point_values:
            return list(self._point_values)
        start = config.inner_deadzone_marker
        end = config.outer_saturation_marker
        count = max(5, config.point_count_per_half_axis)
        step = (end - start) / (count - 1)
        return [round(start + (step * index), 4) for index in range(count)]

    def _build_curve(self, measurements: list[PointMeasurement], yaw_deg_per_px: float | None) -> list[CurvePoint]:
        max_speed = max((item.px_per_sec for item in measurements), default=0.0)
        curve: list[CurvePoint] = []
        for item in measurements:
            normalized = 0.0 if max_speed == 0.0 else item.px_per_sec / max_speed
            deg_per_sec = item.px_per_sec * yaw_deg_per_px if yaw_deg_per_px is not None else None
            curve.append(
                CurvePoint(
                    axis=item.axis,
                    direction=item.direction,
                    input_value=item.input_value,
                    px_per_sec=item.px_per_sec,
                    normalized_speed=round(normalized, 4),
                    deg_per_sec=round(deg_per_sec, 4) if deg_per_sec is not None else None,
                )
            )
        return curve

    def _sample_motion(self, capture, estimator, config: ProbeSessionConfig):
        if hasattr(self._motion_sampler, "sample_filtered"):
            return self._motion_sampler.sample_filtered(
                capture,
                estimator,
                config.roi,
                config.steady_sample_ms,
                min_tracked_points=config.motion_min_tracked_points,
                min_confidence=config.motion_min_confidence,
            )
        return self._motion_sampler.sample(capture, estimator, config.roi, config.steady_sample_ms)

    def _apply_noise_floor(self, sample, axis: str, config: ProbeSessionConfig) -> float:
        raw_value = abs(sample.px_per_sec_x) if axis == "x" else abs(sample.px_per_sec_y)
        floor = config.idle_noise_floor_x if axis == "x" else config.idle_noise_floor_y
        return max(0.0, raw_value - floor)

    def _attach_capture(self, capture: object, config: ProbeSessionConfig) -> None:
        try:
            capture.attach(config.window_id, capture_fps=config.capture_fps)
        except TypeError:
            capture.attach(config.window_id)

    def _needs_retry(self, sample: object) -> bool:
        stability_score = getattr(sample, "stability_score", None)
        return (
            getattr(sample, "duplicate_frames", 0) > 0
            or (stability_score is not None and stability_score > 0.0 and stability_score < self._MIN_STABILITY_SCORE)
        )

    def _build_measurement(
        self,
        axis: str,
        direction: str,
        input_value: float,
        px_per_sec: float,
        point_samples: list[object],
        retry_used: bool,
    ) -> PointMeasurement:
        final_sample = point_samples[-1] if point_samples else None
        quality_label = "invalid"
        if final_sample is not None and getattr(final_sample, "valid_frames", 0) > 0:
            quality_label = "retry_used" if retry_used else "good"
            if getattr(final_sample, "stability_score", 1.0) < self._MIN_STABILITY_SCORE:
                quality_label = "low_confidence"
        return PointMeasurement(
            axis=axis,
            direction=direction,
            input_value=input_value,
            px_per_sec=px_per_sec,
            valid_frames=getattr(final_sample, "valid_frames", 0) if final_sample is not None else 0,
            duplicate_frames=getattr(final_sample, "duplicate_frames", 0) if final_sample is not None else 0,
            sample_duration_ms=getattr(final_sample, "sample_duration_ms", 0) if final_sample is not None else 0,
            stability_score=getattr(final_sample, "stability_score", 0.0) if final_sample is not None else 0.0,
            quality_label=quality_label,
            retry_used=retry_used,
        )

    def _measurement_diagnostic(self, measurement: PointMeasurement) -> dict[str, object]:
        return {
            "input_value": measurement.input_value,
            "valid_frames": measurement.valid_frames,
            "duplicate_frames": measurement.duplicate_frames,
            "sample_duration_ms": measurement.sample_duration_ms,
            "stability_score": measurement.stability_score,
            "quality_label": measurement.quality_label,
            "retry_used": measurement.retry_used,
        }

    def _prepare_measurement_start(self, controller: object) -> None:
        self._sleep(self._PRE_MEASUREMENT_DELAY_SECONDS)
        for _ in range(self._LEFT_STICK_PRESS_COUNT):
            controller.press_left_stick()
            self._sleep(self._LEFT_STICK_PRESS_SECONDS)
            controller.release_left_stick()
            self._sleep(self._LEFT_STICK_RELEASE_SECONDS)

    def _validate_config(self, config: ProbeSessionConfig) -> None:
        if any(axis not in {"x", "y"} for axis in config.axes):
            raise ProbeExecutionError("Unsupported axis selection. Only x and y are allowed.")
        if config.repeats <= 0:
            raise ProbeExecutionError("Probe config repeats must be greater than 0.")
        if config.settle_ms < 0:
            raise ProbeExecutionError("Probe config settle_ms must be 0 or greater.")
        if config.steady_sample_ms <= 0:
            raise ProbeExecutionError("Probe config steady_sample_ms must be greater than 0.")
        if config.point_count_per_half_axis <= 0:
            raise ProbeExecutionError("Probe config point_count_per_half_axis must be greater than 0.")
        if not 0.0 <= config.inner_deadzone_marker <= 1.0:
            raise ProbeExecutionError("Probe config inner_deadzone_marker must stay within [0.0, 1.0].")
        if not 0.0 < config.outer_saturation_marker <= 1.0:
            raise ProbeExecutionError("Probe config outer_saturation_marker must stay within (0.0, 1.0].")
        if config.outer_saturation_marker <= config.inner_deadzone_marker:
            raise ProbeExecutionError(
                "Probe config outer_saturation_marker must be greater than inner_deadzone_marker."
            )

    def _safe_cleanup(self, cleanup: Callable[[], object]) -> None:
        try:
            cleanup()
        except Exception:
            return None
