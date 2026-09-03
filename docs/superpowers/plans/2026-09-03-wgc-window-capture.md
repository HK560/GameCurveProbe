# WGC Independent Window Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `auto` use WGC exclusively, preserve static WGC frames as healthy, expose capture capability, and fail safely when the target window is minimized, closed, resized, or stalled.

**Architecture:** `WgcCaptureBackend` remains the HWND-based Windows Graphics Capture adapter. `CaptureService` is the sole backend reader and owns startup/runtime validation; it consults `WindowService` for HWND lifecycle, exposes structured health, and raises stable domain errors to measurement consumers. DXGI remains an explicit screen-region compatibility mode only.

**Tech Stack:** Python 3.13, windows-capture/WGC, Win32 user32, FastAPI, Vue 3, TypeScript, pytest, Vitest, PyInstaller.

---

## File map

- Modify `src/gamecurveprobe/models.py`: add capture capability and runtime health fields.
- Modify `src/gamecurveprobe/services/window_service.py`: expose existence, minimization, and client-size probes.
- Modify `src/gamecurveprobe/backends/capture/wgc_backend.py`: isolate callback generations and report fresh-frame health.
- Modify `src/gamecurveprobe/services/capture_service.py`: WGC-only auto selection, frame-id startup validation, lifecycle faults, ROI preflight.
- Modify `src/gamecurveprobe/app.py`: inject `WindowService` and publish capture warnings.
- Modify `src/gamecurveprobe/api/routes.py`: run capture/ROI preflight before jobs.
- Modify `webui/src/types/api.ts`: mirror capability and health DTO fields.
- Modify `webui/src/stores/session.ts`: retain capture warnings received over WebSocket.
- Modify `webui/src/components/CaptureStep.vue`: label WGC and warn for explicit DXGI mode/minimization.
- Test `tests/services/test_capture_service.py`, `tests/services/test_window_service.py`, `tests/backends/capture/test_wgc_backend.py`, `tests/api/test_routes.py`, and `webui/tests/capture_modes.test.ts`.

### Task 1: Correct WGC startup semantics and auto selection

**Files:**
- Modify: `tests/services/test_capture_service.py`
- Modify: `src/gamecurveprobe/services/capture_service.py`

- [ ] **Step 1: Write failing service tests**

Add tests whose fake WGC returns ten frames with identical pixels but strictly increasing `frame_id`; assert `auto` succeeds with WGC. Add a stalled WGC plus a recording dxcam backend and assert the WGC error is raised and dxcam `attach` is never called.

```python
def test_static_wgc_pixels_with_fresh_frame_ids_are_healthy():
    service = CaptureService({"wgc": StaticFreshBackend("wgc"), "dxcam": RecordingBackend("dxcam")})
    assert service.attach(42, "auto", 120).backend == "wgc"

def test_auto_never_falls_back_to_desktop_capture():
    dxcam = RecordingBackend("dxcam")
    with pytest.raises(DomainError):
        CaptureService({"wgc": StalledBackend("wgc"), "dxcam": dxcam}).attach(42, "auto", 120)
    assert dxcam.attach_calls == 0
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/services/test_capture_service.py -v`

Expected: the static-frame test fails due to pixel equality and the fallback test records a dxcam attach.

- [ ] **Step 3: Implement frame-id validation**

Change auto candidates to `("wgc",)`. For WGC, collect ten frames and require every returned `frame_id` to be greater than the preceding one. Keep the ten-frame black diagnostic; remove `np.array_equal()` and `Frame.is_duplicate` from WGC startup health decisions.

```python
candidates = ("wgc",) if requested == "auto" else (requested,)
if frames and frame.frame_id <= frames[-1].frame_id:
    raise DomainError("CAPTURE_STALLED", "WGC did not produce a fresh callback frame.")
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/services/test_capture_service.py -v`

Expected: all capture-service tests pass.

### Task 2: Model capture capability and HWND lifecycle

**Files:**
- Modify: `src/gamecurveprobe/models.py`
- Modify: `src/gamecurveprobe/services/window_service.py`
- Modify: `src/gamecurveprobe/backends/capture/wgc_backend.py`
- Modify: `src/gamecurveprobe/backends/capture/dxcam_monitor_backend.py`
- Test: `tests/services/test_window_service.py`
- Test: `tests/backends/capture/test_wgc_backend.py`

- [ ] **Step 1: Write failing lifecycle tests**

Use a fake user32 implementing `IsWindow`, `IsIconic`, and `GetClientRect`; assert `inspect_window()` distinguishes normal, minimized, and gone HWNDs. Add a WGC test proving a callback from a prior attach generation is ignored.

```python
assert service.inspect_window(123).minimized is True
backend._handle_raw_frame(frame, generation=old_generation)
assert backend.health().frame_id == current_id
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/services/test_window_service.py tests/backends/capture/test_wgc_backend.py -v`

Expected: failures because `WindowState`, `inspect_window`, callback generations, and health frame metadata do not exist.

- [ ] **Step 3: Add normalized models and probes**

Add immutable `WindowState(exists, minimized, client_width, client_height)`. Extend `CaptureInfo` with `occlusion_safe`; extend `CaptureHealth` with `frame_id`, `frame_age_ms`, `window_exists`, and `window_minimized`. WGC returns `occlusion_safe=True`; dxcam returns `False`.

