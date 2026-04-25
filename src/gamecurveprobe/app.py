from __future__ import annotations

import argparse
import ctypes
import sys

from gamecurveprobe.backends.controller import VgamepadControllerBackend
from gamecurveprobe.services.http_server import LocalHttpServer
from gamecurveprobe.services.idle_noise_calibration_runner import IdleNoiseCalibrationRunner
from gamecurveprobe.services.inner_deadzone_calibration_service import InnerDeadzoneCalibrationService
from gamecurveprobe.services.motion_sampler import MotionSampler
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.steady_probe_runner import SteadyProbeRunner
from gamecurveprobe.services.window_service import WindowService
from gamecurveprobe.services.yaw360_calibration_runner import Yaw360CalibrationRunner
from gamecurveprobe.vision.motion_estimator import MotionEstimator


def _enable_windows_dpi_awareness(user32=None, shcore=None) -> None:
    if sys.platform != "win32":
        return

    user32 = user32 or ctypes.windll.user32
    shcore = shcore or getattr(ctypes.windll, "shcore", None)

    if shcore is not None:
        per_monitor_v2 = 2
        result = shcore.SetProcessDpiAwareness(per_monitor_v2)
        if result == 0:
            return

    user32.SetProcessDPIAware()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameCurveProbe desktop application")
    parser.add_argument("--ipc-only", action="store_true", help="Run only the local HTTP IPC server")
    parser.add_argument("--port", type=int, default=48231, help="Local IPC port")
    return parser


def _build_preview_capture_backend_factory(window_service: WindowService):
    def create_capture_backend():
        from gamecurveprobe.backends.capture.dxcam_backend import DxcamCaptureBackend

        return DxcamCaptureBackend(window_service=window_service)

    return create_capture_backend


def _build_steady_capture_backend_factory(window_service: WindowService):
    def create_capture_backend():
        from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend

        return DxcamMonitorCaptureBackend(window_service=window_service)

    return create_capture_backend


def _cleanup_persistent_controller(controller: VgamepadControllerBackend) -> None:
    try:
        controller.neutral()
    except Exception:
        pass
    try:
        controller.disconnect()
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    _enable_windows_dpi_awareness()
    args = build_parser().parse_args(argv)

    window_service = WindowService()
    shared_controller = VgamepadControllerBackend()
    if shared_controller.probe():
        shared_controller.connect()

    steady_probe_runner = SteadyProbeRunner(
        controller_backend_factory=lambda: shared_controller,
        capture_backend_factory=_build_steady_capture_backend_factory(window_service),
        motion_sampler=MotionSampler(),
        disconnect_controller_on_finish=False,
    )
    calibration_runner = Yaw360CalibrationRunner(
        controller_backend_factory=lambda: shared_controller,
        capture_backend_factory=_build_preview_capture_backend_factory(window_service),
        motion_estimator_factory=MotionEstimator,
        disconnect_controller_on_finish=False,
    )
    idle_noise_calibration_runner = IdleNoiseCalibrationRunner(
        capture_backend_factory=_build_preview_capture_backend_factory(window_service),
        motion_sampler=MotionSampler(),
        motion_estimator_factory=MotionEstimator,
    )
    session_service = SessionService(
        window_service=window_service,
        steady_probe_runner=steady_probe_runner,
        calibration_runner=calibration_runner,
        idle_noise_calibration_runner=idle_noise_calibration_runner,
    )
    http_server = LocalHttpServer(
        host="127.0.0.1",
        port=args.port,
        session_service=session_service,
        window_service=window_service,
    )
    http_server.start()

    if args.ipc_only:
        print(f"GameCurveProbe IPC listening on http://127.0.0.1:{args.port}")
        try:
            http_server.join()
        except KeyboardInterrupt:
            http_server.stop()
        finally:
            _cleanup_persistent_controller(shared_controller)
        return 0

    from PySide6.QtWidgets import QApplication

    from gamecurveprobe.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("GameCurveProbe")
    inner_deadzone_calibration_service = InnerDeadzoneCalibrationService(shared_controller)
    window = MainWindow(
        session_service=session_service,
        window_service=window_service,
        http_server=http_server,
        inner_deadzone_calibration_service=inner_deadzone_calibration_service,
    )
    window.show()
    try:
        return app.exec()
    finally:
        http_server.stop()
        _cleanup_persistent_controller(shared_controller)
