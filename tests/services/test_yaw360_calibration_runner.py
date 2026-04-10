from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from gamecurveprobe.models import ProbeSessionConfig, RoiRect
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError
from gamecurveprobe.services.yaw360_calibration_runner import Yaw360CalibrationRunner


class FakeController:
    def __init__(self) -> None:
        self.events: list[tuple[str, float, float] | tuple[str]] = []

    def probe(self) -> bool:
        return True

    def connect(self) -> None:
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


@dataclass
class FakeCapturedFrame:
    frame: np.ndarray
    timestamp: float


class FakeCapture:
    def __init__(self, frames: list[FakeCapturedFrame]) -> None:
        self._frames = list(frames)
        self.attached_to: int | None = None
        self.closed = False

    def attach(self, window_id: int) -> None:
        self.attached_to = window_id

    def grab_frame(self) -> FakeCapturedFrame | None:
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeEstimate:
    px_per_sec_x: float
    px_per_sec_y: float
    tracked_points: int
    confidence: float = 1.0


class FakeEstimator:
    def __init__(self, estimates: list[FakeEstimate]) -> None:
        self._estimates = list(estimates)
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def update(self, frame: np.ndarray, roi: RoiRect, timestamp: float) -> FakeEstimate | None:
        if not self._estimates:
            return None
        return self._estimates.pop(0)


def _roi_frame(value: int) -> np.ndarray:
    frame = np.zeros((24, 24, 3), dtype=np.uint8)
    frame[4:20, 4:20] = value
    return frame


def test_runner_builds_x_positive_curve_from_full_rotation_time() -> None:
    controller = FakeController()
    capture = FakeCapture(
        [
            FakeCapturedFrame(_roi_frame(10), 0.0),
            FakeCapturedFrame(_roi_frame(20), 0.2),
            FakeCapturedFrame(_roi_frame(30), 0.6),
            FakeCapturedFrame(_roi_frame(10), 1.2),
            FakeCapturedFrame(_roi_frame(11), 2.0),
            FakeCapturedFrame(_roi_frame(21), 2.5),
            FakeCapturedFrame(_roi_frame(31), 3.0),
            FakeCapturedFrame(_roi_frame(11), 4.0),
        ]
    )
    estimator = FakeEstimator(
        [
            FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
            FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
            FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
            FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
            FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
            FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
        ]
    )
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: capture,
        motion_estimator_factory=lambda: estimator,
        sleep=lambda _: None,
        point_values=[0.25, 0.5],
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=1,
    )
    similarities = iter([0.25, 1.0, 0.25, 1.0])
    runner._compute_similarity = lambda initial_roi, current_roi: next(similarities)  # type: ignore[method-assign]

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=2500,
        )
    )

    assert capture.attached_to == 77
    assert [point.input_value for point in result.x_curve] == [0.25, 0.5]
    assert [point.direction for point in result.x_curve] == ["positive", "positive"]
    assert result.x_curve[0].deg_per_sec == 300.0
    assert result.x_curve[1].deg_per_sec == 180.0
    assert result.x_curve[0].normalized_speed == 1.0
    assert result.x_curve[1].normalized_speed == 0.6
    assert result.y_curve == []
    assert result.measurement_kind == "yaw360_calibration"
    assert result.summary == "Yaw 360 calibration measured 2 points with 0 fallback points."
    assert result.metadata["successful_points"] == 2
    assert result.metadata["failed_points"] == 0
    assert ("neutral",) in controller.events
    assert ("disconnect",) in controller.events


def test_runner_requires_window_and_roi() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture([]),
        motion_estimator_factory=lambda: FakeEstimator([]),
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="Select a target window"):
        runner.run(ProbeSessionConfig(window_id=None, roi=RoiRect(0, 0, 10, 10)))

    with pytest.raises(ProbeExecutionError, match="Select an ROI"):
        runner.run(ProbeSessionConfig(window_id=1, roi=None))


def test_runner_falls_back_to_zero_when_no_full_rotation_is_detected() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(20), 0.3),
                FakeCapturedFrame(_roi_frame(30), 0.6),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=0.0, px_per_sec_y=0.0, tracked_points=0),
                FakeEstimate(px_per_sec_x=150.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=150.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=lambda _: None,
        point_values=[0.5],
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=1,
    )

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=500,
        )
    )

    assert result.x_curve[0].px_per_sec == 0.0
    assert result.x_curve[0].deg_per_sec == 0.0
    assert result.notes == ["x/positive input 0.5000 repeat 1 did not complete a full 360 rotation within 500 ms."]
    assert result.metadata["failed_points"] == 1


