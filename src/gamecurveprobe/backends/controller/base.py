from __future__ import annotations

from abc import ABC, abstractmethod


class VirtualControllerBackend(ABC):
    """Abstract virtual controller backend."""

    @abstractmethod
    def probe(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_right_stick(self, x: float, y: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def press_left_stick(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def release_left_stick(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def neutral(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError
