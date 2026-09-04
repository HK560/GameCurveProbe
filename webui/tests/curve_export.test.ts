import { describe, it, expect } from 'vitest'
import {
  buildControllerMetaJson,
  buildDseCsv,
  buildControllerMetaCurveModel,
  buildNormalizedPolylinePoints,
} from '../src/services/curveExport'
import { fitResponseCurve } from '../src/services/curveFitting'

describe('Curve Export to ControllerMeta Format', () => {
  const dummyPoints = Array.from({ length: 20 }, (_, idx) => ({
    input: idx / 19,
    velocity_px_s: (idx / 19) ** 1.5 * 500,
    valid: true,
  }))

  it('builds valid ControllerMeta JSON transfer bundle for fitted bezier curve', () => {
    const report = fitResponseCurve(dummyPoints, 0.05, 0.95)
    expect(report).not.toBeNull()

    const bezierCandidate = report!.candidates.bezier

    // 1. Normalized mode (default, deadzones set to 0)
    const jsonNorm = buildControllerMetaJson(bezierCandidate, dummyPoints, 0.05, 0.95, 'Test Bezier Norm', true)
    const parsedNorm = JSON.parse(jsonNorm)
    expect(parsedNorm.items[0].curve.innerDeadzone).toBe(0)
    expect(parsedNorm.items[0].curve.outerDeadzone).toBe(0)

    // 2. Raw deadzone mode (deadzones preserved)
    const jsonRaw = buildControllerMetaJson(bezierCandidate, dummyPoints, 0.05, 0.95, 'Test Bezier Raw', false)
    const parsedRaw = JSON.parse(jsonRaw)
    expect(parsedRaw.items[0].curve.innerDeadzone).toBe(5)
    expect(parsedRaw.items[0].curve.outerDeadzone).toBe(5)
    expect(parsedRaw.items[0].curve.bezier.p1.x).toBeGreaterThanOrEqual(0)
    expect(parsedRaw.items[0].curve.bezier.p2.x).toBeLessThanOrEqual(100)
  })

  it('builds valid ControllerMeta JSON for polyline models with exact measured points count', () => {
    const report = fitResponseCurve(dummyPoints, 0.0, 1.0)
    expect(report).not.toBeNull()

    const linearCandidate = report!.candidates.linear
    const jsonStr = buildControllerMetaJson(linearCandidate, dummyPoints, 0.0, 1.0, 'Test Linear', false)
    const parsed = JSON.parse(jsonStr)

    const curve = parsed.items[0].curve
    expect(curve.kind).toBe('polyline')
    expect(curve.innerDeadzone).toBe(0)
    expect(curve.outerDeadzone).toBe(0)
    expect(curve.points).toHaveLength(20) // Exactly 20 measured points!
    expect(curve.basePoints).toHaveLength(20)
    expect(curve.points[0]).toEqual({ x: 0, y: 0 })
    expect(curve.points[19].x).toBe(100)
  })

  it('builds standard DSE CSV with measured points count and 1-based indexing', () => {
    const report = fitResponseCurve(dummyPoints, 0.0, 1.0)
    const candidate = report!.candidates.linear
    const csvStr = buildDseCsv(candidate, dummyPoints, 0.0, 1.0, false)

    const lines = csvStr.trim().split('\n')
    expect(lines[0]).toBe('point_index(1-based),forward_x,forward_y,inv_x,inv_y,note')
    expect(lines).toHaveLength(21) // 1 header + 20 measured points

    const firstRow = lines[1].split(',')
    expect(firstRow[0]).toBe('1')
    expect(firstRow[1]).toBe('0')
    expect(firstRow[2]).toBe('0')
    expect(firstRow[3]).toBe('0')
    expect(firstRow[4]).toBe('0')
    expect(firstRow[5]).toContain('inv_x=(forward_y/Ymax)*Xmax')

    const lastRow = lines[20].split(',')
    expect(lastRow[0]).toBe('20')
    expect(lastRow[1]).toBe('100')
    expect(lastRow[2]).toBe('100')
    expect(lastRow[3]).toBe('100')
    expect(lastRow[4]).toBe('100')
  })

  it('exports exact raw measured points with inner deadzone (x=innerDz, y=0) and outer deadzone (x=outerDz, y=100)', () => {
    const deadzonePoints = [
      { input: 0.08, velocity_px_s: 10, normalized_speed: 0.0, valid: true },
      { input: 0.50, velocity_px_s: 250, normalized_speed: 0.50, valid: true },
      { input: 0.95, velocity_px_s: 500, normalized_speed: 1.0, valid: true },
    ]

    const jsonStr = buildControllerMetaJson(null, deadzonePoints, 0.08, 0.95, 'Deadzone Test', false)
    const parsed = JSON.parse(jsonStr)
    const points = parsed.items[0].curve.points

    expect(points).toHaveLength(3) // Exact 3 measured points!
    expect(points[0]).toEqual({ x: 8, y: 0 }) // First point: (innerDz, 0)
    expect(points[1]).toEqual({ x: 50, y: 50 }) // Interior measured point
    expect(points[2]).toEqual({ x: 95, y: 100 }) // Last point: (outerDz, 100)
  })

  it('handles null candidate and fallback gracefully', () => {
    const jsonStr = buildControllerMetaJson(null, null, 0.0, 1.0)
    const parsed = JSON.parse(jsonStr)
    expect(parsed.items[0].curve.kind).toBe('polyline')
    expect(parsed.items[0].curve.points).toHaveLength(2)
    expect(parsed.items[0].curve.points[0]).toEqual({ x: 0, y: 0 })
    expect(parsed.items[0].curve.points[1]).toEqual({ x: 100, y: 100 })

    const csvStr = buildDseCsv(null, null, 0.0, 1.0)
    expect(csvStr.startsWith('point_index(1-based),forward_x,forward_y,inv_x,inv_y,note')).toBe(true)
    const lines = csvStr.trim().split('\n')
    const lastRow = lines[2].split(',')
    expect(lastRow[0]).toBe('2')
    expect(lastRow[1]).toBe('100')
    expect(lastRow[2]).toBe('100')
  })
})
