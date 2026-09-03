# GameCurveProbe WebUI Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PySide6 desktop client with a safe, local-only FastAPI/WebSocket/Vue application that captures game windows, calibrates noise and deadzone markers, runs cancellable steady-state measurements, analyzes curves, and imports or exports versioned results.

**Architecture:** A FastAPI lifespan owns one `AppContext`, one session, and at most one hardware job. Framework-independent services serialize controller access, own capture backends, run cancellable measurements, and publish typed events; the Vue SPA restores authoritative state through REST and consumes lossy live updates through WebSocket.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, Uvicorn, OpenCV, NumPy, windows-capture/WGC, DXGI, vgamepad, Vue 3, TypeScript, Vite, Pinia, TailwindCSS v4, ECharts, Vitest, Vue Test Utils, Playwright, PyInstaller.

---

## File map

New Python units:

- `src/gamecurveprobe/errors.py`: stable domain error codes and HTTP-independent exceptions.
- `src/gamecurveprobe/models.py`: versioned session, job, capture, configuration, point, and result dataclasses.
- `src/gamecurveprobe/events.py`: typed event envelope and bounded event hub.
- `src/gamecurveprobe/context.py`: `AppContext` composition root and ordered shutdown.
- `src/gamecurveprobe/constants.py`: shared backend thresholds and preset values.
- `src/gamecurveprobe/backends/capture/base.py`: normalized `Frame` and capture protocol.
- `src/gamecurveprobe/backends/capture/wgc_backend.py`: WGC adapter only.
- `src/gamecurveprobe/backends/capture/dxcam_backend.py`: DXGI adapter only.
- `src/gamecurveprobe/services/controller_service.py`: serialized controller ownership and neutralization.
- `src/gamecurveprobe/services/capture_service.py`: backend selection, health checks, latest-frame distribution.
- `src/gamecurveprobe/services/job_manager.py`: single-job executor, state transitions, cancellation.
- `src/gamecurveprobe/services/session_service.py`: authoritative session/config/result snapshots.
- `src/gamecurveprobe/services/deadzone_probe_service.py`: leased X-positive probe.
- `src/gamecurveprobe/services/measurement_runner.py`: cancellable steady measurement.
- `src/gamecurveprobe/services/idle_noise_runner.py`: cancellable noise calibration.
- `src/gamecurveprobe/services/export_service.py`: schema-1 JSON/CSV import and export.
- `src/gamecurveprobe/vision/roi_analyzer.py`: ROI texture/tracking quality.
- `src/gamecurveprobe/vision/curve_classifier.py`: linear, power, and logistic fitting.
- `src/gamecurveprobe/api/schemas.py`: Pydantic request/response DTOs.
- `src/gamecurveprobe/api/auth.py`: token and Origin validation.
- `src/gamecurveprobe/api/routes.py`: REST endpoints.
- `src/gamecurveprobe/api/websocket.py`: JSON events and binary preview framing.
- `src/gamecurveprobe/api/server.py`: FastAPI factory, lifespan, exception mapping, SPA hosting.

New frontend units:

- `frontend/src/api/client.ts`: authenticated REST client.
- `frontend/src/api/events.ts`: WebSocket decoder and reconnect loop.
- `frontend/src/types/api.ts`: backend DTO types.
- `frontend/src/stores/session.ts`: REST-authoritative state and commands.
- `frontend/src/stores/preview.ts`: latest preview frame lifecycle.
- `frontend/src/components/layout/WizardShell.vue`: four-step shell and guards.
- `frontend/src/components/step1-capture/CaptureStep.vue`: window/backend selection and ROI.
- `frontend/src/components/step1-capture/RoiCanvas.vue`: display-to-frame coordinate conversion.
- `frontend/src/components/step2-calibrate/CalibrationStep.vue`: deadzones, probe lease, noise job.
- `frontend/src/components/step3-measure/MeasurementStep.vue`: presets, progress, cancellation.
- `frontend/src/components/step4-dashboard/AnalysisStep.vue`: chart, import/export, TSV.
- `frontend/src/utils/coordinates.ts`: pure ROI coordinate mapping.
- `frontend/src/utils/tsv.ts`: pure TSV generation.

Deleted only after replacement tests pass:

- `src/gamecurveprobe/gui/`
- `src/gamecurveprobe/services/http_server.py`
- `src/gamecurveprobe/services/yaw360_calibration_runner.py`
- `src/gamecurveprobe/services/inner_deadzone_calibration_service.py`
- `src/gamecurveprobe/services/steady_probe_runner.py`
- `src/gamecurveprobe/services/idle_noise_calibration_runner.py`
- `src/gamecurveprobe/backends/capture/dxcam_monitor_backend.py`
- obsolete GUI, IPC, yaw360, and legacy runner tests

## Execution instructions for the next AI

- Execute this plan in a dedicated Git worktree created from the branch/commit containing this plan (the approved design base is `806cb60`); do not work in a dirty user worktree.
- Use `superpowers:subagent-driven-development` for task-by-task execution, or `superpowers:executing-plans` when subagents are unavailable.
- Run commands from the repository root unless a step explicitly uses `npm --prefix frontend` or changes directory.
- Follow tasks in order. Do not delete legacy code before Task 15's replacement-coverage gate passes.
- Treat every “Expected” result as a gate. Investigate unexpected output before continuing; do not weaken tests to accommodate a broken implementation.
- Hardware-marked tests and the Task 17 hardware checklist require real Windows hardware. Report them as unverified when that environment is unavailable; never infer a pass from stub tests.
- Preserve unrelated user changes and commit only the files named by the current task.

## Milestone 1 — Domain core and safe job execution

### Task 1: Freeze dependencies and verify the WGC package

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/backends/capture/test_wgc_dependency.py`

- [ ] **Step 1: Add a dependency import test**

```python
# tests/backends/capture/test_wgc_dependency.py
import importlib.util


def test_windows_capture_dependency_is_importable() -> None:
    assert importlib.util.find_spec("windows_capture") is not None
```

- [ ] **Step 2: Run the test and verify the dependency is absent**

Run: `uv run pytest tests/backends/capture/test_wgc_dependency.py -v`

Expected: FAIL because `windows_capture` is not installed.

- [ ] **Step 3: Add runtime and test dependencies**

Run:

```powershell
uv add fastapi "uvicorn[standard]" pydantic python-multipart windows-capture
uv add --dev httpx pytest-asyncio
```

Expected: `pyproject.toml` and `uv.lock` contain the resolved packages without PySide6 removal yet.

- [ ] **Step 4: Verify Python 3.13 import compatibility**

Run:

```powershell
uv run python -c "import windows_capture; print(windows_capture.__file__)"
uv run pytest tests/backends/capture/test_wgc_dependency.py -v
```

Expected: the import prints a site-packages path and the test passes. If the package cannot import on Python 3.13, stop this plan, record the exact import failure in the design spec, and obtain approval for a replacement WGC library before continuing.

- [ ] **Step 5: Commit the dependency baseline**

```powershell
git add pyproject.toml uv.lock tests/backends/capture/test_wgc_dependency.py
git commit -m "build: add WebUI and WGC dependencies"
```

### Task 2: Replace legacy models with versioned domain models

**Files:**
- Create: `src/gamecurveprobe/constants.py`
- Create: `src/gamecurveprobe/errors.py`
- Modify: `src/gamecurveprobe/models.py`
- Create: `tests/test_models_v2.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/test_models_v2.py
import pytest

from gamecurveprobe.errors import DomainError
from gamecurveprobe.models import JobState, ProbeConfig, RangeMode


def test_standard_preset_has_approved_values() -> None:
    config = ProbeConfig.from_preset("standard")
    assert (config.point_count, config.repeats) == (17, 2)
    assert (config.settle_ms, config.sample_ms) == (300, 700)


def test_full_range_includes_both_deadzone_markers() -> None:
    config = ProbeConfig(inner_deadzone=0.05, outer_deadzone=0.92, point_count=9, range_mode=RangeMode.FULL)
    values = config.point_values()
    assert 0.0 in values and 1.0 in values
    assert 0.05 in values and 0.92 in values


def test_deadzone_order_is_validated() -> None:
    with pytest.raises(DomainError, match="outer_deadzone"):
        ProbeConfig(inner_deadzone=0.8, outer_deadzone=0.8).validate()


