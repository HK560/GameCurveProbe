from __future__ import annotations

import copy
import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import asdict, fields, replace
from pathlib import Path
from uuid import uuid4

from gamecurveprobe.models import (
    CaptureInfo,
    JobSnapshot,
    NoiseResult,
    ProbeConfig,
    RangeMode,
    RoiQuality,
    RoiRect,
    SessionResult,
    SessionSnapshot,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".gamecurveprobe"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


class SessionService:
    """Owns authoritative in-memory session configuration and state with local persistence."""

    def __init__(
        self,
        session_id: str | None = None,
        config: ProbeConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        self._session_id = session_id or uuid4().hex[:12]
        self._config_path = config_path
        self._config = config or self._load_persisted_config() or ProbeConfig()
        self._roi: RoiRect | None = None
        self._capture: CaptureInfo | None = None
        self._roi_quality: RoiQuality | None = None
        self._last_job: JobSnapshot | None = None
        self._active_job: JobSnapshot | None = None
        self._last_result: SessionResult | None = None
        self._noise: NoiseResult | None = None
        self._lock = threading.RLock()

    def _load_persisted_config(self) -> ProbeConfig | None:
        if not self._config_path or not self._config_path.exists():
            return None
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                valid_field_names = {f.name for f in fields(ProbeConfig)}
                filtered: dict[str, object] = {}
                for k, v in data.items():
                    if k in valid_field_names:
                        if k == "range_mode" and isinstance(v, str):
                            try:
                                v = RangeMode(v)
                            except ValueError:
                                continue
                        filtered[k] = v
                cfg = ProbeConfig(**filtered)
                cfg.validate()
                return cfg
        except Exception as exc:
            logger.warning("Failed to load persistent config from %s: %s", self._config_path, exc)
            return None

    def _save_persisted_config(self) -> None:
        if not self._config_path:
            return
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._config), f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Failed to save persistent config to %s: %s", self._config_path, exc)

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
            self._save_persisted_config()
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

    def set_noise(self, noise: NoiseResult | None) -> None:
        with self._lock:
            self._noise = noise

    def noise_snapshot(self) -> NoiseResult | None:
        with self._lock:
            return copy.deepcopy(self._noise)

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
                    noise=self._noise,
                )
            )
