from __future__ import annotations

import ctypes

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gamecurveprobe.backends.capture import DxcamCaptureBackend
from gamecurveprobe.gui.hotkeys import GlobalHotkeyManager
from gamecurveprobe.gui.notifications import DesktopNotifier, QtSystemTrayBackend
from gamecurveprobe.gui.run_worker import RunWorker
from gamecurveprobe.gui.widgets.curve_preview import CurvePreviewWidget
from gamecurveprobe.gui.widgets.live_preview import LivePreviewWidget
from gamecurveprobe.models import RoiRect
from gamecurveprobe.services.http_server import LocalHttpServer
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService
from gamecurveprobe.vision.motion_estimator import MotionEstimate, MotionEstimator


YAW360_PREVIEW_DISABLED_MESSAGE = "Yaw 360 calibration is disabled in this preview build."
DYNAMIC_PREVIEW_DISABLED_MESSAGE = "Dynamic response run is disabled in this preview build."
DEADZONE_STEP = 0.005
DEADZONE_TICK_SCALE = int(round(1.0 / DEADZONE_STEP))
MIN_OUTER_DEADZONE_TICK = 1
MAX_INNER_DEADZONE_TICK = DEADZONE_TICK_SCALE - 1


class MainWindow(QMainWindow):
    WM_HOTKEY = 0x0312

    def __init__(
        self,
        session_service: SessionService,
        window_service: WindowService,
        http_server: LocalHttpServer,
        inner_deadzone_calibration_service,
    ) -> None:
        super().__init__()
        self._session_service = session_service
        self._window_service = window_service
        self._http_server = http_server
        self._inner_deadzone_calibration_service = inner_deadzone_calibration_service
        self._session = self._session_service.create_session()
        self._capture_backend = DxcamCaptureBackend(window_service=window_service)
        self._motion_estimator = MotionEstimator()
        self._latest_motion: MotionEstimate | None = None
        self._is_steady_running = False
        self._inner_deadzone_calibration_active = False
        self._run_thread: QThread | None = None
        self._run_worker: RunWorker | None = None
        self._hotkey_manager = GlobalHotkeyManager() if hasattr(ctypes, "windll") else None
        self._tray_backend = QtSystemTrayBackend(self)
        self._notifier = DesktopNotifier(self._tray_backend)

        self.setWindowTitle("GameCurveProbe")
        self.resize(1440, 920)
        self._build_ui()
        self._refresh_windows()
        self._refresh_session_view()
        self._register_global_hotkeys()

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000 // 20)
        self._preview_timer.timeout.connect(self._poll_preview)
        self._preview_timer.start()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        header = QLabel("Measure controller input curves with a shared GUI + IPC session model.")
        header.setStyleSheet("font-size: 16px; color: #dfe9f7;")
        outer.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, stretch=1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([420, 980])

        left_layout.addWidget(self._build_environment_box())
        left_layout.addWidget(self._build_parameter_box())
        left_layout.addWidget(self._build_actions_box())
        left_layout.addStretch(1)

        right_layout.addWidget(self._build_preview_box(), stretch=4)
        right_layout.addWidget(self._build_curve_box(), stretch=4)
        right_layout.addWidget(self._build_log_box(), stretch=2)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color: #0c1117; color: #d7e2f0; }
            QGroupBox {
              border: 1px solid #253041;
              border-radius: 10px;
              margin-top: 10px;
              font-weight: 600;
            }
            QGroupBox::title {
              subcontrol-origin: margin;
              left: 12px;
              padding: 0 4px;
            }
            QPlainTextEdit, QComboBox, QPushButton {
              background-color: #121923;
              border: 1px solid #2a3648;
              border-radius: 8px;
              padding: 6px 8px;
            }
            QSpinBox, QDoubleSpinBox {
              background-color: #121923;
              border: 1px solid #2a3648;
              border-radius: 8px;
              padding: 6px 28px 6px 8px;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
              subcontrol-origin: border;
              width: 22px;
              background-color: #182231;
              border-left: 1px solid #2a3648;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
              subcontrol-position: top right;
              border-top-right-radius: 8px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
              subcontrol-position: bottom right;
              border-bottom-right-radius: 8px;
              border-top: 1px solid #2a3648;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow,
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
              width: 8px;
              height: 8px;
            }
            QPushButton:hover { border-color: #4d89ff; }
            """
        )

    def _build_environment_box(self) -> QGroupBox:
        box = QGroupBox("Environment")
        layout = QFormLayout(box)

        self.window_combo = QComboBox()
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        self.refresh_windows_button = QPushButton("Refresh Windows")
        self.refresh_windows_button.clicked.connect(self._refresh_windows)

        window_row = QWidget()
        row_layout = QHBoxLayout(window_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.window_combo, stretch=1)
        row_layout.addWidget(self.refresh_windows_button)

        self.status_label = QLabel("IPC ready")
        self.status_label.setWordWrap(True)
        self.ipc_label = QLabel(f"http://127.0.0.1:{self._http_server._port}")
        self.capture_label = QLabel("Capture idle")
        self.capture_label.setWordWrap(True)
        self.motion_label = QLabel("Motion idle")
        self.motion_label.setWordWrap(True)

        layout.addRow("Target window", window_row)
        layout.addRow("Session status", self.status_label)
        layout.addRow("Capture status", self.capture_label)
        layout.addRow("Motion", self.motion_label)
        layout.addRow("Local IPC", self.ipc_label)
        return box

    def _build_parameter_box(self) -> QGroupBox:
        box = QGroupBox("Probe Parameters")
        layout = QFormLayout(box)

        self.capture_fps = QSpinBox()
        self.capture_fps.setRange(15, 240)
        self.capture_fps.setValue(120)
        self.capture_fps.valueChanged.connect(self._on_capture_rate_changed)

        self.point_count = QSpinBox()
        self.point_count.setRange(5, 129)
        self.point_count.setValue(17)

        self.settle_ms = QSpinBox()
        self.settle_ms.setRange(50, 5000)
        self.settle_ms.setValue(300)

        self.steady_sample_ms = QSpinBox()
        self.steady_sample_ms.setRange(50, 5000)
        self.steady_sample_ms.setValue(700)

        self.yaw360_timeout_ms = QSpinBox()
        self.yaw360_timeout_ms.setRange(50, 15000)
        self.yaw360_timeout_ms.setValue(4000)

        self.live_smoothing = QSpinBox()
        self.live_smoothing.setRange(0, 95)
        self.live_smoothing.setValue(65)
        self.live_smoothing.setSuffix("%")

        self.min_tracked_points = QSpinBox()
        self.min_tracked_points.setRange(1, 120)
        self.min_tracked_points.setValue(8)

        self.min_confidence = QDoubleSpinBox()
        self.min_confidence.setRange(0.0, 1.0)
        self.min_confidence.setDecimals(2)
        self.min_confidence.setSingleStep(0.05)
        self.min_confidence.setValue(0.35)

        self.repeat_count = QSpinBox()
        self.repeat_count.setRange(1, 10)
        self.repeat_count.setValue(2)

        self.dynamic_enabled = QCheckBox("Enable dynamic response run")
        self.dynamic_enabled.setChecked(True)
        self.dynamic_enabled.setEnabled(False)
        self.dynamic_enabled.setToolTip(DYNAMIC_PREVIEW_DISABLED_MESSAGE)
        self.live_preview_during_run = QCheckBox("Live preview during tests")
        self.live_preview_during_run.setChecked(False)

        self.inner_deadzone = QSlider(Qt.Orientation.Horizontal)
        self.inner_deadzone.setRange(0, MAX_INNER_DEADZONE_TICK)
        self.inner_deadzone.setValue(0)
        self.inner_deadzone_input = QDoubleSpinBox()
        self.inner_deadzone_input.setRange(0.0, self._deadzone_tick_to_value(MAX_INNER_DEADZONE_TICK))
        self.inner_deadzone_input.setDecimals(4)
        self.inner_deadzone_input.setSingleStep(0.001)
        self.inner_deadzone_input.setValue(0.0)
        self.outer_saturation = QSlider(Qt.Orientation.Horizontal)
        self.outer_saturation.setRange(MIN_OUTER_DEADZONE_TICK, DEADZONE_TICK_SCALE)
        self.outer_saturation.setValue(DEADZONE_TICK_SCALE)
        self.outer_saturation_input = QDoubleSpinBox()
        self.outer_saturation_input.setRange(
            self._deadzone_tick_to_value(MIN_OUTER_DEADZONE_TICK),
            self._deadzone_tick_to_value(DEADZONE_TICK_SCALE),
        )
        self.outer_saturation_input.setDecimals(4)
        self.outer_saturation_input.setSingleStep(0.001)
        self.outer_saturation_input.setValue(1.0)

        layout.addRow("Capture FPS", self.capture_fps)
        layout.addRow("Points / half-axis", self.point_count)
        layout.addRow("Settle (ms)", self.settle_ms)
        layout.addRow("Steady Sample (ms)", self.steady_sample_ms)
        layout.addRow("Yaw360 Timeout (ms)", self.yaw360_timeout_ms)
        layout.addRow("Live smoothing", self.live_smoothing)
        layout.addRow("Min tracked pts", self.min_tracked_points)
        layout.addRow("Min confidence", self.min_confidence)
        layout.addRow("Repeats", self.repeat_count)
        layout.addRow("Inner deadzone", self._build_deadzone_row(self.inner_deadzone, self.inner_deadzone_input))
        layout.addRow("Outer saturation", self._build_deadzone_row(self.outer_saturation, self.outer_saturation_input))
        layout.addRow("", self.dynamic_enabled)
        layout.addRow("", self.live_preview_during_run)
        self._bind_parameter_controls()
        return box

    def _build_deadzone_row(self, slider: QSlider, spinbox: QDoubleSpinBox) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(slider, stretch=1)
        row_layout.addWidget(spinbox)
        return row

    def _build_actions_box(self) -> QGroupBox:
        box = QGroupBox("Actions")
        layout = QGridLayout(box)

        self.calibrate_button = QPushButton("Calibrate Inner Deadzone")
        self.calibrate_button.clicked.connect(self._toggle_inner_deadzone_calibration)
        self.idle_noise_button = QPushButton("Calibrate Idle Noise")
        self.idle_noise_button.clicked.connect(self._calibrate_idle_noise)
        self.steady_button = QPushButton("Run Steady")
        self.steady_button.clicked.connect(self._start_steady_run)
        self.dynamic_button = QPushButton("Run Dynamic")
        self.dynamic_button.clicked.connect(self._run_dynamic)
        self.dynamic_button.setEnabled(False)
        self.dynamic_button.setToolTip(DYNAMIC_PREVIEW_DISABLED_MESSAGE)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        self.clear_roi_button = QPushButton("Clear ROI")
        self.clear_roi_button.clicked.connect(self._clear_roi)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._export_session)

        layout.addWidget(self.calibrate_button, 0, 0)
        layout.addWidget(self.steady_button, 0, 1)
        layout.addWidget(self.idle_noise_button, 1, 0)
        layout.addWidget(self.dynamic_button, 1, 1)
        layout.addWidget(self.cancel_button, 2, 0)
        layout.addWidget(self.clear_roi_button, 2, 1)
        layout.addWidget(self.export_button, 3, 0, 1, 2)
        return box

    def _build_preview_box(self) -> QGroupBox:
        box = QGroupBox("Preview & ROI")
        layout = QVBoxLayout(box)
        self.preview_widget = LivePreviewWidget()
        self.preview_widget.roi_changed.connect(self._on_roi_changed)
        layout.addWidget(self.preview_widget)
        self.preview_help = QLabel("Drag on the preview to define the tracking ROI.")
        self.preview_help.setStyleSheet("color: #89a6c7;")
        layout.addWidget(self.preview_help)
        return box

    def _build_curve_box(self) -> QGroupBox:
        box = QGroupBox("Curve Preview")
        layout = QHBoxLayout(box)
        self.x_curve_widget = CurvePreviewWidget("X / yaw")
        layout.addWidget(self.x_curve_widget, stretch=1)
        return box

    def _build_log_box(self) -> QGroupBox:
        box = QGroupBox("Notes")
        layout = QVBoxLayout(box)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setReadOnly(True)
        layout.addWidget(self.notes_edit)
        return box

    def _refresh_windows(self) -> None:
        windows = self._window_service.list_windows()
        current_id = self._session.config.window_id
        self.window_combo.blockSignals(True)
        self.window_combo.clear()
        for window in windows:
            label = f"{window.title} [{window.window_id}]"
            self.window_combo.addItem(label, window.window_id)
        self.window_combo.blockSignals(False)

        if current_id is not None:
            index = self.window_combo.findData(current_id)
            if index >= 0:
                self.window_combo.setCurrentIndex(index)
        elif self.window_combo.count() > 0:
            self.window_combo.setCurrentIndex(0)
            self._on_window_changed()

    def _on_window_changed(self) -> None:
        window_id = self.window_combo.currentData()
        if window_id is None:
            return
        self._session.config.window_id = int(window_id)
        self._session.status.touch(message=f"Selected window {window_id}.")
        self._connect_capture()
        self._refresh_session_view()

    def _connect_capture(self) -> None:
        window_id = self._session.config.window_id
        if window_id is None:
            return

        try:
            self._capture_backend.attach(window_id)
            self.capture_label.setText(f"Attached to window {window_id}.")
            self.preview_widget.set_status("Live preview ready.")
        except ValueError as exc:
            self.capture_label.setText(str(exc))
            self.preview_widget.set_status(str(exc))
            self.preview_widget.clear()
        self._motion_estimator.reset()
        self._latest_motion = None

    def _on_capture_rate_changed(self, value: int) -> None:
        fps = max(15, min(value, 60))
        self._preview_timer.setInterval(max(16, 1000 // fps))
        self._capture_backend.set_target_fps(value)
        self._session.config.capture_fps = value

    def _deadzone_tick_to_value(self, tick: int) -> float:
        return tick / DEADZONE_TICK_SCALE

    def _deadzone_value_to_tick(self, value: float) -> int:
        return int(round(value * DEADZONE_TICK_SCALE))

    def _set_deadzone_ticks(
        self,
        *,
        inner_tick: int | None = None,
        outer_tick: int | None = None,
        inner_value: float | None = None,
        outer_value: float | None = None,
    ) -> None:
        next_inner = self.inner_deadzone.value() if inner_tick is None else max(0, min(inner_tick, MAX_INNER_DEADZONE_TICK))
        next_outer = (
            self.outer_saturation.value()
            if outer_tick is None
            else max(MIN_OUTER_DEADZONE_TICK, min(outer_tick, DEADZONE_TICK_SCALE))
        )

        # Use exact float values when provided (from spinbox), otherwise derive from tick.
        next_inner_value = inner_value if inner_value is not None else self._deadzone_tick_to_value(next_inner)
        next_outer_value = outer_value if outer_value is not None else self._deadzone_tick_to_value(next_outer)

        if next_inner >= next_outer:
            if inner_tick is not None and outer_tick is None:
                next_outer = min(DEADZONE_TICK_SCALE, next_inner + 1)
                next_inner = min(next_inner, next_outer - 1)
            elif outer_tick is not None and inner_tick is None:
                next_inner = max(0, next_outer - 1)
            else:
                next_inner = min(next_inner, next_outer - 1)
            next_inner_value = self._deadzone_tick_to_value(next_inner)
            next_outer_value = self._deadzone_tick_to_value(next_outer)

        for widget, value in (
            (self.inner_deadzone, next_inner),
            (self.outer_saturation, next_outer),
            (self.inner_deadzone_input, next_inner_value),
            (self.outer_saturation_input, next_outer_value),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

    def _bind_parameter_controls(self) -> None:
        self.point_count.valueChanged.connect(self._on_parameter_control_changed)
        self.settle_ms.valueChanged.connect(self._on_parameter_control_changed)
        self.steady_sample_ms.valueChanged.connect(self._on_parameter_control_changed)
        self.yaw360_timeout_ms.valueChanged.connect(self._on_parameter_control_changed)
        self.live_smoothing.valueChanged.connect(self._on_parameter_control_changed)
        self.min_tracked_points.valueChanged.connect(self._on_parameter_control_changed)
        self.min_confidence.valueChanged.connect(self._on_parameter_control_changed)
        self.repeat_count.valueChanged.connect(self._on_parameter_control_changed)
        self.dynamic_enabled.toggled.connect(self._on_parameter_control_changed)
        self.live_preview_during_run.toggled.connect(self._on_parameter_control_changed)
        self.inner_deadzone.valueChanged.connect(self._on_inner_deadzone_slider_changed)
        self.outer_saturation.valueChanged.connect(self._on_outer_saturation_slider_changed)
        self.inner_deadzone_input.valueChanged.connect(self._on_inner_deadzone_input_changed)
        self.outer_saturation_input.valueChanged.connect(self._on_outer_saturation_input_changed)

    def _on_parameter_control_changed(self, *_args) -> None:
        self._sync_config_from_ui()

    def _on_inner_deadzone_slider_changed(self, value: int) -> None:
        self._set_deadzone_ticks(inner_tick=value)
        self._sync_config_from_ui()

    def _on_outer_saturation_slider_changed(self, value: int) -> None:
        self._set_deadzone_ticks(outer_tick=value)
        self._sync_config_from_ui()

    def _on_inner_deadzone_input_changed(self, value: float) -> None:
        self._set_deadzone_ticks(inner_tick=self._deadzone_value_to_tick(value), inner_value=value)
        self._sync_config_from_ui()

    def _on_outer_saturation_input_changed(self, value: float) -> None:
        self._set_deadzone_ticks(outer_tick=self._deadzone_value_to_tick(value), outer_value=value)
        self._sync_config_from_ui()

    def _on_roi_changed(self, roi: RoiRect) -> None:
        self._session = self._session_service.update_roi(self._session.status.session_id, roi.to_dict())
        self._motion_estimator.reset()
        self.preview_widget.set_roi(roi)
        self.preview_widget.set_status(f"ROI {roi.width}x{roi.height} selected.")
        self._refresh_session_view()

    def _clear_roi(self) -> None:
        self._session.config.roi = None
        self._motion_estimator.reset()
        self._latest_motion = None
        self.preview_widget.set_roi(None)
        self.preview_widget.set_motion(None)
        self.motion_label.setText("Motion idle")
        self.preview_widget.set_status("ROI cleared.")

    def _poll_preview(self) -> None:
        snapshot = self._capture_backend.grab_frame()
        if snapshot is None:
            return

        self.preview_widget.set_frame(snapshot.frame)
        self.preview_widget.set_roi(self._session.config.roi)
        self.preview_widget.set_status("Live preview running.")

        if self._session.config.roi is not None:
            raw_motion = self._motion_estimator.update(snapshot.frame, self._session.config.roi, snapshot.timestamp)
            motion = self._filter_and_smooth_motion(raw_motion)
            self._latest_motion = motion
            self.preview_widget.set_motion(motion)
            if motion is not None:
                display_vx = self._apply_noise_floor(motion.px_per_sec_x, self._session.config.idle_noise_floor_x)
                display_vy = self._apply_noise_floor(motion.px_per_sec_y, self._session.config.idle_noise_floor_y)
                self.motion_label.setText(
                    f"vx {display_vx:8.1f}px/s | vy {display_vy:8.1f}px/s | "
                    f"pts {motion.tracked_points} | conf {motion.confidence:.2f}"
                )
            elif raw_motion is not None:
                self.motion_label.setText(
                    f"Motion filtered | pts {raw_motion.tracked_points} | conf {raw_motion.confidence:.2f}"
                )

    def _sync_config_from_ui(self) -> None:
        self._session.config.capture_fps = self.capture_fps.value()
        self._session.config.point_count_per_half_axis = self.point_count.value()
        self._session.config.settle_ms = self.settle_ms.value()
        self._session.config.steady_sample_ms = self.steady_sample_ms.value()
        self._session.config.yaw360_timeout_ms = self.yaw360_timeout_ms.value()
        self._session.config.live_smoothing_factor = self.live_smoothing.value() / 100.0
        self._session.config.motion_min_tracked_points = self.min_tracked_points.value()
        self._session.config.motion_min_confidence = self.min_confidence.value()
        self._session.config.repeats = self.repeat_count.value()
        self._session.config.dynamic_enabled = self.dynamic_enabled.isChecked()
        self._session.config.push_live_preview_during_run = self.live_preview_during_run.isChecked()
        self._session.config.inner_deadzone_marker = self.inner_deadzone_input.value()
        self._session.config.outer_saturation_marker = self.outer_saturation_input.value()

    def _refresh_inner_deadzone_calibration_status(self) -> None:
        deadzone = self._inner_deadzone_calibration_service.current_deadzone
        output = self._inner_deadzone_calibration_service.current_output
        self.status_label.setText(
            f"calibrating_deadzone: active | deadzone={deadzone:.3f} | "
            f"output={output:.3f} | F8/F9 adjust | F10 exit"
        )

    def _set_inner_deadzone_calibration_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.window_combo,
            self.refresh_windows_button,
            self.capture_fps,
            self.point_count,
            self.settle_ms,
            self.steady_sample_ms,
            self.yaw360_timeout_ms,
            self.live_smoothing,
            self.min_tracked_points,
            self.min_confidence,
            self.repeat_count,
            self.inner_deadzone,
            self.inner_deadzone_input,
            self.outer_saturation,
            self.outer_saturation_input,
            self.dynamic_enabled,
            self.live_preview_during_run,
            self.idle_noise_button,
            self.steady_button,
            self.dynamic_button,
            self.cancel_button,
            self.clear_roi_button,
            self.export_button,
            self.preview_widget,
        ):
            widget.setEnabled(enabled)
        self.dynamic_button.setEnabled(False)

    def _restore_inner_deadzone_calibration_ui(self) -> None:
        self._inner_deadzone_calibration_active = False
        self.calibrate_button.setText("Calibrate Inner Deadzone")
        self._set_inner_deadzone_calibration_controls_enabled(True)
        self._refresh_session_view()

    def _toggle_inner_deadzone_calibration(self) -> None:
        if self._inner_deadzone_calibration_active:
            self._exit_inner_deadzone_calibration()
            return
        self._enter_inner_deadzone_calibration()

    def _enter_inner_deadzone_calibration(self) -> None:
        try:
            value = self._inner_deadzone_calibration_service.enter(self.inner_deadzone_input.value())
        except Exception as exc:
            self.status_label.setText(f"calibrating_deadzone: failed | {exc}")
            self._notify_status(f"Inner deadzone calibration unavailable: {exc}")
            return
        self._inner_deadzone_calibration_active = True
        self._set_inner_deadzone_calibration_controls_enabled(False)
        self._set_deadzone_ticks(inner_tick=self._deadzone_value_to_tick(value))
        self.calibrate_button.setText("Exit Inner Deadzone Calibration")
        self.calibrate_button.setEnabled(True)
        self._refresh_inner_deadzone_calibration_status()
        self._notify_status("Inner deadzone calibration started.")

    def _step_inner_deadzone_calibration(self, direction: int) -> None:
        try:
            value = (
                self._inner_deadzone_calibration_service.increase()
                if direction > 0
                else self._inner_deadzone_calibration_service.decrease()
            )
        except Exception as exc:
            self.status_label.setText(f"calibrating_deadzone: failed | {exc}")
            self._notify_status(f"Inner deadzone calibration stopped: {exc}")
            self._restore_inner_deadzone_calibration_ui()
            return
        self._set_deadzone_ticks(inner_tick=self._deadzone_value_to_tick(value))
        self._refresh_inner_deadzone_calibration_status()

    def _exit_inner_deadzone_calibration(self) -> None:
        value = self._inner_deadzone_calibration_service.exit()
        self._set_deadzone_ticks(inner_tick=self._deadzone_value_to_tick(value))
        self._sync_config_from_ui()
        self._restore_inner_deadzone_calibration_ui()
        self._notify_status("Inner deadzone calibration finished.")

    def _should_push_live_preview_during_run(self) -> bool:
        return self._session.config.push_live_preview_during_run

    def _pause_preview_for_run_if_needed(self) -> None:
        if not self._should_push_live_preview_during_run():
            self._set_preview_running(False)

    def _filter_and_smooth_motion(self, motion: MotionEstimate | None) -> MotionEstimate | None:
        if motion is None:
            return None
        if motion.tracked_points < self._session.config.motion_min_tracked_points:
            return None
        if motion.confidence < self._session.config.motion_min_confidence:
            return None

        previous = self._latest_motion
        smoothing = min(max(self._session.config.live_smoothing_factor, 0.0), 0.95)
        if previous is None or smoothing <= 0.0:
            return motion

        blend = 1.0 - smoothing
        return MotionEstimate(
            dx=motion.dx,
            dy=motion.dy,
            px_per_sec_x=(previous.px_per_sec_x * smoothing) + (motion.px_per_sec_x * blend),
            px_per_sec_y=(previous.px_per_sec_y * smoothing) + (motion.px_per_sec_y * blend),
            tracked_points=motion.tracked_points,
            confidence=motion.confidence,
        )

    def _calibrate(self) -> None:
        if not self.calibrate_button.isEnabled():
            self._notify_status(YAW360_PREVIEW_DISABLED_MESSAGE)
            return
        self._sync_config_from_ui()
        self._set_steady_controls_enabled(False)
        self._pause_preview_for_run_if_needed()
        self.status_label.setText("calibrating: Running yaw 360 calibration.")
        self._notify_status("Yaw 360 calibration started.")
        self._create_run_worker("calibrate_yaw360")
        assert self._run_thread is not None
        self._run_thread.start()

    def _calibrate_idle_noise(self) -> None:
        self._sync_config_from_ui()
        self._set_steady_controls_enabled(False)
        self._pause_preview_for_run_if_needed()
        self.status_label.setText("calibrating: Calibrating idle noise.")
        self._notify_status("Idle noise calibration started.")
        self._create_run_worker("calibrate_idle_noise")
        assert self._run_thread is not None
        self._run_thread.start()

    def _start_steady_run(self) -> None:
        if self._is_steady_running:
            self._notify_status("Steady probe is already running.")
            return
        self._sync_config_from_ui()
        self._is_steady_running = True
        self._set_steady_controls_enabled(False)
        self._pause_preview_for_run_if_needed()
        self.status_label.setText("running_steady: Running steady-state measurement.")
        self._notify_status("Steady probe started.")
        self._create_run_worker("run_steady")
        assert self._run_thread is not None
        self._run_thread.start()

    def _create_run_worker(self, action: str) -> None:
        self._run_thread = QThread(self)
        self._run_worker = RunWorker(
            session_service=self._session_service,
            session_id=self._session.status.session_id,
            action=action,
        )
        self._run_worker.moveToThread(self._run_thread)
        self._run_thread.started.connect(self._run_worker.run)
        self._run_worker.finished.connect(self._on_run_finished)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_worker.finished.connect(self._run_thread.quit)
        self._run_worker.failed.connect(self._run_thread.quit)
        self._run_thread.finished.connect(self._cleanup_run_worker)

    def _run_dynamic(self) -> None:
        if not self.dynamic_button.isEnabled():
            self._notify_status(DYNAMIC_PREVIEW_DISABLED_MESSAGE)
            return
        self._sync_config_from_ui()
        self._session = self._session_service.run_dynamic(self._session.status.session_id)
        self._refresh_session_view()

    def _cancel(self) -> None:
        self._session = self._session_service.cancel(self._session.status.session_id)
        if self._run_thread is not None:
            self._set_preview_running(True)
        self._notify_status("Session canceled.")
        self._refresh_session_view()

    def _export_session(self) -> None:
        output_dir = QFileDialog.getExistingDirectory(self, "Select export directory")
        if not output_dir:
            return
        exported = self._session_service.export_session(self._session.status.session_id, output_dir)
        self._session.result.notes.append(f"Exported files to {output_dir}.")
        self._session.result.notes.extend(exported.values())
        self.capture_label.setText(f"Exported curve data to {output_dir}.")
        self._notify_status(f"Exported curve data to {output_dir}.")
        self._refresh_session_view()

    def _refresh_session_view(self) -> None:
        self.status_label.setText(f"{self._session.status.state.value}: {self._session.status.message}")
        preview_points = self._session.result.x_curve
        if hasattr(self._session_service, "build_driver_curve"):
            preview_points = self._session_service.build_driver_curve(self._session.result.x_curve)
        self.x_curve_widget.set_title(self._curve_title_for_result())
        self.x_curve_widget.set_points(preview_points)
        notes = self._notes_text_for_result()
        self.notes_edit.setPlainText(notes)

    def _curve_title_for_result(self) -> str:
        if self._session.result.measurement_kind == "yaw360_calibration":
            return "X / yaw (Yaw 360 calibration)"
        if self._session.result.measurement_kind == "steady_probe":
            return "X / yaw (Steady probe)"
        return "X / yaw"

    def _notes_text_for_result(self) -> str:
        lines: list[str] = []
        if self._session.result.summary:
            lines.append(self._session.result.summary)
        if self._session.result.notes:
            lines.extend(self._session.result.notes)
        if not lines:
            return "No notes yet."
        return "\n".join(lines)

    def _on_run_finished(self, session) -> None:
        self._session = session
        self._set_preview_running(True)
        if self._latest_motion is not None:
            self._session.result.notes.append(
                f"Latest live ROI velocity: vx={self._latest_motion.px_per_sec_x:.1f}px/s, "
                f"vy={self._latest_motion.px_per_sec_y:.1f}px/s."
            )
        self._is_steady_running = False
        self._set_steady_controls_enabled(True)
        self._notify_status(self._session.status.message)
        self._refresh_session_view()

    def _on_run_failed(self, exc: Exception) -> None:
        self._set_preview_running(True)
        self._is_steady_running = False
        self._set_steady_controls_enabled(True)
        self._notify_status(f"Background run failed: {exc}")
        self._refresh_session_view()

    def _cleanup_run_worker(self) -> None:
        if self._run_worker is not None:
            self._run_worker.deleteLater()
            self._run_worker = None
        if self._run_thread is not None:
            self._run_thread.deleteLater()
            self._run_thread = None

    def _set_steady_controls_enabled(self, enabled: bool) -> None:
        self.calibrate_button.setEnabled(enabled and not self._inner_deadzone_calibration_active)
        self.idle_noise_button.setEnabled(enabled and not self._inner_deadzone_calibration_active)
        self.steady_button.setEnabled(enabled and not self._inner_deadzone_calibration_active)
        self.dynamic_button.setEnabled(False)
        self.cancel_button.setEnabled(not self._inner_deadzone_calibration_active)

    def _apply_noise_floor(self, value: float, floor: float) -> float:
        if value > 0:
            return max(0.0, value - floor)
        if value < 0:
            return -max(0.0, abs(value) - floor)
        return 0.0

    def _set_preview_running(self, enabled: bool) -> None:
        if enabled:
            if not self._preview_timer.isActive():
                self._preview_timer.start()
                self.preview_widget.set_status("Live preview running.")
            return
        if self._preview_timer.isActive():
            self._preview_timer.stop()
        self.preview_widget.set_status("Live preview paused during measurement.")

    def _notify_status(self, message: str) -> None:
        self._session.result.notes.append(message)
        if self._notifier is not None:
            self._notifier.notify("GameCurveProbe", message)

    def _register_global_hotkeys(self) -> None:
        if self._hotkey_manager is None:
            return
        result = self._hotkey_manager.register_defaults(int(self.winId()))
        if result.failures:
            self._notify_status(f"Failed to register global hotkeys: {', '.join(result.failures)}.")

    def _handle_hotkey(self, hotkey_id: int) -> bool:
        if self._inner_deadzone_calibration_active:
            if hotkey_id == 1:
                self._step_inner_deadzone_calibration(1)
                return True
            if hotkey_id == 2:
                self._step_inner_deadzone_calibration(-1)
                return True
            if hotkey_id == 3:
                self._exit_inner_deadzone_calibration()
                return True
        if hotkey_id == 1:
            self._start_steady_run()
            return True
        if hotkey_id == 2:
            self._cancel()
            return True
        if hotkey_id == 3:
            self._export_session()
            return True
        return False

    def nativeEvent(self, event_type, message):  # noqa: N802
        if event_type == "windows_generic_MSG" and message is not None:
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY and self._handle_hotkey(int(msg.wParam)):
                return True, 0
        return super().nativeEvent(event_type, message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._inner_deadzone_calibration_active:
            self._exit_inner_deadzone_calibration()
        self._preview_timer.stop()
        if self._run_thread is not None:
            self._run_thread.quit()
            self._run_thread.wait(2000)
        if self._hotkey_manager is not None:
            self._hotkey_manager.unregister_all()
        if self._tray_backend is not None:
            self._tray_backend.close()
        self._capture_backend.close()
        super().closeEvent(event)
