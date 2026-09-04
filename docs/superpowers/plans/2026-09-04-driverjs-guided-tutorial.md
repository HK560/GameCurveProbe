# Driver.js Guided Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete, bilingual, non-destructive Driver.js tutorial that automatically runs once for new users and can be replayed from Settings.

**Architecture:** Keep tutorial persistence and lifecycle in small framework-agnostic services, and expose a Vue tutorial context that overlays demo values without mutating the Pinia session. A single `TutorialOverlay.vue` orchestrates Driver.js, step navigation, DOM readiness, and cleanup; existing screens only gain stable anchors and consume optional demo values.

**Tech Stack:** Vue 3, TypeScript, Pinia, Driver.js, Vitest, Vite, Tailwind CSS

---

## File map

- Create `webui/src/services/tutorialState.ts`: safe localStorage persistence and a small lifecycle state machine.
- Create `webui/src/services/tutorialDemo.ts`: typed, immutable demonstration data and animation snapshots.
- Create `webui/src/services/tutorialSteps.ts`: seven chapters, bilingual copy keys, target selectors, and page/action metadata.
- Create `webui/src/composables/useTutorial.ts`: provide/inject tutorial controller and computed display overrides.
- Create `webui/src/components/TutorialOverlay.vue`: Driver.js adapter, page transitions, target waiting, animation, and cleanup.
- Modify `webui/src/App.vue`: provide tutorial state, auto-start after initialization, render overlay, annotate navigation, and handle Settings replay.
- Modify `webui/src/components/CaptureStep.vue`: stable anchors and demo display values.
- Modify `webui/src/components/DeadzoneStep.vue`: stable anchors and demo display values.
- Modify `webui/src/components/DeadzoneRangeSlider.vue`: stable anchors and demo-safe visual inputs.
- Modify `webui/src/components/MeasurementStep.vue`: stable anchors and demo job/log/result display values.
- Modify `webui/src/components/AnalysisStep.vue`: stable anchors and demo report display value.
- Modify `webui/src/components/HotkeySettingsModal.vue`: tutorial replay card and event.
- Modify `webui/src/services/i18n.ts`: tutorial and Settings copy in Chinese and English.
- Modify `webui/src/assets/main.css`: Driver.js theme and responsive treatment.
- Modify `webui/package.json` and `webui/package-lock.json`: Driver.js runtime dependency.
- Create tests under `webui/tests/tutorial_*.test.ts` for persistence, demo isolation, content, targets, and lifecycle.

### Task 1: Persistence and lifecycle state machine

**Files:**
- Create: `webui/src/services/tutorialState.ts`
- Test: `webui/tests/tutorial_state.test.ts`

- [ ] **Step 1: Write failing persistence and lifecycle tests**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  TUTORIAL_COMPLETED_KEY,
  createTutorialState,
  hasCompletedTutorial,
  markTutorialCompleted,
} from '../src/services/tutorialState'

describe('tutorial persistence', () => {
  beforeEach(() => localStorage.clear())

  it('auto-starts only while completion marker is absent', () => {
    expect(hasCompletedTutorial(localStorage)).toBe(false)
    markTutorialCompleted(localStorage)
    expect(localStorage.getItem(TUTORIAL_COMPLETED_KEY)).toBe('1')
    expect(hasCompletedTutorial(localStorage)).toBe(true)
  })

  it('degrades safely when storage throws', () => {
    const storage = { getItem: vi.fn(() => { throw new Error('blocked') }), setItem: vi.fn(() => { throw new Error('blocked') }) }
    expect(hasCompletedTutorial(storage)).toBe(false)
    expect(() => markTutorialCompleted(storage)).not.toThrow()
  })
})

