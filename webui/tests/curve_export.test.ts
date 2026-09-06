import { describe, it, expect } from 'vitest'
import {
  buildMultiLayerControllerMetaJson,
  buildControllerMetaJson,
  buildDseCsv,
  buildNormalizedPolylinePoints,
  parseExportedCurveFile,
} from '../src/services/curveExport'
import { fitResponseCurve } from '../src/services/curveFitting'

describe('Curve Export and Multi-Layer Support', () => {
  const dummyPoints = Array.from({ length: 8 }, (_, idx) => ({
    input: idx / 7,
    velocity_px_s: (idx / 7) ** 1.5 * 500,
    normalized_speed: (idx / 7) ** 1.5,
    valid: true,
  }))

  it('builds valid Multi-Layer ControllerMeta JSON transfer bundle with 2 layers and exact point counts', () => {
    const report = fitResponseCurve(dummyPoints, 0.0, 1.0)
    expect(report).not.toBeNull()

    const bezierCandidate = report!.candidates.bezier

    const jsonStr = buildMultiLayerControllerMetaJson(
      bezierCandidate,
      dummyPoints,
      0.0,
      1.0,
      'Cubic Bezier',
      '实测点位 (归一化)',
      '拟合曲线'
    )
    const parsed = JSON.parse(jsonStr)

    expect(parsed.identifier).toBe('ControllerMeta')
    expect(parsed.exportKind).toBe('curve_transfer')
    expect(parsed.itemCount).toBe(2)
    expect(parsed.items).toHaveLength(2)

    // Layer 1: Measured Polyline (exactly 8 measured sample points, no deadzones)
    const layer1 = parsed.items[0].curve
    expect(layer1.kind).toBe('polyline')
    expect(layer1.name).toBe('实测点位 (归一化)')
    expect(layer1.color).toBe('#4f8cff')
    expect(layer1.innerDeadzone).toBe(0)
    expect(layer1.outerDeadzone).toBe(0)
    expect(layer1.points).toHaveLength(8)
    expect(layer1.points[0]).toEqual({ x: 0, y: 0 })
    expect(layer1.points[7]).toEqual({ x: 100, y: 100 })

    // Layer 2: Fitted Bezier Model (Native Bezier, 0 deadzones)
    const layer2 = parsed.items[1].curve
    expect(layer2.kind).toBe('bezier')
    expect(layer2.name).toBe('拟合曲线 (Cubic Bezier)')
    expect(layer2.color).toBe('#10b981')
    expect(layer2.innerDeadzone).toBe(0)
    expect(layer2.outerDeadzone).toBe(0)
    expect(layer2.bezier).toBeDefined()
  })

  it('builds concise keyPoints (<= 4 points) for piecewise and linear models instead of 100+ points', () => {
    const report = fitResponseCurve(dummyPoints, 0.0, 1.0)
    expect(report).not.toBeNull()

    // Linear model: exactly 2 endpoints
    const linearCandidate = report!.candidates.linear
    const jsonLinear = buildMultiLayerControllerMetaJson(linearCandidate, dummyPoints, 0.0, 1.0, 'Linear')
    const parsedLinear = JSON.parse(jsonLinear)
    expect(parsedLinear.items[1].curve.points).toHaveLength(2)

    // Piecewise1 model: exactly 3 keypoints
    const pw1Candidate = report!.candidates.piecewise1
    const jsonPw1 = buildMultiLayerControllerMetaJson(pw1Candidate, dummyPoints, 0.0, 1.0, 'Piecewise1')
    const parsedPw1 = JSON.parse(jsonPw1)
    expect(parsedPw1.items[1].curve.points).toHaveLength(3)

    // Piecewise2 model: exactly 4 keypoints
    const pw2Candidate = report!.candidates.piecewise2
    const jsonPw2 = buildMultiLayerControllerMetaJson(pw2Candidate, dummyPoints, 0.0, 1.0, 'Piecewise2')
    const parsedPw2 = JSON.parse(jsonPw2)
    expect(parsedPw2.items[1].curve.points).toHaveLength(4)
  })

  it('normalizes in-range valid points when inner and outer deadzones exclude edges (e.g. 12.5% -> 0%, 87.5% -> 100%)', () => {
    const rawPoints = [
      { input: 0.0, velocity_px_s: 0, normalized_speed: 0.0, in_analysis_range: false, valid: true },
      { input: 0.125, velocity_px_s: 15, normalized_speed: 0.0, in_analysis_range: true, valid: true },
      { input: 0.25, velocity_px_s: 68, normalized_speed: 0.06, in_analysis_range: true, valid: true },
      { input: 0.50, velocity_px_s: 300, normalized_speed: 0.32, in_analysis_range: true, valid: true },
      { input: 0.75, velocity_px_s: 660, normalized_speed: 0.73, in_analysis_range: true, valid: true },
      { input: 0.875, velocity_px_s: 893, normalized_speed: 1.0, in_analysis_range: true, valid: true },
      { input: 1.0, velocity_px_s: 820, normalized_speed: 1.0, in_analysis_range: false, valid: true },
    ]

    const normPoints = buildNormalizedPolylinePoints(rawPoints, 0.10, 0.88)
    // 只有处于死区内 (0.10 ~ 0.88) 的 5 个点参与导出
    expect(normPoints).toHaveLength(5)
    // 第一个在死区内的有效点 (12.5%) 归一化为 0%
    expect(normPoints[0]).toEqual({ x: 0, y: 0 })
    // 最后一个在死区内的有效点 (87.5%) 归一化为 100%
    expect(normPoints[4]).toEqual({ x: 100, y: 100 })
    // 中间点 50% 应该归一化到 (0.50 - 0.125) / (0.875 - 0.125) * 100 = 50.0%
    expect(normPoints[2].x).toBe(50)
  })

  it('normalizes X-axis fully to 100% across remaining points when last point is excluded (e.g. 85% -> 100%)', () => {
    // 假设排除了后面的坏点，当前剩余最后一个有效点是 85% (0.85)，速度归一化后是 100%
    const remainingPoints = [
      { input: 0.0, velocity_px_s: 0, normalized_speed: 0.0, valid: true },
      { input: 0.20, velocity_px_s: 80, normalized_speed: 0.10, valid: true },
      { input: 0.40, velocity_px_s: 200, normalized_speed: 0.25, valid: true },
      { input: 0.60, velocity_px_s: 420, normalized_speed: 0.55, valid: true },
      { input: 0.85, velocity_px_s: 800, normalized_speed: 1.00, valid: true }, // 当前最后一个有效点
    ]

    const normPoints = buildNormalizedPolylinePoints(remainingPoints, 0.0, 1.0)
    expect(normPoints).toHaveLength(5)
    // 首点归一化为 0%
    expect(normPoints[0]).toEqual({ x: 0, y: 0 })
    // 末点 85% 必须全部归一化为 100% 满量程！
    expect(normPoints[4]).toEqual({ x: 100, y: 100 })
    // 中间点按实际行程比例映射
    expect(normPoints[2].x).toBeCloseTo((0.4 / 0.85) * 100, 1)

    // 导出的 ControllerMeta JSON 也必须是 0 死区
    const jsonStr = buildMultiLayerControllerMetaJson(null, remainingPoints, 0.0, 1.0)
    const parsed = JSON.parse(jsonStr)
    expect(parsed.items[0].curve.innerDeadzone).toBe(0)
    expect(parsed.items[0].curve.outerDeadzone).toBe(0)
    expect(parsed.items[0].curve.points[4]).toEqual({ x: 100, y: 100 })
  })
})

