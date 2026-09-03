from __future__ import annotations

import asyncio
import time

import pytest

from gamecurveprobe.api.websocket import next_event_async


@pytest.mark.asyncio
async def test_event_queue_wait_does_not_block_event_loop() -> None:
    class SlowSubscriber:
        def next_event(self, timeout: float):
            time.sleep(timeout)
            return None

    ticked = False

    async def tick() -> None:
        nonlocal ticked
        await asyncio.sleep(0.005)
        ticked = True

    waiting = asyncio.create_task(next_event_async(SlowSubscriber(), 0.05))
    await tick()
    await waiting

    assert ticked is True
