from __future__ import annotations

import argparse
import os
import secrets
import sys
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import uvicorn

from gamecurveprobe.api.server import create_app
from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend
from gamecurveprobe.backends.capture.wgc_backend import WgcCaptureBackend
from gamecurveprobe.backends.controller.vgamepad_backend import VgamepadControllerBackend
from gamecurveprobe.context import AppContext
from gamecurveprobe.events import EventHub, publish_job_event
from gamecurveprobe.models import SessionResult
from gamecurveprobe.services.audio_service import AudioService
from gamecurveprobe.services.capture_service import CaptureService
from gamecurveprobe.services.controller_service import ControllerService
from gamecurveprobe.services.deadzone_probe_service import DeadzoneProbeService
from gamecurveprobe.services.export_service import ExportService
from gamecurveprobe.services.hotkey_service import HotkeyService
from gamecurveprobe.services.idle_noise_runner import IdleNoiseRunner
from gamecurveprobe.services.job_manager import JobManager
from gamecurveprobe.services.measurement_runner import MeasurementRunner
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService
from gamecurveprobe.vision.curve_classifier import classify_curve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameCurveProbe 2.0 Web Application Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        choices=("127.0.0.1", "localhost", "::1"),
        help="Loopback host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--token", default=None, help="Authentication token (generated automatically if omitted)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically on startup")
    return parser


def build_context(
    token: str,
    host: str,
    port: int,
    shutdown_callback: Callable[[], None] | None = None,
) -> AppContext:
    controller_backend = VgamepadControllerBackend()
    controller = ControllerService(controller_backend)

    window_service = WindowService()
    events = EventHub()
    wgc_backend = WgcCaptureBackend()
    dxcam_backend = DxcamMonitorCaptureBackend(window_service=window_service)
    capture = CaptureService(
        {"wgc": wgc_backend, "dxcam": dxcam_backend},
        preview_callback=events.publish_preview,
        window_service=window_service,
    )
    session = SessionService()

    def handle_job_publish(ev: Mapping[str, object]) -> None:
        publish_job_event(events, ev)
        session.set_active_job(jobs.active_job)
        session.set_last_job(jobs.last_job)

    jobs = JobManager(
        publish=handle_job_publish,
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
    audio = AudioService(enabled=session.config_snapshot().sound_enabled)

    def on_start_hotkey() -> None:
        snap = session.snapshot()
        if snap.active_job is not None:
            return
        if snap.capture is None or snap.roi is None:
            events.publish("job_failed", {"error": "未选定抓图窗口或ROI区域"})
            return

        cfg = snap.config
        capture.assert_ready(snap.roi)
        controller.acquire("measurement")

        def runner(cancel_event, publish):
            try:
                result = measurement.run(
                    cfg,
                    cancel_event,
                    publish,
                    roi=snap.roi,
                    noise=snap.noise,
                )
                analysis = classify_curve(result.points)
                final_result = SessionResult(
                    points=result.points,
                    noise=result.noise,
                    analysis=analysis,
                    schema_version=result.schema_version,
                    measured_at=result.measured_at,
                    session_id=snap.id,
                    environment={
                        "window_title": snap.capture.title,
                        "capture_backend": snap.capture.backend,
                        "requested_fps": snap.capture.target_fps,
                        "actual_fps": capture.health().fps,
                        "frame_size": [snap.capture.width, snap.capture.height],
                        "roi": asdict(snap.roi),
                    },
                    config=asdict(cfg),
                    warnings=(),
                )
                session.set_last_result(final_result)
                audio.play_sound("complete", cfg.sound_enabled)
                return final_result
            finally:
                controller.release("measurement")

        job = jobs.start("measurement", runner)
        session.set_active_job(job)
        audio.play_sound("start", cfg.sound_enabled)

    def on_stop_hotkey() -> None:
        if jobs.active_job is not None:
            jobs.cancel_active()
            audio.play_sound("stop", session.config_snapshot().sound_enabled)

    cfg = session.config_snapshot()
    hotkey = HotkeyService(on_start=on_start_hotkey, on_stop=on_stop_hotkey)
    hotkey.start(enabled=cfg.hotkey_enabled, start_key=cfg.hotkey_start, stop_key=cfg.hotkey_stop)

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
        audio=audio,
        hotkey=hotkey,
        allowed_origins=allowed_origins,
        shutdown_callback=shutdown_callback or (lambda: None),
    )


def build_browser_url(host: str, port: int, token: str) -> str:
    return f"http://{host}:{port}/#token={token}"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = args.token or secrets.token_urlsafe(16)
    host = args.host
    port = args.port

    static_dir = Path(__file__).resolve().parent / "web_dist"
    def exit_process() -> None:
        timer = threading.Timer(0.1, lambda: os._exit(0))
        timer.daemon = True
        timer.start()

    app = create_app(
        context_factory=lambda: build_context(token, host, port, shutdown_callback=exit_process),
        static_dir=static_dir,
    )

    url = build_browser_url(host, port, token)
    print("\n" + "=" * 60)
    print(" GameCurveProbe 2.0 WebUI Server")
    print(f" Web Interface: {url}")
    print(f" Token: {token}")
    print("=" * 60 + "\n")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
