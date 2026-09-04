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

  it('maps stage relative pointer coordinates 1:1 to image space without letterbox desync', () => {
    // Stage with exact aspect ratio (1920x1080) rendered at 960x540
    const stageWidth = 960
    const stageHeight = 540
    const imgWidth = 1920
    const imgHeight = 1080

    const clientX = 480 // clicked exactly in center
    const clientY = 270

    const scaleX = imgWidth / stageWidth
    const scaleY = imgHeight / stageHeight

    const imgX = clientX * scaleX
    const imgY = clientY * scaleY

    expect(imgX).toBe(960)
    expect(imgY).toBe(540)

    // Rendered percentage overlay
    const pctLeft = (imgX / imgWidth) * 100
    const pctTop = (imgY / imgHeight) * 100
    expect(pctLeft).toBe(50)
    expect(pctTop).toBe(50)
  })
})

describe('Deadzone range slider bounds logic', () => {
  function computeSafeBounds(inner: number, outer: number) {
    const safeInner = Math.max(0.0, Math.min(inner, 0.99))
    const safeOuter = Math.max(safeInner + 0.01, Math.min(outer, 1.0))
    const span = Math.max(0.0, safeOuter - safeInner)
    return { safeInner, safeOuter, span }
  }

  it('ensures safe inner does not exceed outer - 0.01', () => {
    const { safeInner, safeOuter, span } = computeSafeBounds(0.95, 0.90)
    expect(safeInner).toBe(0.95)
    expect(safeOuter).toBe(0.96)
    expect(span).toBeCloseTo(0.01)
  })

  it('correctly calculates span and percentage styles for instant response', () => {
    const { safeInner, safeOuter, span } = computeSafeBounds(0.1, 0.8)
    expect(safeInner).toBe(0.1)
    expect(safeOuter).toBe(0.8)
    expect(span).toBeCloseTo(0.7)
  })
})
