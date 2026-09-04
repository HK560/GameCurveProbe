import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTutorialDriver, waitForTourTarget } from '../src/services/tutorialDriver'

describe('tutorial driver adapter', () => {
  afterEach(() => vi.useRealTimers())

  it('keeps one instance and destroys it during restart and cleanup', () => {
    const first = { drive: vi.fn(), destroy: vi.fn() }
    const second = { drive: vi.fn(), destroy: vi.fn() }
    const factory = vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second)
    const adapter = createTutorialDriver(factory)
    adapter.start({ steps: [] })
    adapter.start({ steps: [] })
    expect(first.destroy).toHaveBeenCalledOnce()
    adapter.destroy()
    expect(second.destroy).toHaveBeenCalledOnce()
  })

  it('returns false instead of hanging when an element never renders', async () => {
    vi.useFakeTimers()
    const promise = waitForTourTarget('[data-tour="missing"]', {
      timeoutMs: 100,
      pollMs: 20,
      query: () => null,
    })
    await vi.advanceTimersByTimeAsync(120)
    await expect(promise).resolves.toBe(false)
  })

  it('resolves immediately for a rendered element', async () => {
    await expect(waitForTourTarget('[data-tour="ready"]', {
      timeoutMs: 100,
      pollMs: 20,
      query: () => ({}) as Element,
    })).resolves.toBe(true)
  })
})
