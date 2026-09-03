from __future__ import annotations

import secrets
import sys
import webbrowser
from pathlib import Path

import uvicorn

from gamecurveprobe.api.server import create_app
from gamecurveprobe.backends.capture.stub import StubCaptureBackend
from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.context import AppContext
from gamecurveprobe.events import EventHub
from gamecurveprobe.models import WindowInfo
from gamecurveprobe.services.capture_service import CaptureService
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.deadzone_probe_service import DeadzoneProbeService
from gamecurveprobe.services.export_service import ExportService
from gamecurveprobe.services.idle_noise_runner import IdleNoiseRunner
from gamecurveprobe.services.job_manager import JobManager
from gamecurveprobe.services.measurement_runner import MeasurementRunner
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService


class MockWindowService(WindowService):
    def list_windows(self) -> list[WindowInfo]:
        return [
            WindowInfo(window_id=1001, title="Cyberpunk 2077", rect=(0, 0, 1920, 1080)),
            WindowInfo(window_id=1002, title="Apex Legends", rect=(0, 0, 2560, 1440)),
            WindowInfo(window_id=1003, title="Counter-Strike 2", rect=(0, 0, 1920, 1080)),
        ]


def main() -> None:
    token = secrets.token_urlsafe(16)
    port = 8765
    host = "127.0.0.1"

    controller_backend = StubControllerBackend()
    controller = ControllerService(controller_backend)
    capture_backend = StubCaptureBackend(width=1920, height=1080)
    events = EventHub()
    capture = CaptureService(
        {"wgc": capture_backend, "dxcam": capture_backend},
        preview_callback=events.publish_preview,
    )
    session = SessionService()
    jobs = JobManager(publish=lambda ev: events.publish("job_event", ev))
    windows = MockWindowService()
    probe = DeadzoneProbeService(controller)
    measurement = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: capture_backend,
        motion_sampler=None,
    )
    idle_noise = IdleNoiseRunner(
        capture_factory=lambda: capture_backend,
        motion_sampler=None,
    )
    export = ExportService()

    context = AppContext(
        token=token,
        windows=windows,
        session=session,
        jobs=jobs,
        capture=capture,
        controller=controller,
        probe=probe,
        measurement=measurement,
        idle_noise=idle_noise,
        export=export,
        events=events,
        allowed_origins=frozenset({f"http://{host}:{port}", f"http://localhost:{port}", "http://127.0.0.1:5173", "http://localhost:5173"}),
    )

    static_dir = Path(__file__).resolve().parent.parent / "src" / "gamecurveprobe" / "web_dist"
    app = create_app(context_factory=lambda: context, static_dir=static_dir)

    url = f"http://{host}:{port}/#token={token}"
    print(f"\n=======================================================")
    print(f" GameCurveProbe 2.0 WebUI Stub Server")
    print(f" Running at: {url}")
    print(f" Web static dir: {static_dir}")
    print(f"=======================================================\n")

    webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
