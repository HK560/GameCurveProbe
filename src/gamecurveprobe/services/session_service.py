from __future__ import annotations

import csv
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from gamecurveprobe.models import CurvePoint, JobState, ProbeSession, ProbeSessionConfig, RoiRect, SessionResult
from gamecurveprobe.services.steady_probe_runner import ProbeExecutionError
from gamecurveprobe.services.window_service import WindowService


class SteadyProbeRunnerLike(Protocol):
    def run(self, config: ProbeSessionConfig, yaw_deg_per_px: float | None = None) -> SessionResult: ...


class CalibrationRunnerLike(Protocol):
    def run(self, config: ProbeSessionConfig) -> SessionResult: ...


class IdleNoiseCalibrationRunnerLike(Protocol):
    def run(self, config: ProbeSessionConfig) -> SessionResult: ...


class SessionService:
    """Owns in-memory probe sessions used by both GUI and IPC."""

    def __init__(
        self,
        window_service: WindowService,
        steady_probe_runner: SteadyProbeRunnerLike | None = None,
        calibration_runner: CalibrationRunnerLike | None = None,
        idle_noise_calibration_runner: IdleNoiseCalibrationRunnerLike | None = None,
    ) -> None:
        self._window_service = window_service
        self._steady_probe_runner = steady_probe_runner
        self._calibration_runner = calibration_runner
        self._idle_noise_calibration_runner = idle_noise_calibration_runner
        self._lock = threading.Lock()
        self._sessions: dict[str, ProbeSession] = {}

    def create_session(self, payload: dict[str, Any] | None = None) -> ProbeSession:
        session = ProbeSession(config=ProbeSessionConfig.from_payload(payload))
        session.status.touch(state=JobState.READY, message="Session created.")
        with self._lock:
            self._sessions[session.status.session_id] = session
        return session

    def get_session(self, session_id: str) -> ProbeSession:
        with self._lock:
            return self._sessions[session_id]

    def list_sessions(self) -> list[ProbeSession]:
        with self._lock:
            return list(self._sessions.values())

    def update_roi(self, session_id: str, payload: dict[str, Any]) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            session.config.roi = RoiRect(**payload)
            session.status.touch(message="ROI updated.")
            return session

    def calibrate_yaw360(self, session_id: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.status.touch(state=JobState.CALIBRATING, message="Running yaw 360 calibration.")
            config = ProbeSessionConfig.from_payload(session.config.to_dict())

        try:
            if self._calibration_runner is None:
                raise ProbeExecutionError("Yaw calibration runner is not configured.")
            result = self._calibration_runner.run(config)
        except ProbeExecutionError as exc:
            return self._fail_session(session_id, str(exc), str(exc))
        except Exception as exc:
            error_name = type(exc).__name__
            return self._fail_session(
                session_id,
                f"{error_name}: {exc}",
                f"Unexpected yaw calibration failure ({error_name}): {exc}",
            )

        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.result = result
            session.status.touch(state=JobState.READY, message="Yaw calibration complete.")
            return session

    def calibrate_idle_noise(self, session_id: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.status.touch(state=JobState.CALIBRATING, message="Calibrating idle noise.")
            config = ProbeSessionConfig.from_payload(session.config.to_dict())

        try:
            if self._idle_noise_calibration_runner is None:
                raise ProbeExecutionError("Idle noise calibration runner is not configured.")
            result = self._idle_noise_calibration_runner.run(config)
        except ProbeExecutionError as exc:
            return self._fail_session(session_id, str(exc), str(exc))
        except Exception as exc:
            error_name = type(exc).__name__
            return self._fail_session(
                session_id,
                f"{error_name}: {exc}",
                f"Unexpected idle noise calibration failure ({error_name}): {exc}",
            )

        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.config.idle_noise_floor_x = float(result.metadata.get("idle_noise_floor_x", 0.0))
            session.config.idle_noise_floor_y = float(result.metadata.get("idle_noise_floor_y", 0.0))
            session.result.notes.extend(result.notes)
            session.result.metadata.update(result.metadata)
            session.status.touch(state=JobState.READY, message="Idle noise calibration complete.")
            return session

    def run_steady(self, session_id: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.status.touch(state=JobState.RUNNING_STEADY, message="Running steady-state measurement.")
            config = ProbeSessionConfig.from_payload(session.config.to_dict())
            yaw_deg_per_px = session.result.yaw_deg_per_px

        try:
            if self._steady_probe_runner is None:
                raise ProbeExecutionError("Steady probe runner is not configured.")
            result = self._steady_probe_runner.run(
                config,
                yaw_deg_per_px=yaw_deg_per_px,
            )
        except ProbeExecutionError as exc:
            return self._fail_session(session_id, str(exc), str(exc))
        except Exception as exc:
            error_name = type(exc).__name__
            return self._fail_session(
                session_id,
                f"{error_name}: {exc}",
                f"Unexpected steady probe failure ({error_name}): {exc}",
            )

        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.result = result
            session.status.touch(state=JobState.COMPLETED, message="Steady-state measurement complete.")
            return session

    def run_dynamic(self, session_id: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            session.status.touch(state=JobState.RUNNING_DYNAMIC, message="Dynamic preview is not implemented yet.")
            session.result.notes.append("Dynamic response execution is still a scaffold placeholder.")
            session.status.touch(state=JobState.COMPLETED, message="Dynamic preview placeholder completed.")
            return session

    def cancel(self, session_id: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            session.status.touch(state=JobState.CANCELED, message="Session canceled.")
            return session

    def export_session(self, session_id: str, output_dir: str) -> dict[str, str]:
        with self._lock:
            session = self._sessions[session_id]
            export_dir = Path(output_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            raw_samples_path = export_dir / "raw_samples.csv"
            curve_summary_path = export_dir / "curve_summary.csv"
            session_meta_path = export_dir / "session_meta.json"
            controller_meta_curve_path = export_dir / "controller_meta_curve.cmcurves.json"

            rows = [*session.result.x_curve, *session.result.y_curve]
            self._write_curve_csv(raw_samples_path, rows, session.result.measurement_kind)
            self._write_curve_csv(curve_summary_path, rows, session.result.measurement_kind)
            session_meta_path.write_text(
                json.dumps(
                    {
                        "config": session.config.to_dict(),
                        "status": session.status.to_dict(),
                        "result": session.result.to_dict(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            controller_meta_curve_path.write_text(
                json.dumps(
                    self._build_controller_meta_curve_package(session),
                    indent=2,
                ),
                encoding="utf-8",
            )

            return {
                "raw_samples_csv": str(raw_samples_path),
                "curve_summary_csv": str(curve_summary_path),
                "session_meta_json": str(session_meta_path),
                "controller_meta_curve_json": str(controller_meta_curve_path),
            }

    def health(self) -> dict[str, Any]:
        windows = self._window_service.list_windows()
        return {
            "status": "ok",
            "window_count": len(windows),
            "session_count": len(self.list_sessions()),
            "capture_backend": "pending",
            "controller_backend": "pending",
        }

    def _write_curve_csv(self, path: Path, points: list[CurvePoint], measurement_kind: str | None) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "axis",
                    "direction",
                    "input_value",
                    "px_per_sec",
                    "normalized_speed",
                    "deg_per_sec",
                    "measurement_kind",
                ],
            )
            writer.writeheader()
            for point in points:
                row = point.to_dict()
                row["measurement_kind"] = measurement_kind
                writer.writerow(row)

    def _build_controller_meta_curve_package(self, session: ProbeSession) -> dict[str, Any]:
        exported_at = datetime.now(UTC).isoformat()
        inner_dz = session.config.inner_deadzone_marker
        outer_sat = session.config.outer_saturation_marker
        points = self._build_controller_meta_points(session.result.x_curve, inner_dz, outer_sat)

        return {
            "identifier": "ControllerMeta",
            "formatVersion": "1.0.0",
            "exportKind": "curve_transfer",
            "exportTime": exported_at,
            "itemCount": 1,
            "items": [
                {
                    "savedAt": exported_at,
                    "note": session.result.summary,
                    "curve": {
                        "id": f"{session.status.session_id}_x_curve",
                        "name": "Steady Probe Curve",
                        "kind": "polyline",
                        "color": "#34d399",
                        "visible": True,
                        "createdAt": exported_at,
                        "updatedAt": exported_at,
                        "sourceMeta": {
                            "kind": "conversion",
                            "description": "Converted from GameCurveProbe x_curve positive half-axis",
                        },
                        "innerDeadzone": 0,
                        "outerDeadzone": 0,
                        "deadzoneAdjustMode": "compress",
                        "points": points,
                        "basePoints": points,
                    },
                }
            ],
        }

    def _build_controller_meta_points(
        self,
        curve: list[CurvePoint],
        inner_deadzone: float = 0.0,
        outer_saturation: float = 1.0,
    ) -> list[dict[str, float]]:
        positive_points = [
            point for point in curve
            if point.axis == "x" and point.direction == "positive"
        ]
        if not positive_points:
            return [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 100.0}]

        # Determine the actual measured input range for normalization.
        input_min = inner_deadzone
        input_max = outer_saturation
        input_span = input_max - input_min

        # Find the max normalized_speed among measured points to rescale output.
        max_norm = max((p.normalized_speed for p in positive_points), default=1.0)
        if max_norm <= 0.0:
            max_norm = 1.0

        converted_points: list[dict[str, float]] = []
        for point in positive_points:
            # Remap input_value from [input_min, input_max] to [0, 100].
            if input_span > 0.0:
                x = (point.input_value - input_min) / input_span * 100.0
            else:
                x = point.input_value * 100.0
            # Remap normalized_speed so the max measured value maps to 100.
            y = point.normalized_speed / max_norm * 100.0
            converted_points.append({
                "x": round(min(max(x, 0.0), 100.0), 3),
                "y": round(min(max(y, 0.0), 100.0), 3),
            })

        converted_points.sort(key=lambda item: item["x"])

        points: list[dict[str, float]] = [{"x": 0.0, "y": 0.0}]
        points.extend(item for item in converted_points if 0.0 < item["x"] < 100.0)
        # Use the last measured point's y-value (rescaled) to close at (100, y_max),
        # which should be (100, 100) after normalization.
        points.append({"x": 100.0, "y": converted_points[-1]["y"] if converted_points else 100.0})
        return points

    def _fail_session(self, session_id: str, message: str, note: str) -> ProbeSession:
        with self._lock:
            session = self._sessions[session_id]
            if session.status.state is JobState.CANCELED:
                return session
            session.status.touch(state=JobState.FAILED, message=message)
            session.result.notes.append(note)
            return session
