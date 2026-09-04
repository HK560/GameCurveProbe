# Unified Step Layout and Sticky Bottom Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a consistent, polished layout across all 4 wizard steps with a centralized sticky bottom navigation bar hosting "上一步" (Previous Step) and "下一步" (Next Step) buttons.

**Architecture:** Move wizard progression responsibility out of individual step components (`CaptureStep.vue`, `DeadzoneStep.vue`, `MeasurementStep.vue`, `AnalysisStep.vue`) into `App.vue`. In `App.vue`, implement a sticky bottom navigation bar (`sticky bottom-0`) with glassmorphism styling, centered actions, and reactive enablement logic based on session store state.

**Tech Stack:** Vue 3 (Composition API `<script setup>`), TypeScript, TailwindCSS v4, Pinia, Lucide Icons, Vitest.

## Global Constraints

- Never break existing step functionality or reactive state updates in `sessionStore`.
- Keep complete i18n support for both Chinese (`zh`) and English (`en`).
- Maintain WCAG contrast and button accessibility standards.
- Add `pb-28` bottom spacing to `<main>` to prevent tables, charts, or inputs from being clipped by the sticky bottom bar.

---

### Task 1: Add and Verify Localized Navigation Labels in i18n

**Files:**
- Modify: `webui/src/services/i18n.ts`
- Test: `webui/tests/i18n_nav.test.ts`

**Interfaces:**
- Produces: `back_to_capture`, `back_to_deadzone`, `back_to_measurement`, `proceed_to_deadzone`, `proceed_to_measurement`, `proceed_to_analysis`, `restart_test` in both `zh` and `en` message dictionaries.

- [x] **Step 1: Write unit test for navigation i18n keys**

```typescript
// webui/tests/i18n_nav.test.ts
import { describe, expect, it } from 'vitest'
import { messages } from '../src/services/i18n'

describe('Navigation i18n keys', () => {
  const requiredKeys = [
    'back_to_capture',
    'back_to_deadzone',
    'back_to_measurement',
    'proceed_to_deadzone',
    'proceed_to_measurement',
    'proceed_to_analysis',
    'restart_test',
  ] as const

  it('contains all navigation keys in zh', () => {
    for (const key of requiredKeys) {
      expect((messages.zh as any)[key]).toBeDefined()
      expect((messages.zh as any)[key].length).toBeGreaterThan(0)
    }
  })

  it('contains all navigation keys in en', () => {
    for (const key of requiredKeys) {
      expect((messages.en as any)[key]).toBeDefined()
      expect((messages.en as any)[key].length).toBeGreaterThan(0)
    }
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm --dir webui test run tests/i18n_nav.test.ts`
Expected: FAIL due to missing keys in `messages.zh` / `messages.en`.

- [x] **Step 3: Update `webui/src/services/i18n.ts`**

