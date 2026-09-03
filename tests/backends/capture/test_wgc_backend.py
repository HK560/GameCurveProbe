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


def test_wgc_read_does_not_return_cached_frame_after_timeout() -> None:
    backend = WgcCaptureBackend(capture_impl=lambda window_id, handler: None)
    backend._handle_raw_frame(np.ones((10, 10, 4), dtype=np.uint8))

    assert backend.read(timeout_ms=0) is not None
    assert backend.read(timeout_ms=1) is None


def test_wgc_ignores_frames_from_an_old_attachment_generation() -> None:
    handlers = []

    def capture_impl(window_id, handler):
        handlers.append(handler)
        handler(np.full((10, 10, 4), window_id, dtype=np.uint8))
        return None

    backend = WgcCaptureBackend(capture_impl=capture_impl)
    backend.attach(1)
    backend.attach(2)
    handlers[0](np.full((10, 10, 4), 99, dtype=np.uint8))
    handlers[1](np.full((10, 10, 4), 2, dtype=np.uint8))

    frame = backend.read(timeout_ms=0)
    assert frame is not None
    assert int(frame.image[0, 0, 0]) == 2


def test_wgc_attach_does_not_consume_the_initial_callback_frame() -> None:
    def capture_impl(window_id, handler):
        handler(np.full((10, 10, 4), 7, dtype=np.uint8))
        return None

    backend = WgcCaptureBackend(capture_impl=capture_impl)

    backend.attach(1)

    frame = backend.read(timeout_ms=0)
    assert frame is not None
    assert frame.frame_id == 1
