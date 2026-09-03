import { describe, it, expect } from 'vitest'

describe('Roi Clamping Math', () => {
  function clampRoi(
    x: number,
    y: number,
    width: number,
    height: number,
    imgWidth: number,
    imgHeight: number,
    minSide = 32
  ) {
    let clX = Math.max(0, Math.min(x, imgWidth - minSide))
    let clY = Math.max(0, Math.min(y, imgHeight - minSide))
    let clW = Math.max(minSide, Math.min(width, imgWidth - clX))
    let clH = Math.max(minSide, Math.min(height, imgHeight - clY))
    return {
      x: Math.round(clX),
      y: Math.round(clY),
      width: Math.round(clW),
      height: Math.round(clH),
    }
  }

  it('clamps rectangle to image boundaries', () => {
    const res = clampRoi(-10, -20, 2000, 2000, 1920, 1080)
    expect(res.x).toBe(0)
    expect(res.y).toBe(0)
    expect(res.width).toBe(1920)
    expect(res.height).toBe(1080)
  })

  it('enforces minimum side of 32 pixels', () => {
    const res = clampRoi(100, 100, 10, 15, 1920, 1080, 32)
    expect(res.width).toBe(32)
    expect(res.height).toBe(32)
  })
})
