from __future__ import annotations

from dataclasses import dataclass

from gamecurveprobe.models import RoiRect
from gamecurveprobe.services.motion_sampler import MotionSampler


@dataclass
class FakeFrame:
    frame: object
    timestamp: float
    is_duplicate: bool = False


@dataclass
class FakeEstimate:
    px_per_sec_x: float
    px_per_sec_y: float
    tracked_points: int
    confidence: float
    dx: float | None = None
    dy: float | None = None


class FakeCaptureBackend:
    def __init__(self, frames: list[FakeFrame | None]) -> None:
        self._frames = list(frames)

    def grab_frame(self) -> FakeFrame | None:
        if not self._frames:
            return None
        return self._frames.pop(0)


class FakeEstimator:
    def __init__(self, estimates: list[FakeEstimate | None]) -> None:
        self._estimates = list(estimates)

    def update(self, frame: object, roi: RoiRect, timestamp: float) -> FakeEstimate | None:
        if not self._estimates:
            return None
        return self._estimates.pop(0)


def test_sample_averages_valid_motion_estimates() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.024),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=100.0, px_per_sec_y=20.0, tracked_points=10, confidence=0.50),
            None,
            FakeEstimate(px_per_sec_x=200.0, px_per_sec_y=40.0, tracked_points=12, confidence=0.75),
        ]
    )

    sample = sampler.sample(capture, estimator, RoiRect(0, 0, 20, 20), sample_ms=25)

    assert sample.valid_frames == 2
    assert sample.px_per_sec_x == 150.0
    assert sample.px_per_sec_y == 30.0
    assert sample.average_confidence == 0.625


def test_sample_uses_median_to_reject_single_frame_velocity_spike() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03, 0.04]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.03),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=110.0, px_per_sec_y=10.0, tracked_points=18, confidence=0.95),
            FakeEstimate(px_per_sec_x=950.0, px_per_sec_y=220.0, tracked_points=4, confidence=0.25),
            FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=12.0, tracked_points=19, confidence=0.96),
        ]
    )

    sample = sampler.sample(capture, estimator, RoiRect(0, 0, 20, 20), sample_ms=35)

    assert sample.valid_frames == 3
    assert sample.px_per_sec_x == 120.0
    assert sample.px_per_sec_y == 12.0
    assert sample.average_confidence == 0.7200000000000001


def test_sample_ignores_frame_past_deadline() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.03),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=100.0, px_per_sec_y=20.0, tracked_points=10, confidence=0.50),
            None,
            FakeEstimate(px_per_sec_x=200.0, px_per_sec_y=40.0, tracked_points=12, confidence=0.75),
        ]
    )

    sample = sampler.sample(capture, estimator, RoiRect(0, 0, 20, 20), sample_ms=25)

    assert sample.valid_frames == 1
    assert sample.px_per_sec_x == 100.0
    assert sample.px_per_sec_y == 20.0
    assert sample.average_confidence == 0.5


def test_sample_skips_placeholder_estimates_with_no_tracked_motion() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=0.0, px_per_sec_y=0.0, tracked_points=0, confidence=0.0),
            FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=45.0, tracked_points=9, confidence=0.9),
        ]
    )

    sample = sampler.sample(capture, estimator, RoiRect(0, 0, 20, 20), sample_ms=25)

    assert sample.valid_frames == 1
    assert sample.px_per_sec_x == 180.0
    assert sample.px_per_sec_y == 45.0
    assert sample.average_confidence == 0.9


def test_sample_returns_zeroes_when_no_valid_estimates() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.01, 0.02]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend([None, None])
    estimator = FakeEstimator([])

    sample = sampler.sample(capture, estimator, RoiRect(0, 0, 20, 20), sample_ms=15)

    assert sample.valid_frames == 0
    assert sample.px_per_sec_x == 0.0
    assert sample.px_per_sec_y == 0.0
    assert sample.average_confidence == 0.0


