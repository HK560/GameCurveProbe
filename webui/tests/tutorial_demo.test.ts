import { describe, expect, it } from 'vitest'
import { createTutorialDemo, tutorialMeasurementFrames } from '../src/services/tutorialDemo'

describe('tutorial demo data', () => {
  it('contains a complete capture-to-report path', () => {
    const demo = createTutorialDemo()
    expect(demo.windows[0].title).toBeTruthy()
    expect(demo.capture).toMatchObject({ width: 1920, height: 1080, backend: 'wgc', target_fps: 120 })
    expect(demo.roiQualityExcellent.score).toBeGreaterThanOrEqual(60)
    expect(demo.roiQualityPoor.score).toBeLessThan(25)
    expect(demo.noise.confidence).toBeGreaterThan(0)
    expect(demo.result.points.length).toBeGreaterThanOrEqual(9)
  })

  it('returns fresh structures and ordered measurement frames', () => {
    const first = createTutorialDemo()
    const second = createTutorialDemo()
    first.result.points[0].stability = 0
    expect(second.result.points[0].stability).not.toBe(0)
    expect(tutorialMeasurementFrames.map(frame => frame.phase)).toContain('point_retry')
  })
})
