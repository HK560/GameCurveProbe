from __future__ import annotations

from dataclasses import dataclass

import pytest

from gamecurveprobe.models import ProbeSessionConfig, RoiRect
from gamecurveprobe.services.motion_sampler import MotionSample
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError, SteadyProbeRunner


class FakeController:
    def __init__(self) -> None:
        self.connected = False
        self.events: list[tuple[str, float, float] | tuple[str]] = []

    def probe(self) -> bool:
        return True

    def connect(self) -> None:
        self.connected = True
        self.events.append(("connect",))

    def set_right_stick(self, x: float, y: float) -> None:
        self.events.append(("stick", x, y))

    def press_left_stick(self) -> None:
        self.events.append(("press_left_stick",))

    def release_left_stick(self) -> None:
        self.events.append(("release_left_stick",))

    def neutral(self) -> None:
        self.events.append(("neutral",))

    def disconnect(self) -> None:
        self.events.append(("disconnect",))


class ProbeFalseController(FakeController):
    def probe(self) -> bool:
        return False


class FailingConnectController(FakeController):
    def connect(self) -> None:
        raise RuntimeError("connect failed")

    def neutral(self) -> None:
        raise RuntimeError("neutral failed")

    def disconnect(self) -> None:
        raise RuntimeError("disconnect failed")


class CleanupAttemptedOnConnectFailureController(FakeController):
    def connect(self) -> None:
        self.events.append(("connect",))
        raise RuntimeError("connect failed")


class FakeCapture:
    def __init__(self) -> None:
        self.attached_to: int | None = None
        self.capture_fps: int | None = None
        self.closed = False

    def attach(self, window_id: int, capture_fps: int | None = None) -> None:
        self.attached_to = window_id
        self.capture_fps = capture_fps

    def close(self) -> None:
        self.closed = True


class FailingAttachCapture(FakeCapture):
    def attach(self, window_id: int, capture_fps: int | None = None) -> None:
        super().attach(window_id, capture_fps)
        raise RuntimeError("attach failed")


class FailingCloseCapture(FakeCapture):
    def close(self) -> None:
        raise RuntimeError("close failed")


class EstimatorConstructionError(RuntimeError):
    pass


@dataclass
class FakeEstimator:
    reset_count: int = 0

    def reset(self) -> None:
        self.reset_count += 1


class FakeSampler:
    def __init__(self, samples: list[MotionSample]) -> None:
        self._samples = list(samples)

    def sample(self, capture_backend, estimator, roi, sample_ms: int) -> MotionSample:
        return self._samples.pop(0)

    def sample_filtered(
        self,
        capture_backend,
        estimator,
        roi,
        sample_ms: int,
        min_tracked_points: int = 1,
        min_confidence: float = 0.0,
    ) -> MotionSample:
        return self._samples.pop(0)


class RecordingSampler(FakeSampler):
    def __init__(self, samples: list[MotionSample]) -> None:
        super().__init__(samples)
        self.sample_ms_values: list[int] = []

    def sample(self, capture_backend, estimator, roi, sample_ms: int) -> MotionSample:
        self.sample_ms_values.append(sample_ms)
        return super().sample(capture_backend, estimator, roi, sample_ms)

    def sample_filtered(
        self,
        capture_backend,
        estimator,
        roi,
        sample_ms: int,
        min_tracked_points: int = 1,
        min_confidence: float = 0.0,
    ) -> MotionSample:
        self.sample_ms_values.append(sample_ms)
        return super().sample_filtered(
            capture_backend,
            estimator,
            roi,
            sample_ms,
            min_tracked_points=min_tracked_points,
            min_confidence=min_confidence,
        )


def test_runner_builds_x_positive_curve_only_and_neutralizes_controller() -> None:
    controller = FakeController()
    capture = FakeCapture()
    sampler = FakeSampler(
        [
            MotionSample(px_per_sec_x=10.0, px_per_sec_y=1.0, valid_frames=4, average_confidence=0.8),
            MotionSample(px_per_sec_x=12.0, px_per_sec_y=1.0, valid_frames=4, average_confidence=0.8),
            MotionSample(px_per_sec_x=20.0, px_per_sec_y=2.0, valid_frames=4, average_confidence=0.8),
            MotionSample(px_per_sec_x=22.0, px_per_sec_y=2.0, valid_frames=4, average_confidence=0.8),
        ]
    )
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=sampler,
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.25, 0.5],
    )
    config = ProbeSessionConfig(
        window_id=77,
        roi=RoiRect(10, 10, 80, 80),
        axes=["x"],
        point_count_per_half_axis=5,
        settle_ms=100,
        steady_sample_ms=200,
        repeats=2,
    )

    result = runner.run(config, yaw_deg_per_px=0.5)

    assert capture.attached_to == 77
    assert [point.input_value for point in result.x_curve] == [0.25, 0.5]
    assert [point.direction for point in result.x_curve] == ["positive", "positive"]
    assert result.x_curve[0].px_per_sec == 11.0
    assert result.x_curve[-1].normalized_speed == 1.0
    assert result.x_curve[0].deg_per_sec == 5.5
    assert result.y_curve == []
    assert ("neutral",) in controller.events


