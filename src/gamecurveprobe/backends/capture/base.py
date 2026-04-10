from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CaptureBackend(ABC):
    """Abstract screen capture backend."""

    @abstractmethod
    def list_windows(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def attach(self, window_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def grab_frame(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
