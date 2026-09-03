from __future__ import annotations

import cv2
import numpy as np

from gamecurveprobe.constants import MIN_ROI_SIDE
from gamecurveprobe.models import RoiQuality


class RoiAnalyzer:
    """Analyze ROI image texture, gradient, and feature richness for tracking."""

    def analyze(self, roi_image: np.ndarray) -> RoiQuality:
        height, width = roi_image.shape[:2]
        if height < MIN_ROI_SIDE or width < MIN_ROI_SIDE:
            return RoiQuality(
                score=0,
                level="poor",
                metrics={"gradient": 0.0, "corners": 0.0, "entropy": 0.0, "tracking": 0.0},
                suggestions=("ROI_TOO_SMALL",),
            )

        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY) if roi_image.ndim == 3 else roi_image

        # 1. Gradient magnitude
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(grad_x, grad_y)
        mean_mag = float(np.mean(mag))
        norm_gradient = min(1.0, mean_mag / 40.0)

        # 2. Corners
        corners = cv2.goodFeaturesToTrack(gray, maxCorners=100, qualityLevel=0.01, minDistance=5)
        corner_count = len(corners) if corners is not None else 0
        norm_corners = min(1.0, corner_count / 30.0)

        # 3. Edge-angle histogram entropy
        angles = cv2.phase(grad_x, grad_y, angleInDegrees=True)
        significant_mask = mag > (mean_mag * 0.5)
        if np.any(significant_mask):
            hist, _ = np.histogram(angles[significant_mask], bins=8, range=(0, 360))
            prob = hist / (np.sum(hist) + 1e-6)
            prob = prob[prob > 0]
            entropy = -float(np.sum(prob * np.log2(prob)))
            max_entropy = 3.0  # log2(8)
            norm_entropy = min(1.0, entropy / max_entropy)
        else:
            norm_entropy = 0.0

        # 4. Horizontal tracking suitability (horizontal vs vertical gradient balance)
        mean_gx = float(np.mean(np.abs(grad_x)))
        mean_gy = float(np.mean(np.abs(grad_y)))
        total_g = mean_gx + mean_gy
        norm_tracking = (mean_gx / total_g) if total_g > 1e-3 else 0.0

        score = round(100 * (0.35 * norm_gradient + 0.25 * norm_corners + 0.20 * norm_entropy + 0.20 * norm_tracking))
        score = max(0, min(100, score))

        if score < 25:
            level = "poor"
        elif score < 50:
            level = "fair"
        elif score < 75:
            level = "good"
        else:
            level = "excellent"

        suggestions: list[str] = []
        if norm_gradient < 0.2:
            suggestions.append("REGION_TOO_FLAT")
        if norm_corners < 0.2:
            suggestions.append("FEW_FEATURE_POINTS")
        if norm_tracking < 0.3:
            suggestions.append("LOW_HORIZONTAL_TEXTURE")

        return RoiQuality(
            score=score,
            level=level,
            metrics={
                "gradient": round(norm_gradient, 4),
                "corners": round(norm_corners, 4),
                "entropy": round(norm_entropy, 4),
                "tracking": round(norm_tracking, 4),
            },
            suggestions=tuple(suggestions),
        )
