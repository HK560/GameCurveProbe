from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from gamecurveprobe.services.session_service import SessionService
from gamecurveprobe.services.window_service import WindowService


YAW360_PREVIEW_DISABLED_MESSAGE = "Yaw 360 calibration is disabled in this preview build."
DYNAMIC_PREVIEW_DISABLED_MESSAGE = "Dynamic response run is disabled in this preview build."


class LocalHttpServer:
    """Tiny local JSON HTTP server for IPC control."""

    def __init__(self, host: str, port: int, session_service: SessionService, window_service: WindowService) -> None:
        self._host = host
        self._port = port
        self._session_service = session_service
        self._window_service = window_service
        self._thread: threading.Thread | None = None
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        handler_class = self._build_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler_class)
        self._thread = threading.Thread(target=self._server.serve_forever, name="gamecurveprobe-ipc", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def join(self) -> None:
        if self._thread is not None:
            self._thread.join()

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        session_service = self._session_service
        window_service = self._window_service

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if path == "/health":
                    self._send_json(HTTPStatus.OK, session_service.health())
                    return
                if path == "/windows":
                    self._send_json(HTTPStatus.OK, {"windows": [item.to_dict() for item in window_service.list_windows()]})
                    return
                if path.startswith("/session/") and path.endswith("/status"):
                    session_id = path.split("/")[2]
                    session = session_service.get_session(session_id)
                    self._send_json(HTTPStatus.OK, session.status.to_dict())
                    return
                if path.startswith("/session/") and path.endswith("/result"):
                    session_id = path.split("/")[2]
                    session = session_service.get_session(session_id)
                    self._send_json(HTTPStatus.OK, session.result.to_dict())
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                payload = self._read_json()
                try:
                    if path == "/session":
                        session = session_service.create_session(payload)
                        self._send_json(HTTPStatus.CREATED, session.to_dict())
                        return
                    if path.startswith("/session/") and path.endswith("/roi"):
                        session_id = path.split("/")[2]
                        session = session_service.update_roi(session_id, payload)
                        self._send_json(HTTPStatus.OK, session.to_dict())
                        return
                    if path.startswith("/session/") and path.endswith("/calibrate/yaw360"):
                        self._send_json(
                            HTTPStatus.CONFLICT,
                            {"error": YAW360_PREVIEW_DISABLED_MESSAGE},
                        )
                        return
                    if path.startswith("/session/") and path.endswith("/calibrate/idle-noise"):
                        session_id = path.split("/")[2]
                        session = session_service.calibrate_idle_noise(session_id)
                        self._send_json(HTTPStatus.OK, session.to_dict())
                        return
                    if path.startswith("/session/") and path.endswith("/run/steady"):
                        session_id = path.split("/")[2]
                        session = session_service.run_steady(session_id)
                        self._send_json(HTTPStatus.OK, session.to_dict())
                        return
                    if path.startswith("/session/") and path.endswith("/run/dynamic"):
                        self._send_json(
                            HTTPStatus.CONFLICT,
                            {"error": DYNAMIC_PREVIEW_DISABLED_MESSAGE},
                        )
                        return
                    if path.startswith("/session/") and path.endswith("/cancel"):
                        session_id = path.split("/")[2]
                        session = session_service.cancel(session_id)
                        self._send_json(HTTPStatus.OK, session.to_dict())
                        return
                    if path.startswith("/session/") and path.endswith("/export"):
                        session_id = path.split("/")[2]
                        exported = session_service.export_session(session_id, payload["output_dir"])
                        self._send_json(HTTPStatus.OK, exported)
                        return
                except KeyError:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown session"})
                    return
                except (TypeError, ValueError) as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return

                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

            def _read_json(self) -> dict[str, Any]:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0:
                    return {}
                raw = self.rfile.read(content_length)
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status.value)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
