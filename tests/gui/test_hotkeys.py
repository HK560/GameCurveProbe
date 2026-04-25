from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox
from PySide6.QtWidgets import QApplication

from gamecurveprobe.gui.main_window import MainWindow
from gamecurveprobe.gui.hotkeys import GlobalHotkeyManager
from gamecurveprobe.vision.motion_estimator import MotionEstimate

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeRegistrar:
    def __init__(self) -> None:
        self.registered: list[tuple[int, int, int]] = []
        self.unregistered: list[int] = []
        self.fail_ids: set[int] = set()

    def register(self, hwnd: int, hotkey_id: int, virtual_key: int) -> bool:
        if hotkey_id in self.fail_ids:
            return False
        self.registered.append((hwnd, hotkey_id, virtual_key))
        return True

    def unregister(self, hotkey_id: int) -> None:
        self.unregistered.append(hotkey_id)


def test_global_hotkey_manager_registers_expected_function_keys() -> None:
    registrar = FakeRegistrar()
    manager = GlobalHotkeyManager(registrar=registrar)

    result = manager.register_defaults(1234)

    assert result.failures == []
    assert registrar.registered == [(1234, 1, 0x77), (1234, 2, 0x78), (1234, 3, 0x79)]


def test_global_hotkey_manager_reports_partial_registration_failures() -> None:
    registrar = FakeRegistrar()
    registrar.fail_ids.add(2)
    manager = GlobalHotkeyManager(registrar=registrar)

    result = manager.register_defaults(5678)

    assert result.failures == ["F9"]
    assert registrar.registered == [(5678, 1, 0x77), (5678, 3, 0x79)]


class FakeHttpServer:
    _port = 48231


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.messages.append((title, message))


class FakeWindowService:
    def list_windows(self):
        return []


class FakeInnerDeadzoneCalibrationService:
    def __init__(self) -> None:
        self.is_active = False
        self.current_deadzone = 0.0
        self.current_output = 0.005
        self.calls: list[tuple[str, float] | tuple[str]] = []

    def enter(self, initial_deadzone: float) -> float:
        self.calls.append(("enter", initial_deadzone))
        self.is_active = True
        self.current_deadzone = initial_deadzone
        self.current_output = round(initial_deadzone + 0.005, 3)
        return self.current_deadzone

    def increase(self) -> float:
        self.calls.append(("increase", self.current_deadzone))
        self.current_deadzone = round(min(0.995, self.current_deadzone + 0.005), 3)
        self.current_output = round(self.current_deadzone + 0.005, 3)
        return self.current_deadzone

    def decrease(self) -> float:
        self.calls.append(("decrease", self.current_deadzone))
        self.current_deadzone = round(max(0.0, self.current_deadzone - 0.005), 3)
        self.current_output = round(self.current_deadzone + 0.005, 3)
        return self.current_deadzone

    def exit(self) -> float:
        self.calls.append(("exit",))
        self.is_active = False
        return self.current_deadzone


class FakeSessionService:
    def create_session(self, payload=None):
        from gamecurveprobe.models import ProbeSession, SessionResult

        session = ProbeSession()
        session.result = SessionResult(
            summary="Yaw 360 calibration measured 3 points with 1 fallback point.",
            measurement_kind="yaw360_calibration",
        )
        return session

    def build_driver_curve(self, points):
        return points

    def run_steady(self, session_id: str):
        raise AssertionError("run_steady should not be called synchronously in this test")

    def calibrate_yaw360(self, session_id: str):
        raise AssertionError("calibrate_yaw360 should not be called synchronously in this test")

    def cancel(self, session_id: str):
        session = self.create_session()
        session.status.session_id = session_id
        session.status.message = "Session canceled."
        return session


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window():
    _app()
    window = MainWindow(
        session_service=FakeSessionService(),
        window_service=FakeWindowService(),
        http_server=FakeHttpServer(),
        inner_deadzone_calibration_service=FakeInnerDeadzoneCalibrationService(),
    )
    try:
        yield window
    finally:
        window.close()


def test_main_window_blocks_duplicate_steady_start_and_notifies(main_window) -> None:
    window = main_window
    window._is_steady_running = True
    window._notifier = FakeNotifier()

    window._start_steady_run()

    assert window._notifier.messages[-1] == ("GameCurveProbe", "Steady probe is already running.")


def test_main_window_moves_steady_worker_to_background_thread(main_window) -> None:
    window = main_window

    window._create_run_worker("run_steady")

    assert window._run_thread is not None
    assert isinstance(window._run_thread, QThread)
    assert window._run_worker.thread() is window._run_thread


def test_main_window_uses_split_default_timing_controls(main_window) -> None:
    window = main_window

    assert window.steady_sample_ms.value() == 700
    assert window.yaw360_timeout_ms.value() == 4000


def test_main_window_disables_live_preview_during_tests_by_default(main_window) -> None:
    window = main_window

    assert window.live_preview_during_run.isChecked() is False
    assert window._session.config.push_live_preview_during_run is False


