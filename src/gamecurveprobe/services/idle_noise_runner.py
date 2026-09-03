from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any

from gamecurveprobe.constants import MIN_TRACKED_POINTS, MIN_TRACKING_CONFIDENCE
from gamecurveprobe.errors import JobCanceled
from gamecurveprobe.models import NoiseResult, ProbeConfig, RoiRect
from gamecurveprobe.services.motion_sampler import MotionSampler
from gamecurveprobe.vision.motion_estimator import MotionEstimator


class IdleNoiseRunner:
    """Run cancellable idle noise sampling on the selected ROI."""

    def __init__(
        self,
        capture_factory: Callable[[], Any],
        estimator_factory: Callable[[], Any] | None = None,
        motion_sampler: MotionSampler | None = None,
        roi: RoiRect | None = None,
    ) -> None:
        self._capture_factory = capture_factory
        self._estimator_factory = estimator_factory or MotionEstimator
        self._sampler = motion_sampler or MotionSampler()
        self._roi = roi

    def run(
        self,
        config: ProbeConfig,
        cancel_event: threading.Event,
        publish: Callable[[Mapping[str, object]], None],
    ) -> NoiseResult:
        if cancel_event.is_set():
            raise JobCanceled()

        capture = self._capture_factory()
        estimator = self._estimator_factory()
        roi = self._roi or RoiRect(0, 0, 100, 100)

        sample = self._sampler.sample_noise_floor(
            capture,
            estimator,
            roi,
            1200,
            min_tracked_points=MIN_TRACKED_POINTS,
            min_confidence=MIN_TRACKING_CONFIDENCE,
            band_percentile=0.9,
            cancel_event=cancel_event,
        )

        if sample.canceled:
            raise JobCanceled()

        publish({
            "stage": "completed",
            "floor_x": sample.px_per_sec_x,
            "floor_y": sample.px_per_sec_y,
        })

        return NoiseResult(
            floor_x=round(sample.px_per_sec_x, 4),
            floor_y=round(sample.px_per_sec_y, 4),
            valid_frames=sample.valid_frames,
            confidence=round(sample.average_confidence, 4),
        )