def test_runner_requires_consecutive_similarity_frames_before_finishing_rotation() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(20), 0.2),
                FakeCapturedFrame(_roi_frame(10), 0.6),
                FakeCapturedFrame(_roi_frame(21), 0.9),
                FakeCapturedFrame(_roi_frame(10), 1.2),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=lambda _: None,
        point_values=[0.5],
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=2,
    )
    similarities = iter([0.25, 1.0, 1.0])
    runner._compute_similarity = lambda initial_roi, current_roi: next(similarities)  # type: ignore[method-assign]

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=2000,
        )
    )

    assert result.x_curve[0].deg_per_sec == 300.0


def test_runner_skips_zero_input_when_building_default_point_values() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture([]),
        motion_estimator_factory=lambda: FakeEstimator([]),
        sleep=lambda _: None,
    )

    values = runner._resolve_point_values(ProbeSessionConfig(point_count_per_half_axis=5))

    assert values == [0.25, 0.5, 0.75, 1.0]


def test_runner_applies_deadzone_markers_when_building_default_point_values() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture([]),
        motion_estimator_factory=lambda: FakeEstimator([]),
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


def test_runner_requires_departure_before_similarity_can_finish_rotation() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(10), 0.2),
                FakeCapturedFrame(_roi_frame(10), 0.4),
                FakeCapturedFrame(_roi_frame(20), 0.8),
                FakeCapturedFrame(_roi_frame(10), 1.2),
                FakeCapturedFrame(_roi_frame(10), 1.6),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=120.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=lambda _: None,
        point_values=[0.5],
        similarity_threshold=0.99,
        min_motion_frames=1,
        min_motion_pixels=0.0,
        required_consecutive_similarity_frames=2,
    )
    similarities = iter([1.0, 1.0, 0.25, 1.0, 1.0])
    runner._compute_similarity = lambda initial_roi, current_roi: next(similarities)  # type: ignore[method-assign]

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=2000,
        )
    )

    assert result.x_curve[0].deg_per_sec == pytest.approx(225.0)


def test_runner_uses_yaw360_timeout_ms_for_rotation_timeout() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(20), 0.3),
                FakeCapturedFrame(_roi_frame(30), 0.6),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=0.0, px_per_sec_y=0.0, tracked_points=0),
                FakeEstimate(px_per_sec_x=150.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=150.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=lambda _: None,
        point_values=[0.5],
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=1,
    )

    result = runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            steady_sample_ms=111,
            yaw360_timeout_ms=2345,
        )
    )

    assert result.metadata["sample_timeout_ms"] == 2345


def test_runner_raises_when_controller_probe_fails() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=ProbeFalseController,
        capture_backend_factory=lambda: FakeCapture([]),
        motion_estimator_factory=lambda: FakeEstimator([]),
        sleep=lambda _: None,
        point_values=[0.5],
    )

    with pytest.raises(ProbeExecutionError, match="vgamepad is unavailable"):
        runner.run(ProbeSessionConfig(window_id=77, roi=RoiRect(0, 0, 10, 10)))


def test_runner_rejects_deadzone_marker_range_when_outer_is_not_greater_than_inner() -> None:
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=FakeController,
        capture_backend_factory=lambda: FakeCapture([]),
        motion_estimator_factory=lambda: FakeEstimator([]),
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


def test_runner_can_keep_controller_connected_after_calibration() -> None:
    controller = FakeController()
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(20), 0.2),
                FakeCapturedFrame(_roi_frame(10), 0.6),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=0.0, px_per_sec_y=0.0, tracked_points=0),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=lambda _: None,
        point_values=[0.5],
        disconnect_controller_on_finish=False,
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=1,
    )

    runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=500,
        )
    )

    assert ("neutral",) in controller.events
    assert ("disconnect",) not in controller.events


def test_runner_waits_then_presses_left_stick_three_times_before_calibration() -> None:
    controller = FakeController()
    sleeps: list[float] = []
    runner = Yaw360CalibrationRunner(
        controller_backend_factory=lambda: controller,
        capture_backend_factory=lambda: FakeCapture(
            [
                FakeCapturedFrame(_roi_frame(10), 0.0),
                FakeCapturedFrame(_roi_frame(20), 0.2),
                FakeCapturedFrame(_roi_frame(10), 0.6),
            ]
        ),
        motion_estimator_factory=lambda: FakeEstimator(
            [
                FakeEstimate(px_per_sec_x=0.0, px_per_sec_y=0.0, tracked_points=0),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
                FakeEstimate(px_per_sec_x=180.0, px_per_sec_y=0.0, tracked_points=12),
            ]
        ),
        sleep=sleeps.append,
        point_values=[0.5],
        similarity_threshold=0.99,
        min_motion_frames=2,
        min_motion_pixels=1.0,
        required_consecutive_similarity_frames=1,
    )

    runner.run(
        ProbeSessionConfig(
            window_id=77,
            roi=RoiRect(0, 0, 24, 24),
            axes=["x"],
            repeats=1,
            settle_ms=0,
            yaw360_timeout_ms=500,
        )
    )

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
