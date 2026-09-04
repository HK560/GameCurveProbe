import { describe, expect, it, vi } from 'vitest'
import {
  TUTORIAL_COMPLETED_KEY,
  createTutorialState,
  hasCompletedTutorial,
  markTutorialCompleted,
} from '../src/services/tutorialState'

describe('tutorial persistence', () => {
  it('auto-starts only while completion marker is absent', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value) },
    }
    expect(hasCompletedTutorial(storage)).toBe(false)
    markTutorialCompleted(storage)
    expect(storage.getItem(TUTORIAL_COMPLETED_KEY)).toBe('1')
    expect(hasCompletedTutorial(storage)).toBe(true)
  })

  it('degrades safely when storage throws', () => {
    const storage = {
      getItem: vi.fn(() => { throw new Error('blocked') }),
      setItem: vi.fn(() => { throw new Error('blocked') }),
    }
    expect(hasCompletedTutorial(storage)).toBe(false)
    expect(() => markTutorialCompleted(storage)).not.toThrow()
  })
})

describe('tutorial lifecycle', () => {
  it('restores the launch page and marks only explicit completion', () => {
    const state = createTutorialState()
    state.start('settings', 3)
    state.goTo(7)
    expect(state.snapshot()).toMatchObject({ active: true, source: 'settings', launchStep: 3, nodeIndex: 7 })
    expect(state.stop('interrupted')).toEqual({ restoreStep: 3, persistCompletion: false })
    state.start('first-run', 2)
    expect(state.stop('completed')).toEqual({ restoreStep: 1, persistCompletion: true })
  })
})
