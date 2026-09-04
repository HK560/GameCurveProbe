# 游戏手柄响应曲线自动拟合估算与可视化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现游戏手柄响应曲线的前端轻量级自动拟合与估算引擎，支持纯线性、凹曲线/幂函数、1点折线（额外加速型）、2点折线和贝塞尔曲线，自动剔除离群噪点并基于 BIC 准则评选最优模型，并在 ECharts 图表中叠加高亮平滑拟合线与拐点标注，提供多模型对比切换与游戏参数反推展示。

**Architecture:** 
- 拟合计算层：`webui/src/services/curveFitting.ts` 纯 TypeScript 实现数值优化、MAD 异常点过滤、分段线性拐点搜索、贝塞尔插值与 BIC 打分评选。
- 国际化与配置层：`webui/src/services/i18n.ts` 补全各拟合模型、拐点参数、加速比与图例的多语言文案。
- 图表渲染层：`webui/src/components/CurveChart.vue` 支持接收拟合平滑点序列与拐点位置，渲染青蓝色拟合实线与垂直加速指示虚线。
- 分析与交互面板：`webui/src/components/AnalysisStep.vue` 实时联动死区滑块计算最优模型，展示参数解析胶囊，提供模型切换单选组供用户对比。

**Tech Stack:** Vue 3 (Composition API), TypeScript, ECharts 5, TailwindCSS 4, Vitest.

## Global Constraints
- 必须纯前端 TS 求解，单次拟合耗时不得超过 5ms，确保拖动死区滑块时 60fps 零卡顿。
- 不引入重型外部数学依赖库（如 mathjs），全部采用纯原生向量/矩阵运算与精简优化器。
- ECharts 渲染保持平滑（`smooth: true`），原始离散采样点与拟合曲线分层分色渲染。

---

### Task 1: 曲线拟合数学引擎与异常点过滤核心模块 (`webui/src/services/curveFitting.ts`)

**Files:**
- Create: `webui/src/services/curveFitting.ts`
- Test: `webui/tests/curve_fitting.test.ts`

**Interfaces:**
- Produces:
  ```typescript
  export type FitModelType = 'linear' | 'power' | 'piecewise1' | 'piecewise2' | 'bezier'
  export interface FitCandidate {
    type: FitModelType
    name: string
    nrmse: number
    r2: number
    bic: number
    confidence: number
    params: Record<string, number | string>
    breakpoints?: number[] // 物理推杆输入坐标 (0.0 - 1.0)
    curvePoints: [number, number][] // [x_input, y_speed_px_s] 供绘图的平滑插值点 (100点)
  }
  export interface CurveFitReport {
    best: FitCandidate
    candidates: Record<FitModelType, FitCandidate>
    outlierInputs: number[] // 被识别为离群点的物理 input 坐标
  }
  export function fitResponseCurve(
    points: { input: number; velocity_px_s: number | null; valid: boolean }[],
    innerDz?: number,
    outerDz?: number
  ): CurveFitReport | null
  ```

- [ ] **Step 1: Write the failing tests in `webui/tests/curve_fitting.test.ts`**

```typescript
import { describe, it, expect } from 'vitest'
import { fitResponseCurve } from '../src/services/curveFitting'

describe('curveFitting engine', () => {
  it('identifies pure linear curve with low nrmse and selects linear model', () => {
    // 0% - 100% 匀速线性上升
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      return { input, velocity_px_s: input * 1000, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()
    expect(report!.best.type).toBe('linear')
    expect(report!.best.r2).toBeGreaterThan(0.99)
    expect(report!.best.curvePoints.length).toBe(100)
  })

  it('identifies 1-breakpoint piecewise linear (outer threshold acceleration)', () => {
    // 0% - 90% 斜率 1000, 90% - 100% 斜率 6000 (典型 Apex/Halo 额外加速)
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      let velocity = 0
      if (input <= 0.9) {
        velocity = input * 1000 // 0 -> 900
      } else {
        velocity = 900 + (input - 0.9) * 6000 // 900 -> 1500
      }
      return { input, velocity_px_s: velocity, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()
    expect(report!.best.type).toBe('piecewise1')
    expect(report!.best.breakpoints).toBeDefined()
    expect(report!.best.breakpoints![0]).toBeCloseTo(0.9, 1)
    expect(report!.best.params.boostRatio).toBeGreaterThan(3.0)
  })

  it('identifies power curve (exponential / classic curve)', () => {
    // y = x^2 凹曲线
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      return { input, velocity_px_s: Math.pow(input, 2) * 1000, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()
    expect(report!.best.type).toBe('power')
    expect(Number(report!.best.params.gamma)).toBeCloseTo(2.0, 0.2)
  })

  it('rejects outliers without dragging the linear curve down', () => {
    // 线性点集 + 一个中间恶劣离群噪点 (丢帧)
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      let velocity = input * 1000
      if (i === 10) velocity = 200 // 明显凹坑异常点
      return { input, velocity_px_s: velocity, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()
    expect(report!.outlierInputs).toContain(0.5)
    expect(report!.best.type).toBe('linear')
    expect(report!.best.r2).toBeGreaterThan(0.98)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pnpm test tests/curve_fitting.test.ts`
