# Unified Step Layout and Sticky Bottom Navigation Specification

## Background & Problem
In GameCurveProbe 2.0 WebUI, each of the 4 wizard steps currently manages its own navigation buttons and internal layout independently:
1. **Step 1 (Capture & ROI)**: The "Next Step" button is nested at the bottom of the right-hand diagnostic sidebar.
2. **Step 2 (Deadzone Calibration)**: The "Previous Step" and "Next Step" buttons are cramped into a 5-column space sharing a row with the Noise Floor Benchmark card.
3. **Step 3 (Curve Measurement)**: Navigation buttons are placed at the bottom, stretched across 100% of the container width (`flex-1`).
4. **Step 4 (Analysis & Export)**: Has no bottom navigation at all; user must locate a small text link in the top-right export card to re-run measurements.

This lack of structural consistency creates visual clutter and makes navigation unpredictable as the user progresses through the workflow.

## Objectives
1. **Centralized Sticky Bottom Navigation Bar**:
   - Provide a persistent, floating/docked bottom bar in `App.vue` that clearly centers the "Previous Step" (`上一步`) and "Next Step" (`下一步`) actions across all steps.
   - Decouple step navigation logic from individual step components.
   - Automatically adapt action labels, icons, and enablement/disabled tooltips based on current step requirements and state.
2. **Standardized Card & Column Layout Across Steps**:
   - **Step 1**: Remove the nested Next button from `CaptureStep.vue`. ROI diagnostics column expands naturally with clean padding.
   - **Step 2**: Remove the 5-column button block from `DeadzoneStep.vue`. The Noise Floor Benchmark card becomes a full-width, balanced diagnostic section.
   - **Step 3**: Remove full-width stretching buttons from `MeasurementStep.vue`. Content terminates cleanly at the live sampling data table.
   - **Step 4**: Provide unified back-navigation to Step 3 and action to re-run test or reset flow.
3. **Responsive Visual & Ergonomic Polish**:
   - Ensure `pb-24` / `pb-28` bottom padding on `<main>` so that tables and charts are never obscured by the sticky bottom bar.
   - Glassmorphism styling (`bg-white/90 backdrop-blur-md border-t border-neutral-200/80`) consistent with the top header.
   - Maintain complete i18n support in both Chinese and English.

## Architecture & Data Flow

```
+-------------------------------------------------------------+
| App.vue Top Navigation Header (HWND, ViGEm, Hotkeys, Lang)  |
+-------------------------------------------------------------+
| App.vue Wizard Step Indicator Tabs (1. 2. 3. 4.)            |
+-------------------------------------------------------------+
| <main class="pb-28">                                        |
|   +-------------------------------------------------------+ |
|   | Active Step Component                                 | |
|   |  - Step 1: CaptureStep.vue (Window & ROI)             | |
|   |  - Step 2: DeadzoneStep.vue (Dual Thumb & Noise)      | |
|   |  - Step 3: MeasurementStep.vue (Live Sampling)        | |
|   |  - Step 4: AnalysisStep.vue (Curves, Fits & Export)   | |
|   +-------------------------------------------------------+ |
| </main>                                                     |
+-------------------------------------------------------------+
| Sticky Bottom Navigation Bar (App.vue)                      |
| [  <- 上一步: [Previous Step Title]  ]  [  下一步: [Next Step Title] ->  ] |
+-------------------------------------------------------------+
```

### Navigation Rules Matrix

| Step | Previous Button | Next / Primary Action Button | Next Disabled Condition |
| :--- | :--- | :--- | :--- |
| **Step 1: Capture** | *Hidden* | `下一步：手柄死区标定` (proceed_to_deadzone) | No window captured OR No ROI selected OR ROI quality score < 25 |
| **Step 2: Deadzone** | `← 返回：窗口与抓图` | `下一步：曲线测定` (proceed_to_measurement) | Enabled (user can proceed anytime) |
| **Step 3: Measurement** | `← 返回：死区标定` (Disabled while running) | `下一步：拟合分析` (proceed_to_analysis) | Active measurement running OR No completed session result |
| **Step 4: Analysis** | `← 返回：曲线测定` | `重新测定 ↺` / `重测曲线` | Enabled (jumps back to Step 3 for new run) |

## Implementation Scope
1. **`webui/src/App.vue`**:
   - Introduce `canProceed` computed logic based on `sessionStore.capture`, `sessionStore.roi`, `sessionStore.roiQuality`, `sessionStore.activeJob`, and `sessionStore.lastResult`.
   - Add the sticky footer with smooth transitions, centered flex layout, and keyboard-accessible buttons.
   - Adjust `<main>` padding bottom to prevent occlusion.
2. **`webui/src/components/CaptureStep.vue`**:
   - Remove `<div class="pt-2"><button @click="proceedToDeadzone">...</div>`.
   - Keep ROI quality badge, coordinates, and recommendations cleanly aligned.
3. **`webui/src/components/DeadzoneStep.vue`**:
   - Replace the split 7-col / 5-col bottom grid with a unified, full-width Noise Benchmark card matching the visual polish of upper cards.
   - Remove `goBack()` and `proceedToMeasurement()` calls from component.
4. **`webui/src/components/MeasurementStep.vue`**:
   - Remove the bottom navigation buttons row (`flex items-center space-x-4 pt-2`).
5. **`webui/src/components/AnalysisStep.vue`**:
   - Verify layout consistency and ensure restart actions interact seamlessly with the sticky bottom bar.
6. **`webui/src/services/i18n.ts`**:
   - Add missing localized labels for unified previous/next actions if needed.
7. **Verification**:
   - Verify with Vitest (`npm test` in `webui/`).
   - Validate TypeScript compilation (`npm run typecheck`).
   - Verify live behavior and appearance in the active Vite dev server.
