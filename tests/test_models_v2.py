import pytest

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import JobState, ProbeConfig, RangeMode


def test_standard_preset_has_approved_values() -> None:
    config = ProbeConfig.from_preset("standard")
    assert (config.point_count, config.repeats) == (17, 2)
    assert (config.settle_ms, config.sample_ms) == (300, 700)


def test_full_range_includes_both_deadzone_markers() -> None:
    config = ProbeConfig(inner_deadzone=0.05, outer_deadzone=0.92, point_count=9, range_mode=RangeMode.FULL)
    values = config.point_values()
    assert 0.0 in values and 1.0 in values
    assert 0.05 in values and 0.92 in values


def test_deadzone_order_is_validated() -> None:
    with pytest.raises(DomainError, match="outer_deadzone"):
        ProbeConfig(inner_deadzone=0.8, outer_deadzone=0.8).validate()


def test_job_canceling_is_not_terminal() -> None:
    assert JobState.CANCELING.is_terminal is False
    assert JobState.CANCELED.is_terminal is True
