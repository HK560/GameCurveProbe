from __future__ import annotations

import logging
import sys
import threading
from typing import Literal

logger = logging.getLogger(__name__)

SoundType = Literal["start", "stop", "complete", "test"]


class AudioService:
    """Service to play audio cues for measurement start/stop/complete events."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def play_sound(self, sound_type: SoundType, enabled: bool | None = None) -> None:
        is_enabled = self.enabled if enabled is None else enabled
        if not is_enabled:
            return

        thread = threading.Thread(target=self._play_sound_worker, args=(sound_type,), daemon=True)
        thread.start()

    def _play_sound_worker(self, sound_type: SoundType) -> None:
        if sys.platform != "win32":
            logger.debug("Sound effects skipped on non-Windows platform (%s)", sys.platform)
            return

        try:
            import winsound

            if sound_type == "start":
                # Ascending tone: C5 -> G5
                winsound.Beep(523, 90)
                winsound.Beep(784, 140)
            elif sound_type == "stop":
                # Descending tone: E5 -> A4
                winsound.Beep(659, 90)
                winsound.Beep(440, 140)
            elif sound_type == "complete":
                # Triumph chime: C5 -> E5 -> C6
                winsound.Beep(523, 70)
                winsound.Beep(659, 70)
                winsound.Beep(1046, 180)
            elif sound_type == "test":
                # Test tone: G5 -> C6
                winsound.Beep(784, 100)
                winsound.Beep(1046, 150)
        except Exception as exc:
            logger.warning("Failed to play winsound audio effect '%s': %s", sound_type, exc)
