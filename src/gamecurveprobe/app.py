from __future__ import annotations

import argparse
import secrets
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

import uvicorn

from gamecurveprobe.api.server import create_app
from gamecurveprobe.backends.capture.dxcam_backend import DxcamCaptureBackend
from gamecurveprobe.backends.capture.wgc_backend import WgcCaptureBackend
from gamecurveprobe.backends.controller.vgamepad_backend import VgamepadControllerBackend
from gamecurveprobe.context import AppContext
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameCurveProbe 2.0 Web Application Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--token", default=None, help="Authentication token (generated automatically if omitted)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically on startup")
    return parser


def build_context(token: str, host: str, port: int) -> AppContext:
    controller_backend = VgamepadControllerBackend()
    controller = ControllerService(controller_backend)

    window_service = WindowService()
    wgc_backend = WgcCaptureBackend()
    dxcam_backend = DxcamCaptureBackend(window_service=window_service)
    capture = CaptureService({"wgc": wgc_backend, "dxcam": dxcam_backend})

    session = SessionService()
    events = EventHub()
    jobs = JobManager(
        publish=lambda ev: events.publish("job_event", ev),
    )

    probe = DeadzoneProbeService(controller)
    measurement = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: capture,
        motion_sampler=None,
    )
    idle_noise = IdleNoiseRunner(
        capture_factory=lambda: capture,
        motion_sampler=None,
    )
    export = ExportService()

    allowed_origins = frozenset({
        f"http://{host}:{port}",
        f"http://localhost:{port}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    })

    return AppContext(
        token=token,
        windows=window_service,
        session=session,
        jobs=jobs,
        capture=capture,
        controller=controller,
        probe=probe,
        measurement=measurement,
        idle_noise=idle_noise,
        export=export,
        events=events,
        allowed_origins=allowed_origins,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = args.token or secrets.token_urlsafe(16)
    host = args.host
    port = args.port

    static_dir = Path(__file__).resolve().parent / "web_dist"
    app = create_app(
        context_factory=lambda: build_context(token, host, port),
        static_dir=static_dir,
    )

    url = f"http://{host}:{port}/?token={token}"
    print("\n" + "=" * 60)
    print(" GameCurveProbe 2.0 WebUI Server")
    print(f" Web Interface: {url}")
    print(f" Token: {token}")
    print("=" * 60 + "\n")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
