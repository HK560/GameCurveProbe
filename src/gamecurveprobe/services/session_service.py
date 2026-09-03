from __future__ import annotations

import copy
import threading
from collections.abc import Mapping
from dataclasses import replace
from uuid import uuid4

from gamecurveprobe.models import (
    CaptureInfo,
    JobSnapshot,
    ProbeConfig,
    RoiQuality,
    RoiRect,
    SessionResult,
    SessionSnapshot,
)


class SessionService:
    """Owns authoritative in-memory session configuration and state."""

    def __init__(self, session_id: str | None = None) -> None:
        self._session_id = session_id or uuid4().hex[:12]
        self._config = ProbeConfig()
        self._roi: RoiRect | None = None
        self._capture: CaptureInfo | None = None
        self._roi_quality: RoiQuality | None = None
        self._last_job: JobSnapshot | None = None
        self._active_job: JobSnapshot | None = None
        self._last_result: SessionResult | None = None
        self._lock = threading.RLock()

    @property
    def id(self) -> str:
        return self._session_id

    def config_snapshot(self) -> ProbeConfig:
        with self._lock:
            return copy.deepcopy(self._config)

    def update_config(self, changes: Mapping[str, object]) -> ProbeConfig:
        with self._lock:
            candidate = replace(self._config, **changes)
            candidate.validate()
            self._config = candidate
            return copy.deepcopy(candidate)

    def update_roi(self, roi: RoiRect | None) -> RoiRect | None:
        with self._lock:
            self._roi = copy.deepcopy(roi)
            return self._roi

    def update_capture(self, capture: CaptureInfo | None) -> CaptureInfo | None:
        with self._lock:
            self._capture = capture
            return self._capture

    def update_roi_quality(self, quality: RoiQuality | None) -> RoiQuality | None:
        with self._lock:
            self._roi_quality = quality
            return self._roi_quality

    def set_active_job(self, job: JobSnapshot | None) -> None:
        with self._lock:
            self._active_job = job

    def set_last_job(self, job: JobSnapshot | None) -> None:
        with self._lock:
            self._last_job = job

    def set_last_result(self, result: SessionResult | None) -> None:
        with self._lock:
            self._last_result = result

    def snapshot(self) -> SessionSnapshot:
        with self._lock:
            return copy.deepcopy(
                SessionSnapshot(
                    id=self._session_id,
                    config=self._config,
                    roi=self._roi,
                    capture=self._capture,
                    roi_quality=self._roi_quality,
                    last_job=self._last_job,
                    active_job=self._active_job,
                    last_result=self._last_result,
                )
            )