Expected: FAIL with "Cannot find module '../src/services/curveFitting'"

- [ ] **Step 3: Implement `webui/src/services/curveFitting.ts`**
包含 MAD 异常检测、5 大模型拟合器（线性解析解、幂函数黄金分割搜索、1点折线分段扫描、2点折线双拐点扫描、三次贝塞尔参数拟合）、BIC 评价与 100 点物理坐标反变换插值。

- [ ] **Step 4: Run test to verify it passes**
Run: `pnpm test tests/curve_fitting.test.ts`
Expected: PASS (all 4 tests passing)

- [ ] **Step 5: Commit**
```bash
git add webui/src/services/curveFitting.ts webui/tests/curve_fitting.test.ts
git commit -m "feat: implement robust curve fitting engine with 5 models and outlier rejection"
```

---

### Task 2: 多语言支持与类型定义更新 (`webui/src/services/i18n.ts`)

**Files:**
- Modify: `webui/src/services/i18n.ts`
- Test: `webui/tests/i18n_nav.test.ts`

**Interfaces:**
- Produces i18n keys for:
  - `model_auto_label`, `model_linear_label`, `model_power_label`, `model_piecewise1_label`, `model_piecewise2_label`, `model_bezier_label`
  - `model_piecewise1_desc`, `model_piecewise2_desc`, `model_power_desc`, `model_linear_desc`, `model_bezier_desc`
  - `metric_accel_threshold`, `metric_accel_ratio`, `metric_base_slope`, `metric_gamma`, `metric_r2`, `metric_confidence`
  - `series_fitted_curve`, `breakpoint_accel_label`, `outlier_point_tag`

- [ ] **Step 1: Add translation keys for Chinese (zh-CN) and English (en-US)**
In `webui/src/services/i18n.ts`, add:
- zh-CN:
  - `series_fitted_curve`: '🎯 估算拟合曲线'
  - `model_auto_label`: '自动推荐'
  - `model_piecewise1_label`: '折线 (1拐点/额外加速)'
  - `model_piecewise1_desc`: '主段匀速，末端达到阈值后触发高倍率额外转动加速（常见于 Apex、Titanfall、Halo 等）。'
  - `model_piecewise2_label`: '折线 (2拐点/三段式)'
  - `model_piecewise2_desc`: '包含微调启动段、中间平稳巡航段与末端极限加速段。'
  - `model_power_label`: '幂函数凹曲线 (Classic/Exponential)'
  - `model_power_desc`: '中心推杆小幅微调细腻，推杆行程过半后速度渐进非线性放大。'
  - `model_bezier_label`: '三次贝塞尔曲线 (Custom Bézier)'
  - `model_bezier_desc`: '两控制点平滑 S 型或缓入缓出自定义曲线。'
  - `metric_accel_threshold`: '加速触发阈值'
  - `metric_accel_ratio`: '额外加速倍率'
  - `metric_base_slope`: '基础巡航速度'
  - `metric_gamma`: '曲率指数 γ'
  - `outlier_point_tag`: '⚠️ 采样偏差过大（已在拟合中忽略）'
- en-US 相应对照。

