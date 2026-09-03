from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from statistics import median
from typing import Protocol

from gamecurveprobe.models import RoiRect


@dataclass(slots=True)
class MotionSample:
    px_per_sec_x: float = 0.0
    px_per_sec_y: float = 0.0
    valid_frames: int = 0
    duplicate_frames: int = 0
    average_confidence: float = 0.0
    sample_duration_ms: int = 0
    stability_score: float = 0.0
    rejected_frames: int = 0
    velocity_mad: float = 0.0
    coverage: float = 0.0
    canceled: bool = False


class CapturedFrame(Protocol):
    frame: object
    timestamp: float


class CaptureBackend(Protocol):
    def grab_frame(self) -> CapturedFrame | None:
        ...


class MotionEstimateLike(Protocol):
    dx: float
    dy: float
    px_per_sec_x: float
    px_per_sec_y: float
    tracked_points: int
    confidence: float


class MotionEstimator(Protocol):
    def update(self, frame: object, roi: RoiRect, timestamp: float) -> MotionEstimateLike | None:
        ...


class MotionSampler:
    """Aggregate ROI motion over a fixed sampling window."""

    def __init__(
        self,
        time_source: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._time_source = time_source or time.perf_counter
        self._sleep = sleep or time.sleep

    def sample(
        self,
        capture_backend: CaptureBackend,
        estimator: MotionEstimator,
        roi: RoiRect,
        sample_ms: int,
    ) -> MotionSample:
        return self.sample_filtered(
            capture_backend,
            estimator,
            roi,
            sample_ms,
        )

    def sample_filtered(
        self,
        capture_backend: CaptureBackend,
        estimator: MotionEstimator,
        roi: RoiRect,
        sample_ms: int,
        min_tracked_points: int = 1,
        min_confidence: float = 0.0,
        cancel_event: threading.Event | None = None,
    ) -> MotionSample:
        if cancel_event is not None and cancel_event.is_set():
            return MotionSample(canceled=True)

        estimates, duplicate_frames, rejected_frames, was_canceled = self._collect_estimates(
            capture_backend,
            estimator,
            roi,
            sample_ms,
            min_tracked_points=min_tracked_points,
            min_confidence=min_confidence,
            cancel_event=cancel_event,
        )

        if was_canceled:
            return MotionSample(canceled=True)

        if not estimates:
            return MotionSample()

        xs = [estimate.px_per_sec_x for estimate in estimates]
        ys = [estimate.px_per_sec_y for estimate in estimates]
        confidences = [estimate.confidence for estimate in estimates]
        times = [estimate.timestamp for estimate in estimates]
        dxs = [estimate.dx for estimate in estimates if estimate.dx is not None]
        dys = [estimate.dy for estimate in estimates if estimate.dy is not None]
        dts = [estimate.dt for estimate in estimates]
        duration_ms = int(round(max(0.0, times[-1] - times[0]) * 1000)) if len(times) >= 2 else 0
        total_frames = len(estimates) + duplicate_frames + rejected_frames
        stability_score = 0.0 if total_frames <= 0 else round(len(estimates) / total_frames, 4)
        median_speed = float(median(xs))
        velocity_mad = float(median([abs(value - median_speed) for value in xs])) if xs else 0.0

        return MotionSample(
            px_per_sec_x=self._calculate_axis_speed(xs, dxs, times, dts),
            px_per_sec_y=self._calculate_axis_speed(ys, dys, times, dts),
            valid_frames=len(estimates),
            duplicate_frames=duplicate_frames,
            average_confidence=sum(confidences) / len(confidences),
            sample_duration_ms=duration_ms,
            stability_score=stability_score,
            rejected_frames=rejected_frames,
            velocity_mad=round(1.4826 * velocity_mad, 4),
            coverage=stability_score,
        )

    def sample_noise_floor(
        self,
        capture_backend: CaptureBackend,
        estimator: MotionEstimator,
        roi: RoiRect,
        sample_ms: int,
        min_tracked_points: int = 1,
        min_confidence: float = 0.0,
        band_percentile: float = 0.9,
        cancel_event: threading.Event | None = None,
    ) -> MotionSample:
        if cancel_event is not None and cancel_event.is_set():
            return MotionSample(canceled=True)

        estimates, _duplicate_frames, _rejected_frames, was_canceled = self._collect_estimates(
            capture_backend,
            estimator,
            roi,
            sample_ms,
            min_tracked_points=min_tracked_points,
            min_confidence=min_confidence,
            cancel_event=cancel_event,
        )
        if was_canceled:
            return MotionSample(canceled=True)

        xs = [estimate.px_per_sec_x for estimate in estimates]
        ys = [estimate.px_per_sec_y for estimate in estimates]
        confidences = [estimate.confidence for estimate in estimates]
        if not xs:
            return MotionSample()

        return MotionSample(
            px_per_sec_x=self._percentile([abs(value) for value in xs], band_percentile),
            px_per_sec_y=self._percentile([abs(value) for value in ys], band_percentile),
            valid_frames=len(xs),
            average_confidence=sum(confidences) / len(confidences),
        )

    def _collect_estimates(
        self,
        capture_backend: CaptureBackend,
        estimator: MotionEstimator,
        roi: RoiRect,
        sample_ms: int,
        min_tracked_points: int,
        min_confidence: float,
        cancel_event: threading.Event | None = None,
    ) -> tuple[list[_AcceptedEstimate], int, int, bool]:
        deadline = self._time_source() + (sample_ms / 1000.0)
        estimates: list[_AcceptedEstimate] = []
        duplicate_frames = 0
        rejected_frames = 0

        while self._time_source() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                return estimates, duplicate_frames, rejected_frames, True

            if hasattr(capture_backend, "read"):
                captured = capture_backend.read(100)
            elif hasattr(capture_backend, "grab_frame"):
                captured = capture_backend.grab_frame()
            else:
                captured = None

            if captured is None:
                if cancel_event is not None:
                    if cancel_event.wait(0.005):
                        return estimates, duplicate_frames, rejected_frames, True
                else:
                    self._sleep(0.005)
                continue

            frame_obj = getattr(captured, "image", None)
            if frame_obj is None:
                frame_obj = getattr(captured, "frame", None)

            ts = getattr(captured, "timestamp", None)
            if ts is None and hasattr(captured, "monotonic_ns"):
                ts = captured.monotonic_ns / 1e9
            ts = float(ts or self._time_source())

            if ts > deadline:
                break
            if bool(getattr(captured, "is_duplicate", False)):
                duplicate_frames += 1
                continue

            estimate = estimator.update(frame_obj, roi, ts)
            if estimate is None or estimate.tracked_points <= 0:
                rejected_frames += 1
                continue
            if estimate.tracked_points < min_tracked_points:
                rejected_frames += 1
                continue
            if estimate.confidence < min_confidence:
                rejected_frames += 1
                continue

            estimates.append(
                _AcceptedEstimate(
                    timestamp=ts,
                    px_per_sec_x=float(estimate.px_per_sec_x),
                    px_per_sec_y=float(estimate.px_per_sec_y),
                    confidence=float(estimate.confidence),
                    dx=self._optional_float(getattr(estimate, "dx", None)),
                    dy=self._optional_float(getattr(estimate, "dy", None)),
                    dt=self._optional_float(getattr(estimate, "dt", None)),
                )
            )

        return estimates, duplicate_frames, rejected_frames, False

    def _calculate_axis_speed(
        self, velocities: list[float], displacements: list[float | None], times: list[float], dts: list[float | None] | None = None
    ) -> float:
        usable_displacements = [value for value in displacements if value is not None]
        usable_dts = [value for value in (dts or []) if value is not None and value > 0]
        if len(usable_displacements) == len(times) and len(usable_dts) == len(times):
            duration = sum(usable_dts)
            if duration > 0:
                return round(sum(usable_displacements) / duration, 4)
        if len(usable_displacements) == len(times) and len(times) >= 2:
            duration = times[-1] - times[0]
            if duration > 0:
                return round(sum(usable_displacements) / duration, 4)
        return float(median(velocities))

    def _optional_float(self, value: object) -> float | None:
        if value is None:
            return None
        return float(value)

    def _percentile(self, values: list[float], quantile: float) -> float:
        ordered = sorted(values)
        quantile = min(max(quantile, 0.0), 1.0)
        index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile))))
        return float(ordered[index])


@dataclass(slots=True)
class _AcceptedEstimate:
    timestamp: float
    px_per_sec_x: float
    px_per_sec_y: float
    confidence: float
    dx: float | None
    dy: float | None
    dt: float | None = None