def test_job_canceling_is_not_terminal() -> None:
    assert JobState.CANCELING.is_terminal is False
    assert JobState.CANCELED.is_terminal is True
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `uv run pytest tests/test_models_v2.py -v`

Expected: FAIL on missing `ProbeConfig`, `RangeMode`, or `DomainError`.

- [ ] **Step 3: Define constants and stable errors**

```python
# src/gamecurveprobe/constants.py
PRESETS = {
    "quick": {"point_count": 9, "repeats": 1, "settle_ms": 250, "sample_ms": 500},
    "standard": {"point_count": 17, "repeats": 2, "settle_ms": 300, "sample_ms": 700},
    "precision": {"point_count": 33, "repeats": 2, "settle_ms": 500, "sample_ms": 1000},
}
MIN_ROI_SIDE = 32
MIN_TRACKED_POINTS = 8
MIN_TRACKING_CONFIDENCE = 0.35
MIN_VALID_POINTS = 5
MIN_VALID_POINT_RATIO = 0.60


# src/gamecurveprobe/errors.py
class DomainError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JobCanceled(RuntimeError):
    """Internal control-flow exception; never exposed as a 500 response."""
```

- [ ] **Step 4: Implement the new model surface**

Replace the legacy yaw/dynamic model with enums and dataclasses named exactly:

```python
class RangeMode(StrEnum):
    ACTIVE_RANGE = "active_range"
    FULL = "full"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELING = "canceling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in {self.COMPLETED, self.FAILED, self.CANCELED}


@dataclass(slots=True)
class ProbeConfig:
    capture_fps: int = 120
    point_count: int = 17
    repeats: int = 2
    settle_ms: int = 300
    sample_ms: int = 700
    range_mode: RangeMode = RangeMode.ACTIVE_RANGE
    inner_deadzone: float = 0.0
    outer_deadzone: float = 1.0

    @classmethod
    def from_preset(cls, name: str) -> "ProbeConfig":
        try:
            return cls(**PRESETS[name])
        except KeyError as exc:
            raise DomainError("INVALID_PRESET", f"Unknown preset: {name}") from exc

    def validate(self) -> None:
        if not 30 <= self.capture_fps <= 240:
            raise DomainError("INVALID_CONFIG", "capture_fps must be within [30, 240].")
        if self.point_count < 5 or self.repeats < 1 or self.settle_ms < 0 or self.sample_ms <= 0:
            raise DomainError("INVALID_CONFIG", "Measurement timing and count values are invalid.")
        if not 0.0 <= self.inner_deadzone < self.outer_deadzone <= 1.0:
            raise DomainError("INVALID_CONFIG", "outer_deadzone must be greater than inner_deadzone within [0, 1].")

    def point_values(self) -> list[float]:
        start, end = ((0.0, 1.0) if self.range_mode is RangeMode.FULL else (self.inner_deadzone, self.outer_deadzone))
        values = {round(start + (end - start) * i / (self.point_count - 1), 4) for i in range(self.point_count)}
        if self.range_mode is RangeMode.FULL:
            values.update({self.inner_deadzone, self.outer_deadzone})
        return sorted(values)
```

Also define focused dataclasses `RoiRect`, `CaptureInfo`, `CaptureHealth`, `MeasurementPoint`, `NoiseResult`, `RoiQuality`, `CurveAnalysis`, `SessionResult`, `JobSnapshot`, and `SessionSnapshot`; every `SessionResult` must have `schema_version=1`, and no class may contain yaw, degree, dynamic, or Y-axis result fields. Use these exact nullable/result fields:

```python
@dataclass(frozen=True, slots=True)
class MeasurementPoint:
    input: float
    velocity_px_s: float | None
    normalized_speed: float | None
    stability: float
    valid: bool
    attempts: int

@dataclass(frozen=True, slots=True)
class NoiseResult:
    floor_x: float
    floor_y: float
    valid_frames: int
    confidence: float

@dataclass(frozen=True, slots=True)
class RoiQuality:
    score: int
    level: str
    metrics: Mapping[str, float]
    suggestions: tuple[str, ...]
```

- [ ] **Step 5: Run model tests**

Run: `uv run pytest tests/test_models_v2.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit the domain contract**

```powershell
git add src/gamecurveprobe/constants.py src/gamecurveprobe/errors.py src/gamecurveprobe/models.py tests/test_models_v2.py
git commit -m "refactor: define WebUI domain models"
```

### Task 3: Serialize controller access and guarantee neutralization

**Files:**
- Create: `src/gamecurveprobe/services/controller_service.py`
- Modify: `src/gamecurveprobe/backends/controller/base.py`
- Modify: `src/gamecurveprobe/backends/controller/stub.py`
- Create: `tests/services/test_controller_service.py`

- [ ] **Step 1: Write controller safety tests**

```python
# tests/services/test_controller_service.py
import threading

from gamecurveprobe.backends.controller.stub import StubControllerBackend
from gamecurveprobe.services.controller_service import ControllerService


def test_cancel_neutralizes_and_blocks_later_writes() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    cancel = threading.Event()
    service.set_right_stick(0.5, 0.0, cancel)
    cancel.set()
    service.cancel_and_neutralize(cancel)
    assert backend.events[-1] == ("neutral",)
    assert service.set_right_stick(0.8, 0.0, cancel) is False


def test_close_neutralizes_before_disconnect() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    service.connect()
    service.close()
    assert backend.events[-2:] == [("neutral",), ("disconnect",)]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/services/test_controller_service.py -v`

Expected: FAIL because `ControllerService` and the recording stub do not exist.

- [ ] **Step 3: Implement serialized writes**

```python
# src/gamecurveprobe/services/controller_service.py
class ControllerService:
    def __init__(self, backend: VirtualControllerBackend) -> None:
        self._backend = backend
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            if not self._backend.probe():
                raise DomainError("CONTROLLER_UNAVAILABLE", "Install vgamepad and ViGEmBus first.")
            self._backend.connect()

    def set_right_stick(self, x: float, y: float, cancel: threading.Event) -> bool:
        with self._lock:
            if cancel.is_set():
                return False
            self._backend.set_right_stick(x, y)
            return True

    def cancel_and_neutralize(self, cancel: threading.Event) -> None:
        cancel.set()
        self.neutralize()

    def neutralize(self) -> None:
        with self._lock:
            self._backend.neutral()

    def close(self) -> None:
        with self._lock:
            try:
                self._backend.neutral()
            finally:
                self._backend.disconnect()
```

Update `StubControllerBackend` to implement the complete controller protocol and append deterministic tuples to `events`.

- [ ] **Step 4: Run controller tests**

Run: `uv run pytest tests/services/test_controller_service.py tests/backends/controller/test_vgamepad_backend.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit controller safety**

```powershell
git add src/gamecurveprobe/services/controller_service.py src/gamecurveprobe/backends/controller tests/services/test_controller_service.py
git commit -m "feat: serialize controller access and cancellation"
```

### Task 4: Make motion sampling and steady measurement cancellable

**Files:**
- Modify: `src/gamecurveprobe/services/motion_sampler.py`
- Create: `src/gamecurveprobe/services/measurement_runner.py`
- Create: `src/gamecurveprobe/services/idle_noise_runner.py`
- Modify: `tests/services/test_motion_sampler.py`
- Create: `tests/services/test_measurement_runner.py`
- Create: `tests/services/test_idle_noise_runner.py`

- [ ] **Step 1: Add cancellation and invalid-point tests**

```python
def test_sampler_stops_when_cancel_is_set() -> None:
    cancel = threading.Event()
    cancel.set()
    sample = MotionSampler().sample_filtered(FakeCapture(), FakeEstimator(), ROI, 700, cancel_event=cancel)
    assert sample.canceled is True


def test_runner_keeps_invalid_point_without_faking_zero() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    runner = MeasurementRunner(controller, capture, FakeSampler(valid_frames=0), sleep=lambda *_: None)
    result = runner.run(config, threading.Event(), lambda event: None)
    assert result.points[0].valid is False
    assert result.points[0].velocity_px_s is None


def test_runner_neutralizes_when_canceled_during_settle() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    cancel = threading.Event()
    runner = MeasurementRunner(controller, capture, sampler, sleep=lambda _: cancel.set())
    with pytest.raises(JobCanceled):
        runner.run(config, cancel, lambda event: None)
    assert backend.events[-1] == ("neutral",)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tests/services/test_motion_sampler.py tests/services/test_measurement_runner.py tests/services/test_idle_noise_runner.py -v`

