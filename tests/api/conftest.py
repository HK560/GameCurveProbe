from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from gamecurveprobe.api.server import create_app
from gamecurveprobe.backends.capture.stub import StubCaptureBackend
from gamecurveprobe.backends.controller.stub import StubControllerBackend
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


@pytest.fixture
def token() -> str:
    return "test-secret-token-12345"


@pytest.fixture
def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Origin": "http://127.0.0.1",
    }


@pytest.fixture
def context(token: str) -> AppContext:
    controller_backend = StubControllerBackend()
    controller = ControllerService(controller_backend)
    capture_backend = StubCaptureBackend()
    capture = CaptureService({"wgc": capture_backend, "dxcam": capture_backend})
    session = SessionService()
    events = EventHub()
    jobs = JobManager(publish=lambda ev: events.publish("job_event", ev))
    windows = WindowService()
    probe = DeadzoneProbeService(controller)
    measurement = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: capture_backend,
        motion_sampler=None,
        sleep=lambda *_: None,
    )
    idle_noise = IdleNoiseRunner(
        capture_factory=lambda: capture_backend,
        motion_sampler=None,
    )
    export = ExportService()

    return AppContext(
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
        allowed_origins=frozenset({"http://127.0.0.1", "http://localhost"}),
    )


@pytest.fixture
def app(context: AppContext):
    return create_app(context_factory=lambda: context)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c
