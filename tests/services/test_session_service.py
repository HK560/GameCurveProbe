from __future__ import annotations

import pytest

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import (
    CaptureInfo,
    ProbeConfig,
    RangeMode,
    RoiQuality,
    RoiRect,
    SessionResult,
    SessionSnapshot,
)
from gamecurveprobe.services.session_service import SessionService


def test_session_service_has_stable_id() -> None:
    service = SessionService()
    assert service.id
    assert isinstance(service.id, str)
    assert len(service.id) >= 8


def test_update_config_validates_and_updates_atomically() -> None:
    service = SessionService()
    initial_config = service.config_snapshot()
    assert initial_config.point_count == 17

    updated = service.update_config({"point_count": 33, "range_mode": RangeMode.FULL})
    assert updated.point_count == 33
    assert updated.range_mode == RangeMode.FULL
    assert service.config_snapshot().point_count == 33

    # Invalid update should fail and leave config unchanged
    with pytest.raises(DomainError):
        service.update_config({"outer_deadzone": 0.05, "inner_deadzone": 0.5})

    assert service.config_snapshot().point_count == 33
    assert service.config_snapshot().inner_deadzone == 0.0


def test_session_snapshot_is_immutable_copy() -> None:
    service = SessionService()
    service.update_roi(RoiRect(10, 20, 100, 100))
    service.update_capture(
        CaptureInfo(
            window_id=123,
            backend="wgc",
            width=1920,
            height=1080,
            target_fps=120,
            title="Test Game",
        )
    )

    snapshot = service.snapshot()
    assert isinstance(snapshot, SessionSnapshot)
    assert snapshot.id == service.id
    assert snapshot.roi == RoiRect(10, 20, 100, 100)
    assert snapshot.capture is not None
    assert snapshot.capture.backend == "wgc"

    # Updating service should not change already returned snapshot
    service.update_roi(RoiRect(30, 40, 200, 200))
    assert snapshot.roi == RoiRect(10, 20, 100, 100)
    assert service.snapshot().roi == RoiRect(30, 40, 200, 200)