describe('tutorial lifecycle', () => {
  it('restores the launch page and marks only explicit completion', () => {
    const state = createTutorialState()
    state.start('settings', 3)
    state.goTo(7)
    expect(state.snapshot()).toMatchObject({ active: true, source: 'settings', launchStep: 3, nodeIndex: 7 })
    expect(state.stop('interrupted')).toEqual({ restoreStep: 3, persistCompletion: false })
    state.start('first-run', 2)
    expect(state.stop('completed')).toEqual({ restoreStep: 1, persistCompletion: true })
  })
})
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm test -- tutorial_state.test.ts`

Expected: FAIL because `tutorialState.ts` does not exist.

- [ ] **Step 3: Implement the minimal state module**

```ts
export const TUTORIAL_COMPLETED_KEY = 'gamecurveprobe_tutorial_completed'
export type TutorialSource = 'first-run' | 'settings'
export type TutorialExit = 'completed' | 'skipped' | 'interrupted'

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

export function hasCompletedTutorial(storage: StorageLike | undefined = globalThis.localStorage): boolean {
  try { return storage?.getItem(TUTORIAL_COMPLETED_KEY) === '1' } catch { return false }
}

export function markTutorialCompleted(storage: StorageLike | undefined = globalThis.localStorage): void {
  try { storage?.setItem(TUTORIAL_COMPLETED_KEY, '1') } catch { /* persistence is optional */ }
}

export function createTutorialState() {
  let value = { active: false, source: 'first-run' as TutorialSource, launchStep: 1, nodeIndex: 0 }
  return {
    snapshot: () => ({ ...value }),
    start(source: TutorialSource, launchStep: number) { value = { active: true, source, launchStep, nodeIndex: 0 } },
    goTo(nodeIndex: number) { value.nodeIndex = nodeIndex },
    stop(reason: TutorialExit) {
      const result = {
        restoreStep: value.source === 'first-run' ? 1 : value.launchStep,
        persistCompletion: reason === 'completed' || reason === 'skipped',
      }
      value.active = false
      return result
    },
  }
}
```

- [ ] **Step 4: Run the focused test and full frontend tests**

Run: `npm test -- tutorial_state.test.ts && npm test`

Expected: focused test and existing suite PASS.

- [ ] **Step 5: Commit**

```powershell
git add webui/src/services/tutorialState.ts webui/tests/tutorial_state.test.ts
git commit -m "feat(tutorial): add safe first-run lifecycle state"
```

### Task 2: Typed demo data that cannot mutate the real session

**Files:**
- Create: `webui/src/services/tutorialDemo.ts`
- Test: `webui/tests/tutorial_demo.test.ts`

- [ ] **Step 1: Write failing demo-data tests**

```ts
import { describe, expect, it } from 'vitest'
import { createTutorialDemo, tutorialMeasurementFrames } from '../src/services/tutorialDemo'

describe('tutorial demo data', () => {
  it('contains a complete capture-to-report path', () => {
    const demo = createTutorialDemo()
    expect(demo.windows[0].title).toBeTruthy()
    expect(demo.capture).toMatchObject({ width: 1920, height: 1080, backend: 'wgc', target_fps: 120 })
    expect(demo.roiQualityExcellent.score).toBeGreaterThanOrEqual(60)
    expect(demo.roiQualityPoor.score).toBeLessThan(25)
    expect(demo.noise.confidence).toBeGreaterThan(0)
    expect(demo.result.points.length).toBeGreaterThanOrEqual(9)
  })

  it('returns fresh structures and ordered measurement frames', () => {
    const first = createTutorialDemo()
    const second = createTutorialDemo()
    first.result.points[0].stability = 0
    expect(second.result.points[0].stability).not.toBe(0)
    expect(tutorialMeasurementFrames.map(frame => frame.phase)).toContain('point_retry')
  })
})
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm test -- tutorial_demo.test.ts`

Expected: FAIL because demo factory is missing.

- [ ] **Step 3: Implement fixtures using existing API types**

Create `createTutorialDemo()` returning `windows`, `capture`, `roi`, poor/excellent `RoiQuality`, `noise`, `config`, `probe`, logs, and a `SessionResult`. Build 17 points with inputs from 0 to 1, increasing velocities, normalized speeds, stability, attempts, and coverage. Use factory-created arrays/objects on every call; do not export mutable singleton session objects.

```ts
export const tutorialMeasurementFrames = [
  { phase: 'stage_start', currentPoint: 0, totalPoints: 17 },
  { phase: 'point_settle', currentPoint: 4, totalPoints: 17 },
  { phase: 'point_sampling', currentPoint: 8, totalPoints: 17 },
  { phase: 'point_retry', currentPoint: 8, totalPoints: 17 },
  { phase: 'point_done', currentPoint: 13, totalPoints: 17 },
  { phase: 'stage_completed', currentPoint: 17, totalPoints: 17 },
] as const
```

- [ ] **Step 4: Run focused tests and typecheck**

Run: `npm test -- tutorial_demo.test.ts && npm run typecheck`

Expected: PASS and exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add webui/src/services/tutorialDemo.ts webui/tests/tutorial_demo.test.ts
git commit -m "feat(tutorial): add isolated demonstration fixtures"
```