Add navigation keys in `messages.zh`:
```typescript
    back_to_capture: '返回：窗口与抓图',
    back_to_deadzone: '返回：死区标定',
    back_to_measurement: '返回：曲线测定',
    proceed_to_deadzone: '下一步：死区标定',
    proceed_to_measurement: '下一步：曲线测定',
    proceed_to_analysis: '下一步：拟合分析',
    restart_test: '重新测定',
```
And in `messages.en`:
```typescript
    back_to_capture: 'Back: Window & Capture',
    back_to_deadzone: 'Back: Deadzone',
    back_to_measurement: 'Back: Measurement',
    proceed_to_deadzone: 'Next: Deadzone Calibration',
    proceed_to_measurement: 'Next: Curve Measurement',
    proceed_to_analysis: 'Next: Fit & Analysis',
    restart_test: 'Re-measure Curve',
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm --dir webui test run tests/i18n_nav.test.ts`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add webui/src/services/i18n.ts webui/tests/i18n_nav.test.ts
git commit -m "feat(i18n): add localized step navigation labels"
```

---

### Task 2: Clean Up Step 1 (CaptureStep.vue) Layout

**Files:**
- Modify: `webui/src/components/CaptureStep.vue`

**Interfaces:**
- Consumes: `sessionStore.roi`, `sessionStore.capture`, `sessionStore.roiQuality`
- Produces: Cleaner right-hand diagnostic panel without nested next button; exposes ROI quality cleanly.

- [x] **Step 1: Inspect and remove nested proceed button**

In `webui/src/components/CaptureStep.vue`:
- Remove `proceedToDeadzone()` function.
- Remove `<div class="pt-2"><button @click="proceedToDeadzone" ...></div>`.
- Adjust right-side column `<div class="lg:col-span-4 space-y-4">` so it displays ROI diagnostic tools and coordinates without trailing bottom action button.

- [x] **Step 2: Run typecheck**

Run: `pnpm --dir webui run typecheck`
Expected: PASS with 0 errors.

- [x] **Step 3: Commit**

```bash
git add webui/src/components/CaptureStep.vue
git commit -m "refactor(capture): remove nested next button to unify step layout"
```

---

### Task 3: Clean Up Step 2 (DeadzoneStep.vue) Layout

**Files:**
- Modify: `webui/src/components/DeadzoneStep.vue`

**Interfaces:**
- Consumes: `sessionStore.noise`, `sessionStore.startIdleNoise`
- Produces: Full-width, clean Noise Benchmark card.

- [x] **Step 1: Remove 5-column button section and expand Noise card**

In `webui/src/components/DeadzoneStep.vue`:
- Remove `goBack()` and `proceedToMeasurement()` functions and unused arrow icon imports.
- Replace the bottom split row:
```html
<div class="p-4 bg-white border border-neutral-200/80 rounded-xl space-y-2.5 shadow-xs">
  <div class="flex items-center justify-between">
    <div class="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-neutral-600">
      <Activity class="w-3.5 h-3.5 text-neutral-700" />
      <span>{{ t('noise_calibration_title') }}</span>
    </div>
    <button
      type="button"
      @click="runNoiseBenchmark"
      :disabled="isMeasuringNoise"
      class="text-xs bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-white px-3 py-1.5 rounded-md transition cursor-pointer font-medium"
    >
      {{ isMeasuringNoise ? t('noise_measuring') : t('measure_noise') }}
    </button>
  </div>
  <p class="text-[11px] text-neutral-500">
    {{ t('noise_desc') }}
  </p>
  <div v-if="sessionStore.noise" class="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-lg text-xs font-mono text-neutral-700 flex justify-between">
    <span>{{ t('noise_x') }}: {{ sessionStore.noise.floor_x }} px/s</span>
    <span>{{ t('noise_y') }}: {{ sessionStore.noise.floor_y }} px/s</span>
  </div>
</div>
```

- [x] **Step 2: Run typecheck**

Run: `pnpm --dir webui run typecheck`
Expected: PASS with 0 errors.

- [x] **Step 3: Commit**

```bash
git add webui/src/components/DeadzoneStep.vue
git commit -m "refactor(deadzone): clean up bottom navigation buttons and expand noise card"
```

---

### Task 4: Clean Up Step 3 (MeasurementStep.vue) and Step 4 (AnalysisStep.vue) Layouts

**Files:**
- Modify: `webui/src/components/MeasurementStep.vue`
- Modify: `webui/src/components/AnalysisStep.vue`

**Interfaces:**
- Consumes: `sessionStore.activeStep`, `sessionStore.lastResult`
- Produces: Clean bottom table layout in Step 3 and seamless navigation handoff in Step 4.

- [x] **Step 1: Remove bottom full-width button row in MeasurementStep.vue**

In `webui/src/components/MeasurementStep.vue`:
- Remove `goBack()` and `proceedToAnalysis()` functions.
- Remove `<div class="flex items-center space-x-4 pt-2">` block containing the full-width previous/next buttons.

- [x] **Step 2: Verify AnalysisStep.vue layout alignment**

In `webui/src/components/AnalysisStep.vue`:
- Ensure top summary banner and export card are visually balanced and margins consistent with `space-y-6`.

- [x] **Step 3: Run typecheck and test**

Run: `pnpm --dir webui run typecheck`
Expected: PASS with 0 errors.

- [x] **Step 4: Commit**

```bash
git add webui/src/components/MeasurementStep.vue webui/src/components/AnalysisStep.vue
git commit -m "refactor(measurement): remove redundant bottom navigation buttons"
```

---

### Task 5: Implement Centralized Sticky Bottom Navigation Bar in App.vue

**Files:**
- Modify: `webui/src/App.vue`

**Interfaces:**
- Consumes: `sessionStore.activeStep`, `sessionStore.capture`, `sessionStore.roi`, `sessionStore.roiQuality`, `sessionStore.activeJob`, `sessionStore.lastResult`
- Produces: Sticky bottom bar with centered buttons:
  - Previous button (steps 2, 3, 4): `<button @click="navigatePrev">...`
  - Next button (steps 1, 2, 3, 4): `<button @click="navigateNext">...`

- [x] **Step 1: Implement navigation computed properties and handlers in `App.vue`**

In `<script setup>` of `webui/src/App.vue`:
```typescript
import { ArrowLeft, ArrowRight, RotateCcw } from 'lucide-vue-next'