Expected: FAIL on the new cancellation contract.

- [ ] **Step 3: Extend the sampler contract**

Add `cancel_event: threading.Event | None = None` to `sample_filtered`, `sample_noise_floor`, and `_collect_estimates`; return `MotionSample(canceled=True)` immediately when set and check it on every loop iteration and every 5ms wait.

```python
if cancel_event is not None and cancel_event.is_set():
    return estimates, duplicate_frames, True
```

Add `canceled: bool = False` to `MotionSample` and adjust callers to unpack the flag.

- [ ] **Step 4: Implement the measurement runner**

`MeasurementRunner.run(config, cancel_event, publish)` must:

```python
try:
    for index, input_value in enumerate(config.point_values(), start=1):
        self._check_cancel(cancel_event)
        self._controller.neutralize()
        self._interruptible_wait(0.10, cancel_event)
        if not self._controller.set_right_stick(input_value, 0.0, cancel_event):
            raise JobCanceled()
        self._interruptible_wait(config.settle_ms / 1000, cancel_event)
        point = self._measure_point(input_value, config, cancel_event)
        points.append(point)
        publish({"current_point": index, "total_points": len(values), "input_value": input_value})
finally:
    self._controller.neutralize()
```

Use repeat medians, one retry for low quality, noise-floor subtraction, `velocity_px_s=None` for invalid points, and the 5-point/60% quality gate. `_interruptible_wait` uses `cancel_event.wait(min(0.02, remaining))`.

- [ ] **Step 5: Implement idle-noise sampling**

`IdleNoiseRunner.run(config, cancel_event, publish)` calls `sample_noise_floor` with the selected capture, estimator, ROI, `sample_ms=1200`, `band_percentile=0.9`, and the cancellation event; it raises `JobCanceled` when canceled and returns both thresholds plus valid-frame and confidence statistics.

```python
sample = self._sampler.sample_noise_floor(
    self._capture, self._estimator, roi, 1200,
    min_tracked_points=MIN_TRACKED_POINTS,
    min_confidence=MIN_TRACKING_CONFIDENCE,
    band_percentile=0.9,
    cancel_event=cancel_event,
)
if sample.canceled:
    raise JobCanceled()
return NoiseResult(sample.px_per_sec_x, sample.px_per_sec_y, sample.valid_frames, sample.average_confidence)
```

- [ ] **Step 6: Run focused and legacy measurement tests**

Run: `uv run pytest tests/services/test_motion_sampler.py tests/services/test_measurement_runner.py tests/services/test_idle_noise_runner.py -v`

Expected: all tests pass. Legacy `test_steady_probe_runner.py` may still pass independently until its replacement is complete.

- [ ] **Step 7: Commit cancellable runners**

```powershell
git add src/gamecurveprobe/services/motion_sampler.py src/gamecurveprobe/services/measurement_runner.py src/gamecurveprobe/services/idle_noise_runner.py tests/services
git commit -m "feat: add cancellable measurement runners"
```

### Task 5: Add the single-job manager and authoritative session

**Files:**
- Create: `src/gamecurveprobe/services/job_manager.py`
- Rewrite: `src/gamecurveprobe/services/session_service.py`
- Create: `tests/services/test_job_manager.py`
- Rewrite: `tests/services/test_session_service.py`

- [ ] **Step 1: Write job state and conflict tests**

```python
def test_job_transitions_to_completed_and_publishes_result() -> None:
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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/services/test_job_manager.py tests/services/test_session_service.py -v`

Expected: FAIL because the WebUI job model is missing.

- [ ] **Step 3: Implement the job manager**

Use a one-worker `ThreadPoolExecutor`, a lock, and one `threading.Event` per job. `start()` snapshots the callable, installs `active_job` before submission, maps `JobCanceled` to `canceled`, maps exceptions to `failed`, and only stores a result after successful completion. `cancel()` validates the ID, changes running jobs to `canceling`, and sets the event. Terminal jobs become `last_job` and clear `active_job`.

```python
JobRunner = Callable[[threading.Event, Callable[[Mapping[str, object]], None]], object]

@dataclass(slots=True)
class JobRecord:
    id: str
    kind: str
    state: JobState
    cancel_event: threading.Event
    future: Future[object] | None = None

    @classmethod
    def create(cls, kind: str) -> "JobRecord":
        return cls(uuid4().hex, kind, JobState.QUEUED, threading.Event())

def start(self, kind: str, runner: JobRunner) -> JobSnapshot:
    with self._lock:
        if self._active_job is not None:
            raise DomainError("RESOURCE_BUSY", "A hardware job is already running.")
        record = JobRecord.create(kind)
        self._active_job = record
        record.future = self._executor.submit(self._run, record, runner)
        return record.snapshot()

def cancel(self, job_id: str) -> JobSnapshot:
    with self._lock:
        record = self._require_job(job_id)
        if not record.snapshot().state.is_terminal:
            record.state = JobState.CANCELING
            record.cancel_event.set()
        return record.snapshot()
```

- [ ] **Step 4: Rewrite session ownership**

`SessionService` creates one stable session ID, owns `ProbeConfig`, capture/ROI summaries, `active_job`, `last_job`, and `last_result`, and exposes immutable snapshot copies. Configuration updates must validate a candidate copy before replacing the current config. Remove CSV writing, yaw calibration, dynamic run, and direct background execution from this service.

```python
@property
def id(self) -> str:
    return self._session_id

def update_config(self, changes: Mapping[str, object]) -> ProbeConfig:
    with self._lock:
        candidate = replace(self._config, **changes)
        candidate.validate()
        self._config = candidate
        return copy.deepcopy(candidate)

def snapshot(self) -> SessionSnapshot:
    with self._lock:
        return copy.deepcopy(self._build_snapshot())
```

- [ ] **Step 5: Run service tests**

Run: `uv run pytest tests/services/test_job_manager.py tests/services/test_session_service.py -v`

Expected: all tests pass, including conflict, cancellation, immutable snapshot, and atomic invalid-config tests.

- [ ] **Step 6: Commit job/session orchestration**

```powershell
git add src/gamecurveprobe/services/job_manager.py src/gamecurveprobe/services/session_service.py tests/services/test_job_manager.py tests/services/test_session_service.py
git commit -m "feat: add single-job session orchestration"
```

## Milestone 2 — Capture, vision, analysis, and transport

### Task 6: Normalize capture backends and health evaluation

**Files:**
- Rewrite: `src/gamecurveprobe/backends/capture/base.py`
- Create: `src/gamecurveprobe/backends/capture/wgc_backend.py`
- Rewrite: `src/gamecurveprobe/backends/capture/dxcam_backend.py`
- Rewrite: `src/gamecurveprobe/backends/capture/stub.py`
- Create: `src/gamecurveprobe/services/capture_service.py`
- Create: `tests/backends/capture/test_wgc_backend.py`
- Rewrite: `tests/backends/capture/test_dxcam_backend.py`
- Create: `tests/services/test_capture_service.py`

- [ ] **Step 1: Write contract and fallback tests**

```python
def test_all_backends_return_normalized_bgr_frames(capture_backend) -> None:
    info = capture_backend.attach(42, 120)
    frame = capture_backend.read(100)
    assert frame.image.dtype == np.uint8
    assert frame.image.shape[2] == 3
    assert frame.frame_id >= 1
    assert info.width == frame.image.shape[1]


def test_auto_falls_back_when_wgc_stalls() -> None:
    service = CaptureService({"wgc": StalledBackend(), "dxcam": HealthyBackend()})
    info = service.attach(42, "auto", 120)
    assert info.backend == "dxcam"


def test_forced_wgc_does_not_fallback() -> None:
    service = CaptureService({"wgc": StalledBackend(), "dxcam": HealthyBackend()})
    with pytest.raises(DomainError) as exc:
        service.attach(42, "wgc", 120)
    assert exc.value.code == "CAPTURE_STALLED"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/backends/capture tests/services/test_capture_service.py -v`

