from __future__ import annotations

import struct
from starlette.testclient import TestClient

from gamecurveprobe.events import PreviewFrame


def test_ws_rejects_missing_token(client) -> None:
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws/events") as ws:
            pass
    assert exc.value.code == 4401


def test_ws_streams_events_after_auth(app, token, context) -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        with client.websocket_connect(
            f"/api/ws/events?token={token}",
            headers={"Origin": "http://127.0.0.1"},
        ) as ws:
            # First message should be session_sync
            data = ws.receive_json()
            assert data["type"] == "session_sync"
            assert "session" in data["payload"]


def test_ws_binary_preview_header_layout(app, token, context) -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        with client.websocket_connect(
            f"/api/ws/preview?token={token}",
            headers={"Origin": "http://127.0.0.1"},
        ) as ws:
            # Publish preview frame
            jpeg_payload = b"\xff\xd8\xff\xe0mockjpeg"
            context.events.publish_preview(
                PreviewFrame(
                    seq=1,
                    frame_id=42,
                    monotonic_ns=1_500_000_000,
                    width=640,
                    height=480,
                    jpeg=jpeg_payload,
                )
            )
            raw = ws.receive_bytes()
            assert len(raw) >= 20
            magic, width, height, frame_id, monotonic_ms = struct.unpack("<4sHHIQ", raw[:20])
            assert magic == b"GCPV"
            assert width == 640
            assert height == 480
            assert frame_id == 42
            assert monotonic_ms == 1500
            assert raw[20:] == jpeg_payload