const canGoPrev = computed(() => {
  if (sessionStore.activeStep <= 1) return false
  if (sessionStore.activeStep === 3 && sessionStore.activeJob !== null) return false
  return true
})

const canGoNext = computed(() => {
  switch (sessionStore.activeStep) {
    case 1:
      return Boolean(
        sessionStore.capture &&
        sessionStore.roi &&
        (sessionStore.roiQuality ? sessionStore.roiQuality.score >= 25 : true)
      )
    case 2:
      return true
    case 3:
      return Boolean(sessionStore.activeJob === null && sessionStore.lastResult)
    case 4:
      return true
    default:
      return false
  }
})

function navigatePrev() {
  if (!canGoPrev.value) return
  if (sessionStore.activeStep > 1) {
    sessionStore.activeStep--
  }
}

function navigateNext() {
  if (!canGoNext.value) return
  if (sessionStore.activeStep < 4) {
    sessionStore.activeStep++
  } else if (sessionStore.activeStep === 4) {
    // Jump to step 3 to measure again
    sessionStore.activeStep = 3
  }
}
```

- [x] **Step 2: Add template markup for the Sticky Bottom Bar**

In `webui/src/App.vue`:
- Add `pb-28` to `<main>` container class.
- Add sticky bottom bar below `<main>`:
```html
<footer class="sticky bottom-0 z-40 bg-white/90 backdrop-blur-md border-t border-neutral-200/80 shadow-xs py-3 px-4">
  <div class="max-w-7xl mx-auto flex items-center justify-center gap-4">
    <!-- Previous Step Button -->
    <button
      v-if="sessionStore.activeStep > 1"
      type="button"
      @click="navigatePrev"
      :disabled="!canGoPrev"
      class="min-w-[150px] inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium text-neutral-700 transition cursor-pointer shadow-xs"
    >
      <ArrowLeft class="w-4 h-4" />
      <span>
        {{
          sessionStore.activeStep === 2
            ? t('back_to_capture')
            : sessionStore.activeStep === 3
            ? t('back_to_deadzone')
            : t('back_to_measurement')
        }}
      </span>
    </button>

    <!-- Next / Action Button -->
    <button
      type="button"
      @click="navigateNext"
      :disabled="!canGoNext"
      class="min-w-[150px] inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium text-white transition cursor-pointer shadow-xs"
    >
      <span>
        {{
          sessionStore.activeStep === 1
            ? t('proceed_to_deadzone')
            : sessionStore.activeStep === 2
            ? t('proceed_to_measurement')
            : sessionStore.activeStep === 3
            ? t('proceed_to_analysis')
            : t('restart_test')
        }}
      </span>
      <RotateCcw v-if="sessionStore.activeStep === 4" class="w-4 h-4" />
      <ArrowRight v-else class="w-4 h-4" />
    </button>
  </div>
</footer>
```

- [x] **Step 3: Run typecheck and tests**

Run: `pnpm --dir webui run typecheck`
Run: `pnpm --dir webui test run`
Expected: All tests PASS.

- [x] **Step 4: Commit**

```bash
git add webui/src/App.vue
git commit -m "feat(layout): implement centralized sticky bottom navigation bar"
```

---

### Task 6: Comprehensive Verification & Visual Check

**Files:**
- Test: All webui tests

- [x] **Step 1: Execute all tests**

Run: `pnpm --dir webui test run`
Expected: PASS.

- [x] **Step 2: Execute build validation**

Run: `pnpm --dir webui run build`
Expected: Clean build into `webui/dist` without type errors or warnings.

- [x] **Step 3: Commit build verification**

```bash
git add docs/superpowers/plans/2026-09-04-unified-step-layout-navigation.md
git commit -m "docs: complete implementation plan for unified step layout and sticky navigation"
```
