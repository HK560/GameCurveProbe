from __future__ import annotations

from pathlib import Path
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


def test_session_service_persists_and_reloads_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "test_config.json"
    s1 = SessionService(config_path=cfg_file)
    assert s1.config_snapshot().hotkey_start == "F9"
    assert s1.config_snapshot().wake_input == "left_stick"

    # Update config with custom preferences
    s1.update_config({
        "hotkey_start": "F8",
        "hotkey_stop": "F12",
        "auto_wake": False,
        "wake_input": "left_stick",
        "sound_enabled": False,
        "inner_deadzone": 0.08,
        "range_mode": RangeMode.FULL,
    })

    assert cfg_file.exists()

    # Create new session service pointing to the same file to verify automatic loading
    s2 = SessionService(config_path=cfg_file)
    loaded = s2.config_snapshot()
    assert loaded.hotkey_start == "F8"
    assert loaded.hotkey_stop == "F12"
    assert loaded.auto_wake is False
    assert loaded.wake_input == "left_stick"
    assert loaded.sound_enabled is False
    assert loaded.inner_deadzone == 0.08
    assert loaded.range_mode == RangeMode.FULL

