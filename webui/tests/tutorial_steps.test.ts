import { describe, expect, it } from 'vitest'
import { createTutorialSteps } from '../src/services/tutorialSteps'

describe('tutorial catalog', () => {
  it('covers seven chapters and every application page', () => {
    const steps = createTutorialSteps('zh')
    expect(new Set(steps.map(step => step.chapter))).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]))
    expect(new Set(steps.map(step => step.page).filter(Boolean))).toEqual(new Set([1, 2, 3, 4]))
    expect(steps.length).toBeGreaterThanOrEqual(28)
  })

  it.each(['zh', 'en'] as const)('has complete %s copy and stable targets', locale => {
    const steps = createTutorialSteps(locale)
    for (const step of steps) {
      expect(step.title.trim()).not.toBe('')
      expect(step.description.trim()).not.toBe('')
      if (step.element) expect(step.element).toMatch(/^\[data-tour="[a-z0-9-]+"\]$/)
    }
  })

  it('covers poor/good ROI, measurement animation, report, and completion actions', () => {
    const actions = createTutorialSteps('en').map(step => step.action).filter(Boolean)
    expect(actions).toEqual(expect.arrayContaining([
      'show-poor-roi', 'show-good-roi', 'show-noise', 'show-probe',
      'animate-measurement', 'show-report', 'show-summary',
    ]))
  })
})
