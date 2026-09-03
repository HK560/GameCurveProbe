from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from gamecurveprobe.models import RoiRect


@dataclass(slots=True)
class MotionEstimate:
    dx: float = 0.0
    dy: float = 0.0
    px_per_sec_x: float = 0.0
    px_per_sec_y: float = 0.0
    tracked_points: int = 0
    confidence: float = 0.0
    dt: float | None = None


class MotionEstimator:
    """Estimate per-frame ROI motion using sparse optical flow."""

    def __init__(self, horizontal_texture_bias: float = 1.15, minimum_feature_count: int = 6) -> None:
        self._horizontal_texture_bias = max(1.0, float(horizontal_texture_bias))
        self._minimum_feature_count = max(1, int(minimum_feature_count))
        self.reset()

    def reset(self) -> None:
        self._prev_gray: np.ndarray | None = None
        self._prev_points: np.ndarray | None = None
        self._prev_timestamp: float | None = None

    def update(self, frame: np.ndarray, roi: RoiRect | None, timestamp: float) -> MotionEstimate | None:
        if roi is None:
            self.reset()
            return None

        cropped = self._crop_roi(frame, roi)
        if cropped is None:
            self.reset()
            return None

        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is None or self._prev_points is None or len(self._prev_points) < 6:
            self._prev_gray = gray
            self._prev_points = self._detect_features(gray)
            self._prev_timestamp = timestamp
            return MotionEstimate(tracked_points=0, confidence=0.0)

        lk_params = dict(
            winSize=(31, 31),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        next_points, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, self._prev_points, None, **lk_params
        )
        if next_points is None or status is None:
            self._prev_gray = gray
            self._prev_points = self._detect_features(gray)
            self._prev_timestamp = timestamp
            return MotionEstimate(tracked_points=0, confidence=0.0)

        valid_mask = status.reshape(-1) == 1
        prev_valid = self._prev_points[valid_mask].reshape(-1, 2)
        next_valid = next_points[valid_mask].reshape(-1, 2)
        if len(next_valid):
            back_points, back_status, _ = cv2.calcOpticalFlowPyrLK(
                gray, self._prev_gray, next_valid.reshape(-1, 1, 2), None, **lk_params
            )
            if back_points is not None and back_status is not None:
                fb_error = np.linalg.norm(
                    prev_valid - back_points.reshape(-1, 2), axis=1
                )
                # A one-pixel gate is too strict at 60 FPS/high turn rates;
                # retain only clearly divergent tracks while allowing normal
                # pyramid interpolation error.
                valid_mask = (back_status.reshape(-1) == 1) & (fb_error <= 2.5)
                if int(valid_mask.sum()) >= self._minimum_feature_count:
                    prev_valid = prev_valid[valid_mask]
                    next_valid = next_valid[valid_mask]
        if len(next_valid) >= 4:
            try:
                _transform, inlier_mask = cv2.estimateAffinePartial2D(
                    prev_valid,
                    next_valid,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=2.0,
                    maxIters=200,
                    confidence=0.99,
                )
                if inlier_mask is not None and int(inlier_mask.sum()) >= self._minimum_feature_count:
                    inliers = inlier_mask.reshape(-1).astype(bool)
                    prev_valid = prev_valid[inliers]
                    next_valid = next_valid[inliers]
            except cv2.error:
                pass
        tracked_points = len(next_valid)
        if tracked_points == 0:
            self._prev_gray = gray
            self._prev_points = self._detect_features(gray)
            self._prev_timestamp = timestamp
            return MotionEstimate(tracked_points=0, confidence=0.0)

        deltas = next_valid - prev_valid
        median_dx = float(np.median(deltas[:, 0]))
        median_dy = float(np.median(deltas[:, 1]))
        dt = max(1e-6, timestamp - (self._prev_timestamp if self._prev_timestamp is not None else timestamp))
        estimate = MotionEstimate(
            dx=median_dx,
            dy=median_dy,
            px_per_sec_x=median_dx / dt,
            px_per_sec_y=median_dy / dt,
            tracked_points=tracked_points,
            confidence=float(tracked_points / max(1, len(self._prev_points))),
            dt=dt,
        )

        self._prev_gray = gray
        self._prev_points = next_valid.reshape(-1, 1, 2)
        if tracked_points < 12:
            self._prev_points = self._detect_features(gray)
        self._prev_timestamp = timestamp
        return estimate

    def _crop_roi(self, frame: np.ndarray, roi: RoiRect) -> np.ndarray | None:
        height, width = frame.shape[:2]
        left = max(0, roi.x)
        top = max(0, roi.y)
        right = min(width, roi.x + roi.width)
        bottom = min(height, roi.y + roi.height)
        if right - left < 8 or bottom - top < 8:
            return None
        return frame[top:bottom, left:right]

    def _detect_features(self, gray: np.ndarray) -> np.ndarray | None:
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=120,
            qualityLevel=0.01,
            minDistance=6,
            blockSize=7,
        )
        return self._filter_horizontal_texture_features(gray, corners)

    def _filter_horizontal_texture_features(self, gray: np.ndarray, corners: np.ndarray | None) -> np.ndarray | None:
        if corners is None or len(corners) == 0:
            return None

        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

        kept: list[np.ndarray] = []
        ranked: list[tuple[float, np.ndarray]] = []
        height, width = gray.shape[:2]

        for point in corners.reshape(-1, 2):
            x = int(np.clip(round(float(point[0])), 0, width - 1))
            y = int(np.clip(round(float(point[1])), 0, height - 1))
            gx = abs(float(grad_x[y, x]))
            gy = abs(float(grad_y[y, x]))
            ranked.append((gx - gy, np.array([[float(point[0]), float(point[1])]], dtype=np.float32)))
            if gx >= gy * self._horizontal_texture_bias:
                kept.append(np.array([[float(point[0]), float(point[1])]], dtype=np.float32))

        if len(kept) >= self._minimum_feature_count:
            return np.array(kept, dtype=np.float32)

        ranked.sort(key=lambda item: item[0], reverse=True)
        fallback = [point for _, point in ranked[: min(self._minimum_feature_count, len(ranked))]]
        if not fallback:
            return None
        return np.array(fallback, dtype=np.float32)
