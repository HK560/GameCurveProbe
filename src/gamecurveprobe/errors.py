from __future__ import annotations


class DomainError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JobCanceled(RuntimeError):
    """Internal control-flow exception; never exposed as a 500 response."""