### Task 3: Seven-chapter bilingual step catalog

**Files:**
- Create: `webui/src/services/tutorialSteps.ts`
- Modify: `webui/src/services/i18n.ts`
- Test: `webui/tests/tutorial_steps.test.ts`

- [ ] **Step 1: Write failing catalog tests**

```ts
import { describe, expect, it } from 'vitest'
import { messages } from '../src/services/i18n'
import { createTutorialSteps } from '../src/services/tutorialSteps'

describe('tutorial catalog', () => {
  it('covers seven chapters and every application page', () => {
    const steps = createTutorialSteps(key => messages.zh[key])
    expect(new Set(steps.map(step => step.chapter))).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]))
    expect(new Set(steps.map(step => step.page).filter(Boolean))).toEqual(new Set([1, 2, 3, 4]))
    expect(steps.length).toBeGreaterThanOrEqual(26)
  })

  it.each(['zh', 'en'] as const)('has complete %s copy', locale => {
    const steps = createTutorialSteps(key => messages[locale][key])
    for (const step of steps) {
      expect(step.title.trim()).not.toBe('')
      expect(step.description.trim()).not.toBe('')
      if (step.element) expect(step.element).toMatch(/^\[data-tour="[a-z0-9-]+"\]$/)
    }
  })
})
```

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- tutorial_steps.test.ts`

Expected: FAIL because the catalog and translation keys are missing.

- [ ] **Step 3: Add typed step metadata and all copy**

Define `TutorialAction = 'show-poor-roi' | 'show-good-roi' | 'show-noise' | 'show-probe' | 'animate-measurement' | 'show-report' | 'show-summary'` and `TutorialStepDefinition` with `id`, `chapter`, `page?`, `element?`, `title`, `description`, and `action?`. Add 26–30 explicit steps covering every item in the design, including parameter presets, retry behavior, model interpretation, outliers, export/import, and completion.

Add matching `tutorial_*` keys to both `messages.zh` and `messages.en`, plus Driver button labels and Settings replay copy. Keep the existing `t()` key typing intact by ensuring both locale objects have identical keys.

- [ ] **Step 4: Run catalog and existing i18n tests**

Run: `npm test -- tutorial_steps.test.ts i18n_nav.test.ts`

Expected: PASS for both locales.

- [ ] **Step 5: Commit**

```powershell
git add webui/src/services/tutorialSteps.ts webui/src/services/i18n.ts webui/tests/tutorial_steps.test.ts
git commit -m "feat(tutorial): define bilingual seven-chapter tour"
```

### Task 4: Vue tutorial context and safe display overrides

**Files:**
- Create: `webui/src/composables/useTutorial.ts`
- Modify: `webui/src/App.vue`
- Modify: `webui/src/components/CaptureStep.vue`
- Modify: `webui/src/components/DeadzoneStep.vue`
- Modify: `webui/src/components/DeadzoneRangeSlider.vue`
- Modify: `webui/src/components/MeasurementStep.vue`
- Modify: `webui/src/components/AnalysisStep.vue`
- Test: `webui/tests/tutorial_context.test.ts`

- [ ] **Step 1: Write failing isolation tests**

```ts
import { describe, expect, it, vi } from 'vitest'
import { createTutorialController } from '../src/composables/useTutorial'

