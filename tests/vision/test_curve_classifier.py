from __future__ import annotations

import numpy as np

from gamecurveprobe.models import MeasurementPoint
from gamecurveprobe.vision.curve_classifier import classify_curve


def valid_point(x: float, y: float) -> MeasurementPoint:
    return MeasurementPoint(
        input=x,
        velocity_px_s=y * 100.0,
        normalized_speed=y,
        stability=0.9,
        valid=True,
        attempts=1,
    )


def test_linear_points_classify_as_linear() -> None:
    points = [valid_point(float(x), float(x)) for x in np.linspace(0, 1, 9)]
    assert classify_curve(points).curve_type == "linear"


def test_ambiguous_fit_is_undetermined() -> None:
    points = [
        valid_point(0.0, 0.0),
        valid_point(0.25, 0.9),
        valid_point(0.5, 0.1),
        valid_point(0.75, 0.8),
        valid_point(1.0, 0.2),
    ]
    assert classify_curve(points).curve_type == "undetermined"