Expected: FAIL because current backends use incompatible `grab_frame` contracts.

- [ ] **Step 3: Define the normalized capture protocol**

```python
@dataclass(frozen=True, slots=True)
class Frame:
    image: np.ndarray
    monotonic_ns: int
    frame_id: int
    is_duplicate: bool = False


class CaptureBackend(Protocol):
    name: str
    def attach(self, window_id: int, target_fps: int) -> CaptureInfo: raise NotImplementedError
    def read(self, timeout_ms: int) -> Frame | None: raise NotImplementedError
    def health(self) -> CaptureHealth: raise NotImplementedError
    def close(self) -> None: raise NotImplementedError
```

- [ ] **Step 4: Adapt WGC and DXGI**

Keep library-specific callbacks, pixel conversion, and shutdown entirely inside each adapter. Convert BGRA/RGBA to contiguous BGR, assign monotonic timestamps and frame IDs, make `close()` idempotent, and surface minimized/window-gone/device-loss conditions as `DomainError` codes. Preserve `WindowService` for enumeration and geometry validation.

```python
def _to_bgr(pixels: np.ndarray) -> np.ndarray:
    if pixels.ndim != 3 or pixels.shape[2] not in {3, 4}:
        raise DomainError("CAPTURE_FORMAT_INVALID", "Capture frame format is unsupported.")
    image = pixels[:, :, :3] if pixels.shape[2] == 4 else pixels
    return np.ascontiguousarray(image, dtype=np.uint8)
```

- [ ] **Step 5: Implement capture health and distribution**

`CaptureService.attach()` collects a 2-second/10-frame startup sample, rejects ≥80% duplicates, detects 10 consecutive frames with mean and standard deviation ≤1, and implements exactly one WGC→DXGI fallback in `auto`. Maintain one latest-frame slot guarded by a condition variable; consumers read copies/references without owning backend shutdown.

```python
def attach(self, window_id: int, requested: str, fps: int) -> CaptureInfo:
    candidates = ("wgc", "dxcam") if requested == "auto" else (requested,)
    failures: list[DomainError] = []
    for name in candidates:
        try:
            return self._attach_and_validate(name, window_id, fps)
        except DomainError as exc:
            failures.append(exc)
            self._backends[name].close()
    raise failures[-1]
```

- [ ] **Step 6: Run capture tests**

Run: `uv run pytest tests/backends/capture tests/services/test_capture_service.py tests/services/test_window_service.py -v`

Expected: all tests pass with stub frames; hardware-specific tests are marked `@pytest.mark.hardware` and are not part of the default run.

- [ ] **Step 7: Commit capture services**

```powershell
git add src/gamecurveprobe/backends/capture src/gamecurveprobe/services/capture_service.py tests/backends/capture tests/services/test_capture_service.py
git commit -m "feat: add WGC capture with DXGI fallback"
```

### Task 7: Add ROI scoring, curve classification, and versioned export

**Files:**
- Create: `src/gamecurveprobe/vision/roi_analyzer.py`
- Create: `src/gamecurveprobe/vision/curve_classifier.py`
- Create: `src/gamecurveprobe/services/export_service.py`
- Create: `tests/vision/test_roi_analyzer.py`
- Create: `tests/vision/test_curve_classifier.py`
- Create: `tests/services/test_export_service.py`

- [ ] **Step 1: Write deterministic algorithm tests**

```python
def test_flat_roi_is_poor() -> None:
    result = RoiAnalyzer().analyze(np.zeros((64, 64, 3), dtype=np.uint8))
    assert result.level == "poor"
    assert result.score < 25


def test_linear_points_classify_as_linear() -> None:
    points = [valid_point(x, x) for x in np.linspace(0, 1, 9)]
    assert classify_curve(points).curve_type == "linear"


def test_ambiguous_fit_is_undetermined() -> None:
    points = [valid_point(0.0, 0.0), valid_point(0.25, 0.9), valid_point(0.5, 0.1), valid_point(0.75, 0.8), valid_point(1.0, 0.2)]
    assert classify_curve(points).curve_type == "undetermined"


def test_schema_one_round_trip_and_csv_header() -> None:
    service = ExportService()
    restored = service.import_json(service.export_json(RESULT))
    assert restored == RESULT
    assert service.export_csv(RESULT).splitlines()[0] == "Input,Velocity_px_s,Normalized_Ratio,Stability,Valid,Attempts"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/vision/test_roi_analyzer.py tests/vision/test_curve_classifier.py tests/services/test_export_service.py -v`

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement ROI analysis**

Validate 32×32 minimum size. Compute normalized Sobel magnitude, `goodFeaturesToTrack` count, edge-angle histogram entropy, and short tracking statistics. Combine normalized metrics into a 0–100 score and map `<25`, `<50`, `<75`, and `≥75` to `poor`, `fair`, `good`, and `excellent`. Return raw metric values and stable suggestion codes.

```python
score = round(100 * (0.35 * gradient + 0.25 * corners + 0.20 * entropy + 0.20 * tracking))
level = "poor" if score < 25 else "fair" if score < 50 else "good" if score < 75 else "excellent"
return RoiQuality(score=score, level=level, metrics=metrics, suggestions=suggestions)
```

- [ ] **Step 4: Implement classification**

Fit normalized valid points to linear `a*x+b`, power `a*x**p+b`, and monotonic logistic candidates. Use NumPy least squares plus bounded deterministic grids for power/logistic parameters; do not add SciPy. Calculate NRMSE; accept the best only when NRMSE ≤0.12 and at least 0.02 below second place. Return `confidence=max(0,min(1,1-nrmse))`; catch numerical failures and return `undetermined`.

```python
ranked = sorted((_fit_linear(x, y), _fit_power_grid(x, y), _fit_logistic_grid(x, y)), key=lambda fit: fit.nrmse)
best, second = ranked[:2]
if best.nrmse > 0.12 or second.nrmse - best.nrmse < 0.02:
    return CurveAnalysis("undetermined", 0.0, {})
return CurveAnalysis(best.kind, max(0.0, min(1.0, 1.0 - best.nrmse)), best.metrics)
```

- [ ] **Step 5: Implement import/export**

Use a Pydantic schema to validate `schema_version == 1`, field ranges, `valid=false`/null velocity consistency, and a 5 MiB input limit before JSON decoding. Emit UTF-8 JSON with stable field names and RFC 4180 CSV using `io.StringIO(newline="")`. Raise `UNSUPPORTED_SCHEMA_VERSION` for non-1 versions.

```python
def import_json(self, payload: bytes) -> SessionResult:
    if len(payload) > 5 * 1024 * 1024:
        raise DomainError("IMPORT_TOO_LARGE", "Result JSON exceeds 5 MiB.")
    raw = json.loads(payload)
    if raw.get("schema_version") != 1:
        raise DomainError("UNSUPPORTED_SCHEMA_VERSION", "Only schema version 1 is supported.")
    return result_from_dto(ResultDocument.model_validate(raw))
```

- [ ] **Step 6: Run algorithm/export tests**

Run: `uv run pytest tests/vision/test_roi_analyzer.py tests/vision/test_curve_classifier.py tests/services/test_export_service.py -v`

Expected: all tests pass without hardware.

- [ ] **Step 7: Commit analysis and serialization**

```powershell
git add src/gamecurveprobe/vision src/gamecurveprobe/services/export_service.py tests/vision tests/services/test_export_service.py
git commit -m "feat: add ROI analysis and result serialization"
```

### Task 8: Add the deadzone probe lease and bounded event hub

**Files:**
- Create: `src/gamecurveprobe/events.py`
- Create: `src/gamecurveprobe/services/deadzone_probe_service.py`
- Create: `tests/test_events.py`
- Create: `tests/services/test_deadzone_probe_service.py`

- [ ] **Step 1: Write lease and queue tests**

```python
def test_expired_probe_is_neutralized() -> None:
    backend = StubControllerBackend()
    controller = ControllerService(backend)
    clock = FakeClock()
    service = DeadzoneProbeService(controller, clock=clock, lease_seconds=2.0)
    service.start(0.05, 0.005)
    clock.advance(2.01)
    service.expire_if_needed()
    assert backend.events[-1] == ("neutral",)


def test_preview_queue_keeps_only_latest_frame() -> None:
    subscriber = EventHub().subscribe()
    subscriber.publish_preview(frame(1))
    subscriber.publish_preview(frame(2))
    assert subscriber.next_preview().frame_id == 2
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_events.py tests/services/test_deadzone_probe_service.py -v`

