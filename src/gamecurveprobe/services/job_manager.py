from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from gamecurveprobe.errors import DomainError, JobCanceled
from gamecurveprobe.models import JobSnapshot, JobState

JobRunner = Callable[[threading.Event, Callable[[Mapping[str, object]], None]], object]


@dataclass(slots=True)
class JobRecord:
    id: str
    kind: str
    state: JobState
    cancel_event: threading.Event
    progress: Mapping[str, object] | None = None
    result: object | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""
    future: Future[object] | None = None

    @classmethod
    def create(cls, kind: str) -> "JobRecord":
        now = datetime.now(UTC).isoformat()
        return cls(
            id=uuid4().hex[:12],
            kind=kind,
            state=JobState.QUEUED,
            cancel_event=threading.Event(),
            created_at=now,
            updated_at=now,
        )

    def snapshot(self) -> JobSnapshot:
        return JobSnapshot(
            id=self.id,
            kind=self.kind,
            state=self.state,
            progress=self.progress,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class JobManager:
    """Manages execution of single hardware jobs (measurement, calibration)."""

    def __init__(
        self,
        executor: Executor | None = None,
        publish: Callable[[Mapping[str, object]], None] | None = None,
        on_result: Callable[[object], None] | None = None,
    ) -> None:
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="gcp-job")
        self._publish = publish or (lambda _: None)
        self._on_result = on_result
        self._lock = threading.RLock()
        self._active_job: JobRecord | None = None
        self._last_job: JobRecord | None = None
        self._last_result: object | None = None
        self._jobs_history: dict[str, JobRecord] = {}

    @property
    def active_job(self) -> JobSnapshot | None:
        with self._lock:
            return self._active_job.snapshot() if self._active_job is not None else None

    @property
    def last_job(self) -> JobSnapshot | None:
        with self._lock:
            return self._last_job.snapshot() if self._last_job is not None else None

    @property
    def last_result(self) -> object | None:
        with self._lock:
            return self._last_result

    def get(self, job_id: str) -> JobSnapshot:
        with self._lock:
            record = self._require_job(job_id)
            return record.snapshot()

    def start(self, kind: str, runner: JobRunner) -> JobSnapshot:
        with self._lock:
            if self._active_job is not None and not self._active_job.state.is_terminal:
                raise DomainError("RESOURCE_BUSY", "A hardware job is already running.")
            record = JobRecord.create(kind)
            self._active_job = record
            self._jobs_history[record.id] = record

            record.future = self._executor.submit(self._run, record, runner)
            return record.snapshot()

    def cancel(self, job_id: str) -> JobSnapshot:
        with self._lock:
            record = self._require_job(job_id)
            if not record.state.is_terminal:
                record.state = JobState.CANCELING
                record.updated_at = datetime.now(UTC).isoformat()
                record.cancel_event.set()
                self._publish({"type": "job_status", "job": record.snapshot()})
            return record.snapshot()

    def cancel_active(self) -> JobSnapshot | None:
        with self._lock:
            if self._active_job is not None and not self._active_job.state.is_terminal:
                return self.cancel(self._active_job.id)
            return None

    def wait(self, timeout: float = 3.0) -> None:
        with self._lock:
            fut = self._active_job.future if self._active_job is not None else None
        if fut is not None:
            try:
                fut.result(timeout=timeout)
            except Exception:
                pass

    def close(self) -> None:
        self.cancel_active()
        if isinstance(self._executor, ThreadPoolExecutor):
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, record: JobRecord, runner: JobRunner) -> None:
        with self._lock:
            record.state = JobState.RUNNING
            record.updated_at = datetime.now(UTC).isoformat()
            self._publish({"type": "job_status", "job": record.snapshot()})

        def progress_callback(data: Mapping[str, object]) -> None:
            with self._lock:
                record.progress = data
                record.updated_at = datetime.now(UTC).isoformat()
            self._publish({"type": "job_progress", "job_id": record.id, "data": data})

        try:
            res = runner(record.cancel_event, progress_callback)
            with self._lock:
                record.state = JobState.COMPLETED
                record.result = res
                record.updated_at = datetime.now(UTC).isoformat()
                self._last_result = res
                self._last_job = record
                self._active_job = None
                if self._on_result is not None:
                    self._on_result(res)
                self._publish({"type": "job_completed", "job": record.snapshot(), "result": res})
        except JobCanceled:
            with self._lock:
                record.state = JobState.CANCELED
                record.updated_at = datetime.now(UTC).isoformat()
                self._last_job = record
                self._active_job = None
                self._publish({"type": "job_canceled", "job": record.snapshot()})
        except Exception as exc:
            with self._lock:
                record.state = JobState.FAILED
                record.error = str(exc)
                record.updated_at = datetime.now(UTC).isoformat()
                self._last_job = record
                self._active_job = None
                self._publish({"type": "job_failed", "job": record.snapshot(), "error": str(exc)})

    def _require_job(self, job_id: str) -> JobRecord:
        if job_id not in self._jobs_history:
            raise DomainError("JOB_NOT_FOUND", f"Job {job_id} not found.")
        return self._jobs_history[job_id]