describe('Curve Import and Reconstruction (parseExportedCurveFile)', () => {
  const dummyPoints = Array.from({ length: 8 }, (_, idx) => ({
    input: idx / 7,
    velocity_px_s: (idx / 7) ** 1.5 * 500,
    valid: true,
  }))

  it('reconstructs session result from Multi-Layer ControllerMeta JSON export', () => {
    const report = fitResponseCurve(dummyPoints, 0.0, 1.0)
    const multiLayerJson = buildMultiLayerControllerMetaJson(
      report!.candidates.bezier,
      dummyPoints,
      0.0,
      1.0,
      'Cubic Bezier'
    )

    const reconstructed = parseExportedCurveFile(multiLayerJson, 'test_export.json')
    expect(reconstructed).toBeDefined()
    expect(reconstructed.points).toHaveLength(8)
    expect(reconstructed.points[0].input).toBe(0)
    expect(reconstructed.points[7].input).toBe(1)
  })

  it('reconstructs session result from CSV with metadata comments', () => {
    const csvStr = buildDseCsv(null, dummyPoints, 0.05, 0.95, false)
    const reconstructed = parseExportedCurveFile(csvStr, 'test_export.csv')

    expect(reconstructed).toBeDefined()
    expect(reconstructed.points).toHaveLength(8)
    expect(reconstructed.config?.inner_deadzone).toBe(0.05)
    expect(reconstructed.config?.outer_deadzone).toBe(0.95)
  })
})
