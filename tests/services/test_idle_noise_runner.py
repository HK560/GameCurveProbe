import threading
import pytest

from gamecurveprobe.errors import JobCanceled
from gamecurveprobe.models import NoiseResult, ProbeConfig, RoiRect
from gamecurveprobe.services.idle_noise_runner import IdleNoiseRunner
from gamecurveprobe.services.motion_sampler import MotionSample


class FakeCapture:
    def grab_frame(self):
        return None


class FakeEstimator:
    def reset(self):
        pass


class FakeSampler:
    def __init__(self, canceled: bool = False) -> None:
        self.canceled = canceled

    def sample_noise_floor(
        self,
        capture,
        estimator,
        roi,
        duration_ms,
        min_tracked_points=8,
        min_confidence=0.35,
        band_percentile=0.9,
        cancel_event=None,
    ):
        if self.canceled or (cancel_event is not None and cancel_event.is_set()):
            return MotionSample(canceled=True)
        return MotionSample(
            px_per_sec_x=1.5,
            px_per_sec_y=0.8,
            valid_frames=30,
            average_confidence=0.85,
        )


def test_idle_noise_runner_returns_noise_result() -> None:
    runner = IdleNoiseRunner(
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(),
        roi=RoiRect(0, 0, 100, 100),
    )
    result = runner.run(ProbeConfig(), threading.Event(), lambda event: None)
    assert isinstance(result, NoiseResult)
    assert result.floor_x == 1.5
    assert result.floor_y == 0.8
    assert result.valid_frames == 30


def test_idle_noise_runner_raises_job_canceled_when_canceled() -> None:
    runner = IdleNoiseRunner(
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(canceled=True),
        roi=RoiRect(0, 0, 100, 100),
    )
    with pytest.raises(JobCanceled):
        runner.run(ProbeConfig(), threading.Event(), lambda event: None)