def test_main_window_syncs_split_timing_fields_to_session_config(main_window) -> None:
    window = main_window

    window.steady_sample_ms.setValue(850)
    window.yaw360_timeout_ms.setValue(4600)

    window._sync_config_from_ui()

    assert window._session.config.steady_sample_ms == 850
    assert window._session.config.yaw360_timeout_ms == 4600


def test_main_window_moves_calibration_worker_to_background_thread(main_window) -> None:
    window = main_window

    window._create_run_worker("calibrate_yaw360")

    assert window._run_thread is not None
    assert isinstance(window._run_thread, QThread)
    assert window._run_worker.thread() is window._run_thread


def test_main_window_exposes_inner_deadzone_calibration_action(main_window) -> None:
    window = main_window

    assert window.calibrate_button.isEnabled() is True
    assert window.calibrate_button.text() == "Calibrate Inner Deadzone"
    assert window.dynamic_button.isEnabled() is False
    assert "preview build" in window.dynamic_button.toolTip().lower()


def test_main_window_enters_inner_deadzone_calibration_mode(main_window) -> None:
    window = main_window
    service = window._inner_deadzone_calibration_service

    window.inner_deadzone_input.setValue(0.120)
    window._toggle_inner_deadzone_calibration()

    assert service.calls == [("enter", 0.12)]
    assert window.calibrate_button.text() == "Exit Inner Deadzone Calibration"
    assert window._inner_deadzone_calibration_active is True
    assert window.steady_button.isEnabled() is False
    assert window.idle_noise_button.isEnabled() is False
    assert window.export_button.isEnabled() is False
    assert window.inner_deadzone_input.isEnabled() is False
    assert "deadzone=0.120" in window.status_label.text()


def test_main_window_pauses_preview_when_steady_measurement_starts_by_default(main_window) -> None:
    window = main_window
    create_run_worker_calls: list[str] = []

    def fake_create_run_worker(action: str) -> None:
        create_run_worker_calls.append(action)
        window._run_thread = QThread(window)

    window._create_run_worker = fake_create_run_worker  # type: ignore[method-assign]

    assert window._preview_timer.isActive()

    window._start_steady_run()

    assert create_run_worker_calls == ["run_steady"]
    assert not window._preview_timer.isActive()
    assert "paused during measurement" in window.preview_widget._status_text


def test_main_window_keeps_preview_running_when_live_preview_during_tests_is_enabled(main_window) -> None:
    window = main_window
    create_run_worker_calls: list[str] = []

    def fake_create_run_worker(action: str) -> None:
        create_run_worker_calls.append(action)
        window._run_thread = QThread(window)

    window.live_preview_during_run.setChecked(True)
    window._create_run_worker = fake_create_run_worker  # type: ignore[method-assign]

    assert window._preview_timer.isActive()

    window._start_steady_run()

    assert create_run_worker_calls == ["run_steady"]
    assert window._preview_timer.isActive()
    assert "paused during measurement" not in window.preview_widget._status_text


def test_main_window_removes_y_curve_widget(main_window) -> None:
    window = main_window

    assert not hasattr(window, "y_curve_widget")


def test_main_window_shows_result_summary_in_notes_and_curve_title(main_window) -> None:
    window = main_window

    assert "Yaw 360 calibration measured 3 points with 1 fallback point." in window.notes_edit.toPlainText()
    assert "Yaw 360 calibration" in window.x_curve_widget._title


def test_main_window_applies_parameter_changes_immediately(main_window) -> None:
    window = main_window

    window.steady_sample_ms.setValue(850)
    window.yaw360_timeout_ms.setValue(4600)
    window.live_smoothing.setValue(40)
    window.min_confidence.setValue(0.55)

    assert window._session.config.steady_sample_ms == 850
    assert window._session.config.yaw360_timeout_ms == 4600
    assert window._session.config.live_smoothing_factor == 0.4
    assert window._session.config.motion_min_confidence == 0.55


def test_main_window_exposes_deadzone_spinboxes_with_half_percent_precision(main_window) -> None:
    window = main_window

    assert window.inner_deadzone_input.decimals() == 3
    assert window.inner_deadzone_input.singleStep() == pytest.approx(0.005)
    assert window.inner_deadzone_input.minimum() == pytest.approx(0.0)
    assert window.inner_deadzone_input.maximum() == pytest.approx(0.995)
    assert window.outer_saturation_input.decimals() == 3
    assert window.outer_saturation_input.singleStep() == pytest.approx(0.005)
    assert window.outer_saturation_input.minimum() == pytest.approx(0.005)
    assert window.outer_saturation_input.maximum() == pytest.approx(1.0)
    assert window.inner_deadzone.value() == 0
    assert window.outer_saturation.value() == 200


def test_main_window_syncs_deadzone_spinboxes_to_sliders_and_session_config(main_window) -> None:
    window = main_window

    window.inner_deadzone_input.setValue(0.235)
    window.outer_saturation_input.setValue(0.875)

    assert window.inner_deadzone.value() == 47
    assert window.outer_saturation.value() == 175
    assert window._session.config.inner_deadzone_marker == pytest.approx(0.235)
    assert window._session.config.outer_saturation_marker == pytest.approx(0.875)


