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


@ws_router.websocket("/events")
async def ws_events(websocket: WebSocket) -> None:
    context: AppContext = websocket.app.state.context
    if not _verify_ws_auth(websocket, context):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    subscriber = context.events.subscribe()

    try:
        # Initial session sync
        snapshot = context.session.snapshot()
        initial_event = {
            "seq": 0,
            "type": "session_sync",
            "timestamp": "",
            "payload": {
                "session": {
                    "id": snapshot.id,
                    "config": snapshot.config.__dict__ if hasattr(snapshot.config, "__dict__") else {},
                    "roi": snapshot.roi.__dict__ if snapshot.roi and hasattr(snapshot.roi, "__dict__") else None,
                    "capture": snapshot.capture.__dict__ if snapshot.capture and hasattr(snapshot.capture, "__dict__") else None,
                    "roi_quality": snapshot.roi_quality.__dict__ if snapshot.roi_quality and hasattr(snapshot.roi_quality, "__dict__") else None,
                    "last_job": snapshot.last_job.__dict__ if snapshot.last_job and hasattr(snapshot.last_job, "__dict__") else None,
                    "active_job": snapshot.active_job.__dict__ if snapshot.active_job and hasattr(snapshot.active_job, "__dict__") else None,
                }
            },
        }
        await websocket.send_text(json.dumps(initial_event, default=str))

        while True:
            envelope = subscriber.next_event(timeout=0.05)
            if envelope is not None:
                msg = {
                    "seq": envelope.seq,
                    "type": envelope.type,
                    "timestamp": envelope.timestamp,
                    "payload": envelope.payload,
                    "job_id": envelope.job_id,
                }
                await websocket.send_text(json.dumps(msg, default=str))
            else:
                await asyncio.sleep(0.02)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        context.events.unsubscribe(subscriber)


@ws_router.websocket("/preview")
async def ws_preview(websocket: WebSocket) -> None:
    context: AppContext = websocket.app.state.context
    if not _verify_ws_auth(websocket, context):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    subscriber = context.events.subscribe()

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
            else:
                await asyncio.sleep(0.02)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        context.events.unsubscribe(subscriber)
