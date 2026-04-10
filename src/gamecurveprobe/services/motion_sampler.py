from __future__ import annotations

import time
from statistics import median
from collections.abc import Callable
from dataclasses import dataclass
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

    def sample(self, capture_backend: CaptureBackend, estimator: MotionEstimator, roi: RoiRect, sample_ms: int) -> MotionSample:
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
    ) -> MotionSample:
        estimates, duplicate_frames = self._collect_estimates(
            capture_backend,
            estimator,
            roi,
            sample_ms,
            min_tracked_points=min_tracked_points,
            min_confidence=min_confidence,
        )

        if not estimates:
            return MotionSample()

        xs = [estimate.px_per_sec_x for estimate in estimates]
        ys = [estimate.px_per_sec_y for estimate in estimates]
        confidences = [estimate.confidence for estimate in estimates]
        times = [estimate.timestamp for estimate in estimates]
        dxs = [estimate.dx for estimate in estimates if estimate.dx is not None]
        dys = [estimate.dy for estimate in estimates if estimate.dy is not None]
        duration_ms = int(round(max(0.0, times[-1] - times[0]) * 1000)) if len(times) >= 2 else 0
        total_frames = len(estimates) + duplicate_frames
        stability_score = 0.0 if total_frames <= 0 else round(len(estimates) / total_frames, 4)

        return MotionSample(
            px_per_sec_x=self._calculate_axis_speed(xs, dxs, times),
            px_per_sec_y=self._calculate_axis_speed(ys, dys, times),
            valid_frames=len(estimates),
            duplicate_frames=duplicate_frames,
            average_confidence=sum(confidences) / len(confidences),
            sample_duration_ms=duration_ms,
            stability_score=stability_score,
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
    ) -> MotionSample:
        estimates, _duplicate_frames = self._collect_estimates(
            capture_backend,
            estimator,
            roi,
            sample_ms,
            min_tracked_points=min_tracked_points,
            min_confidence=min_confidence,
        )
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
    ) -> tuple[list[_AcceptedEstimate], int]:
        deadline = self._time_source() + (sample_ms / 1000.0)
        estimates: list[_AcceptedEstimate] = []
        duplicate_frames = 0

        while self._time_source() < deadline:
            captured = capture_backend.grab_frame()
            if captured is None:
                self._sleep(0.005)
                continue

            if captured.timestamp > deadline:
                break
            if bool(getattr(captured, "is_duplicate", False)):
                duplicate_frames += 1
                continue

            estimate = estimator.update(captured.frame, roi, captured.timestamp)
            if estimate is None or estimate.tracked_points <= 0:
                continue
            if estimate.tracked_points < min_tracked_points:
                continue
            if estimate.confidence < min_confidence:
                continue

            estimates.append(
                _AcceptedEstimate(
                    timestamp=float(captured.timestamp),
                    px_per_sec_x=float(estimate.px_per_sec_x),
                    px_per_sec_y=float(estimate.px_per_sec_y),
                    confidence=float(estimate.confidence),
                    dx=self._optional_float(getattr(estimate, "dx", None)),
                    dy=self._optional_float(getattr(estimate, "dy", None)),
                )
            )

        return estimates, duplicate_frames

    def _calculate_axis_speed(self, velocities: list[float], displacements: list[float | None], times: list[float]) -> float:
        usable_displacements = [value for value in displacements if value is not None]
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
