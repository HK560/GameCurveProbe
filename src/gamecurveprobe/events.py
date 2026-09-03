from __future__ import annotations

import queue
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    seq: int
    type: str
    timestamp: str
    payload: Mapping[str, object]
    job_id: str | None = None


@dataclass(frozen=True, slots=True)
class PreviewFrame:
    seq: int
    frame_id: int
    monotonic_ns: int
    width: int
    height: int
    jpeg: bytes


class EventSubscriber:
    """Subscriber queue receiving JSON events and latest-preview frame."""

    def __init__(self, max_events: int = 100) -> None:
        self._event_queue: queue.Queue[EventEnvelope] = queue.Queue(maxsize=max_events)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._latest_preview: PreviewFrame | None = None
        self._closed = False

    def publish_event(self, envelope: EventEnvelope) -> None:
        if self._closed:
            return
        try:
            self._event_queue.put_nowait(envelope)
        except queue.Full:
            # Drop oldest non-terminal progress event if possible
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._event_queue.put_nowait(envelope)
            except queue.Full:
                pass

    def publish_preview(self, frame: PreviewFrame) -> None:
        if self._closed:
            return
        with self._condition:
            self._latest_preview = frame
            self._condition.notify_all()

    def next_event(self, timeout: float = 0.1) -> EventEnvelope | None:
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def next_preview(self, timeout: float = 0.1) -> PreviewFrame | None:
        with self._condition:
            if self._latest_preview is not None:
                frame = self._latest_preview
                self._latest_preview = None
                return frame
            self._condition.wait(timeout=timeout)
            frame = self._latest_preview
            self._latest_preview = None
            return frame

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class EventHub:
    """Bounded event distribution center for real-time WebSocket clients."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[EventSubscriber] = []
        self._seq = 0
        self._closed = False

    def subscribe(self) -> EventSubscriber:
        with self._lock:
            subscriber = EventSubscriber()
            self._subscribers.append(subscriber)
            return subscriber

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)
            subscriber.close()

    def publish(self, event_type: str, payload: Mapping[str, object], job_id: str | None = None) -> EventEnvelope:
        with self._lock:
            self._seq += 1
            envelope = EventEnvelope(
                seq=self._seq,
                type=event_type,
                timestamp=datetime.now(UTC).isoformat(),
                payload=dict(payload),
                job_id=job_id,
            )
            for sub in list(self._subscribers):
                sub.publish_event(envelope)
            return envelope

    def publish_preview(self, frame: PreviewFrame) -> None:
        with self._lock:
            for sub in list(self._subscribers):
                sub.publish_preview(frame)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for sub in self._subscribers:
                sub.close()
            self._subscribers.clear()
