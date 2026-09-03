from __future__ import annotations

import numpy as np

from gamecurveprobe.backends.capture.wgc_backend import WgcCaptureBackend


def test_wgc_backend_converts_bgra_to_bgr() -> None:
    bgra = np.zeros((100, 100, 4), dtype=np.uint8)
    bgra[:, :, 0] = 10
    bgra[:, :, 1] = 20
    bgra[:, :, 2] = 30
    bgra[:, :, 3] = 255

    backend = WgcCaptureBackend(capture_impl=lambda window_id, handler: None)
    backend._handle_raw_frame(bgra)
    frame = backend.read(timeout_ms=100)
    assert frame is not None
    assert frame.image.shape == (100, 100, 3)
    assert frame.image[0, 0, 0] == 10
    assert frame.image[0, 0, 1] == 20
    assert frame.image[0, 0, 2] == 30
