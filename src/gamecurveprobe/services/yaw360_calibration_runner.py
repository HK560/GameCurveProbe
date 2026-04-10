from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from gamecurveprobe.models import CurvePoint, ProbeSessionConfig, RoiRect, SessionResult
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError


@dataclass(slots=True)
class RotationMeasurement:
    elapsed_seconds: float
    traveled_pixels: float


@dataclass(slots=True)
class CalibrationMeasurement:
    axis: str
    direction: str
    input_value: float
    px_per_sec: float
    deg_per_sec: float


class Yaw360CalibrationRunner:
    """Measure x-axis turn speed by timing one full 360-degree rotation per input point."""

    _PRE_MEASUREMENT_DELAY_SECONDS = 1.0
    _LEFT_STICK_PRESS_SECONDS = 0.05
    _LEFT_STICK_RELEASE_SECONDS = 0.05
    _LEFT_STICK_PRESS_COUNT = 3

    def __init__(
        self,
        controller_backend_factory: Callable[[], object],
        capture_backend_factory: Callable[[], object],
        motion_estimator_factory: Callable[[], object],
        sleep: Callable[[float], None] | None = None,
        point_values: Sequence[float] | None = None,
        disconnect_controller_on_finish: bool = True,
        similarity_threshold: float = 0.985,
        min_motion_frames: int = 4,
        min_motion_pixels: float = 16.0,
        required_consecutive_similarity_frames: int = 2,
    ) -> None:
        self._controller_backend_factory = controller_backend_factory
        self._capture_backend_factory = capture_backend_factory
        self._motion_estimator_factory = motion_estimator_factory
        self._sleep = sleep or time.sleep
        self._point_values = list(point_values) if point_values is not None else []
        self._disconnect_controller_on_finish = disconnect_controller_on_finish
        self._similarity_threshold = similarity_threshold
        self._min_motion_frames = min_motion_frames
        self._min_motion_pixels = min_motion_pixels
        self._required_consecutive_similarity_frames = max(1, required_consecutive_similarity_frames)
        if any(value < 0.0 or value > 1.0 for value in self._point_values):
            raise ProbeExecutionError("Yaw calibration point_values override must stay within [0.0, 1.0].")

    def run(self, config: ProbeSessionConfig) -> SessionResult:
        if config.window_id is None:
            raise ProbeExecutionError("Select a target window before running yaw calibration.")
        if config.roi is None:
            raise ProbeExecutionError("Select an ROI before running yaw calibration.")
        self._validate_config(config)

        controller = self._controller_backend_factory()
        if not controller.probe():
            raise ProbeExecutionError("vgamepad is unavailable. Install vgamepad and ViGEmBus first.")

        capture = None
        estimator = None
        notes: list[str] = []
        measurements: list[CalibrationMeasurement] = []
        failed_points = 0
        connect_attempted = False

        try:
            capture = self._capture_backend_factory()
            estimator = self._motion_estimator_factory()
            connect_attempted = True
            controller.connect()
            capture.attach(config.window_id)
            self._prepare_measurement_start(controller)

            for input_value in self._resolve_point_values(config):
                controller.set_right_stick(input_value, 0.0)
                self._sleep(config.settle_ms / 1000.0)

                repeat_times: list[RotationMeasurement] = []
                for repeat_index in range(config.repeats):
                    estimator.reset()
                    measurement = self._measure_full_rotation(capture, estimator, config.roi, config.yaw360_timeout_ms)
                    if measurement is None:
                        notes.append(
                            f"x/positive input {input_value:.4f} repeat {repeat_index + 1} "
                            f"did not complete a full 360 rotation within {config.yaw360_timeout_ms} ms."
                        )
                        continue
                    repeat_times.append(measurement)

                if not repeat_times:
                    failed_points += 1
                    measurements.append(
                        CalibrationMeasurement(
                            axis="x",
                            direction="positive",
                            input_value=input_value,
                            px_per_sec=0.0,
                            deg_per_sec=0.0,
                        )
                    )
                    continue

                median_elapsed = sorted(item.elapsed_seconds for item in repeat_times)[len(repeat_times) // 2]
                median_pixels = sorted(item.traveled_pixels for item in repeat_times)[len(repeat_times) // 2]
                deg_per_sec = round(360.0 / median_elapsed, 4)
                measurements.append(
                    CalibrationMeasurement(
                        axis="x",
                        direction="positive",
                        input_value=input_value,
                        px_per_sec=round(median_pixels / median_elapsed, 4),
                        deg_per_sec=deg_per_sec,
                    )
                )
                notes.append(f"x={input_value:.2f} -> {deg_per_sec:.1f} deg/s")
        finally:
            if connect_attempted:
                self._safe_cleanup(controller.neutral)
                if self._disconnect_controller_on_finish:
                    self._safe_cleanup(controller.disconnect)
            if capture is not None:
                self._safe_cleanup(capture.close)

        return SessionResult(
            x_curve=self._build_curve(measurements),
            y_curve=[],
            notes=notes,
            yaw_deg_per_px=None,
            measurement_kind="yaw360_calibration",
            summary=(
                f"Yaw 360 calibration measured {len(measurements)} points with {failed_points} fallback point"
                f"{'s' if failed_points != 1 else ''}."
            ),
            metadata={
                "successful_points": len(measurements) - failed_points,
                "failed_points": failed_points,
                "sample_timeout_ms": config.yaw360_timeout_ms,
                "similarity_threshold": self._similarity_threshold,
                "min_motion_frames": self._min_motion_frames,
                "min_motion_pixels": self._min_motion_pixels,
                "required_consecutive_similarity_frames": self._required_consecutive_similarity_frames,
            },
        )

    def _measure_full_rotation(self, capture, estimator, roi: RoiRect, timeout_ms: int) -> RotationMeasurement | None:
        start_frame = None
        start_timestamp: float | None = None
        last_timestamp: float | None = None
        motion_frames = 0
        traveled_pixels = 0.0
        deadline = None
        consecutive_similarity_frames = 0
        has_departed_from_start = False

        while True:
            captured = capture.grab_frame()
            if captured is None:
                if deadline is not None:
                    return None
                self._sleep(0.005)
                continue

            if start_frame is None:
                cropped = self._crop_roi(captured.frame, roi)
                if cropped is None:
                    raise ProbeExecutionError("Selected ROI is too small for yaw calibration.")
                start_frame = cropped
                start_timestamp = float(captured.timestamp)
                last_timestamp = float(captured.timestamp)
                deadline = start_timestamp + (timeout_ms / 1000.0)
                continue

            current_timestamp = float(captured.timestamp)
            if deadline is not None and current_timestamp > deadline:
                return None

            estimate = estimator.update(captured.frame, roi, current_timestamp)
            dt = max(0.0, current_timestamp - (last_timestamp or current_timestamp))
            last_timestamp = current_timestamp
            if estimate is not None and getattr(estimate, "tracked_points", 0) > 0:
                traveled_pixels += abs(float(getattr(estimate, "px_per_sec_x", 0.0))) * dt
                motion_frames += 1

            if motion_frames < self._min_motion_frames or traveled_pixels < self._min_motion_pixels:
                continue

            current_roi = self._crop_roi(captured.frame, roi)
            if current_roi is None:
                consecutive_similarity_frames = 0
                continue
            similarity = self._compute_similarity(start_frame, current_roi)
            if similarity < self._similarity_threshold:
                has_departed_from_start = True
                consecutive_similarity_frames = 0
                continue
            if not has_departed_from_start:
                consecutive_similarity_frames = 0
                continue
            if similarity >= self._similarity_threshold and start_timestamp is not None:
                consecutive_similarity_frames += 1
                if consecutive_similarity_frames >= self._required_consecutive_similarity_frames:
                    elapsed_seconds = max(1e-6, current_timestamp - start_timestamp)
                    return RotationMeasurement(elapsed_seconds=elapsed_seconds, traveled_pixels=traveled_pixels)
            else:
                consecutive_similarity_frames = 0

    def _build_curve(self, measurements: list[CalibrationMeasurement]) -> list[CurvePoint]:
        max_speed = max((item.deg_per_sec for item in measurements), default=0.0)
        curve: list[CurvePoint] = []
        for item in measurements:
            normalized = 0.0 if max_speed == 0.0 else round(item.deg_per_sec / max_speed, 4)
            curve.append(
                CurvePoint(
                    axis=item.axis,
                    direction=item.direction,
                    input_value=item.input_value,
                    px_per_sec=item.px_per_sec,
                    normalized_speed=normalized,
                    deg_per_sec=item.deg_per_sec,
                )
            )
        return curve

    def _resolve_point_values(self, config: ProbeSessionConfig) -> list[float]:
        if self._point_values:
            return list(self._point_values)
        start = config.inner_deadzone_marker
        end = config.outer_saturation_marker
        count = max(5, config.point_count_per_half_axis)
        step = (end - start) / (count - 1)
        values = [round(start + (step * index), 4) for index in range(count)]
        return [value for value in values if value > 0.0]

    def _validate_config(self, config: ProbeSessionConfig) -> None:
        if any(axis not in {"x", "y"} for axis in config.axes):
            raise ProbeExecutionError("Unsupported axis selection. Only x and y are allowed.")
        if "x" not in config.axes:
            raise ProbeExecutionError("Yaw calibration currently only supports the x axis.")
        if config.repeats <= 0:
            raise ProbeExecutionError("Probe config repeats must be greater than 0.")
        if config.settle_ms < 0:
            raise ProbeExecutionError("Probe config settle_ms must be 0 or greater.")
        if config.yaw360_timeout_ms <= 0:
            raise ProbeExecutionError("Probe config yaw360_timeout_ms must be greater than 0.")
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

    def _crop_roi(self, frame: np.ndarray, roi: RoiRect) -> np.ndarray | None:
        height, width = frame.shape[:2]
        left = max(0, roi.x)
        top = max(0, roi.y)
        right = min(width, roi.x + roi.width)
        bottom = min(height, roi.y + roi.height)
        if right - left < 8 or bottom - top < 8:
            return None
        return frame[top:bottom, left:right]

    def _compute_similarity(self, initial_roi: np.ndarray, current_roi: np.ndarray) -> float:
        initial_gray = cv2.cvtColor(initial_roi, cv2.COLOR_BGR2GRAY)
        current_gray = cv2.cvtColor(current_roi, cv2.COLOR_BGR2GRAY)
        return float(cv2.matchTemplate(current_gray, initial_gray, cv2.TM_CCOEFF_NORMED)[0][0])

    def _safe_cleanup(self, cleanup: Callable[[], object]) -> None:
        try:
            cleanup()
        except Exception:
            return None

    def _prepare_measurement_start(self, controller: object) -> None:
        self._sleep(self._PRE_MEASUREMENT_DELAY_SECONDS)
        for _ in range(self._LEFT_STICK_PRESS_COUNT):
            controller.press_left_stick()
            self._sleep(self._LEFT_STICK_PRESS_SECONDS)
            controller.release_left_stick()
            self._sleep(self._LEFT_STICK_RELEASE_SECONDS)