def test_sample_filtered_ignores_low_quality_frames() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.024),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=400.0, px_per_sec_y=40.0, tracked_points=4, confidence=0.9),
            FakeEstimate(px_per_sec_x=150.0, px_per_sec_y=15.0, tracked_points=12, confidence=0.2),
            FakeEstimate(px_per_sec_x=110.0, px_per_sec_y=11.0, tracked_points=18, confidence=0.8),
        ]
    )

    sample = sampler.sample_filtered(
        capture,
        estimator,
        RoiRect(0, 0, 20, 20),
        sample_ms=25,
        min_tracked_points=8,
        min_confidence=0.35,
    )

    assert sample.valid_frames == 1
    assert sample.px_per_sec_x == 110.0
    assert sample.px_per_sec_y == 11.0
    assert sample.average_confidence == 0.8


def test_sample_noise_floor_uses_absolute_velocity_band_percentile() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03, 0.04]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.03),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=-20.0, px_per_sec_y=5.0, tracked_points=12, confidence=0.8),
            FakeEstimate(px_per_sec_x=10.0, px_per_sec_y=-7.0, tracked_points=12, confidence=0.8),
            FakeEstimate(px_per_sec_x=40.0, px_per_sec_y=9.0, tracked_points=12, confidence=0.8),
        ]
    )

    sample = sampler.sample_noise_floor(
        capture,
        estimator,
        RoiRect(0, 0, 20, 20),
        sample_ms=35,
        band_percentile=0.9,
    )

    assert sample.valid_frames == 3
    assert sample.px_per_sec_x == 40.0
    assert sample.px_per_sec_y == 9.0


def test_sample_filtered_tracks_duplicate_frames_and_quality_metrics() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02, is_duplicate=True),
            FakeFrame(object(), 0.03),
            FakeFrame(object(), 0.04),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=100.0, px_per_sec_y=10.0, tracked_points=12, confidence=0.9),
            FakeEstimate(px_per_sec_x=100.0, px_per_sec_y=10.0, tracked_points=12, confidence=0.9),
            FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=12.0, tracked_points=12, confidence=0.9),
            FakeEstimate(px_per_sec_x=130.0, px_per_sec_y=13.0, tracked_points=12, confidence=0.9),
        ]
    )

    sample = sampler.sample_filtered(
        capture,
        estimator,
        RoiRect(0, 0, 20, 20),
        sample_ms=45,
        min_tracked_points=8,
        min_confidence=0.35,
    )

    assert sample.valid_frames == 3
    assert sample.duplicate_frames == 1
    assert sample.sample_duration_ms == 30
    assert sample.stability_score == 0.75


def test_sample_filtered_uses_cumulative_displacement_slope_when_dx_is_available() -> None:
    sampler = MotionSampler(time_source=iter([0.0, 0.005, 0.01, 0.02, 0.04, 0.05]).__next__, sleep=lambda _: None)
    capture = FakeCaptureBackend(
        [
            FakeFrame(object(), 0.01),
            FakeFrame(object(), 0.02),
            FakeFrame(object(), 0.04),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=80.0, px_per_sec_y=8.0, tracked_points=12, confidence=0.9, dx=1.0, dy=0.1),
            FakeEstimate(px_per_sec_x=320.0, px_per_sec_y=32.0, tracked_points=12, confidence=0.9, dx=3.0, dy=0.3),
            FakeEstimate(px_per_sec_x=110.0, px_per_sec_y=11.0, tracked_points=12, confidence=0.9, dx=2.0, dy=0.2),
        ]
    )

    sample = sampler.sample_filtered(
        capture,
        estimator,
        RoiRect(0, 0, 20, 20),
        sample_ms=45,
        min_tracked_points=8,
        min_confidence=0.35,
    )

    assert sample.valid_frames == 3
    assert sample.px_per_sec_x == 200.0
    assert sample.px_per_sec_y == 20.0
