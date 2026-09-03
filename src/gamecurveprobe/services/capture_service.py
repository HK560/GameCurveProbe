from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import cv2
import numpy as np

from gamecurveprobe.backends.capture.base import CaptureBackend, Frame
from gamecurveprobe.errors import DomainError
from gamecurveprobe.events import PreviewFrame
from gamecurveprobe.models import CaptureHealth, CaptureInfo, RoiRect, WindowState
from gamecurveprobe.services.window_service import WindowService


class CaptureService:
    """Manages backend selection, health evaluation, and frame distribution."""

    def __init__(
        self,
        backends: Mapping[str, CaptureBackend],
        preview_callback: Callable[[PreviewFrame], None] | None = None,
        window_service: WindowService | None = None,
    ) -> None:
        self._backends = dict(backends)
        self._preview_callback = preview_callback
        self._window_service = window_service
        self._active_backend: CaptureBackend | None = None
        self._active_info: CaptureInfo | None = None
        self._lock = threading.RLock()
        self._frame_ready = threading.Condition(self._lock)
        self._latest_frame: Frame | None = None
        self._stop_preview = threading.Event()
        self._preview_thread: threading.Thread | None = None
        self._fault: DomainError | None = None

    @property
    def active_backend_name(self) -> str | None:
        with self._lock:
            return self._active_backend.name if self._active_backend is not None else None

    @property
    def active_info(self) -> CaptureInfo | None:
        with self._lock:
            return self._active_info

    def attach(self, window_id: int, requested: str = "auto", fps: int = 120) -> CaptureInfo:
        # Automatic capture must remain occlusion-safe.  dxcam duplicates the
        # composed desktop and therefore cannot be a transparent fallback for
        # a window capture backend.
        candidates = ("wgc",) if requested == "auto" else (requested,)
        failures: list[DomainError] = []

        print(f"[CaptureService] Attaching to window_id={window_id}, requested={requested}, fps={fps}")
        self.close()
        state = self._inspect_window(window_id)
        if state is not None:
            if not state.exists:
                raise DomainError("WINDOW_GONE", "The target window no longer exists.")
            if state.minimized:
                raise DomainError("WINDOW_MINIMIZED", "目标窗口已最小化，请不要最小化窗口。")
        with self._lock:
            self._fault = None
            for name in candidates:
                if name not in self._backends:
                    print(f"[CaptureService] Backend '{name}' not available in registered backends.")
                    continue
                backend = self._backends[name]
                print(f"[CaptureService] Trying capture backend '{name}'...")
                try:
                    info = self._attach_and_validate(
                        backend,
                        window_id,
                        fps,
                        strict_health=name == "wgc",
                    )
                    self._active_backend = backend
                    self._active_info = info
                    print(f"[CaptureService] Successfully attached with '{name}': {info.width}x{info.height} @ {info.target_fps}fps")
                    self._start_preview_worker()
                    return info
                except DomainError as exc:
                    print(f"[CaptureService] Backend '{name}' DomainError: {exc}")
                    failures.append(exc)
                    backend.close()
                except Exception as exc:
                    print(f"[CaptureService] Backend '{name}' unexpected Exception: {exc}")
                    failures.append(DomainError("CAPTURE_FAILED", f"{name} failed: {exc}"))
                    backend.close()

            if failures:
                print(f"[CaptureService] All candidate backends failed: {failures}")
                raise failures[-1]
            raise DomainError("BACKEND_NOT_FOUND", f"No suitable capture backend found for {requested}.")

    def _attach_and_validate(
        self,
        backend: CaptureBackend,
        window_id: int,
        fps: int,
        *,
        strict_health: bool,
    ) -> CaptureInfo:
        info = backend.attach(window_id, fps)
        frames: list[Frame] = []
        expected_count = 10 if strict_health else 1
        for _ in range(expected_count):
            frame = backend.read(timeout_ms=200)
            if frame is None:
                if frames:
                    break
                raise DomainError("CAPTURE_STALLED", f"{backend.name} capture stalled during startup.")
            if frames and frame.frame_id <= frames[-1].frame_id:
                raise DomainError(
                    "CAPTURE_STALLED",
                    f"{backend.name} did not produce a fresh callback frame during startup.",
                )
            if frames and frame.image.shape != frames[0].image.shape:
                raise DomainError("CAPTURE_UNSTABLE", f"{backend.name} changed frame size during startup.")
            frames.append(frame)

        if strict_health:
            black_frames = sum(
                float(frame.image.mean()) <= 1.0 and float(frame.image.std()) <= 1.0
                for frame in frames
            )
            if black_frames == len(frames):
                raise DomainError("CAPTURE_BLACK_FRAME", f"{backend.name} returned only black frames.")
        self._latest_frame = frames[-1]
        return info

    def _start_preview_worker(self) -> None:
        self._stop_preview.clear()
        print("[CaptureService] Starting background frame distribution worker...")
        self._preview_thread = threading.Thread(
            target=self._preview_loop,
            daemon=True,
            name="CapturePreviewWorker",
        )
        self._preview_thread.start()

    def _preview_loop(self) -> None:
        seq = 0
        logged_first_frame = False
        last_preview_at = 0.0
        last_state_check = 0.0
        while not self._stop_preview.is_set():
            with self._lock:
                backend = self._active_backend
                info = self._active_info
            if backend is None:
                time.sleep(0.05)
                continue

            now = time.monotonic()
            if info is not None and now - last_state_check >= 0.25:
                last_state_check = now
                state = self._inspect_window(info.window_id)
                if state is not None:
                    if not state.exists:
                        self._set_fault(DomainError("WINDOW_GONE", "The target window was closed."))
                        return
                    if state.minimized:
                        self._set_fault(
                            DomainError("WINDOW_MINIMIZED", "目标窗口已最小化，请不要最小化窗口。")
                        )
                        return

            frame = backend.read(timeout_ms=50)
            if frame is not None and frame.image is not None:
                if info is not None and frame.image.shape[:2] != (info.height, info.width):
                    self._set_fault(
                        DomainError(
                            "ROI_INVALIDATED",
                            "The capture size changed; select the ROI again.",
                        )
                    )
                    return
                with self._frame_ready:
                    self._latest_frame = frame
                    self._frame_ready.notify_all()
                now = time.monotonic()
                if self._preview_callback is None or now - last_preview_at < 1 / 30:
                    continue
                last_preview_at = now
                try:
                    success, encoded = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if success:
                        preview = PreviewFrame(
                            seq=seq,
                            frame_id=frame.frame_id,
                            monotonic_ns=frame.monotonic_ns,
                            width=frame.image.shape[1],
                            height=frame.image.shape[0],
                            jpeg=encoded.tobytes(),
                        )
                        seq += 1
                        self._preview_callback(preview)
                        if not logged_first_frame:
                            print(f"[CaptureService] First preview frame published to EventHub ({frame.image.shape[1]}x{frame.image.shape[0]}, size={len(preview.jpeg)} bytes)")
                            logged_first_frame = True
                except Exception as exc:
                    print(f"[CaptureService] Error encoding preview frame: {exc}")
            else:
                if not backend.health().is_healthy:
                    self._set_fault(
                        DomainError("CAPTURE_STALLED", "The capture stopped producing new frames.")
                    )
                    return

    def read_latest(self, timeout_ms: int = 100) -> Frame | None:
        with self._frame_ready:
            return self._latest_frame

    def assert_ready(self, roi: RoiRect | None = None) -> None:
        with self._lock:
            info = self._active_info
            frame = self._latest_frame
            fault = self._fault
        if info is None:
            raise DomainError("CAPTURE_REQUIRED", "Attach a capture source first.")
        if fault is not None:
            raise fault
        state = self._inspect_window(info.window_id)
        if state is not None:
            if not state.exists:
                raise DomainError("WINDOW_GONE", "The target window was closed.")
            if state.minimized:
                raise DomainError("WINDOW_MINIMIZED", "目标窗口已最小化，请不要最小化窗口。")
        if frame is None:
            raise DomainError("CAPTURE_STALLED", "The capture has not produced a frame.")
        if not self._active_backend.health().is_healthy:
            raise DomainError("CAPTURE_STALLED", "The capture stopped producing new frames.")
        if roi is not None:
            height, width = frame.image.shape[:2]
            if (
                roi.x < 0
                or roi.y < 0
                or roi.width <= 0
                or roi.height <= 0
                or roi.x + roi.width > width
                or roi.y + roi.height > height
            ):
                raise DomainError("ROI_INVALIDATED", "The ROI is outside the current capture frame.")

    def read(self, timeout_ms: int = 100) -> Frame | None:
        """Implement the frame-provider contract consumed by MotionSampler."""
        with self._frame_ready:
            if self._fault is not None:
                raise self._fault
            if self._active_backend is None:
                return None
            current_id = self._latest_frame.frame_id if self._latest_frame is not None else -1
            ready = self._frame_ready.wait_for(
                lambda: self._active_backend is None
                or (self._latest_frame is not None and self._latest_frame.frame_id > current_id),
                timeout=max(0.0, timeout_ms / 1000.0),
            )
            if not ready or self._active_backend is None:
                if self._fault is not None:
                    raise self._fault
                if not self._active_backend.health().is_healthy:
                    fault = DomainError(
                        "CAPTURE_STALLED",
                        "The capture stopped producing new frames.",
                    )
                    self._fault = fault
                    raise fault
                return None
            return self._latest_frame

    def health(self) -> CaptureHealth:
        with self._lock:
            if self._active_backend is None:
                return CaptureHealth(
                    is_healthy=False,
                    fps=0.0,
                    duplicate_ratio=1.0,
                    last_error=self._fault.code if self._fault is not None else None,
                )
            health = self._active_backend.health()
            info = self._active_info
            fault = self._fault
        state = self._inspect_window(info.window_id) if info is not None else None
        return CaptureHealth(
            is_healthy=health.is_healthy and fault is None,
            fps=health.fps,
            duplicate_ratio=health.duplicate_ratio,
            last_error=fault.code if fault is not None else health.last_error,
            frame_id=health.frame_id,
            frame_age_ms=health.frame_age_ms,
            window_exists=state.exists if state is not None else True,
            window_minimized=state.minimized if state is not None else False,
        )

    def _inspect_window(self, window_id: int) -> WindowState | None:
        if self._window_service is None:
            return None
        return self._window_service.inspect_window(window_id)

    def _set_fault(self, fault: DomainError) -> None:
        with self._frame_ready:
            self._fault = fault
            self._frame_ready.notify_all()

    def close(self) -> None:
        self._stop_preview.set()
        with self._lock:
            backend = self._active_backend
        if backend is not None:
            try:
                backend.close()
            except Exception:
                pass
        if self._preview_thread is not None and self._preview_thread.is_alive():
            self._preview_thread.join(timeout=0.3)
        self._preview_thread = None

        with self._frame_ready:
            self._active_backend = None
            self._active_info = None
            self._latest_frame = None
            self._fault = None
            self._frame_ready.notify_all()