def test_runner_requires_window_and_roi() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="Select a target window"):
        runner.run(ProbeSessionConfig(window_id=None, roi=RoiRect(0, 0, 10, 10)))

    with pytest.raises(ProbeExecutionError, match="Select an ROI"):
        runner.run(ProbeSessionConfig(window_id=1, roi=None))


def test_runner_cleans_up_when_capture_attach_fails() -> None:
    controller = FakeController()
    capture = FailingAttachCapture()
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(RuntimeError, match="attach failed"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))

    assert ("connect",) in controller.events
    assert ("neutral",) in controller.events
    assert ("disconnect",) in controller.events
    assert capture.closed is True


def test_runner_generates_positive_half_axis_points_only_from_config() -> None:
    controller = FakeController()
    capture = FakeCapture()
    sampler = FakeSampler(
        [MotionSample(px_per_sec_x=10.0, px_per_sec_y=0.0, valid_frames=4, average_confidence=0.8) for _ in range(5)]
    )
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=sampler,
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
    )

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 10, 10),
            axes=["x"],
            point_count_per_half_axis=3,
            repeats=1,
        )
    )

    assert [point.input_value for point in result.x_curve] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert result.y_curve == []


def test_runner_applies_deadzone_markers_when_building_default_point_values() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
    )

    values = runner._resolve_point_values(
        ProbeSessionConfig(
            point_count_per_half_axis=5,
            inner_deadzone_marker=0.2,
            outer_saturation_marker=0.8,
        )
    )

    assert values == [0.2, 0.35, 0.5, 0.65, 0.8]


def test_runner_notes_only_reference_x_positive_when_repeat_has_no_valid_frames() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler(
            [
                MotionSample(px_per_sec_x=0.0, px_per_sec_y=0.0, valid_frames=0, average_confidence=0.0),
            ]
        ),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    result = runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["x"], repeats=1))

    assert result.notes == [
        "x/positive input 0.5000 repeat 1 had no valid frames.",
        "x/positive input 0.5000 fell back to 0.0 px/s.",
    ]


def test_runner_raises_probe_execution_error_when_controller_probe_fails() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=ProbeFalseController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
    )

    with pytest.raises(ProbeExecutionError, match="vgamepad is unavailable"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))


def test_runner_preserves_connect_failure_when_cleanup_also_fails() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FailingConnectController,
        capture_backend_factory=FailingCloseCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))


def test_runner_closes_capture_when_estimator_construction_fails() -> None:
    capture = FakeCapture()
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=lambda: (_ for _ in ()).throw(EstimatorConstructionError("estimator failed")),
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(EstimatorConstructionError, match="estimator failed"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))

    assert capture.closed is True


def test_runner_attempts_cleanup_on_connect_failure_without_masking_original_error() -> None:
    controller = CleanupAttemptedOnConnectFailureController()
    capture = FakeCapture()
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))

    assert ("neutral",) in controller.events
    assert ("disconnect",) in controller.events
    assert capture.closed is True


def test_runner_rejects_unsupported_axis() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="Unsupported axis"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["z"]))


def test_runner_rejects_invalid_numeric_config() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="repeats"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), repeats=0))


def test_runner_rejects_deadzone_marker_range_when_outer_is_not_greater_than_inner() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler([]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="outer_saturation_marker"):
        runner._validate_config(
            ProbeSessionConfig(
                inner_deadzone_marker=0.8,
                outer_saturation_marker=0.8,
            )
        )


def test_runner_rejects_out_of_range_point_value_override() -> None:
    with pytest.raises(ProbeExecutionError, match="point_values"):
        SteadyProbeRunner(
            controller_backend_factory=FakeController,
            capture_backend_factory=FakeCapture,
            motion_sampler=FakeSampler([]),
            motion_estimator_factory=FakeEstimator,
            sleep=lambda _: None,
            point_values=[1.1],
        )


def test_probe_session_config_defaults_to_x_axis_only() -> None:
    config = ProbeSessionConfig.from_payload({})

    assert config.axes == ["x"]


def test_probe_session_config_reads_split_timing_fields_and_legacy_fallback() -> None:
    config = ProbeSessionConfig.from_payload({"steady_sample_ms": 321, "yaw360_timeout_ms": 4321})

    assert config.steady_sample_ms == 321
    assert config.yaw360_timeout_ms == 4321

    legacy = ProbeSessionConfig.from_payload({"sample_ms": 900})

    assert legacy.steady_sample_ms == 900
    assert legacy.yaw360_timeout_ms == 900


