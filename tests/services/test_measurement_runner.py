import threading
import pytest

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.errors import DomainError, JobCanceled
from gamecurveprobe.models import NoiseResult, ProbeConfig, RoiRect
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
    class FirstPointInvalidSampler(FakeSampler):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def sample_filtered(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return MotionSample(valid_frames=0)
            return super().sample_filtered(*args, **kwargs)

    backend = StubControllerBackend()
    controller = ControllerService(backend)
    config = ProbeConfig(point_count=6, repeats=1)
    runner = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FirstPointInvalidSampler(),
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
    config = ProbeConfig(point_count=5, repeats=1, start_countdown_s=0)
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


def test_runner_uses_job_roi_and_subtracts_noise_floor() -> None:
    class RecordingSampler(FakeSampler):
        seen_roi = None

        def sample_filtered(self, capture, estimator, roi, duration_ms, **kwargs):
            self.seen_roi = roi
            return super().sample_filtered(capture, estimator, roi, duration_ms, **kwargs)

    sampler = RecordingSampler(px_per_sec=25.0)
    runner = MeasurementRunner(
        controller=ControllerService(StubControllerBackend()),
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=sampler,
        sleep=lambda *_: None,
    )
    roi = RoiRect(11, 12, 80, 90)

    result = runner.run(
        ProbeConfig(point_count=5, repeats=1),
        threading.Event(),
        lambda event: None,
        roi=roi,
        noise=NoiseResult(floor_x=5.0, floor_y=0.0, valid_frames=10, confidence=0.9),
    )

    assert sampler.seen_roi == roi
    assert result.points[0].velocity_px_s == 20.0
    assert result.noise is not None


def test_runner_rejects_result_below_valid_point_threshold() -> None:
    runner = MeasurementRunner(
        controller=ControllerService(StubControllerBackend()),
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(valid_frames=0),
        sleep=lambda *_: None,
    )

    with pytest.raises(DomainError) as exc:
        runner.run(
            ProbeConfig(point_count=5, repeats=1),
            threading.Event(),
            lambda event: None,
            roi=RoiRect(0, 0, 100, 100),
        )

    assert exc.value.code == "MEASUREMENT_QUALITY_LOW"


def test_measurement_runner_publishes_lifecycle_phases() -> None:
    events: list[dict] = []
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    config = ProbeConfig(point_count=5, repeats=1)
    runner = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=FakeSampler(px_per_sec=120.0),
        roi=RoiRect(0, 0, 100, 100),
        sleep=lambda *_: None,
    )

    result = runner.run(config, threading.Event(), lambda ev: events.append(dict(ev)))

    phases = [ev.get("phase") for ev in events]
    assert "stage_start" in phases
    assert "point_settle" in phases
    assert "point_sampling" in phases
    assert "point_done" in phases
    assert "stage_completed" in phases

    # Check point_done payload contains point and message
    done_events = [ev for ev in events if ev.get("phase") == "point_done"]
    assert len(done_events) == 5
    assert "point" in done_events[0]
    assert "message" in done_events[0]
    assert done_events[0]["current_point"] == 1
    assert done_events[0]["total_points"] == 5


def test_runner_early_breaks_when_repeats_consistent() -> None:
    class ConsistentSampler(FakeSampler):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def sample_filtered(self, *args, **kwargs):
            self.calls += 1
            return MotionSample(
                px_per_sec_x=100.0 if self.calls % 2 == 1 else 101.0,
                px_per_sec_y=0.0,
                valid_frames=10,
                average_confidence=0.9,
                stability_score=0.95,
            )

    sampler = ConsistentSampler()
    runner = MeasurementRunner(
        controller=ControllerService(StubControllerBackend()),
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=sampler,
        roi=RoiRect(0, 0, 100, 100),
        sleep=lambda *_: None,
    )
    config = ProbeConfig(point_count=5, repeats=2, start_countdown_s=0, auto_wake=False)
    result = runner.run(config, threading.Event(), lambda _: None)
    # 5 points, each point takes 2 samples because 100 and 101 are consistent (diff <= 6%)
    assert sampler.calls == 10
    assert result.points[1].velocity_px_s is not None
    assert abs(result.points[1].velocity_px_s - 100.5) <= 1.0


def test_runner_adaptive_repeats_when_diverging_and_rejects_outlier() -> None:
    # 1st sample: 100, 2nd sample: 50 (diverges), 3rd sample: 102 (50 is an outlier)
    sequence = [100.0, 50.0, 102.0]
    call_idx = 0

    class SequenceSampler(FakeSampler):
        def sample_filtered(self, *args, **kwargs):
            nonlocal call_idx
            val = sequence[min(call_idx, len(sequence) - 1)]
            call_idx += 1
            return MotionSample(
                px_per_sec_x=val,
                px_per_sec_y=0.0,
                valid_frames=10,
                average_confidence=0.9,
                stability_score=0.95,
            )

    events: list[dict] = []
    runner = MeasurementRunner(
        controller=ControllerService(StubControllerBackend()),
        capture_factory=lambda: FakeCapture(),
        estimator_factory=lambda: FakeEstimator(),
        motion_sampler=SequenceSampler(),
        roi=RoiRect(0, 0, 100, 100),
        sleep=lambda *_: None,
    )
    config = ProbeConfig(point_count=5, repeats=2, start_countdown_s=0, auto_wake=False)
    # Only measure 1 point to check sequence
    pt = runner._measure_point(
        0.5, config, FakeCapture(), FakeEstimator(), RoiRect(0, 0, 10, 10),
        threading.Event(), publish=lambda ev: events.append(dict(ev))
    )
    # 3 samples taken because first two diverged
    assert call_idx == 3
    # 50.0 was rejected, velocity should be close to 101.0 (mean/median of 100 and 102)
    assert pt.velocity_px_s is not None
    assert pt.velocity_px_s >= 99.0 and pt.velocity_px_s <= 102.0
    # Notification sent
    retry_msgs = [e.get("message", "") for e in events if e.get("phase") == "point_retry"]
    assert any("检测到测速波动" in m for m in retry_msgs)


