import { describe, it, expect } from 'vitest'
import type { MeasurementPoint } from '../src/types/api'

describe('Chart Options Builder', () => {
  function buildSeriesData(points: MeasurementPoint[]) {
    const rawVelocitySeries = points.map(p => [p.input, p.velocity_px_s])
    const normalizedSeries = points.map(p => [p.input, p.normalized_speed])
    return { rawVelocitySeries, normalizedSeries }
  }

  it('correctly maps valid and invalid measurement points to coordinate pairs', () => {
    const points: MeasurementPoint[] = [
      { input: 0.0, velocity_px_s: 0.0, normalized_speed: 0.0, stability: 1.0, valid: true, attempts: 1 },
      { input: 0.5, velocity_px_s: null, normalized_speed: null, stability: 0.0, valid: false, attempts: 2 },
      { input: 1.0, velocity_px_s: 100.0, normalized_speed: 1.0, stability: 0.95, valid: true, attempts: 1 },
    ]

    const { rawVelocitySeries, normalizedSeries } = buildSeriesData(points)
    expect(rawVelocitySeries[0]).toEqual([0.0, 0.0])
    expect(rawVelocitySeries[1]).toEqual([0.5, null])
    expect(rawVelocitySeries[2]).toEqual([1.0, 100.0])
    expect(normalizedSeries[2]).toEqual([1.0, 1.0])
  })
})
