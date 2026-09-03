from __future__ import annotations

import time
from gamecurveprobe.services.audio_service import AudioService


def test_audio_service_disabled() -> None:
    audio = AudioService(enabled=False)
    # Playing sound when disabled should return immediately without error
    audio.play_sound("start")
    audio.play_sound("stop")
    audio.play_sound("complete")


def test_audio_service_play_sound_non_blocking() -> None:
    audio = AudioService(enabled=True)
    start_time = time.time()
    # play_sound spawns a daemon thread and returns almost instantly
    audio.play_sound("test")
    elapsed = time.time() - start_time
    assert elapsed < 0.2
