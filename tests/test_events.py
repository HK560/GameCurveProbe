from __future__ import annotations

from gamecurveprobe.events import EventHub, PreviewFrame, publish_job_event


def frame(frame_id: int) -> PreviewFrame:
    return PreviewFrame(
        seq=frame_id,
        frame_id=frame_id,
        monotonic_ns=frame_id * 10_000_000,
        width=100,
        height=100,
        jpeg=b"\xff\xd8\xff\xe0test",
    )


def test_preview_queue_keeps_only_latest_frame() -> None:
    hub = EventHub()
    subscriber = hub.subscribe()
    hub.publish_preview(frame(1))
    hub.publish_preview(frame(2))
    assert subscriber.next_preview().frame_id == 2


def test_job_event_bridge_preserves_lifecycle_event_type() -> None:
    hub = EventHub()
    subscriber = hub.subscribe()
    event = {
        "type": "job_progress",
        "job_id": "measure-1",
        "data": {"phase": "stage_start", "current_point": 0},
    }

    publish_job_event(hub, event)

    envelope = subscriber.next_event()
    assert envelope is not None
    assert envelope.type == "job_progress"
    assert envelope.payload == event