Expected: FAIL because neither unit exists.

- [ ] **Step 3: Implement event queues**

Create immutable `EventEnvelope(seq, type, timestamp, payload, job_id=None)` and `PreviewFrame(seq, frame_id, monotonic_ns, width, height, jpeg)`. `EventHub` maintains a global session sequence and per-subscriber bounded JSON queue plus one latest-preview slot. When a JSON queue is full, discard the oldest non-terminal progress event; never block producers. REST remains the recovery source if any event is lost.

```python
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
```

- [ ] **Step 4: Implement the leased probe**

Support only `x_positive`, output `[0,1]`, and steps `{0.001, 0.005, 0.01}`. `start()` acquires the controller resource, `update(output)` applies an absolute value and renews the 2-second deadline, `stop()` neutralizes and releases, and `expire_if_needed()` does the same after expiry. A daemon watchdog checks every 100ms and is stopped by `close()`.

```python
def update(self, output: float) -> ProbeSnapshot:
    with self._lock:
        self._require_active()
        if not 0.0 <= output <= 1.0:
            raise DomainError("INVALID_PROBE_OUTPUT", "Probe output must be within [0, 1].")
        self._controller.set_right_stick(output, 0.0, self._cancel)
        self._output = output
        self._deadline = self._clock() + self._lease_seconds
        return self.snapshot()
```

- [ ] **Step 5: Run event/probe tests**

Run: `uv run pytest tests/test_events.py tests/services/test_deadzone_probe_service.py -v`

Expected: all tests pass, including update renewal, invalid direction, conflict, expiry, idempotent stop, and close.

- [ ] **Step 6: Commit live-event and probe services**

```powershell
git add src/gamecurveprobe/events.py src/gamecurveprobe/services/deadzone_probe_service.py tests/test_events.py tests/services/test_deadzone_probe_service.py
git commit -m "feat: add leased deadzone probing and events"
```

### Task 9: Build the authenticated FastAPI REST application

**Files:**
- Create: `src/gamecurveprobe/api/__init__.py`
- Create: `src/gamecurveprobe/api/schemas.py`
- Create: `src/gamecurveprobe/api/auth.py`
- Create: `src/gamecurveprobe/api/routes.py`
- Create: `src/gamecurveprobe/api/server.py`
- Create: `src/gamecurveprobe/context.py`
- Create: `tests/api/conftest.py`
- Create: `tests/api/test_auth.py`
- Create: `tests/api/test_routes.py`
- Create: `tests/api/test_lifespan.py`

- [ ] **Step 1: Write authentication and route-contract tests**

```python
def test_session_requires_bearer_token(client) -> None:
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/session", headers=AUTH).status_code == 200


def test_measurement_returns_202_job_snapshot(client) -> None:
    response = client.post("/api/jobs/measurement", headers=AUTH, json={})
    assert response.status_code == 202
    assert response.json()["state"] in {"queued", "running"}


def test_export_is_download_not_path_write(client) -> None:
    response = client.get("/api/result/export?format=csv", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `uv run pytest tests/api/test_auth.py tests/api/test_routes.py tests/api/test_lifespan.py -v`

Expected: FAIL because `create_app` is missing.

- [ ] **Step 3: Define Pydantic DTOs**

Define strict models with `extra="forbid"`: `CaptureAttachRequest`, `RoiRequest`, `ConfigUpdateRequest`, `DeadzoneRequest`, `ProbeStartRequest`, `ProbeUpdateRequest`, `WindowResponse`, `JobResponse`, `SessionResponse`, `ResultResponse`, and `ErrorResponse`. Apply the exact numeric and enum constraints from the design spec.

```python
class StrictDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

class CaptureAttachRequest(StrictDto):
    window_id: int
    backend: Literal["auto", "wgc", "dxcam"] = "auto"
    target_fps: int = Field(default=120, ge=30, le=240)

class RoiRequest(StrictDto):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=MIN_ROI_SIDE)
    height: int = Field(ge=MIN_ROI_SIDE)
```

- [ ] **Step 4: Implement token and Origin checks**

Generate `secrets.token_urlsafe(32)`. REST accepts only an exact `Authorization: Bearer <token>`. WebSocket accepts the token query parameter. In production allow only the actual `http://127.0.0.1:<port>` or `http://localhost:<port>` origin; tests inject their exact origin. `/api/health` and static files remain unauthenticated.

```python
def require_token(request: Request) -> None:
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not secrets.compare_digest(supplied, request.app.state.context.token):
        raise HTTPException(status_code=401, detail="Unauthorized")

def require_origin(origin: str | None, allowed: frozenset[str]) -> None:
    if origin not in allowed:
        raise DomainError("ORIGIN_FORBIDDEN", "Request origin is not allowed.")
```

- [ ] **Step 5: Implement routes and exception mapping**

Keep handlers thin: validate DTO, call one service method, convert snapshot to DTO. Map `DomainError` codes to the approved 400/404/409/503 statuses and return the stable error envelope. Return `202` for job start/cancel; use `StreamingResponse`/`Response` for exports; reject import before reading beyond 5 MiB.

```python
@router.post("/jobs/measurement", response_model=JobResponse, status_code=202)
def start_measurement(request: Request, _: None = Depends(require_token)) -> JobResponse:
    context = request.app.state.context
    config = context.session.config_snapshot()
    job = context.jobs.start("measurement", lambda cancel, publish: context.measurement.run(config, cancel, publish))
    return JobResponse.model_validate(job, from_attributes=True)
```

- [ ] **Step 6: Implement lifespan cleanup**

Define the composition root explicitly:

```python
@dataclass(slots=True)
class AppContext:
    token: str
    windows: WindowService
    session: SessionService
    jobs: JobManager
    capture: CaptureService
    controller: ControllerService
    probe: DeadzoneProbeService
    measurement: MeasurementRunner
    idle_noise: IdleNoiseRunner
    export: ExportService
    events: EventHub

    def close(self) -> None:
        self.jobs.cancel_active()
        self.jobs.wait(timeout=3.0)
        for cleanup in (self.probe.close, self.controller.close, self.capture.close, self.jobs.close, self.events.close):
            self._run_bounded(cleanup, timeout=0.5)

    @staticmethod
    def _run_bounded(cleanup: Callable[[], None], timeout: float) -> None:
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logging.critical("Shutdown cleanup timed out: %r", cleanup)
```

`create_app(context_factory, static_dir)` installs a lifespan that creates this `AppContext`, stores it on `app.state`, and calls `context.close()` on shutdown. Mount built assets when `static_dir/index.html` exists; route unknown non-API GET paths to that file, but never convert missing `/api/*` routes into HTML. The blocking-backend test must prove shutdown returns and records the fatal cleanup error.

- [ ] **Step 7: Run API tests**

Run: `uv run pytest tests/api -v`

Expected: all tests pass, covering every tabled endpoint, 401, 403 Origin, 404, 409, 422, 503, import size/version, atomic config, and cleanup.

- [ ] **Step 8: Commit REST application**

```powershell
git add src/gamecurveprobe/api tests/api
git commit -m "feat: add authenticated FastAPI REST API"
```

### Task 10: Add WebSocket events, binary preview, and reconnect semantics

**Files:**
- Create: `src/gamecurveprobe/api/websocket.py`
- Modify: `src/gamecurveprobe/api/server.py`
- Create: `tests/api/test_websocket.py`

- [ ] **Step 1: Write WebSocket framing tests**

```python
def test_binary_preview_has_gcpf_envelope(client, token, context) -> None:
    context.events.publish_preview(preview_fixture(frame_id=1))
    with client.websocket_connect(f"/ws/events?session_id={context.session.id}&token={token}", headers={"origin": ORIGIN}) as ws:
        payload = ws.receive_bytes()
    assert payload[:4] == b"GCPF"
    version = payload[4]
    header_length = int.from_bytes(payload[5:7], "big")
    header = json.loads(payload[7:7 + header_length])
    assert version == 1
    assert header["jpeg_length"] == len(payload) - 7 - header_length


def test_disconnect_does_not_cancel_active_job(client, token, context) -> None:
    with client.websocket_connect(f"/ws/events?session_id={context.session.id}&token={token}", headers={"origin": ORIGIN}):
        pass
    assert context.jobs.active_job.state is JobState.RUNNING
```

