from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from gamecurveprobe.events import EventHub
from gamecurveprobe.services.capture_service import CaptureService
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.deadzone_probe_service import DeadzoneProbeService
from gamecurveprobe.services.export_service import ExportService
from gamecurveprobe.services.idle_noise_runner import IdleNoiseRunner
from gamecurveprobe.services.job_manager import JobManager
from gamecurveprobe.services.measurement_runner import MeasurementRunner
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService


@dataclass(slots=True)
class AppContext:
    token: str
    windows: WindowService
    session: SessionService
    jobs: JobManager
    capture: CaptureService
    controller: ControllerService
    probe: DeadzoneProbeService
    measurement: MeasurementRunner
    idle_noise: IdleNoiseRunner
    export: ExportService
    events: EventHub
    allowed_origins: frozenset[str] = frozenset({"http://127.0.0.1", "http://localhost"})
    shutdown_callback: Callable[[], None] = lambda: None

    def close(self) -> None:
        self.jobs.cancel_active()
        self.jobs.wait(timeout=3.0)
        for cleanup in (
            self.probe.close,
            self.controller.close,
            self.capture.close,
            self.jobs.close,
            self.events.close,
        ):
            self._run_bounded(cleanup, timeout=0.5)

    def request_shutdown(self) -> None:
        """Release hardware resources before terminating the local application."""
        self.close()
        self.shutdown_callback()

    @staticmethod
    def _run_bounded(cleanup: Callable[[], None], timeout: float) -> None:
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logging.critical("Shutdown cleanup timed out: %r", cleanup)
