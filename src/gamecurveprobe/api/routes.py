from __future__ import annotations

import io
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from gamecurveprobe.api.auth import require_token, verify_origin
from gamecurveprobe.api.schemas import (
    AudioTestRequest,
    CaptureAttachRequest,
    ConfigUpdateRequest,
    ControllerStateRequest,
    ControllerWakeRequest,
    DeadzoneRequest,
    HealthResponse,
    JobResponse,
    JobStartRequest,
    ProbeStartRequest,
    ProbeUpdateRequest,
    RoiRequest,
    SessionResponse,
    WindowsListResponse,
)
from gamecurveprobe.context import AppContext
from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import RoiRect, SessionResult
from gamecurveprobe.vision.curve_classifier import classify_curve
from gamecurveprobe.vision.roi_analyzer import RoiAnalyzer

router = APIRouter(prefix="/api")


def get_context(request: Request) -> AppContext:
    return request.app.state.context


@router.get("/health", response_model=HealthResponse)
def health(context: AppContext = Depends(get_context)) -> dict[str, Any]:
    return {
        "status": "ok",
        "controller_ready": context.controller.is_available(),
        "controller_enabled": context.controller.is_enabled(),
    }


@router.get("/controller", dependencies=[Depends(verify_origin), Depends(require_token)])
def get_controller_state(context: AppContext = Depends(get_context)) -> dict[str, bool]:
    return {"enabled": context.controller.is_enabled(), "available": context.controller.is_available()}


@router.put("/controller", dependencies=[Depends(verify_origin), Depends(require_token)])
def update_controller_state(req: ControllerStateRequest, context: AppContext = Depends(get_context)) -> dict[str, bool]:
    enabled = context.controller.set_enabled(req.enabled)
    return {"enabled": enabled, "available": context.controller.is_available()}


@router.post("/controller/wake", dependencies=[Depends(verify_origin), Depends(require_token)])
def wake_controller(req: ControllerWakeRequest, context: AppContext = Depends(get_context)) -> dict[str, str]:
    context.controller.wake(req.input)
    return {"input": req.input, "duration": "0.5s"}


@router.post("/app/quit", dependencies=[Depends(verify_origin), Depends(require_token)])
def quit_app(background_tasks: BackgroundTasks, context: AppContext = Depends(get_context)) -> dict[str, str]:
    background_tasks.add_task(context.request_shutdown)
    return {"status": "shutting_down"}