- [ ] **Step 2: Verify `webui/tests/i18n_nav.test.ts` still passes**
Run: `pnpm test tests/i18n_nav.test.ts`
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add webui/src/services/i18n.ts
git commit -m "feat(i18n): add translations for curve fitting models and metrics"
```

---

### Task 3: 图表拟合曲线与拐点指示线渲染 (`webui/src/components/CurveChart.vue`)

**Files:**
- Modify: `webui/src/components/CurveChart.vue`
- Test: `webui/tests/chart_series.test.ts`

**Interfaces:**
- Consumes:
  - `props.fittedCurve?: [number, number][]`
  - `props.breakpoints?: number[]`
  - `props.outlierInputs?: number[]`
- Produces:
  - ECharts series: `t('series_fitted_curve')`
  - MarkLine: vertical dashed lines for each breakpoint
  - Tooltip: outlier marker tag

- [ ] **Step 1: Write test for fitted curve series creation in `webui/tests/chart_series.test.ts`**
Verify that when `fittedCurve` and `breakpoints` are provided, the ECharts options include the fitted curve line series and mark lines.

- [ ] **Step 2: Update `webui/src/components/CurveChart.vue`**
- Extend `props` with `fittedCurve`, `breakpoints`, `outlierInputs`.
- In `updateChart()`:
  - If `props.fittedCurve && props.fittedCurve.length > 0`, append a line series:
    ```typescript
    {
      name: t('series_fitted_curve'),
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: props.fittedCurve,
      lineStyle: {
        color: '#06b6d4', // cyan-500
        width: 2.5,
        shadowColor: 'rgba(6, 182, 212, 0.3)',
        shadowBlur: 6,
      },
      itemStyle: { color: '#06b6d4' },
      z: 4,
    }
    ```
  - For each `bp` in `props.breakpoints`, add a markLine with cyan dashed line and label `⚡ ${(bp*100).toFixed(1)}%`.
  - In tooltip formatter: if current x is close to any `props.outlierInputs`, show the outlier badge `⚠️ 已忽略偏差点`.

- [ ] **Step 3: Run vitest to verify tests pass**
Run: `pnpm test`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add webui/src/components/CurveChart.vue webui/tests/chart_series.test.ts
git commit -m "feat(ui): render fitted curve and breakpoint marklines in CurveChart"
```

---

### Task 4: 分析步骤面板参数解析与模型选择器 (`webui/src/components/AnalysisStep.vue`)

**Files:**
- Modify: `webui/src/components/AnalysisStep.vue`
- Test: `webui/tests/sampling_points.test.ts` (or dedicated component test)

**Interfaces:**
- Consumes: `fitResponseCurve` from `../services/curveFitting`
- Renders:
  - `activeModelType` ref (`'auto' | FitModelType`)
  - Auto recommendation badge & confidence badge
  - Parameter cards: e.g. Breakpoint / Boost Ratio / Gamma / R²
  - Model switcher pills: `[⭐ 自动] [线性] [幂函数] [1点折线] [2点折线] [贝塞尔]`
  - Passes `activeFittedCurve`, `activeBreakpoints`, `outlierInputs` to `<CurveChart />`

- [ ] **Step 1: Integrate `fitResponseCurve` in `AnalysisStep.vue`**
- Replace the legacy simplistic `recalculatedAnalysis` with `fitResponseCurve(recalculatedPoints, analysisInnerDeadzone, analysisOuterDeadzone)`.
- Add `selectedModelType = ref<'auto' | FitModelType>('auto')`.
- Compute `activeCandidate`: when `selectedModelType.value === 'auto'`, use `report.best`; otherwise use `report.candidates[selectedModelType.value]`.

- [ ] **Step 2: Add UI controls in `AnalysisStep.vue`**
- Above the chart or inside the Analysis Summary card, render:
  1. A pill toggle row allowing the user to select between `[⭐ 自动: {best.name}]`, `[线性]`, `[幂函数]`, `[1点折线]`, `[2点折线]`, `[贝塞尔]`.
  2. A parameter display strip showing:
     - 置信度 (`Confidence`)
     - 拟合优度 ($R^2$)
     - 若为折线：加速阈值 (例如 $94.2\%$)、额外加速比 (例如 $6.8\times$)、基础巡航速度
     - 若为幂函数：响应系数 $\gamma$ (例如 $1.85$)
  3. Pass `fittedCurve`, `breakpoints`, `outlierInputs` to `<CurveChart>`.

- [ ] **Step 3: Run vitest & vue-tsc typecheck**
Run: `pnpm run typecheck && pnpm test`
Expected: 0 errors, all tests pass.

- [ ] **Step 4: Commit**
```bash
git add webui/src/components/AnalysisStep.vue
git commit -m "feat(ui): add model comparison switcher and parameter badges in AnalysisStep"
```

---

### Task 5: 整体端到端验证与视觉检查

- [ ] **Step 1: Run complete automated test suite**
Run: `pnpm test`
Expected: all tests passing.

- [ ] **Step 2: Verify in browser**
启动 Vite 开发服务器并打开测定报告页，检查：
1. 载入包含尾端突变加速的数据点时，系统自动选中并高亮“折线 (1拐点/额外加速)”，正确标出拐点。
2. 拖动内/外死区滑块，曲线拟合与拐点实时更新无卡顿。
3. 点击切换其他模型（如“纯线性”或“贝塞尔”），图表拟合曲线即刻切换。