def test_main_window_syncs_deadzone_sliders_back_to_spinboxes(main_window) -> None:
    window = main_window

    window.inner_deadzone.setValue(50)
    window.outer_saturation.setValue(150)

    assert window.inner_deadzone_input.value() == pytest.approx(0.25)
    assert window.outer_saturation_input.value() == pytest.approx(0.75)


def test_main_window_keeps_deadzone_controls_in_valid_order(main_window) -> None:
    window = main_window

    window.inner_deadzone_input.setValue(0.995)

    assert window.outer_saturation_input.value() == pytest.approx(1.0)
    assert window._session.config.inner_deadzone_marker == pytest.approx(0.995)
    assert window._session.config.outer_saturation_marker == pytest.approx(1.0)

    window.outer_saturation_input.setValue(0.005)

    assert window.inner_deadzone_input.value() == pytest.approx(0.0)
    assert window._session.config.inner_deadzone_marker == pytest.approx(0.0)
    assert window._session.config.outer_saturation_marker == pytest.approx(0.005)


def test_main_window_uses_large_spinbox_step_button_hit_areas(main_window) -> None:
    window = main_window
    window.show()
    _app().processEvents()

    for spin in (window.capture_fps, window.min_confidence):
        option = QStyleOptionSpinBox()
        spin.initStyleOption(option)
        style = spin.style()
        up_rect = style.subControlRect(QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxUp, spin)
        down_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxDown,
            spin,
        )

        assert up_rect.width() >= 20
        assert down_rect.width() >= 20
        assert up_rect.height() >= 15
        assert down_rect.height() >= 15


def test_main_window_restores_preview_after_run_finish_when_it_was_paused(main_window) -> None:
    window = main_window
    window._set_preview_running(False)

    session = window._session
    session.status.message = "done"
    window._on_run_finished(session)

    assert window._preview_timer.isActive()


def test_main_window_remaps_hotkeys_while_inner_deadzone_calibration_is_active(main_window) -> None:
    window = main_window
    service = window._inner_deadzone_calibration_service

    window._toggle_inner_deadzone_calibration()

    assert window._handle_hotkey(1) is True
    assert window.inner_deadzone_input.value() == pytest.approx(0.005)
    assert window._handle_hotkey(2) is True
    assert window.inner_deadzone_input.value() == pytest.approx(0.0)
    assert window._handle_hotkey(3) is True
    assert window._inner_deadzone_calibration_active is False
    assert ("increase", 0.0) in service.calls
    assert ("decrease", 0.005) in service.calls
    assert ("exit",) in service.calls


def test_main_window_writes_calibrated_deadzone_back_on_exit(main_window) -> None:
    window = main_window

    window._toggle_inner_deadzone_calibration()
    window._handle_hotkey(1)
    window._toggle_inner_deadzone_calibration()

    assert window._session.config.inner_deadzone_marker == pytest.approx(0.005)
    assert window.calibrate_button.text() == "Calibrate Inner Deadzone"
    assert window.steady_button.isEnabled() is True
    assert window.inner_deadzone_input.isEnabled() is True


def test_main_window_close_event_exits_inner_deadzone_calibration_mode(main_window) -> None:
    window = main_window
    service = window._inner_deadzone_calibration_service

    window._toggle_inner_deadzone_calibration()
    window.close()

    assert ("exit",) in service.calls


def test_main_window_pauses_preview_when_idle_noise_starts_by_default(main_window) -> None:
    window = main_window

    def fake_create_run_worker(action: str) -> None:
        window._run_thread = QThread(window)

    window._create_run_worker = fake_create_run_worker  # type: ignore[method-assign]

    window._calibrate_idle_noise()

    assert not window._preview_timer.isActive()


def test_main_window_cancel_restores_preview_if_measurement_paused_it(main_window) -> None:
    window = main_window
    window._set_preview_running(False)
    window._run_thread = QThread(window)

    window._cancel()

    assert window._preview_timer.isActive()


def test_main_window_filters_low_quality_live_motion(main_window) -> None:
    window = main_window
    window._session.config.motion_min_tracked_points = 8
    window._session.config.motion_min_confidence = 0.35

    motion = window._filter_and_smooth_motion(
        MotionEstimate(px_per_sec_x=250.0, px_per_sec_y=25.0, tracked_points=4, confidence=0.9)
    )

    assert motion is None


def test_main_window_smooths_live_motion_with_previous_value(main_window) -> None:
    window = main_window
    window._session.config.live_smoothing_factor = 0.5
    window._session.config.motion_min_tracked_points = 8
    window._session.config.motion_min_confidence = 0.35
    window._latest_motion = MotionEstimate(px_per_sec_x=100.0, px_per_sec_y=20.0, tracked_points=12, confidence=0.8)

    motion = window._filter_and_smooth_motion(
        MotionEstimate(px_per_sec_x=140.0, px_per_sec_y=40.0, tracked_points=12, confidence=0.8)
    )

    assert motion is not None
    assert motion.px_per_sec_x == 120.0
    assert motion.px_per_sec_y == 30.0