- [ ] **Step 2: Run the WebSocket tests and verify failure**

Run: `uv run pytest tests/api/test_websocket.py -v`

Expected: FAIL because the route and framing function are missing.

- [ ] **Step 3: Implement the binary encoder**

```python
def encode_preview(frame: PreviewFrame) -> bytes:
    header = json.dumps({
        "seq": frame.seq,
        "frame_id": frame.frame_id,
        "monotonic_ns": frame.monotonic_ns,
        "width": frame.width,
        "height": frame.height,
        "jpeg_length": len(frame.jpeg),
    }, separators=(",", ":")).encode("utf-8")
    return b"GCPF" + bytes([1]) + len(header).to_bytes(2, "big") + header + frame.jpeg
```

- [ ] **Step 4: Implement the WebSocket loop**

Validate session, token, and Origin before accepting. Subscribe to `EventHub`; concurrently forward JSON and latest preview without allowing either to block producers. Cancel only connection-local sender tasks on disconnect, unsubscribe in `finally`, and never cancel a measurement because the socket closed.

```python
@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket, session_id: str, token: str) -> None:
    context = websocket.app.state.context
    validate_websocket(websocket, context, session_id, token)
    await websocket.accept()
    subscriber = context.events.subscribe()
    try:
        await forward_events(websocket, subscriber)
    except WebSocketDisconnect:
        pass
    finally:
        context.events.unsubscribe(subscriber)
```

- [ ] **Step 5: Run all API tests**

Run: `uv run pytest tests/api -v`

Expected: all API and WebSocket tests pass, including bad token, bad Origin, sequence monotonicity, latest-frame replacement, and disconnect behavior.

- [ ] **Step 6: Commit WebSocket transport**

```powershell
git add src/gamecurveprobe/api/websocket.py src/gamecurveprobe/api/server.py tests/api/test_websocket.py
git commit -m "feat: stream bounded WebSocket events"
```

## Milestone 3 — Vue WebUI vertical workflow

### Task 11: Scaffold Vue, API types, authentication, and stores

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/assets/main.css`
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/events.ts`
- Create: `frontend/src/stores/session.ts`
- Create: `frontend/src/stores/preview.ts`
- Create: `frontend/src/stores/session.test.ts`

- [ ] **Step 1: Create the package manifest**

Use scripts `dev`, `build`, `typecheck`, `test`, and `test:run`. Add Vue, Pinia, ECharts, Lucide Vue, Vite, TypeScript, TailwindCSS v4, `@tailwindcss/vite`, Vitest, jsdom, Vue Test Utils, and Playwright. Set Vite output to `../src/gamecurveprobe/web` with `emptyOutDir: true` and proxy `/api` and `/ws` to the development backend.

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "typecheck": "vue-tsc --noEmit",
    "test": "vitest",
    "test:run": "vitest run",
    "e2e": "playwright test"
  }
}
```

```ts
// vite.config.ts
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  build: {outDir: '../src/gamecurveprobe/web', emptyOutDir: true},
  server: {proxy: {'/api': 'http://127.0.0.1:48231', '/ws': {target: 'ws://127.0.0.1:48231', ws: true}}},
})
```

- [ ] **Step 2: Write a failing store restoration test**

```ts
it('restores REST state before opening events', async () => {
  const order: string[] = []
  const store = useSessionStore()
  await store.initialize({
    getSession: async () => { order.push('rest'); return sessionFixture },
    connectEvents: () => { order.push('ws') },
  })
  expect(order).toEqual(['rest', 'ws'])
  expect(store.session?.id).toBe(sessionFixture.id)
})
```

- [ ] **Step 3: Install packages and verify the test fails**

Run:

```powershell
Set-Location frontend
npm install
npm run test:run -- src/stores/session.test.ts
```

Expected: FAIL because the store is missing.

- [ ] **Step 4: Implement token bootstrap and REST client**

Read token from `location.hash` using `URLSearchParams`, immediately call `history.replaceState` to remove it, retain it only in module memory, and add `Authorization: Bearer` to REST requests. Decode the stable error envelope into a typed `ApiError`.

```ts
let token = new URLSearchParams(location.hash.slice(1)).get('token') ?? ''
history.replaceState(null, '', `${location.pathname}${location.search}`)

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {...init, headers: {...init.headers, Authorization: `Bearer ${token}`}})
  const body = await response.json()
  if (!response.ok) throw new ApiError(body.error.code, body.error.message, body.error.details)
  return body as T
}
```

- [ ] **Step 5: Implement WebSocket decoding and stores**

Define DTOs matching `schemas.py`. Decode JSON envelopes and `GCPF` binary frames, validate JPEG length, replace the prior Blob URL and revoke it. `session.initialize()` must fetch `/api/session` before connecting; reconnect uses capped exponential delays of 250ms, 500ms, 1s, 2s, then 5s.

```ts
async function initialize(): Promise<void> {
  session.value = await api.getSession()
  eventConnection.value = connectEvents(session.value.id, handleEvent)
}

function replacePreview(jpeg: Blob): void {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(jpeg)
}
```

- [ ] **Step 6: Run frontend baseline checks**

Run:

```powershell
Set-Location frontend
npm run typecheck
npm run test:run
npm run build
```

Expected: typecheck and tests pass; build creates `src/gamecurveprobe/web/index.html`.

- [ ] **Step 7: Commit frontend foundation**

```powershell
git add frontend src/gamecurveprobe/web
git commit -m "feat: scaffold Vue WebUI state layer"
```

### Task 12: Build capture/ROI and calibration steps

**Files:**
- Create: `frontend/src/components/layout/WizardShell.vue`
- Create: `frontend/src/components/step1-capture/CaptureStep.vue`
- Create: `frontend/src/components/step1-capture/RoiCanvas.vue`
- Create: `frontend/src/components/step2-calibrate/CalibrationStep.vue`
- Create: `frontend/src/utils/coordinates.ts`
- Create: `frontend/src/utils/coordinates.test.ts`
- Create: `frontend/src/components/step2-calibrate/CalibrationStep.test.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Write coordinate and lease-cleanup tests**

```ts
it('maps a displayed drag to frame pixels', () => {
  expect(toFrameRoi({x: 50, y: 25, width: 100, height: 50}, {width: 400, height: 200}, {width: 1600, height: 800}))
    .toEqual({x: 200, y: 100, width: 400, height: 200})
})

it('stops probing before unmount', async () => {
  const wrapper = mount(CalibrationStep, {global: {plugins: [pinia]}})
  await wrapper.get('[data-test="probe-start"]').trigger('click')
  wrapper.unmount()
  expect(api.stopProbe).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm --prefix frontend run test:run -- src/utils/coordinates.test.ts src/components/step2-calibrate/CalibrationStep.test.ts`

Expected: FAIL on missing components/functions.

- [ ] **Step 3: Implement the wizard and capture step**

Implement four visible steps with guards derived from backend session state. Capture step loads windows, selects `auto/wgc/dxcam`, attaches, renders latest preview, shows actual backend/FPS/health, and refreshes vanished windows. `RoiCanvas` uses `ResizeObserver`, pointer capture, clamping, and `toFrameRoi`; show score, level, and localized suggestion from the API response.

```ts
const canEnter = computed(() => ({
  capture: true,
  calibration: Boolean(store.session?.capture.attached && store.session.roi),
  measurement: Boolean(store.session?.capture.attached && store.session.roi && !store.probe.active),
  analysis: Boolean(store.session?.last_result),
}))
```

```vue
<RoiCanvas :src="preview.url" :frame-size="session.capture.frame_size" @commit="store.updateRoi" />
<p :data-level="session.roi_quality.level">{{ roiQualityMessage }}</p>
```

- [ ] **Step 4: Implement calibration controls**

