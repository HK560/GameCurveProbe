import { describe, expect, it } from 'vitest'

function computeSamplingPoints(
  inner: number,
  outer: number,
  count: number,
  mode: 'active_range' | 'full'
): number[] {
  const start = mode === 'full' ? 0.0 : inner
  const end = mode === 'full' ? 1.0 : outer
  const span = end - start

  const set = new Set<number>()
  for (let i = 0; i < count; i++) {
    const val = Number((start + (span * i) / (count - 1)).toFixed(4))
    set.add(val)
  }

  if (mode === 'full') {
    set.add(Number(inner.toFixed(4)))
    set.add(Number(outer.toFixed(4)))
  }

  return Array.from(set).sort((a, b) => a - b)
}

describe('sampling points calculation', () => {
  it('computes active_range points within inner and outer bounds', () => {
    const points = computeSamplingPoints(0.05, 0.95, 9, 'active_range')
    expect(points.length).toBe(9)
    expect(points[0]).toBe(0.05)
    expect(points[points.length - 1]).toBe(0.95)
    expect(points).toEqual([0.05, 0.1625, 0.275, 0.3875, 0.5, 0.6125, 0.725, 0.8375, 0.95])
  })

  it('computes full range points and includes inner and outer deadzone thresholds', () => {
    const points = computeSamplingPoints(0.05, 0.95, 5, 'full')
    expect(points).toContain(0.0)
    expect(points).toContain(1.0)
    expect(points).toContain(0.05)
    expect(points).toContain(0.95)
  })
})
