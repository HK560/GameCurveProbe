import { describe, expect, it } from 'vitest'

import { buildVelocitySeries } from '../src/services/chartSeries'


describe('chart comparison series', () => {
  it('keeps measured and imported curves as separate overlays', () => {
    const point = { input: 0.5, velocity_px_s: 10, normalized_speed: 1, stability: 1, valid: true, attempts: 1 }

    const series = buildVelocitySeries([point], [{ ...point, velocity_px_s: 20 }])

    expect(series.map((item) => item.name)).toEqual(['实测速度 (px/s)', '导入速度 (px/s)'])
    expect(series[1].data).toEqual([[0.5, 20]])
  })
})
