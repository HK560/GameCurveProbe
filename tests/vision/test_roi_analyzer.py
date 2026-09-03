from __future__ import annotations

import numpy as np

from gamecurveprobe.vision.roi_analyzer import RoiAnalyzer


def test_flat_roi_is_poor() -> None:
    result = RoiAnalyzer().analyze(np.zeros((64, 64, 3), dtype=np.uint8))
    assert result.level == "poor"
    assert result.score < 25
