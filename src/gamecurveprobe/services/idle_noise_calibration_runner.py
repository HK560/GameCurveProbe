from __future__ import annotations

from collections.abc import Callable

from gamecurveprobe.models import ProbeSessionConfig, SessionResult
from gamecurveprobe.services.motion_sampler import MotionSampler
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError


class IdleNoiseCalibrationRunner:
    """Measure stationary ROI jitter and store it as a noise floor."""

    def __init__(
        self,
        capture_backend_factory: Callable[[], object],
        motion_sampler: MotionSampler,
        motion_estimator_factory: Callable[[], object],
    ) -> None:
        self._capture_backend_factory = capture_backend_factory
        self._motion_sampler = motion_sampler
        self._motion_estimator_factory = motion_estimator_factory

    def run(self, config: ProbeSessionConfig) -> SessionResult:
        if config.window_id is None:
            raise ProbeExecutionError("Select a target window before calibrating idle noise.")
        if config.roi is None:
            raise ProbeExecutionError("Select an ROI before calibrating idle noise.")
        if config.idle_noise_sample_ms <= 0:
            raise ProbeExecutionError("Idle noise sample_ms must be greater than 0.")

        capture = None
        try:
            capture = self._capture_backend_factory()
            estimator = self._motion_estimator_factory()
            capture.attach(config.window_id)
            estimator.reset()
            sample = self._motion_sampler.sample_noise_floor(
                capture,
                estimator,
                config.roi,
                config.idle_noise_sample_ms,
                min_tracked_points=config.motion_min_tracked_points,
                min_confidence=config.motion_min_confidence,
                band_percentile=config.idle_noise_band_percentile,
            )
        finally:
            if capture is not None:
                try:
                    capture.close()
                except Exception:
                    pass

        return SessionResult(
            notes=[
                (
                    f"Idle noise band calibrated: vx +/-{sample.px_per_sec_x:.1f}px/s, "
                    f"vy +/-{sample.px_per_sec_y:.1f}px/s from {sample.valid_frames} valid frames."
                )
            ],
            summary="Idle noise calibration complete.",
            measurement_kind="idle_noise_calibration",
            metadata={
                "idle_noise_floor_x": sample.px_per_sec_x,
                "idle_noise_floor_y": sample.px_per_sec_y,
                "idle_noise_band_percentile": config.idle_noise_band_percentile,
                "valid_frames": sample.valid_frames,
                "average_confidence": sample.average_confidence,
            },
        )