def test_probe_session_config_to_dict_uses_split_timing_fields_only() -> None:
    config = ProbeSessionConfig(steady_sample_ms=321, yaw360_timeout_ms=4321)

    payload = config.to_dict()

    assert payload["steady_sample_ms"] == 321
    assert payload["yaw360_timeout_ms"] == 4321
    assert "sample_ms" not in payload


def test_probe_session_config_persists_live_preview_during_run_flag() -> None:
    config = ProbeSessionConfig.from_payload({"push_live_preview_during_run": True})

    assert config.push_live_preview_during_run is True
    assert ProbeSessionConfig().push_live_preview_during_run is False

    payload = config.to_dict()

    assert payload["push_live_preview_during_run"] is True


def test_runner_uses_steady_sample_ms_for_motion_sampling() -> None:
    sampler = RecordingSampler([MotionSample(px_per_sec_x=10.0, px_per_sec_y=0.0, valid_frames=4, average_confidence=0.8)])
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=sampler,
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 10, 10),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            steady_sample_ms=222,
            yaw360_timeout_ms=4444,
        )
    )

    assert sampler.sample_ms_values == [222]


def test_runner_can_keep_controller_connected_after_run() -> None:
    controller = FakeController()
    capture = FakeCapture()
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler([MotionSample(px_per_sec_x=10.0, px_per_sec_y=0.0, valid_frames=4, average_confidence=0.8)]),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
        disconnect_controller_on_finish=False,
    )

    runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["x"], repeats=1))

    assert ("neutral",) in controller.events
    assert ("disconnect",) not in controller.events


def test_runner_waits_then_presses_left_stick_three_times_before_measurement() -> None:
    controller = FakeController()
    capture = FakeCapture()
    sleeps: list[float] = []
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler([MotionSample(px_per_sec_x=10.0, px_per_sec_y=0.0, valid_frames=4, average_confidence=0.8)]),
        motion_estimator_factory=FakeEstimator,
        sleep=sleeps.append,
        point_values=[0.5],
    )

    runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["x"], repeats=1, settle_ms=0))

    assert sleeps[:7] == [1.0, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05]
    assert controller.events[:8] == [
        ("connect",),
        ("press_left_stick",),
        ("release_left_stick",),
        ("press_left_stick",),
        ("release_left_stick",),
        ("press_left_stick",),
        ("release_left_stick",),
        ("stick", 0.5, 0.0),
    ]


def test_runner_passes_capture_fps_and_emits_point_diagnostics() -> None:
    controller = FakeController()
    capture = FakeCapture()
    runner = SteadyProbeRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_sampler=FakeSampler(
            [
                MotionSample(
                    px_per_sec_x=10.0,
                    px_per_sec_y=0.0,
                    valid_frames=5,
                    duplicate_frames=0,
                    average_confidence=0.9,
                    sample_duration_ms=220,
                    stability_score=1.0,
                )
            ]
        ),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    result = runner.run(
        ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["x"], repeats=1, capture_fps=144)
    )

    assert capture.attached_to == 77
    assert capture.capture_fps == 144
    assert result.metadata["capture_fps_requested"] == 144
    assert result.metadata["successful_points"] == 1
    diagnostics = result.metadata["point_diagnostics"]["x"][0]
    assert diagnostics["quality_label"] == "good"
    assert diagnostics["valid_frames"] == 5
    assert diagnostics["duplicate_frames"] == 0


def test_runner_retries_low_stability_point_once_and_marks_retry_used() -> None:
    runner = SteadyProbeRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=FakeCapture,
        motion_sampler=FakeSampler(
            [
                MotionSample(
                    px_per_sec_x=8.0,
                    px_per_sec_y=0.0,
                    valid_frames=4,
                    duplicate_frames=2,
                    average_confidence=0.8,
                    sample_duration_ms=200,
                    stability_score=0.5,
                ),
                MotionSample(
                    px_per_sec_x=12.0,
                    px_per_sec_y=0.0,
                    valid_frames=6,
                    duplicate_frames=0,
                    average_confidence=0.95,
                    sample_duration_ms=260,
                    stability_score=1.0,
                ),
            ]
        ),
        motion_estimator_factory=FakeEstimator,
        sleep=lambda _: None,
        point_values=[0.5],
    )

    result = runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10), axes=["x"], repeats=1))

    assert result.x_curve[0].px_per_sec == 12.0
    assert result.metadata["retry_used_points"] == 1
    diagnostics = result.metadata["point_diagnostics"]["x"][0]
    assert diagnostics["quality_label"] == "retry_used"
    assert diagnostics["retry_used"] is True