describe('tutorial context', () => {
  it('uses demo values only while active and restores the launch page', () => {
    const setPage = vi.fn()
    const controller = createTutorialController({ getPage: () => 3, setPage })
    const real = { capture: null, lastResult: null }
    expect(controller.display(real).capture).toBeNull()
    controller.start('settings')
    expect(controller.display(real).capture?.backend).toBe('wgc')
    expect(real).toEqual({ capture: null, lastResult: null })
    controller.stop('interrupted')
    expect(setPage).toHaveBeenLastCalledWith(3)
    expect(controller.display(real).capture).toBeNull()
  })

  it('never invokes real actions in demo mode', async () => {
    const dangerousAction = vi.fn()
    const controller = createTutorialController({ getPage: () => 1, setPage: vi.fn() })
    controller.start('first-run')
    await controller.guardAction(dangerousAction)
    expect(dangerousAction).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- tutorial_context.test.ts`

Expected: FAIL because the composable does not exist.

- [ ] **Step 3: Implement provide/inject controller**

The controller owns Vue refs for `active`, `source`, `nodeIndex`, `demoPhase`, and fresh demo data. It exposes `start`, `stop`, `setPage`, `applyAction`, `display(real)`, and `guardAction`. `provideTutorial()` is called once in `App.vue`; `useTutorial()` returns the injected controller in child components.

In each component, introduce narrowly scoped display computeds such as:

```ts
const tutorial = useTutorial()
const displayCapture = computed(() => tutorial.active.value ? tutorial.demo.capture : sessionStore.capture)
const displayResult = computed(() => tutorial.active.value ? tutorial.demo.result : sessionStore.lastResult)
```

Use those computeds only in templates and derived presentation calculations. Wrap any clickable API action with `tutorial.guardAction(() => existingAction())` or disable it while the tour is active. Do not assign demo objects into `sessionStore`.

- [ ] **Step 4: Run isolation tests and store regression tests**

Run: `npm test -- tutorial_context.test.ts session_store.test.ts`

Expected: PASS; session persistence behavior remains unchanged.

- [ ] **Step 5: Commit**

```powershell
git add webui/src/composables/useTutorial.ts webui/src/App.vue webui/src/components/CaptureStep.vue webui/src/components/DeadzoneStep.vue webui/src/components/DeadzoneRangeSlider.vue webui/src/components/MeasurementStep.vue webui/src/components/AnalysisStep.vue webui/tests/tutorial_context.test.ts
git commit -m "feat(tutorial): overlay demo values without mutating sessions"
```

### Task 5: Stable page anchors and Settings replay entry

**Files:**
- Modify: `webui/src/App.vue`
- Modify: `webui/src/components/CaptureStep.vue`
- Modify: `webui/src/components/DeadzoneStep.vue`
- Modify: `webui/src/components/DeadzoneRangeSlider.vue`
- Modify: `webui/src/components/MeasurementStep.vue`
- Modify: `webui/src/components/AnalysisStep.vue`
- Modify: `webui/src/components/HotkeySettingsModal.vue`
- Test: `webui/tests/tutorial_anchors.test.ts`

- [ ] **Step 1: Write a failing source-level anchor contract test**

```ts
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { tutorialTargetNames } from '../src/services/tutorialSteps'

describe('tutorial anchors', () => {
  it('renders every catalog target in a Vue template', () => {
    const root = path.resolve(__dirname, '../src')
    const source = ['App.vue', 'components/CaptureStep.vue', 'components/DeadzoneStep.vue',
      'components/DeadzoneRangeSlider.vue', 'components/MeasurementStep.vue',
      'components/AnalysisStep.vue', 'components/HotkeySettingsModal.vue']
      .map(file => fs.readFileSync(path.join(root, file), 'utf8')).join('\n')
    for (const target of tutorialTargetNames) expect(source).toContain(`data-tour="${target}"`)
  })
})
```

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- tutorial_anchors.test.ts`

Expected: FAIL listing the first missing target.

- [ ] **Step 3: Add semantic anchors and Settings event**

Add anchors for app workflow navigation, window selector, backend, FPS, capture action/status, ROI viewport/quality, deadzone overview/noise/probe/targets/range mode, measurement parameters/start/progress/logs, analysis summary/model/export/range/chart/table, and settings tutorial replay.

Extend the settings emits declaration:

```ts
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'start-tutorial'): void
}>()
```

Add a dedicated tutorial card with explanatory copy and a button that emits `start-tutorial`. In `App.vue`, close the modal and start with source `settings` after `nextTick()`.

- [ ] **Step 4: Run anchor and type tests**

Run: `npm test -- tutorial_anchors.test.ts && npm run typecheck`

Expected: PASS and exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add webui/src/App.vue webui/src/components webui/tests/tutorial_anchors.test.ts
git commit -m "feat(tutorial): add stable anchors and settings replay"
```

### Task 6: Driver.js orchestration, first-run launch, and cleanup

**Files:**
- Create: `webui/src/components/TutorialOverlay.vue`
- Create: `webui/src/services/tutorialDriver.ts`
- Modify: `webui/src/App.vue`
- Modify: `webui/src/main.ts`
- Modify: `webui/src/assets/main.css`
- Modify: `webui/package.json`
- Modify: `webui/package-lock.json`
- Test: `webui/tests/tutorial_driver.test.ts`

- [ ] **Step 1: Install Driver.js dependency**

Run: `npm install driver.js`

Expected: `driver.js` appears in dependencies and the lockfile changes.

- [ ] **Step 2: Write failing adapter tests with an injected driver factory**

```ts
import { describe, expect, it, vi } from 'vitest'
import { createTutorialDriver, waitForTourTarget } from '../src/services/tutorialDriver'

describe('tutorial driver adapter', () => {
  it('keeps one instance and destroys it during restart and cleanup', async () => {
    const first = { drive: vi.fn(), destroy: vi.fn(), moveNext: vi.fn() }
    const second = { drive: vi.fn(), destroy: vi.fn(), moveNext: vi.fn() }
    const factory = vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second)
    const adapter = createTutorialDriver(factory)
    adapter.start({ steps: [] })
    adapter.start({ steps: [] })
    expect(first.destroy).toHaveBeenCalledOnce()
    adapter.destroy()
    expect(second.destroy).toHaveBeenCalledOnce()
  })

  it('returns false instead of hanging when an element never renders', async () => {
    vi.useFakeTimers()
    const promise = waitForTourTarget('[data-tour="missing"]', { timeoutMs: 100, pollMs: 20 })
    await vi.advanceTimersByTimeAsync(120)
    await expect(promise).resolves.toBe(false)
    vi.useRealTimers()
  })
})
```

- [ ] **Step 3: Run and verify RED**

Run: `npm test -- tutorial_driver.test.ts`

Expected: FAIL because adapter functions are missing.

- [ ] **Step 4: Implement the injected Driver.js adapter**

`tutorialDriver.ts` owns one `Driver` instance, exports a cancellable `waitForTourTarget`, destroys before restart, and maps catalog steps into Driver.js steps. Callbacks must delegate navigation and completion back to `TutorialOverlay.vue`; the adapter must not import the Pinia store.

- [ ] **Step 5: Implement `TutorialOverlay.vue` and application wiring**

On start, build localized steps and Driver config with localized next/previous/done labels, progress, keyboard navigation, overlay click disabled, and `allowClose: true`. Before showing each node: apply its demo action, set requested page, await `nextTick`, wait for target, then show or advance past a missing target. On destroy, cancel pending waits and animation timers and call controller stop with the correct exit reason.

In `App.vue`, after `await sessionStore.loadInitialData()` and `await nextTick()`, start only when `hasCompletedTutorial()` is false. Render `TutorialOverlay` once. Import `driver.js/dist/driver.css` from `main.ts`.

Add CSS for `.driver-popover`, `.driver-popover-title`, buttons, chapter badge, high z-index, dark neutral controls, and a mobile `max-width`/font adjustment.

- [ ] **Step 6: Run adapter, lifecycle, and all tutorial tests**

Run: `npm test -- tutorial_driver.test.ts tutorial_state.test.ts tutorial_demo.test.ts tutorial_steps.test.ts tutorial_context.test.ts tutorial_anchors.test.ts`

Expected: all tutorial tests PASS with no unhandled timers.

- [ ] **Step 7: Commit**

```powershell
git add webui/package.json webui/package-lock.json webui/src/main.ts webui/src/assets/main.css webui/src/App.vue webui/src/components/TutorialOverlay.vue webui/src/services/tutorialDriver.ts webui/tests/tutorial_driver.test.ts
git commit -m "feat(tutorial): orchestrate complete Driver.js walkthrough"
```

### Task 7: End-to-end behavior and documentation

**Files:**
- Modify: `webui/tests/tutorial_driver.test.ts`
- Modify: `tests/e2e/test_browser_workflow.py` if its browser harness can inspect localStorage and Driver.js DOM reliably
- Modify: `docs/USER_GUIDE.md`

- [ ] **Step 1: Add a failing integration scenario**

Exercise this sequence in the existing browser harness when supported: clear the completion key, load the app, wait for `.driver-popover`, advance until pages 1–4 have appeared, finish, reload and assert the popover stays absent, open Settings, press the replay button, and assert it returns. If the current Python harness cannot run the built Vue app with Driver.js, add the same scenario to `tutorial_driver.test.ts` using a minimal DOM and the injected adapter.

- [ ] **Step 2: Run and verify RED**

Run the exact selected test:

```powershell
uv run pytest tests/e2e/test_browser_workflow.py -q
```

or:

```powershell
cd webui
npm test -- tutorial_driver.test.ts
```

Expected: FAIL at the first missing first-run/replay integration behavior.

- [ ] **Step 3: Make only the wiring corrections exposed by the integration test**

Keep corrections inside the tutorial modules and event wiring. Do not relax assertions or add delays without a bounded DOM condition.

- [ ] **Step 4: Document tutorial startup and replay**

Add a “新手演示教程” section to `docs/USER_GUIDE.md` explaining first-run auto-start, non-destructive demo data, skip/completion behavior, Settings replay, and that no virtual controller signals are emitted during the tutorial.

- [ ] **Step 5: Run focused integration tests**

Run the selected integration command again.

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add webui/tests/tutorial_driver.test.ts tests/e2e/test_browser_workflow.py docs/USER_GUIDE.md webui/src
git commit -m "test(tutorial): cover first-run completion and replay"
```

### Task 8: Full verification and requirement audit

**Files:**
- Verify only; fix failures in the owning file and rerun the failing command before continuing.

- [ ] **Step 1: Run all frontend unit tests**

Run: `npm test`

Expected: all tests PASS, zero failures and no leaked-timer warnings.

- [ ] **Step 2: Run Vue and TypeScript checking**

Run: `npm run typecheck`

Expected: exit code 0 with no diagnostics.

- [ ] **Step 3: Build the production frontend**

Run: `npm run build`

Expected: exit code 0 and Vite writes `webui/dist`.

- [ ] **Step 4: Run the backend/browser regression suite**

Run from repository root: `uv run pytest -q`

Expected: all tests PASS. Environment-specific WGC skips are acceptable only when reported as skips, not failures.

- [ ] **Step 5: Audit requirements against the design**

Confirm directly in source/tests: first-run auto-start, Settings replay, 7 chapters, 4 page transitions, demo state isolation, no dangerous calls, completion versus interruption persistence, bilingual copy, missing target timeout, singleton cleanup, mobile styling, full report interpretation, and documented usage.

- [ ] **Step 6: Inspect the final diff and commit any verification-only fixes**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and only intended changes. If fixes were necessary:

```powershell
git add webui docs/USER_GUIDE.md tests/e2e/test_browser_workflow.py
git commit -m "fix(tutorial): resolve verification findings"
```
