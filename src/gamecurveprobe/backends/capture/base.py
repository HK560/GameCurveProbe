from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import CaptureHealth, CaptureInfo


@dataclass(frozen=True, slots=True)
class Frame:
    image: np.ndarray
    monotonic_ns: int
    frame_id: int
    is_duplicate: bool = False

    @property
    def frame(self) -> np.ndarray:
        return self.image

    @property
    def timestamp(self) -> float:
        return self.monotonic_ns / 1e9


class CaptureBackend(Protocol):
    name: str

    def attach(self, window_id: int, target_fps: int) -> CaptureInfo:
        raise NotImplementedError

    def read(self, timeout_ms: int) -> Frame | None:
        raise NotImplementedError

    def health(self) -> CaptureHealth:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


def to_bgr(pixels: np.ndarray) -> np.ndarray:
    if pixels.ndim != 3 or pixels.shape[2] not in {3, 4}:
        raise DomainError("CAPTURE_FORMAT_INVALID", "Capture frame format is unsupported.")
    image = pixels[:, :, :3] if pixels.shape[2] == 4 else pixels
    return np.ascontiguousarray(image, dtype=np.uint8)
