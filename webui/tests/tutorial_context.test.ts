import { describe, expect, it, vi } from 'vitest'
import { createTutorialController, shouldDisposeRealProbe } from '../src/composables/useTutorial'

describe('tutorial context', () => {
  it('uses demo values only while active and restores the launch page', () => {
    const setPage = vi.fn()
    const controller = createTutorialController({ getPage: () => 3, setPage })
    const real = { capture: null, lastResult: null }
    expect(controller.display(real).capture).toBeNull()
    controller.start('settings')
    expect(controller.display(real).capture?.backend).toBe('wgc')
    expect(real).toEqual({ capture: null, lastResult: null })
    controller.stop('interrupted')
    expect(setPage).toHaveBeenLastCalledWith(3)
    expect(controller.display(real).capture).toBeNull()
  })

  it('never invokes real actions in demo mode', async () => {
    const dangerousAction = vi.fn()
    const controller = createTutorialController({ getPage: () => 1, setPage: vi.fn() })
    controller.start('first-run')
    await controller.guardAction(dangerousAction)
    expect(dangerousAction).not.toHaveBeenCalled()
  })

  it('does not dispose a real probe when only the tutorial probe is active', () => {
    expect(shouldDisposeRealProbe(true, true)).toBe(false)
    expect(shouldDisposeRealProbe(false, true)).toBe(true)
    expect(shouldDisposeRealProbe(false, false)).toBe(false)
  })
})
