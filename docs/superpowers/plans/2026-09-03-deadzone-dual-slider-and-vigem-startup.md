# Deadzone Dual-Thumb Slider & ViGEmBus Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automatic ViGEmBus virtual controller connection on software startup, a modern single-axis dual-thumb slider for inner/outer deadzones with active range visual representation, and real-time computation and display of predicted joystick sampling points ($x$ values).

**Architecture:**
1. **Backend**: `ControllerService.connect()` is executed during FastAPI `lifespan` startup, ensuring the virtual Xbox 360 controller is plugged in before the user even starts a game or initiates probing.
2. **Frontend Component**: A new dedicated Vue component `DeadzoneRangeSlider.vue` provides mouse/pointer-drag dual-thumb controls on a single rail with shaded inner/outer regions and an active range span badge.
3. **Sampling Points Math**: Calculates the exact $x$ coordinates following `ProbeConfig.point_values()`, displaying tick marks on the axis rail and interactive capsule chips with point-count and range-mode selectors.
4. **Step Integration**: `DeadzoneStep.vue` integrates the new component, linking probe tests and config persistence seamlessly.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, vgamepad, pytest
- Frontend: Vue 3 (Composition API, `<script setup>`), TypeScript, Tailwind CSS, Lucide Icons, Vite

## Global Constraints
- Minimalist monochrome design palette adhering to the existing theme (`neutral-900`, `neutral-100`, `neutral-200`, `white`, `font-mono`).
- Drag math must clamp: $0.0 \le \text{inner} \le \text{outer} - 0.01$ and $\text{inner} + 0.01 \le \text{outer} \le 1.0$.
- Sampling points calculation must match backend `point_values()` behavior exactly.

---

### Task 1: Backend ViGEmBus Startup Initialization & Lifecycle

**Files:**
- Modify: `src/gamecurveprobe/services/controller_service.py`
- Modify: `src/gamecurveprobe/api/server.py`
- Modify: `src/gamecurveprobe/app.py`
- Test: `tests/services/test_controller_service.py`

**Interfaces:**
- Consumes: `VirtualControllerBackend.connect()`, `VirtualControllerBackend.probe()`
- Produces: `ControllerService.connect()` (idempotent, safe on startup)

- [ ] **Step 1: Write unit test for idempotent connect on startup**

In `tests/services/test_controller_service.py`:
```python
def test_controller_connect_is_idempotent() -> None:
    backend = StubControllerBackend()
    service = ControllerService(backend)
    service.connect()
    assert backend.connected is True
    # Calling connect again should be a no-op
    service.connect()
    assert backend.connected is True
```

- [ ] **Step 2: Run pytest to verify test passes/fails**
Run: `uv run pytest tests/services/test_controller_service.py -k test_controller_connect_is_idempotent`

- [ ] **Step 3: Modify `ControllerService` and `api/server.py` lifespan**
Ensure `ControllerService.connect()` handles already-connected backends cleanly.
In `src/gamecurveprobe/api/server.py`, in `lifespan`:
```python
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context = context_factory()
        app.state.context = context
        try:
            context.controller.connect()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to initialize virtual gamepad on startup: %s", exc)
        try:
            yield
        finally:
            app.state.context.close()
```

- [ ] **Step 4: Run all controller tests to ensure green**
Run: `uv run pytest tests/services/test_controller_service.py tests/services/test_deadzone_probe_service.py`

- [ ] **Step 5: Commit changes**
```bash
git add src/gamecurveprobe/services/controller_service.py src/gamecurveprobe/api/server.py tests/services/test_controller_service.py
git commit -m "feat: initialize ViGEmBus virtual controller on app startup"
```

---

### Task 2: Implement `DeadzoneRangeSlider.vue` Component

**Files:**
- Create: `webui/src/components/DeadzoneRangeSlider.vue`

