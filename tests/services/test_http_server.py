from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gamecurveprobe.services.http_server import LocalHttpServer
from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService


def _post_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    request = Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_local_http_server_rejects_preview_disabled_actions() -> None:
    session_service = SessionService(window_service=WindowService())
    session = session_service.create_session({"window_id": 123})
    http_server = LocalHttpServer("127.0.0.1", 0, session_service=session_service, window_service=WindowService())
    http_server.start()

    try:
        port = http_server._server.server_address[1]
        base_url = f"http://127.0.0.1:{port}/session/{session.status.session_id}"

        yaw_status, yaw_payload = _post_json(f"{base_url}/calibrate/yaw360")
        dynamic_status, dynamic_payload = _post_json(f"{base_url}/run/dynamic")

        updated = session_service.get_session(session.status.session_id)

        assert yaw_status == 409
        assert yaw_payload == {"error": "Yaw 360 calibration is disabled in this preview build."}
        assert dynamic_status == 409
        assert dynamic_payload == {"error": "Dynamic response run is disabled in this preview build."}
        assert updated.status.message == "Session created."
    finally:
        http_server.stop()