Use linked range inputs and numeric inputs with `0 ≤ inner < outer ≤ 1`. Probe start sends X-positive and the selected step; output updates are absolute. While active, renew every 500ms by resending current output, and call `DELETE` on stop, route change, and unmount. Display lease expiry and an explicit neutralized state. Start idle-noise as a job and render progress/results from the store.

```ts
let renewTimer: number | undefined
async function startProbe() {
  await store.startProbe({direction: 'x_positive', initial_output: output.value, step: step.value})
  renewTimer = window.setInterval(() => store.updateProbe({output: output.value}), 500)
}
async function stopProbe() {
  if (renewTimer) clearInterval(renewTimer)
  renewTimer = undefined
  await store.stopProbe()
}
onBeforeUnmount(() => { void stopProbe() })
```

- [ ] **Step 5: Run component tests and typecheck**

Run:

```powershell
npm --prefix frontend run test:run -- src/utils/coordinates.test.ts src/components/step2-calibrate/CalibrationStep.test.ts
npm --prefix frontend run typecheck
```

Expected: all pass, including clamping, resize, invalid deadzone, renewal, unmount cleanup, and low-quality ROI warnings.

- [ ] **Step 6: Commit the first two steps**

```powershell
git add frontend/src
git commit -m "feat: add capture and calibration wizard steps"
```

### Task 13: Build measurement progress and analysis/export steps

**Files:**
- Create: `frontend/src/components/step3-measure/MeasurementStep.vue`
- Create: `frontend/src/components/step3-measure/MeasurementStep.test.ts`
- Create: `frontend/src/components/step4-dashboard/AnalysisStep.vue`
- Create: `frontend/src/components/step4-dashboard/AnalysisStep.test.ts`
- Create: `frontend/src/utils/tsv.ts`
- Create: `frontend/src/utils/tsv.test.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Write progress, cancellation, and TSV tests**

```ts
it('locks configuration while a job runs and permits cancel', async () => {
  const wrapper = mountMeasurement({job: {id: 'j1', state: 'running'}})
  expect(wrapper.get('[data-test="preset"]').attributes('disabled')).toBeDefined()
  expect(wrapper.get('[data-test="cancel"]').attributes('disabled')).toBeUndefined()
})

it('writes the approved TSV columns', () => {
  expect(toTsv(resultFixture).split('\n')[0]).toBe('Input\tVelocity_px_s\tNormalized_Ratio\tStability\tValid\tAttempts')
})

it('keeps one imported overlay without replacing measured data', async () => {
  const wrapper = mountAnalysis({measured: resultFixture})
  await importFixture(wrapper, importedFixture)
  expect(wrapper.vm.measured).toEqual(resultFixture)
  expect(wrapper.vm.imported).toEqual(importedFixture)
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm --prefix frontend run test:run -- src/components/step3-measure/MeasurementStep.test.ts src/components/step4-dashboard/AnalysisStep.test.ts src/utils/tsv.test.ts`

Expected: FAIL on missing components/functions.

- [ ] **Step 3: Implement measurement UI**

Render quick/standard/precision presets, range mode, advanced timing, and server-calculated duration. Any manual change displays “custom”. Start via `POST /api/jobs/measurement`; while queued/running/canceling, disable window/config controls. Cancel via job-specific `DELETE`; keep showing `canceling` until the terminal event or REST snapshot arrives.

```ts
const jobBusy = computed(() => ['queued', 'running', 'canceling'].includes(store.job?.state ?? ''))
const cancel = () => store.job ? store.cancelJob(store.job.id) : Promise.resolve()
```

```vue
<select data-test="preset" :disabled="jobBusy" v-model="preset" />
<button data-test="cancel" :disabled="!jobBusy" @click="cancel">Cancel</button>
```

- [ ] **Step 4: Implement analysis and export UI**

Build an ECharts option with solid valid points, hollow invalid points, inner/outer mark lines, normalized/px-s toggle, and measured/imported series. Render classification only with confidence. Export through authenticated Blob downloads, validate and import one JSON through the backend, and copy TSV through `navigator.clipboard.writeText` with fallback error guidance.

```ts
const series = computed(() => [
  toSeries('Measured', measured.value),
  ...(imported.value ? [toSeries('Imported', imported.value)] : []),
])
const chartOption = computed(() => ({
  xAxis: {name: 'Input', min: 0, max: 1},
  yAxis: {name: normalized.value ? 'Normalized' : 'px/s'},
  series: series.value,
}))
```

- [ ] **Step 5: Run all frontend tests and build**

Run:

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run test:run
npm --prefix frontend run build
```

Expected: all tests pass and production assets build without warnings treated as errors.

- [ ] **Step 6: Commit the complete wizard**

```powershell
git add frontend src/gamecurveprobe/web
git commit -m "feat: complete measurement and analysis WebUI"
```

### Task 14: Add the stub-backed browser E2E workflow

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/workflow.spec.ts`
- Modify: `frontend/package.json`
- Modify: `src/gamecurveprobe/app.py`
- Create: `tests/test_app_v2.py`

- [ ] **Step 1: Write CLI and E2E tests**

```python
def test_parser_defaults_to_loopback_and_supports_stub_mode() -> None:
    args = build_parser().parse_args(["--stub", "--no-browser"])
    assert args.host == "127.0.0.1"
    assert args.stub is True
    assert args.no_browser is True
```

```ts
test('completes capture through export', async ({page}) => {
  await page.goto('/#token=test-token')
  await page.getByRole('button', {name: 'Attach'}).click()
  await page.getByTestId('roi-canvas').dragTo(page.getByTestId('roi-target'))
  await page.getByRole('button', {name: 'Sample noise'}).click()
  await page.getByRole('button', {name: 'Start measurement'}).click()
  await expect(page.getByText('Measurement complete')).toBeVisible()
  await expect(page.getByTestId('curve-chart')).toBeVisible()
})
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/test_app_v2.py -v
npm --prefix frontend run e2e
```

Expected: FAIL because stub mode and Playwright configuration are missing.

- [ ] **Step 3: Implement the new application entry point**

`app.py` parses `--host` restricted to loopback, `--port` with `0` allowed, `--no-browser`, `--stub`, and logging level. Build real or deterministic stub `AppContext`, reserve/start the actual port, then open `http://127.0.0.1:<port>/#token=<token>` only after readiness. Remove all PySide imports and old IPC startup from the new path.

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameCurveProbe WebUI")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost", "::1"))
    parser.add_argument("--port", type=int, default=48231)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--stub", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--test-token", help=argparse.SUPPRESS)
    parser.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    return parser