@router.get("/windows", response_model=WindowsListResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def list_windows(context: AppContext = Depends(get_context)) -> dict[str, Any]:
    wins = context.windows.list_windows()
    print(f"[API] GET /api/windows -> found {len(wins)} windows")
    return {
        "windows": [
            {
                "id": w.window_id,
                "title": w.title,
                "pid": getattr(w, "pid", None),
                "width": w.rect[2] - w.rect[0] if w.rect else 0,
                "height": w.rect[3] - w.rect[1] if w.rect else 0,
            }
            for w in wins
        ]
    }


@router.post("/capture/attach", dependencies=[Depends(verify_origin), Depends(require_token)])
def attach_capture(req: CaptureAttachRequest, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    print(f"[API] POST /api/capture/attach: window_id={req.window_id}, backend={req.backend}, fps={req.target_fps}")
    info = context.capture.attach(req.window_id, requested=req.backend, fps=req.target_fps)
    context.session.update_capture(info)
    info_dict = asdict(info)
    context.events.publish("capture_changed", {"capture": info_dict})
    print(f"[API] POST /api/capture/attach -> attached: {info_dict}")
    return {"capture": info_dict}


@router.post("/capture/detach", dependencies=[Depends(verify_origin), Depends(require_token)])
def detach_capture(context: AppContext = Depends(get_context)) -> dict[str, Any]:
    context.capture.close()
    context.session.update_capture(None)
    context.session.update_roi(None)
    context.session.update_roi_quality(None)
    context.events.publish("capture_changed", {"capture": None})
    return {"capture": None}


@router.get("/capture/health", dependencies=[Depends(verify_origin), Depends(require_token)])
def get_capture_health(context: AppContext = Depends(get_context)) -> dict[str, Any]:
    h = context.capture.health()
    return {"health": h}


@router.get("/session", response_model=SessionResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def get_session(context: AppContext = Depends(get_context)) -> Any:
    # Sync job status from job manager
    context.session.set_active_job(context.jobs.active_job)
    context.session.set_last_job(context.jobs.last_job)
    return context.session.snapshot()


@router.put("/session/config", response_model=SessionResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def update_config(req: ConfigUpdateRequest, context: AppContext = Depends(get_context)) -> Any:
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    context.session.update_config(payload)
    cfg = context.session.config_snapshot()
    if context.hotkey is not None:
        context.hotkey.update_config(cfg.hotkey_enabled, cfg.hotkey_start, cfg.hotkey_stop)
    if context.audio is not None:
        context.audio.enabled = cfg.sound_enabled
    context.events.publish("config_updated", {"config": cfg})
    context.session.set_active_job(context.jobs.active_job)
    context.session.set_last_job(context.jobs.last_job)
    return context.session.snapshot()


@router.get("/session/config", dependencies=[Depends(verify_origin), Depends(require_token)])
def get_config(context: AppContext = Depends(get_context)) -> Any:
    return {"config": context.session.config_snapshot()}


@router.put("/session/deadzones", response_model=SessionResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def update_deadzones(req: DeadzoneRequest, context: AppContext = Depends(get_context)) -> Any:
    context.session.update_config(req.model_dump())
    context.events.publish("config_updated", {"config": context.session.config_snapshot()})
    return context.session.snapshot()


@router.post("/session/roi", dependencies=[Depends(verify_origin), Depends(require_token)])
def update_roi(req: RoiRequest, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    roi = RoiRect(x=req.x, y=req.y, width=req.width, height=req.height)
    context.session.update_roi(roi)

    # Analyze ROI quality if frame available
    quality = None
    latest = context.capture.read_latest(timeout_ms=50)
    if latest is not None and latest.image is not None:
        h, w = latest.image.shape[:2]
        if req.x + req.width <= w and req.y + req.height <= h:
            roi_patch = latest.image[req.y : req.y + req.height, req.x : req.x + req.width]
            analyzer = RoiAnalyzer()
            quality = analyzer.analyze(roi_patch)
            context.session.update_roi_quality(quality)

    context.events.publish("roi_changed", {"roi": roi, "quality": quality})
    return {"roi": roi, "quality": quality}


@router.post("/deadzone/start", dependencies=[Depends(verify_origin), Depends(require_token)])
def start_deadzone_probe(req: ProbeStartRequest, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    probe_snap = context.probe.start(req.initial_output, req.step, req.direction)
    context.events.publish("deadzone_probe_updated", {"probe": probe_snap})
    return {"probe": probe_snap}


@router.post("/deadzone/update", dependencies=[Depends(verify_origin), Depends(require_token)])
def update_deadzone_probe(req: ProbeUpdateRequest, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    probe_snap = context.probe.update(req.output)
    context.events.publish("deadzone_probe_updated", {"probe": probe_snap})
    return {"probe": probe_snap}


@router.post("/deadzone/stop", dependencies=[Depends(verify_origin), Depends(require_token)])
def stop_deadzone_probe(context: AppContext = Depends(get_context)) -> dict[str, Any]:
    probe_snap = context.probe.stop()
    context.events.publish("deadzone_probe_updated", {"probe": probe_snap})
    return {"probe": probe_snap}


@router.post("/jobs/measurement", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def start_measurement_job(req: JobStartRequest, context: AppContext = Depends(get_context)) -> Any:
    session = context.session.snapshot()
    cfg = session.config
    if req.range_mode is not None:
        cfg = context.session.update_config({"range_mode": req.range_mode})

    if session.capture is None:
        raise DomainError("CAPTURE_REQUIRED", "Attach a capture source before starting measurement.")
    if session.roi is None:
        raise DomainError("ROI_REQUIRED", "Select an ROI before starting measurement.")

    context.capture.assert_ready(session.roi)

    context.controller.acquire("measurement")

    def runner(cancel_event, publish):
        try:
            result = context.measurement.run(
                cfg,
                cancel_event,
                publish,
                roi=session.roi,
                noise=session.noise,
            )
            analysis = classify_curve(result.points)
            final_result = SessionResult(
                points=result.points,
                noise=result.noise,
                analysis=analysis,
                schema_version=result.schema_version,
                measured_at=result.measured_at,
                session_id=session.id,
                environment={
                    "window_title": session.capture.title,
                    "capture_backend": session.capture.backend,
                    "requested_fps": session.capture.target_fps,
                    "actual_fps": context.capture.health().fps,
                    "frame_size": [session.capture.width, session.capture.height],
                    "roi": asdict(session.roi),
                },
                config=asdict(cfg),
                warnings=(),
            )
            context.session.set_last_result(final_result)
            if context.audio is not None:
                context.audio.play_sound("complete", cfg.sound_enabled)
            return final_result
        finally:
            context.controller.release("measurement")

    try:
        job = context.jobs.start("measurement", runner)
    except Exception:
        context.controller.release("measurement")
        raise
    context.session.set_active_job(job)
    if context.audio is not None:
        context.audio.play_sound("start", cfg.sound_enabled)
    return job


@router.post("/jobs/idle-noise", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def start_idle_noise_job(context: AppContext = Depends(get_context)) -> Any:
    session = context.session.snapshot()
    cfg = session.config
    if session.capture is None:
        raise DomainError("CAPTURE_REQUIRED", "Attach a capture source before measuring idle noise.")
    if session.roi is None:
        raise DomainError("ROI_REQUIRED", "Select an ROI before measuring idle noise.")

    context.capture.assert_ready(session.roi)

    def runner(cancel_event, publish):
        noise = context.idle_noise.run(cfg, cancel_event, publish, roi=session.roi)
        context.session.set_noise(noise)
        # If session has last result, attach noise
        last_res = context.session.snapshot().last_result
        if last_res is not None:
            updated = SessionResult(
                points=last_res.points,
                noise=noise,
                analysis=last_res.analysis,
                schema_version=last_res.schema_version,
                measured_at=last_res.measured_at,
                session_id=last_res.session_id,
                environment=last_res.environment,
                config=last_res.config,
                warnings=last_res.warnings,
            )
            context.session.set_last_result(updated)
        return noise

    job = context.jobs.start("idle_noise", runner)
    context.session.set_active_job(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def get_job(job_id: str, context: AppContext = Depends(get_context)) -> Any:
    return context.jobs.get(job_id)


@router.delete("/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(verify_origin), Depends(require_token)])
def cancel_job(job_id: str, context: AppContext = Depends(get_context)) -> Any:
    job = context.jobs.cancel(job_id)
    context.session.set_active_job(context.jobs.active_job)
    context.session.set_last_job(context.jobs.last_job)
    if context.audio is not None:
        context.audio.play_sound("stop", context.session.config_snapshot().sound_enabled)
    return job


@router.post("/audio/test", dependencies=[Depends(verify_origin), Depends(require_token)])
def test_audio(req: AudioTestRequest, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    if context.audio is not None:
        context.audio.play_sound(req.sound_type, enabled=True)
    return {"status": "ok", "sound_type": req.sound_type}


@router.get("/result/export", dependencies=[Depends(verify_origin), Depends(require_token)])
def export_result(format: str = Query("json", pattern="^(json|csv)$"), context: AppContext = Depends(get_context)) -> Response:
    res = context.session.snapshot().last_result
    if res is None:
        raise DomainError("NO_RESULT", "No measurement result is available to export.")

    if format == "csv":
        content = context.export.export_csv(res)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="gamecurveprobe_result.csv"'},
        )

    json_bytes = context.export.export_json(res)
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="gamecurveprobe_result.json"'},
    )


@router.get("/result", dependencies=[Depends(verify_origin), Depends(require_token)])
def get_result(context: AppContext = Depends(get_context)) -> SessionResult:
    result = context.session.snapshot().last_result
    if result is None:
        raise DomainError("NO_RESULT", "No measurement result is available.")
    return result


@router.post("/result/import", dependencies=[Depends(verify_origin), Depends(require_token)])
async def import_result(request: Request, context: AppContext = Depends(get_context)) -> dict[str, Any]:
    body = await request.body()
    result = context.export.import_json(body)
    context.events.publish("result_imported", {"result": result})
    return {"result": result}
