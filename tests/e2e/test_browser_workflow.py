from __future__ import annotations

import time
import pytest
from starlette.testclient import TestClient

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
from gamecurveprobe.services.motion_sampler import MotionSample
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService


class MockWindowService(WindowService):
    def list_windows(self) -> list[WindowInfo]:
        return [
            WindowInfo(window_id=1001, title="Cyberpunk 2077", rect=(0, 0, 1920, 1080)),
            WindowInfo(window_id=1002, title="Apex Legends", rect=(0, 0, 2560, 1440)),
        ]


def test_full_webui_e2e_workflow() -> None:
    token = "e2e-test-token"
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://127.0.0.1"}

    controller_backend = StubControllerBackend()
    controller = ControllerService(controller_backend)
    capture_backend = StubCaptureBackend(width=1920, height=1080)
    capture = CaptureService({"wgc": capture_backend, "dxcam": capture_backend})
    session = SessionService()
    events = EventHub()
    jobs = JobManager(publish=lambda ev: events.publish("job_event", ev))
    windows = MockWindowService()
    probe = DeadzoneProbeService(controller)
    class FastSampler:
        def sample_filtered(self, *args, **kwargs):
            return MotionSample(
                px_per_sec_x=100.0,
                px_per_sec_y=0.0,
                valid_frames=10,
                average_confidence=0.85,
                stability_score=0.95,
            )

    measurement = MeasurementRunner(
        controller=controller,
        capture_factory=lambda: capture_backend,
        motion_sampler=FastSampler(),
        sleep=lambda *_: None,
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
        allowed_origins=frozenset({"http://127.0.0.1", "http://localhost"}),
    )

    app = create_app(context_factory=lambda: context)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        # 1. Health check
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Window list
        res = client.get("/api/windows", headers=headers)
        assert res.status_code == 200
        wins = res.json()["windows"]
        assert len(wins) == 2
        assert wins[0]["title"] == "Cyberpunk 2077"

        # 3. Attach window
        res = client.post(
            "/api/capture/attach",
            headers=headers,
            json={"window_id": 1001, "backend": "wgc", "target_fps": 120},
        )
        assert res.status_code == 200
        assert res.json()["capture"]["window_id"] == 1001

        # 4. Select ROI
        res = client.post(
            "/api/session/roi",
            headers=headers,
            json={"x": 500, "y": 400, "width": 200, "height": 200},
        )
        assert res.status_code == 200
        assert res.json()["roi"]["width"] == 200

        # 5. Interactive deadzone probing
        res = client.post(
            "/api/deadzone/start",
            headers=headers,
            json={"initial_output": 0.05, "step": 0.005, "direction": "x_positive"},
        )
        assert res.status_code == 200
        assert res.json()["probe"]["active"] is True

        res = client.post(
            "/api/deadzone/update",
            headers=headers,
            json={"output": 0.08},
        )
        assert res.status_code == 200
        assert res.json()["probe"]["output"] == 0.08

        res = client.post("/api/deadzone/stop", headers=headers)
        assert res.status_code == 200
        assert res.json()["probe"]["active"] is False

        # Set deadzones
        res = client.put(
            "/api/session/config",
            headers=headers,
            json={"inner_deadzone": 0.08, "outer_deadzone": 0.95, "point_count": 9},
        )
        assert res.status_code == 200
        assert res.json()["config"]["inner_deadzone"] == 0.08
        assert res.json()["config"]["outer_deadzone"] == 0.95

        # 6. Start measurement job
        res = client.post(
            "/api/jobs/measurement",
            headers=headers,
            json={"range_mode": "full"},
        )
        assert res.status_code == 202
        job_id = res.json()["id"]

        # Wait for job completion
        for _ in range(50):
            res = client.get(f"/api/jobs/{job_id}", headers=headers)
            assert res.status_code == 200
            job_data = res.json()
            st = job_data["state"]
            if st == "completed":
                break
            if st in ("failed", "canceled"):
                pytest.fail(f"Job failed or canceled: {job_data}")
            time.sleep(0.05)
        else:
            pytest.fail(f"Measurement job did not complete within timeout. Last state: {res.json()}")

        # 7. Check session result and classification
        res = client.get("/api/session", headers=headers)
        assert res.status_code == 200
        session_data = res.json()
        assert session_data["last_result"] is not None
        assert len(session_data["last_result"]["points"]) >= 9
        assert session_data["last_result"]["analysis"] is not None

        # 8. Export result as CSV and JSON
        res = client.get("/api/result/export?format=csv", headers=headers)
        assert res.status_code == 200
        assert "Input,Velocity_px_s" in res.text

        res = client.get("/api/result/export?format=json", headers=headers)
        assert res.status_code == 200
        assert res.json()["schema_version"] == 1