```

Reject `--test-token` unless `--stub` is also present; production mode always uses `secrets.token_urlsafe(32)`.

- [ ] **Step 4: Configure Playwright**

Add an `e2e` script, Chromium project, automatic Vite/backend web servers in stub mode, retained traces on failure, and the exact test token supplied through test-only configuration. Expand the workflow to assert ROI score, probe start/stop, noise threshold, progress, result chart, CSV download, JSON download, JSON import overlay, and page refresh state recovery.

```ts
export default defineConfig({
  testDir: './e2e',
  use: {baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure'},
  projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}],
  webServer: [
    {command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173', port: 4173},
    {command: 'uv run gamecurveprobe --stub --test-token test-token --no-browser --port 48231', port: 48231},
  ],
})
```

- [ ] **Step 5: Run CLI and E2E tests**

Run:

```powershell
uv run pytest tests/test_app_v2.py -v
npm --prefix frontend run e2e
```

Expected: all tests pass in stub mode without capture hardware or ViGEmBus.

- [ ] **Step 6: Commit the vertical workflow**

```powershell
git add src/gamecurveprobe/app.py tests/test_app_v2.py frontend
git commit -m "test: cover the WebUI workflow end to end"
```

## Milestone 4 — Remove the old client, package, and release

### Task 15: Remove legacy GUI, IPC, yaw, and dynamic code

**Files:**
- Delete: `src/gamecurveprobe/gui/`
- Delete: `src/gamecurveprobe/services/http_server.py`
- Delete: `src/gamecurveprobe/services/yaw360_calibration_runner.py`
- Delete: `src/gamecurveprobe/services/inner_deadzone_calibration_service.py`
- Delete: `src/gamecurveprobe/services/steady_probe_runner.py`
- Delete: `src/gamecurveprobe/services/idle_noise_calibration_runner.py`
- Delete: `src/gamecurveprobe/backends/capture/dxcam_monitor_backend.py`
- Delete: `tests/gui/`
- Delete: `tests/services/test_http_server.py`
- Delete: `tests/services/test_yaw360_calibration_runner.py`
- Delete: `tests/services/test_inner_deadzone_calibration_service.py`
- Delete: `tests/services/test_steady_probe_runner.py`
- Delete: `tests/backends/capture/test_dxcam_monitor_backend.py`
- Delete: `tests/test_app.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/gamecurveprobe/services/__init__.py`
- Modify: `src/gamecurveprobe/__main__.py`

- [ ] **Step 1: Prove replacement coverage passes before deletion**

Run:

```powershell
uv run pytest tests/test_models_v2.py tests/services/test_controller_service.py tests/services/test_measurement_runner.py tests/services/test_idle_noise_runner.py tests/services/test_job_manager.py tests/api -v
npm --prefix frontend run test:run
npm --prefix frontend run e2e
```

Expected: all replacement tests pass.

- [ ] **Step 2: Delete the superseded files**

Delete only the paths listed in this task. Remove PySide6 from `pyproject.toml`, remove `--ipc-only`, and regenerate the lock:

Run: `uv lock`

Expected: lock succeeds and no PySide6 package remains.

- [ ] **Step 3: Scan for forbidden remnants**

Run:

```powershell
rg -n "PySide6|http_server|yaw360|yaw_deg_per_px|deg_per_sec|RUNNING_DYNAMIC|dynamic_enabled|ipc-only" src tests pyproject.toml README.md docs/USER_GUIDE.md
```

Expected: no matches. If a documentation match describes removal rather than runtime behavior, keep it only in the approved design/plan documents, which are outside this scan.

- [ ] **Step 4: Run the Python and frontend suites**

Run:

```powershell
uv run pytest -v
npm --prefix frontend run typecheck
npm --prefix frontend run test:run
npm --prefix frontend run build
```

Expected: all pass with no collection errors or legacy imports.

- [ ] **Step 5: Commit the architecture cutover**

```powershell
git add -A src tests pyproject.toml uv.lock
git commit -m "refactor: remove the legacy desktop architecture"
```

### Task 16: Update packaging and build verification

**Files:**
- Modify: `build_tools/pyinstaller_support.py`
- Modify: `tests/test_pyinstaller_support.py`
- Modify: `GameCurveProbe.spec`
- Modify: `scripts/build-exe.ps1`
- Create: `scripts/smoke-test-exe.ps1`
- Create: `tests/test_static_assets.py`

- [ ] **Step 1: Write package-data tests**

```python
def test_web_assets_include_index() -> None:
    assets = collect_tree_files(PROJECT_ROOT / "src/gamecurveprobe/web", "gamecurveprobe/web")
    assert any(Path(source).name == "index.html" for source, _ in assets)


def test_spec_collects_wgc_and_web_assets() -> None:
    text = (PROJECT_ROOT / "GameCurveProbe.spec").read_text(encoding="utf-8")
    assert "windows_capture" in text
    assert "gamecurveprobe/web" in text.replace("\\", "/")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_pyinstaller_support.py tests/test_static_assets.py -v`

Expected: FAIL because web/WGC collection is absent.

- [ ] **Step 3: Implement deterministic build orchestration**

`build-exe.ps1` must run `npm ci`, typecheck, frontend tests, build, Python tests, PyInstaller, then smoke test. Resolve `src/gamecurveprobe/web` to an absolute path and assert it is under the repository before clearing it. Do not delete the repository root or use unresolved environment variables.

```powershell
$repoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$webRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'src/gamecurveprobe/web'))
if (-not $webRoot.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) { throw 'Unsafe web output path' }
npm --prefix (Join-Path $repoRoot 'frontend') ci
npm --prefix (Join-Path $repoRoot 'frontend') run typecheck
npm --prefix (Join-Path $repoRoot 'frontend') run test:run
npm --prefix (Join-Path $repoRoot 'frontend') run build
uv run pytest
uv run --extra capture --extra controller --with pyinstaller pyinstaller --noconfirm --clean .\GameCurveProbe.spec
```

- [ ] **Step 4: Update PyInstaller collection**

Add package-tree collection for `gamecurveprobe/web`, WGC package binaries/data, vgamepad DLLs, and required FastAPI/Uvicorn hidden imports. Keep paths package-relative so onefile extraction preserves lookup. Update unit tests to assert each group.

```python
web_datas = collect_tree_files(project_root / "src/gamecurveprobe/web", "gamecurveprobe/web")
wgc_datas = collect_package_files("windows_capture", ["**/*.dll", "**/*.pyd"])
a = Analysis(
    ["src\\gamecurveprobe\\__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[*vgamepad_datas, *wgc_datas, *web_datas],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6"],
    noarchive=False,
    optimize=0,
)
```

- [ ] **Step 5: Add the EXE smoke test**

`smoke-test-exe.ps1` starts the EXE hidden with `--stub --no-browser --port 0`, reads a machine-readable ready line containing port/token from redirected output, requests `/api/health` and `/`, asserts HTTP 200 and an HTML app root, then stops the exact spawned process in `finally`.

```powershell
$process = Start-Process -FilePath $exePath -ArgumentList '--stub','--no-browser','--port','0' -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -PassThru
try {
    $ready = Wait-ReadyLine -Path $stdoutPath -TimeoutSeconds 15
    if ((Invoke-WebRequest $ready.HealthUrl).StatusCode -ne 200) { throw 'Health smoke test failed' }
    if ((Invoke-WebRequest $ready.RootUrl).Content -notmatch '<div id="app">') { throw 'SPA smoke test failed' }
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id }
}
```

- [ ] **Step 6: Run package tests and build**

Run:

```powershell
uv run pytest tests/test_pyinstaller_support.py tests/test_static_assets.py -v
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
```

Expected: tests pass, `dist/GameCurveProbe.exe` exists, and smoke test exits 0.

- [ ] **Step 7: Commit packaging**

```powershell
git add build_tools tests/test_pyinstaller_support.py tests/test_static_assets.py GameCurveProbe.spec scripts
git commit -m "build: package and smoke-test the WebUI application"
```

### Task 17: Update user documentation and perform final verification

**Files:**
- Modify: `README.md`
- Rewrite: `docs/USER_GUIDE.md`
- Modify: `docs/superpowers/specs/2026-09-03-webui-refactoring-design.md` only if implementation revealed an approved contract correction

- [ ] **Step 1: Rewrite runtime and user instructions**

Document Windows/ViGEmBus prerequisites, `uv sync`, frontend development commands, `uv run gamecurveprobe`, automatic browser launch, capture fallback, ROI selection, manual inner/outer calibration, measurement presets, cancellation, import/export, `--no-browser`, and EXE building. Remove desktop GUI, yaw360, `deg/s`, IPC-only, and arbitrary export-directory instructions.

- [ ] **Step 2: Scan documentation for obsolete behavior**

Run:

```powershell
rg -n "PySide6|360|deg/s|ipc-only|output_dir|动态响应" README.md docs/USER_GUIDE.md
```

Expected: no matches.

- [ ] **Step 3: Run the complete automated verification**

Run:

```powershell
uv run pytest -v
npm --prefix frontend run typecheck
npm --prefix frontend run test:run
npm --prefix frontend run e2e
npm --prefix frontend run build
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
git diff --check
```

Expected: every command exits 0 and the worktree has only the intended documentation changes after the last code commit.

- [ ] **Step 4: Execute the Windows hardware checklist**

Record results for WGC and DXGI; dual-GPU if available; multiple monitors; 100%, 125%, and 150% DPI; resize, minimize, close, and cross-monitor window behavior; missing ViGEmBus; cancellation during settle and sample; service exit during probe; 30-minute preview memory stability; and final EXE on a clean Windows machine. Every safety case must record whether `neutral()` occurred.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md docs/USER_GUIDE.md docs/superpowers/specs/2026-09-03-webui-refactoring-design.md
git commit -m "docs: publish the WebUI workflow"
```

- [ ] **Step 6: Capture final evidence**

Run:

```powershell
git status --short
git log --oneline --decorate -20
```

Expected: clean status and a task-by-task commit history matching this plan.
