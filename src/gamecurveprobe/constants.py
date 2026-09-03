from __future__ import annotations

PRESETS: dict[str, dict[str, int]] = {
    "quick": {"point_count": 9, "repeats": 1, "settle_ms": 250, "sample_ms": 500},
    "standard": {"point_count": 17, "repeats": 2, "settle_ms": 300, "sample_ms": 700},
    "precision": {"point_count": 33, "repeats": 2, "settle_ms": 500, "sample_ms": 1000},
}
MIN_ROI_SIDE: int = 32
MIN_TRACKED_POINTS: int = 6
MIN_TRACKING_CONFIDENCE: float = 0.35
MIN_SAMPLE_VALID_FRAMES: int = 5
MIN_VALID_POINTS: int = 5
MIN_VALID_POINT_RATIO: float = 0.60
