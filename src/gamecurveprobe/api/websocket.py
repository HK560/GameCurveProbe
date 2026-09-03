from __future__ import annotations

import asyncio
import json
import struct
from urllib.parse import urlparse
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gamecurveprobe.context import AppContext
from gamecurveprobe.events import PreviewFrame

ws_router = APIRouter(prefix="/api/ws")


def _verify_ws_auth(websocket: WebSocket, context: AppContext) -> bool:
    token = websocket.query_params.get("token")
    if not token or token != context.token:
        return False

    origin = websocket.headers.get("origin")
    if origin:
        parsed = urlparse(origin)
        normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if normalized not in context.allowed_origins and origin.rstrip("/") not in context.allowed_origins:
            return False
    return True


from dataclasses import asdict, is_dataclass
from enum import Enum

def to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


@ws_router.websocket("/events")
async def ws_events(websocket: WebSocket) -> None:
    context: AppContext = websocket.app.state.context
    if not _verify_ws_auth(websocket, context):
        print(f"[WS-Events] Rejected connection (invalid token/origin) from {websocket.client}")
        await websocket.close(code=4401)
        return

    await websocket.accept()
    subscriber = context.events.subscribe()
    print(f"[WS-Events] Accepted client connection from {websocket.client}")

    try:
        # Initial session sync
        snapshot = context.session.snapshot()
        initial_event = {
            "seq": 0,
            "type": "session_sync",
            "timestamp": "",
            "payload": {
                "session": to_dict(snapshot),
            },
        }
        await websocket.send_text(json.dumps(initial_event, default=str))
        print(f"[WS-Events] Dispatched session_sync to {websocket.client} (has_capture={snapshot.capture is not None})")

        while True:
            envelope = subscriber.next_event(timeout=0.05)
            if envelope is not None:
                msg = {
                    "seq": envelope.seq,
                    "type": envelope.type,
                    "timestamp": envelope.timestamp,
                    "payload": to_dict(envelope.payload),
                    "job_id": envelope.job_id,
                }
                await websocket.send_text(json.dumps(msg, default=str))
                print(f"[WS-Events] Dispatched event '{envelope.type}' to {websocket.client}")
            else:
                await asyncio.sleep(0.02)
    except (WebSocketDisconnect, asyncio.CancelledError):
        print(f"[WS-Events] Client disconnected: {websocket.client}")
    finally:
        context.events.unsubscribe(subscriber)


@ws_router.websocket("/preview")
async def ws_preview(websocket: WebSocket) -> None:
    context: AppContext = websocket.app.state.context
    if not _verify_ws_auth(websocket, context):
        print(f"[WS-Preview] Rejected connection (invalid token/origin) from {websocket.client}")
        await websocket.close(code=4401)
        return

    await websocket.accept()
    subscriber = context.events.subscribe()
    print(f"[WS-Preview] Accepted client connection from {websocket.client}")
    logged_first_frame = False

    try:
        while True:
            preview: PreviewFrame | None = subscriber.next_preview(timeout=0.05)
            if preview is not None:
                monotonic_ms = int(preview.monotonic_ns / 1_000_000)
                header = struct.pack(
                    "<4sHHIQ",
                    b"GCPV",
                    preview.width,
                    preview.height,
                    preview.frame_id,
                    monotonic_ms,
                )
                payload = header + preview.jpeg
                await websocket.send_bytes(payload)
                if not logged_first_frame:
                    print(f"[WS-Preview] First binary preview frame sent to {websocket.client} ({preview.width}x{preview.height}, {len(payload)} bytes)")
                    logged_first_frame = True
            else:
                await asyncio.sleep(0.02)
    except (WebSocketDisconnect, asyncio.CancelledError):
        print(f"[WS-Preview] Client disconnected: {websocket.client}")
    finally:
        context.events.unsubscribe(subscriber)