`WindowService.inspect_window()` calls `IsWindow`, then `IsIconic`, then `GetClientRect` without requiring the minimized window to remain in the visible-window enumeration.

- [ ] **Step 4: Isolate WGC callback generations**

Increment `_generation` on attach and close. Capture the generation in event callbacks and ignore raw frames whose generation differs from the active one. Notify the condition when WGC closes. Health reports the latest callback frame id and monotonic age.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/services/test_window_service.py tests/backends/capture/test_wgc_backend.py tests/backends/capture/test_dxcam_monitor_backend.py -v`

Expected: all selected tests pass.

### Task 3: Enforce runtime faults and measurement preflight

**Files:**
- Modify: `src/gamecurveprobe/services/capture_service.py`
- Modify: `src/gamecurveprobe/app.py`
- Modify: `src/gamecurveprobe/api/routes.py`
- Test: `tests/services/test_capture_service.py`
- Test: `tests/api/test_routes.py`

- [ ] **Step 1: Write failing runtime tests**

Inject a fake window inspector. Assert minimized and gone windows produce `WINDOW_MINIMIZED` and `WINDOW_GONE`; changed frame dimensions produce `ROI_INVALIDATED`; stalled reads return no cached frame. Add an API test asserting measurement is rejected before controller acquisition when minimized.

```python
with pytest.raises(DomainError) as exc:
    service.assert_ready(RoiRect(0, 0, 100, 100))
assert exc.value.code == "WINDOW_MINIMIZED"
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/services/test_capture_service.py tests/api/test_routes.py -v`

Expected: failures because runtime inspection and `assert_ready()` are missing.

- [ ] **Step 3: Implement runtime state checks**

Inject `window_service` and a capture-status callback into `CaptureService`. At a throttled interval, inspect HWND existence/minimization. Set a stable fault, publish it once, mark health unhealthy, and make fresh-frame consumers raise the fault. Detect frame-size changes against attached dimensions as `ROI_INVALIDATED`.

`read(timeout_ms)` must return `None` when no newer `frame_id` arrives; it must never return the cached frame as a new sample.

- [ ] **Step 4: Implement preflight**

Add `assert_ready(roi)` to validate no runtime fault, normal window state, fresh frame age, and ROI bounds. Call it in idle-noise and measurement routes before acquiring controller resources or creating a job.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/services/test_capture_service.py tests/api/test_routes.py tests/e2e/test_browser_workflow.py -v`

Expected: all selected tests pass and controller neutralization tests remain green.

### Task 4: Expose safe/compatibility mode in the WebUI

**Files:**
- Modify: `webui/src/types/api.ts`
- Modify: `webui/src/stores/session.ts`
- Modify: `webui/src/components/CaptureStep.vue`
- Create: `webui/tests/capture_modes.test.ts`

- [ ] **Step 1: Write failing frontend test**

Extract pure presentation metadata and assert `auto/wgc` are independent-window capture while dxcam is a screen-region compatibility mode with an occlusion warning.

```ts
expect(captureModeInfo('dxcam').warning).toContain('遮挡')
expect(captureModeInfo('auto').occlusionSafe).toBe(true)
```

- [ ] **Step 2: Verify RED**

Run: `npm --prefix webui test -- tests/capture_modes.test.ts`

Expected: FAIL because the presentation helper does not exist.

- [ ] **Step 3: Implement types and UI**

Add DTO fields matching Python models. Label auto as WGC-only, label dxcam as compatibility mode, render its warning whenever selected, and render runtime `WINDOW_MINIMIZED`, `WINDOW_GONE`, `CAPTURE_STALLED`, or `ROI_INVALIDATED` events from the session store.

- [ ] **Step 4: Verify GREEN**

Run: `npm --prefix webui run typecheck && npm --prefix webui test && npm --prefix webui run build`

Expected: typecheck, all Vitest tests, and production build pass without chunk-size warnings.

### Task 5: Package and validate the complete path

**Files:**
- Modify generated assets under `src/gamecurveprobe/web_dist/`
- Verify `GameCurveProbe.spec` and `scripts/build-exe.ps1`

- [ ] **Step 1: Run full Python verification**

Run: `uv run pytest -v`

Expected: all Python tests pass; only known third-party deprecation warnings may remain.

- [ ] **Step 2: Run full frontend verification**

Run: `npm --prefix webui run typecheck; npm --prefix webui test; npm --prefix webui run build`

Expected: all commands exit zero and output chunks remain below the configured warning threshold.

- [ ] **Step 3: Build and smoke-test the EXE**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1`

Expected: PyInstaller creates `dist/GameCurveProbe.exe`; the script starts the exact EXE, receives HTTP 200 from `/api/health`, terminates the smoke process, and exits zero.

- [ ] **Step 4: Check the patch**

Run: `git diff --check` and confirm no `build-smoke-token-*` process remains.

Expected: no whitespace errors and no leaked smoke process.

- [ ] **Step 5: Record hardware validation boundary**

Run the final EXE against a real WGC-capable game window, cover it completely with another window, and confirm the preview still shows the game. Minimize the game and confirm the UI shows the explicit warning and measurement cannot continue. Record hardware-only validation separately; do not infer it from stubs.
