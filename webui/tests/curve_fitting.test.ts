import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
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
    expect(Number(report!.best.params.boostRatio)).toBeGreaterThan(3.0)
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

  it('handles extreme outlier spikes without contaminating vMin/vMax normalization', () => {
    // 正常速度 0 ~ 1000 px/s，中间注入一个 50,000 px/s 的极端毛刺
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      let velocity = input * 1000
      if (i === 8) velocity = 50000 // 极端异常尖峰
      return { input, velocity_px_s: velocity, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()
    expect(report!.outlierInputs).toContain(0.4)

    // 验证生成曲线的最大速度不会被 50000 污染，最大速度应在 1000 左右
    const maxY = Math.max(...report!.best.curvePoints.map((p) => p[1]))
    expect(maxY).toBeLessThan(1200)
    expect(maxY).toBeGreaterThan(900)
  })

  it('handles deadzone boundaries safely and rejects invalid/insufficient ranges', () => {
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      return { input, velocity_px_s: input * 1000, valid: true }
    })

    // inner=0.99, outer=1.00 -> range = 0.01 < 0.02, should return null
    expect(fitResponseCurve(points, 0.99, 1.0)).toBeNull()

    // inner=0.8, outer=0.2 (inverted) -> should return null
    expect(fitResponseCurve(points, 0.8, 0.2)).toBeNull()

    // inner=0.2, outer=0.8 -> valid, all curve points x should be within [0.2, 0.8]
    const report = fitResponseCurve(points, 0.2, 0.8)
    expect(report).not.toBeNull()
    const xs = report!.best.curvePoints.map((p) => p[0])
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(0.199)
    expect(Math.max(...xs)).toBeLessThanOrEqual(0.801)
  })

  it('gracefully returns null when velocity range is zero (flat / stationary)', () => {
    const points = Array.from({ length: 21 }, (_, i) => ({
      input: i * 0.05,
      velocity_px_s: 500, // 全行程静止/匀速
      valid: true,
    }))
    expect(fitResponseCurve(points, 0.0, 1.0)).toBeNull()
  })

  it('guarantees piecewise curve predictions never exceed normalized range [0, 1]', () => {
    // 快速剧增的分段曲线
    const points = Array.from({ length: 21 }, (_, i) => {
      const input = i * 0.05
      const velocity = input < 0.8 ? input * 500 : 400 + (input - 0.8) * 10000
      return { input, velocity_px_s: velocity, valid: true }
    })
    const report = fitResponseCurve(points, 0.0, 1.0)
    expect(report).not.toBeNull()

    const pw1 = report!.candidates.piecewise1
    const maxV = Math.max(...points.map((p) => p.velocity_px_s))
    for (const [, y] of pw1.curvePoints) {
      expect(y).toBeLessThanOrEqual(maxV + 1e-4)
      expect(y).toBeGreaterThanOrEqual(0)
    }
  })

  it('does not reject normal low-speed measurement jitter', () => {
    const points = Array.from({ length: 9 }, (_, i) => {
      const input = i / 8
      const jitter = [0, 0.8, -0.6, 1.1, -0.9, 0.7, -0.5, 0.6, 0][i]
      return { input, velocity_px_s: input * 8 + jitter, valid: true }
    })
    const report = fitResponseCurve(points, 0, 1)
    expect(report).not.toBeNull()
    expect(report!.outlierInputs).toEqual([])
  })

  it('still rejects a relative spike when absolute velocities are small', () => {
    const points = Array.from({ length: 9 }, (_, i) => {
      const input = i / 8
      const velocity = input * 0.1 + (i === 4 ? 2 : 0)
      return { input, velocity_px_s: velocity, valid: true }
    })
    const report = fitResponseCurve(points, 0, 1)
    expect(report).not.toBeNull()
    expect(report!.outlierInputs).toContain(0.5)
  })
})

describe('Mock curve dataset validation', () => {
  const mockDir = path.resolve(__dirname, '../../mock_curves')

  it('correctly fits 01_linear_standard.json as linear', () => {
    const raw = fs.readFileSync(path.join(mockDir, '01_linear_standard.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(report!.best.type).toBe('linear')
    expect(report!.best.r2).toBeGreaterThan(0.99)
    expect(report!.outlierInputs).toHaveLength(0)
  })

  it('correctly fits 02_piecewise1_outer_boost.json as piecewise1 or bezier with outer inflection', () => {
    const raw = fs.readFileSync(path.join(mockDir, '02_piecewise1_outer_boost.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(['piecewise1', 'bezier']).toContain(report!.best.type)
    expect(report!.candidates.piecewise1.r2).toBeGreaterThan(0.98)
    expect(report!.candidates.piecewise1.breakpoints![0]).toBeGreaterThanOrEqual(0.88)
    expect(report!.candidates.piecewise1.breakpoints![0]).toBeLessThanOrEqual(0.96)
  })

  it('correctly fits 03_power_exponential_concave.json as power', () => {
    const raw = fs.readFileSync(path.join(mockDir, '03_power_exponential_concave.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(['power', 'bezier']).toContain(report!.best.type)
    expect(report!.candidates.power.r2).toBeGreaterThan(0.98)
    expect(Number(report!.candidates.power.params.gamma)).toBeCloseTo(2.0, 0.2)
  })

  it('correctly fits 04_piecewise2_three_stage.json as piecewise2 or bezier', () => {
    const raw = fs.readFileSync(path.join(mockDir, '04_piecewise2_three_stage.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(['piecewise2', 'bezier']).toContain(report!.best.type)
    expect(report!.candidates.piecewise2.r2).toBeGreaterThan(0.98)
  })

  it('correctly fits 05_bezier_smooth_s_curve.json with high fidelity', () => {
    const raw = fs.readFileSync(path.join(mockDir, '05_bezier_smooth_s_curve.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(report!.candidates.bezier.r2).toBeGreaterThan(0.98)
  })

  it('detects both glitches in 06_linear_with_frame_glitch_outliers.json without corrupting linear fit', () => {
    const raw = fs.readFileSync(path.join(mockDir, '06_linear_with_frame_glitch_outliers.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    // Must detect the outliers
    expect(report!.outlierInputs).toContain(0.36)
    expect(report!.outlierInputs).toContain(0.72)
    // Base fit should still be linear with high R^2
    expect(report!.best.type).toBe('linear')
    expect(report!.best.r2).toBeGreaterThan(0.98)
  })

  it('handles deadzones in 07_deadzone_shift_dynamic.json', () => {
    const raw = fs.readFileSync(path.join(mockDir, '07_deadzone_shift_dynamic.json'), 'utf-8')
    const data = JSON.parse(raw)
    const report = fitResponseCurve(data.points, data.config.inner_deadzone, data.config.outer_deadzone)
    expect(report).not.toBeNull()
    expect(report!.candidates.linear.r2).toBeGreaterThan(0.98)
    // Points within deadzones should be handled smoothly
    expect(report!.best.curvePoints[0][0]).toBeGreaterThanOrEqual(data.config.inner_deadzone)
    expect(report!.best.curvePoints[report!.best.curvePoints.length - 1][0]).toBeLessThanOrEqual(data.config.outer_deadzone + 1e-3)
  })
})
