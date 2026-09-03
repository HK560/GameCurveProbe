import threading
import pytest

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.errors import JobCanceled
from gamecurveprobe.models import ProbeConfig, RoiRect
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.measurement_runner import MeasurementRunner
from gamecurveprobe.services.motion_sampler import MotionSample


class FakeCapture:
    def grab_frame(self):
        return None


class FakeEstimator:
    def reset(self):
        pass


class FakeSampler:
    def __init__(self, valid_frames: int = 10, px_per_sec: float = 100.0) -> None:
        self.valid_frames = valid_frames
        self.px_per_sec = px_per_sec

    def sample_filtered(
        self,
        capture,
        estimator,
        roi,
        duration_ms,
        min_tracked_points=8,
        min_confidence=0.35,
        cancel_event=None,
    ):
        if cancel_event is not None and cancel_event.is_set():
            return MotionSample(canceled=True)
        if self.valid_frames == 0:
            return MotionSample(valid_frames=0)
        return MotionSample(
            px_per_sec_x=self.px_per_sec,
            px_per_sec_y=0.0,
            valid_frames=self.valid_frames,
            average_confidence=0.8,
            stability_score=0.9,
        )


def test_runner_keeps_invalid_point_without_faking_zero() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    config = ProbeConfig(point_count=5, repeats=1)
    runner = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(valid_frames=0),
        roi=RoiRect(0, 0, 100, 100),
        sleep=lambda *_: None,
    )
    result = runner.run(config, threading.Event(), lambda event: None)
    assert len(result.points) > 0
    assert result.points[0].valid is False
    assert result.points[0].velocity_px_s is None


def test_runner_neutralizes_when_canceled_during_settle() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    config = ProbeConfig(point_count=5, repeats=1)
    cancel = threading.Event()
    runner = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(),
        roi=RoiRect(0, 0, 100, 100),
        sleep=lambda _: cancel.set(),
    )
    with pytest.raises(JobCanceled):
        runner.run(config, cancel, lambda event: None)
    assert backend.events[-1] == ("neutral",)
