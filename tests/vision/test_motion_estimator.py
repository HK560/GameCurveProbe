from __future__ import annotations

import numpy as np

from gamecurveprobe.vision.motion_estimator import MotionEstimator


def test_detect_features_prefers_points_with_stronger_x_gradient(monkeypatch) -> None:
    gray = np.zeros((32, 32), dtype=np.uint8)
    grad_x = np.zeros((32, 32), dtype=np.float32)
    grad_y = np.zeros((32, 32), dtype=np.float32)

    candidate_points = np.array(
        [
            [[8.0, 10.0]],
            [[15.0, 11.0]],
            [[6.0, 24.0]],
            [[26.0, 24.0]],
        ],
        dtype=np.float32,
    )
    grad_x[10, 8] = 10.0
    grad_y[10, 8] = 2.0
    grad_x[11, 15] = 9.0
    grad_y[11, 15] = 1.0
    grad_x[24, 6] = 2.0
    grad_y[24, 6] = 8.0
    grad_x[24, 26] = 1.0
    grad_y[24, 26] = 7.0

    monkeypatch.setattr(
        "gamecurveprobe.vision.motion_estimator.cv2.goodFeaturesToTrack",
        lambda *args, **kwargs: candidate_points,
    )
    sobel_values = iter([grad_x, grad_y])
    monkeypatch.setattr(
        "gamecurveprobe.vision.motion_estimator.cv2.Sobel",
        lambda *args, **kwargs: next(sobel_values),
    )

    estimator = MotionEstimator(horizontal_texture_bias=1.1, minimum_feature_count=2)

    filtered = estimator._detect_features(gray)

    assert filtered is not None
    kept = {(round(float(point[0][0])), round(float(point[0][1]))) for point in filtered}
    assert (8, 10) in kept
    assert (15, 11) in kept
    assert (6, 24) not in kept
    assert (26, 24) not in kept


def test_detect_features_falls_back_to_x_dominant_points_when_threshold_is_too_strict(monkeypatch) -> None:
    gray = np.zeros((24, 24), dtype=np.uint8)
    grad_x = np.zeros((24, 24), dtype=np.float32)
    grad_y = np.zeros((24, 24), dtype=np.float32)

    candidate_points = np.array(
        [
            [[10.0, 6.0]],
            [[11.0, 12.0]],
            [[10.0, 18.0]],
        ],
        dtype=np.float32,
    )
    grad_x[6, 10] = 5.0
    grad_y[6, 10] = 4.9
    grad_x[12, 11] = 4.0
    grad_y[12, 11] = 3.95
    grad_x[18, 10] = 3.0
    grad_y[18, 10] = 2.98

    monkeypatch.setattr(
        "gamecurveprobe.vision.motion_estimator.cv2.goodFeaturesToTrack",
        lambda *args, **kwargs: candidate_points,
    )
    sobel_values = iter([grad_x, grad_y])
    monkeypatch.setattr(
        "gamecurveprobe.vision.motion_estimator.cv2.Sobel",
        lambda *args, **kwargs: next(sobel_values),
    )

    estimator = MotionEstimator(horizontal_texture_bias=10.0, minimum_feature_count=2)

    filtered = estimator._detect_features(gray)

    assert filtered is not None
    assert len(filtered) == 2