**Interfaces:**
- Props:
  - `innerDeadzone: number` (0.0 to 1.0)
  - `outerDeadzone: number` (0.0 to 1.0)
  - `pointCount: number` (default 17)
  - `rangeMode: 'active_range' | 'full'` (default 'active_range')
  - `probeActive: boolean`
  - `activeProbeTarget: 'inner' | 'outer'`
  - `step: number` (e.g. 0.001, 0.005, 0.01)
- Emits:
  - `update:innerDeadzone`: `(val: number) => void`
  - `update:outerDeadzone`: `(val: number) => void`
  - `update:pointCount`: `(count: number) => void`
  - `update:rangeMode`: `(mode: 'active_range' | 'full') => void`
  - `update:activeProbeTarget`: `(target: 'inner' | 'outer') => void`
  - `probeOutput`: `(val: number) => void`

- [ ] **Step 1: Write `DeadzoneRangeSlider.vue`**
Create `webui/src/components/DeadzoneRangeSlider.vue` with:
1. Pointer down / move / up dragging for both inner and outer thumb handles with window event listeners.
2. Clamping math ($0.0 \le \text{inner} \le \text{outer} - 0.01$ and $\text{inner} + 0.01 \le \text{outer} \le 1.0$).
3. Left and right numeric inputs with stepper buttons (`-` / `+`).
4. Visual regions: Inner deadzone shaded, active detection range highlighted with center span badge (`(outer - inner) * 100%`), outer deadzone shaded.
5. Sampling points calculation function matching `ProbeConfig.point_values()`.
6. Tick marks rendered along the rail corresponding to calculated sampling points.
7. Point count toggle (9 / 17 / 33) and range mode toggle (有效行程 / 全范围).
8. Capsule chips grid listing all sampling point values `#i: x.xxx`, with hover highlighting the corresponding tick mark.
9. Linkage to probe: Clicking a thumb or changing its value triggers `probeOutput` if `probeActive`.

- [ ] **Step 2: Run type check in webui**
Run: `cd webui && pnpm vue-tsc --noEmit`

- [ ] **Step 3: Commit component**
```bash
git add webui/src/components/DeadzoneRangeSlider.vue
git commit -m "feat(webui): add DeadzoneRangeSlider component with dual thumbs and sampling preview"
```

---

### Task 3: Integrate `DeadzoneRangeSlider.vue` into `DeadzoneStep.vue`

**Files:**
- Modify: `webui/src/components/DeadzoneStep.vue`

- [ ] **Step 1: Replace legacy slider and buttons in `DeadzoneStep.vue`**
Integrate `DeadzoneRangeSlider.vue`:
- Bind `innerDeadzone` and `outerDeadzone` to `config.inner_deadzone` and `config.outer_deadzone`.
- Update `sessionStore.updateConfig` on deadzone change.
- Handle active probe target selection and value streaming when `probeActive`.
- Retain "激活摇杆实时输出 / 释放摇杆" button, expiration countdown, and idle noise floor benchmark card.

- [ ] **Step 2: Run type check and Vite build**
Run: `cd webui && pnpm build`

- [ ] **Step 3: Commit integration**
```bash
git add webui/src/components/DeadzoneStep.vue
git commit -m "feat(webui): integrate dual-thumb deadzone slider into DeadzoneStep"
```

---

### Task 4: End-to-End Verification & Build Artifacts

**Files:**
- `src/gamecurveprobe/web_dist/`

- [ ] **Step 1: Run Python tests**
Run: `uv run pytest`

- [ ] **Step 2: Build WebUI and verify distribution**
Run: `cd webui && pnpm build`

- [ ] **Step 3: Test backend boot and ViGEmBus connection**
Run: `uv run python -c "from gamecurveprobe.app import build_context; ctx = build_context('test', '127.0.0.1', 8765); print('Controller available:', ctx.controller.is_available()); ctx.close()"`

- [ ] **Step 4: Final commit and summary**
```bash
git add .
git commit -m "chore: complete deadzone dual slider and ViGEmBus startup implementation"
```
