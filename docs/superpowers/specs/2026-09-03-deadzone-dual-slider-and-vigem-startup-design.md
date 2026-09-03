# Design Spec: Deadzone Dual-Thumb Slider & ViGEmBus Startup Lifecycle

- **Date**: 2026-09-03
- **Topic**: Deadzone dual-thumb slider control, predicted sampling points ($x$ values) visualization, and automatic ViGEmBus virtual controller startup.
- **Status**: Approved by User

---

## 1. Overview & Motivation

### 1.1 ViGEmBus Lifecycle
Currently, the virtual Xbox 360 controller (`vgamepad.VX360Gamepad`) is only initialized on demand when `acquire()` is called during deadzone probing or curve measurement. Many PC games do not recognize newly plugged-in gamepads while the game is already in progress, or experience frame drops when a device is connected.
**Goal**: Initialize and connect the ViGEmBus virtual controller immediately when GameCurveProbe launches (`lifespan` startup), hold it in a neutral state, and safely release/disconnect on application shutdown.

### 1.2 Deadzone Configuration & Sampling Point Visualizer
In the previous WebUI, deadzone adjustment relied on a single probe slider and separate "Set as Inner" / "Set as Outer" buttons, making it unintuitive to see the active range and how measurement samples will be positioned.
**Goal**:
1. Implement a single-axis dual-thumb range slider (`DeadzoneRangeSlider.vue`) with two interactive control points for inner and outer deadzones.
2. The distance between the points visually represents the active detection range ($\Delta = \text{outer} - \text{inner}$).
3. Inner and outer deadzone numerical values and fine-tuning steppers are displayed on the left and right sides.
4. Integrate deadzone probing so that adjusting or selecting a thumb immediately updates the virtual controller output if active probe is enabled.
5. Compute and render the predicted sampling points ($x$ coordinates) directly on the track (as tick marks) and below (as interactive capsule tags with point count toggles).

---

## 2. Architecture & Components

### 2.1 Backend: ViGEmBus Startup Connection (`ControllerService` & `app.py`)

#### Lifecycle State Flow
```
Server Startup (lifespan)
       │
       ▼
controller.connect()  ──►  vgamepad.VX360Gamepad() created & plugged into Windows
       │
       ▼
Idle State (Neutral right stick: X=0.0, Y=0.0)
       │
       ├─► Deadzone Probe: acquires controller lease, sets stick X to probe target
       │
       ├─► Measurement Runner: acquires controller lease, steps through sample points
       │
       ▼
Server Shutdown (AppContext.close())
       │
       ▼
controller.close()  ──►  disconnects virtual gamepad from ViGEmBus
```

#### Key Implementation Details
- `ControllerService.connect()` is called in `lifespan` right after `build_context()`.
- If ViGEmBus or vgamepad driver is unavailable, a clean warning is logged without crashing the WebUI server, but `is_available()` returns `False`.
- `acquire(owner)` re-uses the already connected backend without re-instantiating `VX360Gamepad`.
- `release(owner)` returns the stick to neutral `(0.0, 0.0)` while keeping the virtual device connected.

---

### 2.2 Frontend: Deadzone Dual-Thumb Slider Component (`DeadzoneRangeSlider.vue`)

#### Visual Structure
```
 [ 0.050 / 5.0% ]                                                     [ 0.950 / 95.0% ]
   [ - ] [ + ]                                                           [ - ] [ + ]
  (内死区 Inner)                                                       (外死区 Outer)
  ───────────────────────────────────────────────────────────────────────────────────
  [ 盲区 0~5% ] ───(● Inner)──────[ 有效检测行程: 90.0% ]──────(● Outer)─── [ 饱和区 95~100% ]
                          ·   ·   ·   ·   ·   ·   ·   ·   · (采样刻度 Ticks)
  ───────────────────────────────────────────────────────────────────────────────────
  预计采样点 (17 点 · 有效行程):
  [ #1: 0.050 ] [ #2: 0.106 ] [ #3: 0.163 ] ... [ #16: 0.894 ] [ #17: 0.950 ]
```

#### Component Responsibilities:
- **`DeadzoneRangeSlider.vue`**:
  - Props:
    - `innerDeadzone`: `number` (0.0 to 1.0)
    - `outerDeadzone`: `number` (0.0 to 1.0)
    - `pointCount`: `number` (e.g., 9, 17, 33)
    - `rangeMode`: `'active_range' | 'full'`
    - `probeActive`: `boolean`
    - `activeProbeTarget`: `'inner' | 'outer'`
    - `step`: `number` (resolution, e.g. 0.001, 0.005, 0.01)
  - Emits:
    - `update:innerDeadzone(val: number)`
    - `update:outerDeadzone(val: number)`
    - `update:pointCount(val: number)`
    - `update:rangeMode(mode: RangeMode)`
    - `selectProbeTarget(target: 'inner' | 'outer')`
    - `probeOutput(val: number)`
  - Drag Interaction:
    - Mouse / pointer down on left thumb -> drags inner deadzone, clamped to $[0.0, \text{outer} - 0.01]$.
    - Mouse / pointer down on right thumb -> drags outer deadzone, clamped to $[\text{inner} + 0.01, 1.0]$.
    - Throttled update to parent store / API.
    - If `probeActive` is true, dragging or stepping also streams the updated output to the backend probe API immediately.

---

### 2.3 Sampling Points ($x$ values) Computation

Algorithm matches backend `models.py:point_values()`:
```ts
function computeSamplingPoints(
  inner: number,
  outer: number,
  count: number,
  mode: 'active_range' | 'full'
): number[] {
  const start = mode === 'full' ? 0.0 : inner
  const end = mode === 'full' ? 1.0 : outer
  const span = end - start
  const points = new Set<number>()

  for (let i = 0; i < count; i++) {
    const val = Number((start + (span * i) / (count - 1)).toFixed(4))
    points.add(val)
  }

  if (mode === 'full') {
    points.add(Number(inner.toFixed(4)))
    points.add(Number(outer.toFixed(4)))
  }

  return Array.from(points).sort((a, b) => a - b)
}
```

- Each point is rendered as a tick mark dot on the dual-slider rail at `left: ${val * 100}%`.
- Below the rail, an interactive chips bar renders each point formatted to 3 decimal places (`0.050`), with hover highlighting the corresponding tick on the rail.

---

## 3. Integration with `DeadzoneStep.vue`

- Replace the old single slider and disjointed "Set as Inner" / "Set as Outer" buttons with `DeadzoneRangeSlider.vue`.
- Keep the live probe control ("激活摇杆实时输出 / 释放摇杆") and noise benchmark card intact.
- Seamlessly synchronize config changes to `sessionStore.updateConfig(...)`.

---

## 4. Verification Plan

1. **Backend ViGEm Startup Verification**:
   - Run unit tests `pytest tests/services/test_controller_service.py` to confirm initialization without errors.
   - Start backend server and verify ViGEmBus connection is established at boot.
2. **Frontend UI & Dual Slider Verification**:
   - Run `pnpm check` and `pnpm build` in `webui/`.
   - Test mouse dragging on both inner and outer thumbs: verify clamping, active range width calculation, and left/right numerical updates.
   - Verify predicted sampling points change in real-time when dragging thumbs, toggling 9/17/33 points, and toggling active_range/full mode.
   - Verify probe output synchronization when active.
