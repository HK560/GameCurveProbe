from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from statistics import median
from typing import Any

from gamecurveprobe.constants import MIN_SAMPLE_VALID_FRAMES, MIN_TRACKED_POINTS, MIN_TRACKING_CONFIDENCE
from gamecurveprobe.errors import DomainError, JobCanceled
from gamecurveprobe.models import MeasurementPoint, NoiseResult, ProbeConfig, RoiRect, SessionResult
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.motion_sampler import MotionSampler
from gamecurveprobe.vision.motion_estimator import MotionEstimator


class MeasurementRunner:
    """Run cancellable steady-state measurement across configured probe points."""

    def __init__(
        self,
        controller: ControllerService,
        capture_factory: Callable[[], Any],
        estimator_factory: Callable[[], Any] | None = None,
        motion_sampler: MotionSampler | None = None,
        roi: RoiRect | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._controller = controller
        self._capture_factory = capture_factory
        self._estimator_factory = estimator_factory or MotionEstimator
        self._sampler = motion_sampler or MotionSampler()
        self._roi = roi
        self._sleep = sleep

    def run(
        self,
        config: ProbeConfig,
        cancel_event: threading.Event,
        publish: Callable[[Mapping[str, object]], None],
        *,
        roi: RoiRect | None = None,
        noise: NoiseResult | None = None,
    ) -> SessionResult:
        self._check_cancel(cancel_event)
        capture = self._capture_factory()
        estimator = self._estimator_factory()
        selected_roi = roi or self._roi
        if selected_roi is None:
            raise DomainError("ROI_REQUIRED", "Select an ROI before starting measurement.")
        values = config.point_values()
        raw_points: list[MeasurementPoint] = []

        publish({
            "phase": "stage_start",
            "total_points": len(values),
            "current_point": 0,
            "input_value": 0.0,
            "range_mode": config.range_mode,
            "settle_ms": config.settle_ms,
            "sample_ms": config.sample_ms,
            "message": f"稳态测定启动: 共 {len(values)} 个采样点 (Settle: {config.settle_ms}ms, Sample: {config.sample_ms}ms)",
        })

        try:
            if config.start_countdown_s > 0:
                for count in range(config.start_countdown_s, 0, -1):
                    self._check_cancel(cancel_event)
                    publish({
                        "phase": "countdown",
                        "remaining_seconds": count,
                        "total_seconds": config.start_countdown_s,
                        "current_point": 0,
                        "total_points": len(values),
                        "message": f"请切回游戏画面！测定将在 {count} 秒后正式开始...",
                    })
                    self._interruptible_wait(1.0, cancel_event)

            if config.auto_wake and self._controller.is_enabled():
                publish({
                    "phase": "stage_start",
                    "total_points": len(values),
                    "current_point": 0,
                    "input_value": 0.0,
                    "message": f"自动触发唤醒游戏画面 ({config.wake_input})...",
                })
                try:
                    self._controller.wake(config.wake_input, duration_seconds=0.5)
                    self._interruptible_wait(0.6, cancel_event)
                except Exception:
                    pass

            for index, input_value in enumerate(values, start=1):
                self._check_cancel(cancel_event)
                self._controller.neutralize()
                self._interruptible_wait(0.10, cancel_event)

                publish({
                    "phase": "point_settle",
                    "current_point": index,
                    "total_points": len(values),
                    "input_value": input_value,
                    "message": f"采样点 [{index}/{len(values)}] 右摇杆推杆至 {(input_value * 100):.1f}%，等待视口稳定 ({config.settle_ms}ms)...",
                })

                if not self._controller.set_right_stick(input_value, 0.0, cancel_event):
                    raise JobCanceled()

                self._interruptible_wait(config.settle_ms / 1000.0, cancel_event)
                point = self._measure_point(
                    input_value,
                    config,
                    capture,
                    estimator,
                    selected_roi,
                    cancel_event,
                    publish=publish,
                    index=index,
                    total_points=len(values),
                )
                if config.bidirectional and input_value > 0:
                    self._controller.neutralize()
                    self._interruptible_wait(0.10, cancel_event)
                    if not self._controller.set_right_stick(-input_value, 0.0, cancel_event):
                        raise JobCanceled()
                    self._interruptible_wait(config.settle_ms / 1000.0, cancel_event)
                    reverse = self._measure_point(
                        input_value, config, capture, estimator, selected_roi, cancel_event,
                        publish=publish, index=index, total_points=len(values),
                    )
                    point = combine_directional_points(point, reverse)
                raw_points.append(point)
                publish({
                    "phase": "point_done",
                    "current_point": index,
                    "total_points": len(values),
                    "input_value": input_value,
                    "point": {
                        "input": point.input,
                        "velocity_px_s": point.velocity_px_s,
                        "normalized_speed": point.normalized_speed,
                        "stability": point.stability,
                        "valid": point.valid,
                        "attempts": point.attempts,
                        "coverage": point.coverage,
                        "velocity_mad": point.velocity_mad,
                    },
                    "message": (
                        f"采样点 [{index}/{len(values)}] 测定完成: "
                        f"速度 {point.velocity_px_s} px/s, "
                        f"稳定性 {round(point.stability * 100)}%, "
                        f"判定: {'有效' if point.valid else '无效'}"
                    ),
                })
        finally:
            self._controller.neutralize()

        if noise is not None:
            raw_points = [
                replace_point_velocity(point, noise.floor_x)
                for point in raw_points
            ]

        valid_count = sum(point.valid for point in raw_points)
        publish({
            "phase": "stage_completed",
            "current_point": len(values),
            "total_points": len(values),
            "input_value": values[-1] if values else 1.0,
            "valid_points": valid_count,
            "message": f"全测定流程完成: 共 {len(values)} 点，有效点 {valid_count} 个",
        })
        required_count = max(5, (len(values) * 60 + 99) // 100)
        if valid_count < required_count:
            raise DomainError(
                "MEASUREMENT_QUALITY_LOW",
                f"Only {valid_count} of {len(values)} measurement points were valid; {required_count} are required.",
            )

        # Compute normalized_speed relative to max observed velocity
        valid_velocities = [p.velocity_px_s for p in raw_points if p.valid and p.velocity_px_s is not None]
        endpoint_velocities = [
            p.velocity_px_s for p in raw_points
            if p.valid and p.velocity_px_s is not None and p.input >= 0.85
        ]
        # A single early peak must not make the final endpoint look slower.
        # Use the robust median of the outer region as the normalization anchor.
        max_velocity = float(median(endpoint_velocities)) if len(endpoint_velocities) >= 2 else max(valid_velocities, default=0.0)

        final_points: list[MeasurementPoint] = []
        for p in raw_points:
            if p.valid and p.velocity_px_s is not None and max_velocity > 0:
                normalized = round(p.velocity_px_s / max_velocity, 4)
            else:
                normalized = None
            final_points.append(
                MeasurementPoint(
                    input=p.input,
                    velocity_px_s=p.velocity_px_s,
                    normalized_speed=normalized,
                    stability=p.stability,
                    valid=p.valid,
                    attempts=p.attempts,
                    coverage=p.coverage,
                    velocity_mad=p.velocity_mad,
                    repeat_values=p.repeat_values,
                )
            )

        return SessionResult(
            points=tuple(final_points),
            noise=noise,
            schema_version=1,
        )

    def _measure_point(
        self,
        input_value: float,
        config: ProbeConfig,
        capture: Any,
        estimator: Any,
        roi: RoiRect,
        cancel_event: threading.Event,
        publish: Callable[[Mapping[str, object]], None] | None = None,
        index: int = 1,
        total_points: int = 1,
    ) -> MeasurementPoint:
        velocities: list[float] = []
        stabilities: list[float] = []
        total_attempts = 0

        # A single transient game/capture hitch must not become a curve kink.
        # Allow at most two extra repeats when the requested repeats disagree.
        max_repeats = config.repeats + 2 if config.repeats >= 2 else config.repeats
        for _ in range(max_repeats):
            self._check_cancel(cancel_event)
            estimator.reset()
            total_attempts += 1
            if publish is not None:
                publish({
                    "phase": "point_sampling",
                    "current_point": index,
                    "total_points": total_points,
                    "input_value": input_value,
                    "message": f"采样点 [{index}/{total_points}] 正在进行视觉光流跟踪采样 ({config.sample_ms}ms)...",
                })
            sample = self._sampler.sample_filtered(
                capture,
                estimator,
                roi,
                config.sample_ms,
                min_tracked_points=MIN_TRACKED_POINTS,
                min_confidence=MIN_TRACKING_CONFIDENCE,
                cancel_event=cancel_event,
            )
            if sample.canceled:
                raise JobCanceled()

            if sample.valid_frames > 0 and (sample.valid_frames < MIN_SAMPLE_VALID_FRAMES or sample.stability_score < 0.75):
                # Retry once
                total_attempts += 1
                self._check_cancel(cancel_event)
                estimator.reset()
                if publish is not None:
                    publish({
                        "phase": "point_retry",
                        "current_point": index,
                        "total_points": total_points,
                        "input_value": input_value,
                        "message": (
                            f"采样点 [{index}/{total_points}] 稳定性评分较低 "
                            f"({round(sample.stability_score * 100)}%)，正在触发第 2 轮复测..."
                        ),
                    })
                retry_sample = self._sampler.sample_filtered(
                    capture,
                    estimator,
                    roi,
                    config.sample_ms,
                    min_tracked_points=MIN_TRACKED_POINTS,
                    min_confidence=MIN_TRACKING_CONFIDENCE,
                    cancel_event=cancel_event,
                )
                if retry_sample.canceled:
                    raise JobCanceled()
                if retry_sample.valid_frames >= MIN_SAMPLE_VALID_FRAMES and retry_sample.stability_score >= sample.stability_score:
                    sample = retry_sample

            if sample.valid_frames >= MIN_SAMPLE_VALID_FRAMES and sample.stability_score >= 0.60:
                velocities.append(abs(sample.px_per_sec_x))
                stabilities.append(sample.stability_score)
            if len(velocities) >= config.repeats:
                if config.repeats < 3:
                    break
                center = median(velocities)
                mad = median([abs(value - center) for value in velocities])
                if len(velocities) >= 3 and center > 1e-6 and mad / center <= 0.08:
                    break

        if not velocities:
            return MeasurementPoint(
                input=input_value,
                velocity_px_s=None,
                normalized_speed=None,
                stability=0.0,
                valid=False,
                attempts=total_attempts,
                coverage=0.0,
            )

        med_velocity = round(float(median(velocities)), 4)
        avg_stability = round(sum(stabilities) / len(stabilities), 4)
        repeat_median = float(median(velocities))
        return MeasurementPoint(
            input=input_value,
            velocity_px_s=med_velocity,
            normalized_speed=None,
            stability=avg_stability,
            valid=True,
            attempts=total_attempts,
            coverage=round(min(stabilities), 4),
            velocity_mad=round(1.4826 * median([abs(v - repeat_median) for v in velocities]), 4) if len(velocities) > 1 else 0.0,
            repeat_values=tuple(round(v, 4) for v in velocities),
        )

    def _interruptible_wait(self, duration: float, cancel_event: threading.Event) -> None:
        if self._sleep is not None:
            self._sleep(duration)
            self._check_cancel(cancel_event)
            return

        start = time.perf_counter()
        while True:
            self._check_cancel(cancel_event)
            remaining = duration - (time.perf_counter() - start)
            if remaining <= 0:
                break
            if cancel_event.wait(min(0.02, remaining)):
                raise JobCanceled()

    def _check_cancel(self, cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise JobCanceled()


def replace_point_velocity(point: MeasurementPoint, noise_floor: float) -> MeasurementPoint:
    if not point.valid or point.velocity_px_s is None:
        return point
    speed = abs(point.velocity_px_s)
    net_speed = round(max(0.0, speed - noise_floor), 4)
    return MeasurementPoint(
        input=point.input,
        velocity_px_s=net_speed,
        normalized_speed=point.normalized_speed,
        stability=point.stability,
        valid=point.valid,
        attempts=point.attempts,
        coverage=point.coverage,
        velocity_mad=point.velocity_mad,
        repeat_values=point.repeat_values,
    )


def combine_directional_points(forward: MeasurementPoint, reverse: MeasurementPoint) -> MeasurementPoint:
    values = [v for v in (*forward.repeat_values, *reverse.repeat_values)]
    if not values:
        return MeasurementPoint(input=forward.input, velocity_px_s=None, normalized_speed=None,
                                stability=0.0, valid=False, attempts=forward.attempts + reverse.attempts)
    center = float(median(values))
    mad = median([abs(v - center) for v in values]) if len(values) > 1 else 0.0
    return MeasurementPoint(
        input=forward.input,
        velocity_px_s=round(center, 4),
        normalized_speed=None,
        stability=round(min(forward.stability, reverse.stability), 4),
        valid=forward.valid and reverse.valid,
        attempts=forward.attempts + reverse.attempts,
        coverage=round(min(forward.coverage, reverse.coverage), 4),
        velocity_mad=round(1.4826 * mad, 4),
        repeat_values=tuple(round(v, 4) for v in values),
    )
