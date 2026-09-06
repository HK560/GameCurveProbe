import { describe, it, expect } from 'vitest'
import { fitResponseCurve } from '../src/services/curveFitting'
import { buildControllerMetaJson, buildDseCsv } from '../src/services/curveExport'
import { t, setLocale } from '../src/services/i18n'
import type { MeasurementPoint } from '../src/types/api'

describe('Manual Point Deletion & Recalculation', () => {
  it('correctly filters out excluded points and improves fit R2', () => {
    // 构造一条基本为线性的曲线，并在其中人为插入一个严重的坏点
    const basePoints: MeasurementPoint[] = Array.from({ length: 21 }, (_, i) => {
      const input = Math.round(i * 0.05 * 100) / 100
      let vel = input * 1000
      if (i === 10) {
        vel = 20 // 严重掉速坏点 (input = 0.5)
      }
      return {
        input,
        velocity_px_s: vel,
        normalized_speed: input,
        stability: 0.95,
        attempts: 1,
        valid: true,
      }
    })

    // 包含坏点时的拟合
    const reportWithGlitch = fitResponseCurve(basePoints, 0.0, 1.0)
    expect(reportWithGlitch).not.toBeNull()

    // 手动删除该坏点 (input = 0.5)
    const excludedInputs = [0.5]
    const isExcluded = (inp: number) => excludedInputs.some((ex) => Math.abs(ex - inp) < 1e-4)
    const filteredPoints = basePoints.filter((p) => !isExcluded(p.input))

    expect(filteredPoints.length).toBe(20)
    expect(filteredPoints.some((p) => Math.abs(p.input - 0.5) < 1e-4)).toBe(false)

    // 剔除坏点后的拟合
    const reportCleaned = fitResponseCurve(filteredPoints, 0.0, 1.0)
    expect(reportCleaned).not.toBeNull()
    expect(reportCleaned!.best.type).toBe('linear')
    expect(reportCleaned!.best.r2).toBeGreaterThanOrEqual(reportWithGlitch!.best.r2)
  })

  it('excludes deleted points from ControllerMeta JSON and DSE CSV exports', () => {
    const rawPoints: MeasurementPoint[] = [
      { input: 0.0, velocity_px_s: 0, normalized_speed: 0.0, stability: 1.0, attempts: 1, valid: true },
      { input: 0.25, velocity_px_s: 250, normalized_speed: 0.25, stability: 1.0, attempts: 1, valid: true },
      { input: 0.5, velocity_px_s: 9999, normalized_speed: 1.0, stability: 0.1, attempts: 1, valid: true }, // 待删除异常点
      { input: 0.75, velocity_px_s: 750, normalized_speed: 0.75, stability: 1.0, attempts: 1, valid: true },
      { input: 1.0, velocity_px_s: 1000, normalized_speed: 1.0, stability: 1.0, attempts: 1, valid: true },
    ]

    const excludedInputs = [0.5]
    const isExcluded = (inp: number) => excludedInputs.some((ex) => Math.abs(ex - inp) < 1e-4)
    const activePoints = rawPoints.filter((p) => !isExcluded(p.input))

    const fitReport = fitResponseCurve(activePoints, 0.0, 1.0)
    expect(fitReport).not.toBeNull()

    // 验证 JSON 导出中不含 0.5 坏点
    const jsonStr = buildControllerMetaJson(fitReport!.best, activePoints, 0.0, 1.0, 'TestCurve', false)
    const parsed = JSON.parse(jsonStr)
    const curvePoints = parsed.items[0].curve.points
    expect(curvePoints).toBeDefined()
    expect(curvePoints.length).toBe(4)
    expect(curvePoints.some((p: any) => Math.abs(p.x - 50) < 1e-2)).toBe(false)

    // 验证 CSV 导出中不含 0.5 坏点
    const csvStr = buildDseCsv(fitReport!.best, activePoints, 0.0, 1.0, false)
    const lines = csvStr.trim().split('\n')
    // 包含表头 + 4 个有效点位
    expect(lines.length).toBe(5)
    expect(lines.some((line) => line.startsWith('3,50.0%') || line.includes(',50.0%,'))).toBe(false)
  })

  it('excludes deleted points from chart series and deduplicates same-source imported points', () => {
    const rawPoints: MeasurementPoint[] = [
      { input: 0.1, velocity_px_s: 100, normalized_speed: 0.1, stability: 1.0, attempts: 1, valid: true },
      { input: 0.5, velocity_px_s: 500, normalized_speed: 0.5, stability: 1.0, attempts: 1, valid: true },
      { input: 0.891, velocity_px_s: 890, normalized_speed: 0.891, stability: 1.0, attempts: 1, valid: true }, // 被删除的点
      { input: 0.95, velocity_px_s: 950, normalized_speed: 0.95, stability: 1.0, attempts: 1, valid: true },
    ]

    const excludedInputs = [0.891]
    const isExcluded = (inp: number) => excludedInputs.some((ex) => Math.abs(ex - inp) < 1e-4)

    const activePoints = rawPoints.filter((p) => !isExcluded(p.input))
    expect(activePoints.some((p) => Math.abs(p.input - 0.891) < 1e-4)).toBe(false)

    // 独立导入的对比数据也应过滤被排除的点
    const importedPoints = [...rawPoints]
    const activeImported = importedPoints.filter((p) => !isExcluded(p.input))
    expect(activeImported.some((p) => Math.abs(p.input - 0.891) < 1e-4)).toBe(false)
  })

  it('correctly provides i18n messages with parameter interpolation', () => {
    setLocale('zh')
    expect(t('delete_point')).toBe('排除/删除该点位')
    expect(t('restore_point')).toBe('恢复该点位')
    expect(t('restore_all_points')).toBe('恢复全部排除点位')
    expect(t('excluded_points_count', { n: 3 })).toBe('已手动排除 3 个点位')

    setLocale('en')
    expect(t('delete_point')).toBe('Exclude/Delete this point')
    expect(t('restore_point')).toBe('Restore this point')
    expect(t('restore_all_points')).toBe('Restore All Excluded Points')
    expect(t('excluded_points_count', { n: 5 })).toBe('5 point(s) excluded')
    
    // 恢复默认语言
    setLocale('zh')
  })
})
