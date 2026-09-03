from concurrent.futures import Future
import threading
import time
import pytest

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import JobState
from gamecurveprobe.services.job_manager import JobManager


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


class BlockingExecutor:
    def __init__(self) -> None:
        self.threads = []

    def submit(self, fn, *args, **kwargs):
        future = Future()

        def worker():
            try:
                future.set_result(fn(*args, **kwargs))
            except Exception as exc:
                future.set_exception(exc)

        t = threading.Thread(target=worker, daemon=True)
        self.threads.append(t)
        t.start()
        return future


RESULT = {"status": "ok"}


def blocking_runner(cancel: threading.Event, publish):
    while not cancel.is_set():
        time.sleep(0.01)
    return RESULT


def test_job_transitions_to_completed_and_publishes_result() -> None:
    events = []
    manager = JobManager(executor=InlineExecutor(), publish=events.append)
    job = manager.start("measurement", lambda cancel, progress: RESULT)
    assert manager.get(job.id).state is JobState.COMPLETED
    assert manager.last_result == RESULT


def test_second_job_is_rejected_while_first_is_running() -> None:
    manager = JobManager(executor=BlockingExecutor(), publish=lambda _: None)
    manager.start("measurement", blocking_runner)
    with pytest.raises(DomainError) as exc:
        manager.start("idle_noise", blocking_runner)
    assert exc.value.code == "RESOURCE_BUSY"


def test_cancel_is_canceling_until_runner_exits() -> None:
    manager = JobManager(executor=BlockingExecutor(), publish=lambda _: None)
    job = manager.start("measurement", blocking_runner)
    manager.cancel(job.id)
    assert manager.get(job.id).state is JobState.CANCELING
